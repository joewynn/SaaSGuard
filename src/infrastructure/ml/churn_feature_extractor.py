"""ChurnFeatureExtractor – infrastructure adapter for the ChurnFeatureVector protocol.

Primary path: queries marts.mart_customer_churn_features (built by dbt).
Fallback path: computes the same 15 features inline from raw.* tables.

The fallback allows the API to serve predictions even when dbt has not been
run — useful for local development and Railway cold-deploys.
"""

from __future__ import annotations

import structlog

from src.domain.customer.entities import Customer
from src.infrastructure.db.duckdb_adapter import get_connection

logger = structlog.get_logger(__name__)

# SQL to compute all 15 features directly from raw tables.
# Mirrors the logic in dbt_project/models/marts/mart_customer_churn_features.sql
# and dbt_project/models/staging/stg_*.sql.
# Four ? params — all are customer_id (customer_base, event_agg, integration_agg, ticket_agg).
_FEATURES_FROM_RAW_SQL = """
WITH customer_base AS (
    SELECT
        CAST(signup_date AS DATE)                                               AS signup_date,
        CAST(mrr AS FLOAT)                                                      AS mrr,
        DATEDIFF('day', CAST(signup_date AS DATE), CURRENT_DATE)                AS tenure_days,
        plan_tier,
        industry
    FROM raw.customers
    WHERE customer_id = ?
),
event_agg AS (
    SELECT
        COUNT(*)                                                                AS total_events,
        COUNT(*) FILTER (
            WHERE CAST(timestamp AS DATE) >= CURRENT_DATE - INTERVAL '30 days'
        )                                                                       AS events_last_30d,
        COUNT(*) FILTER (
            WHERE CAST(timestamp AS DATE) >= CURRENT_DATE - INTERVAL '7 days'
        )                                                                       AS events_last_7d,
        AVG(CAST(feature_adoption_score AS FLOAT))                              AS avg_adoption_score,
        DATEDIFF('day', MAX(CAST(timestamp AS DATE)), CURRENT_DATE)             AS days_since_last_event,
        COUNT(*) FILTER (
            WHERE event_type IN ('integration_connect', 'api_call', 'monitoring_run')
        )                                                                       AS retention_signal_count
    FROM raw.usage_events
    WHERE customer_id = ?
),
integration_agg AS (
    SELECT
        COUNT(*) FILTER (
            WHERE e.event_type = 'integration_connect'
              AND CAST(e.timestamp AS DATE)
                  <= (SELECT signup_date FROM customer_base) + INTERVAL '30 days'
        )                                                                       AS integration_connects_first_30d
    FROM raw.usage_events e
    WHERE e.customer_id = ?
),
ticket_agg AS (
    SELECT
        COUNT(*) FILTER (
            WHERE CAST(created_date AS DATE) >= CURRENT_DATE - INTERVAL '30 days'
        )                                                                       AS tickets_last_30d,
        COUNT(*) FILTER (
            WHERE priority IN ('high', 'critical')
        )                                                                       AS high_priority_tickets,
        AVG(CAST(resolution_time AS FLOAT))                                     AS avg_resolution_hours
    FROM raw.support_tickets
    WHERE customer_id = ?
)
SELECT
    c.mrr,
    c.tenure_days,
    COALESCE(e.total_events, 0)                         AS total_events,
    COALESCE(e.events_last_30d, 0)                      AS events_last_30d,
    COALESCE(e.events_last_7d, 0)                       AS events_last_7d,
    COALESCE(e.avg_adoption_score, 0.0)                 AS avg_adoption_score,
    COALESCE(e.days_since_last_event, 999)              AS days_since_last_event,
    COALESCE(e.retention_signal_count, 0)               AS retention_signal_count,
    COALESCE(i.integration_connects_first_30d, 0)       AS integration_connects_first_30d,
    COALESCE(t.tickets_last_30d, 0)                     AS tickets_last_30d,
    COALESCE(t.high_priority_tickets, 0)                AS high_priority_tickets,
    COALESCE(t.avg_resolution_hours, 0.0)               AS avg_resolution_hours,
    c.plan_tier,
    c.industry,
    CAST(c.tenure_days <= 90 AS INT)                    AS is_early_stage
FROM customer_base c
LEFT JOIN event_agg      e ON TRUE
LEFT JOIN integration_agg i ON TRUE
LEFT JOIN ticket_agg      t ON TRUE
"""


class ChurnFeatureExtractor:
    """Thin adapter that maps customer history → model feature dict.

    Business Context: All feature engineering logic mirrors the dbt mart
    (mart_customer_churn_features). The inline SQL fallback ensures the
    API continues to serve predictions even when dbt has not been run,
    at the cost of slightly higher per-request query time (~5 ms vs ~1 ms).

    Primary path: SELECT from marts.mart_customer_churn_features (fast,
    pre-aggregated by dbt).
    Fallback path: inline SQL against raw.* tables (matches dbt logic exactly).
    """

    def extract(self, customer: Customer) -> dict[str, float | str]:
        """Fetch the feature vector for a customer.

        Tries the dbt mart first. Falls back to inline raw-table computation
        if the mart has not been built yet.

        Args:
            customer: Active Customer entity.

        Returns:
            Dict of 15 feature_name → value (numerics as float, categoricals
            as lowercase string to match sklearn OrdinalEncoder fit categories).

        Raises:
            ValueError: If the customer is not present in raw.customers.
        """
        try:
            return self._extract_from_mart(customer)
        except Exception as mart_exc:
            logger.warning(
                "feature_extractor.mart_unavailable",
                customer_id=customer.customer_id,
                reason=str(mart_exc)[:120],
                fallback="raw_tables",
            )
            return self._extract_from_raw(customer)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_from_mart(self, customer: Customer) -> dict[str, float | str]:
        """Query the pre-built dbt mart (fast path)."""
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    mrr,
                    tenure_days,
                    total_events,
                    events_last_30d,
                    events_last_7d,
                    avg_adoption_score,
                    days_since_last_event,
                    retention_signal_count,
                    integration_connects_first_30d,
                    tickets_last_30d,
                    high_priority_tickets,
                    avg_resolution_hours,
                    plan_tier,
                    industry,
                    is_early_stage
                FROM marts.mart_customer_churn_features
                WHERE customer_id = ?
                """,
                [customer.customer_id],
            ).fetchone()

        if row is None:
            raise ValueError(
                f"Customer {customer.customer_id} not found in mart_customer_churn_features. "
                "Run `dbt run --select mart_customer_churn_features` to refresh."
            )

        features = self._row_to_features(row)
        logger.debug(
            "feature_extractor.mart_hit",
            customer_id=customer.customer_id,
            events_last_30d=features["events_last_30d"],
        )
        return features

    def _extract_from_raw(self, customer: Customer) -> dict[str, float | str]:
        """Compute features inline from raw.* tables (fallback path)."""
        cid = customer.customer_id
        with get_connection() as conn:
            row = conn.execute(
                _FEATURES_FROM_RAW_SQL,
                [cid, cid, cid, cid],
            ).fetchone()

        if row is None:
            raise ValueError(
                f"Customer {customer.customer_id} not found in raw.customers."
            )

        features = self._row_to_features(row)
        logger.debug(
            "feature_extractor.raw_hit",
            customer_id=customer.customer_id,
            events_last_30d=features["events_last_30d"],
        )
        return features

    @staticmethod
    def _row_to_features(row: tuple) -> dict[str, float | str]:  # type: ignore[type-arg]
        """Parse a DB result tuple into the feature dict expected by the model.

        Categorical features (plan_tier, industry) are returned as lowercase
        strings so that the sklearn OrdinalEncoder in the model pipeline can
        encode them correctly — matching how they were presented at training time.
        Pre-encoding them as floats here would cause the OrdinalEncoder to treat
        them as unknown values (−1), breaking plan_tier contributions.
        """
        (
            mrr,
            tenure_days,
            total_events,
            events_last_30d,
            events_last_7d,
            avg_adoption_score,
            days_since_last_event,
            retention_signal_count,
            integration_connects_first_30d,
            tickets_last_30d,
            high_priority_tickets,
            avg_resolution_hours,
            plan_tier,
            industry,
            is_early_stage,
        ) = row

        return {
            "mrr": float(mrr),
            "tenure_days": float(tenure_days),
            "total_events": float(total_events),
            "events_last_30d": float(events_last_30d),
            "events_last_7d": float(events_last_7d),
            "avg_adoption_score": float(avg_adoption_score),
            "days_since_last_event": float(days_since_last_event),
            "retention_signal_count": float(retention_signal_count),
            "integration_connects_first_30d": float(integration_connects_first_30d),
            "tickets_last_30d": float(tickets_last_30d),
            "high_priority_tickets": float(high_priority_tickets),
            "avg_resolution_hours": float(avg_resolution_hours),
            # Lowercase strings — OrdinalEncoder categories are lowercase
            "plan_tier": str(plan_tier).lower(),
            "industry": str(industry).lower(),
            "is_early_stage": float(int(is_early_stage)),
        }
