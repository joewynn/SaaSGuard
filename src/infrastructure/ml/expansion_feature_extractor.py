"""ExpansionFeatureExtractor – infrastructure adapter for ExpansionFeatureVector protocol.

Primary path: queries marts.mart_customer_expansion_features (built by dbt).
Fallback path: computes the same 20 features inline from raw.* tables.

Mirrors ChurnFeatureExtractor exactly — dual-path pattern for resilience.
"""

from __future__ import annotations

import structlog

from src.domain.customer.entities import Customer
from src.infrastructure.db.duckdb_adapter import get_connection

logger = structlog.get_logger(__name__)

# SQL to compute all 20 expansion features directly from raw tables.
# Mirrors mart_customer_expansion_features.sql logic.
# Five ? params — all are customer_id.
_EXPANSION_FEATURES_FROM_RAW_SQL = """
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
        )                                                                       AS retention_signal_count,
        COUNT(*) FILTER (
            WHERE event_type = 'premium_feature_trial'
              AND CAST(timestamp AS DATE) >= CURRENT_DATE - INTERVAL '30 days'
        )                                                                       AS premium_feature_trials_30d,
        COUNT(*) FILTER (
            WHERE event_type = 'feature_limit_hit'
              AND CAST(timestamp AS DATE) >= CURRENT_DATE - INTERVAL '30 days'
        )                                                                       AS feature_limit_hit_30d
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
        AVG(CAST(resolution_time AS FLOAT))                                     AS avg_resolution_hours,
        COUNT(*) FILTER (
            WHERE topic = 'feature_request'
              AND CAST(created_date AS DATE) >= CURRENT_DATE - INTERVAL '90 days'
        )                                                                       AS feature_request_tickets_90d
    FROM raw.support_tickets
    WHERE customer_id = ?
),
expansion_opp_agg AS (
    SELECT
        MAX(CASE
            WHEN opportunity_type = 'expansion'
             AND stage NOT IN ('closed_won', 'closed_lost')
            THEN 1 ELSE 0
        END)::BOOLEAN                                                           AS has_open_expansion_opp,
        COALESCE(SUM(
            CASE
                WHEN opportunity_type = 'expansion'
                 AND stage NOT IN ('closed_won', 'closed_lost')
                THEN CAST(amount AS FLOAT) ELSE 0
            END
        ), 0.0)                                                                 AS expansion_opp_amount
    FROM raw.gtm_opportunities
    WHERE customer_id = ?
)
SELECT
    c.mrr,
    c.tenure_days,
    COALESCE(e.total_events, 0)                             AS total_events,
    COALESCE(e.events_last_30d, 0)                         AS events_last_30d,
    COALESCE(e.events_last_7d, 0)                          AS events_last_7d,
    COALESCE(e.avg_adoption_score, 0.0)                    AS avg_adoption_score,
    -- Smart imputation: no events → inactive for account's full lifetime, not 999
    CASE WHEN e.total_events IS NULL THEN c.tenure_days
         ELSE e.days_since_last_event
    END                                                     AS days_since_last_event,
    COALESCE(e.retention_signal_count, 0)                  AS retention_signal_count,
    COALESCE(i.integration_connects_first_30d, 0)          AS integration_connects_first_30d,
    -- Activation gate: ≥3 integrations in onboarding window → 2.7× lower churn
    CASE WHEN COALESCE(i.integration_connects_first_30d, 0) >= 3 THEN 1 ELSE 0 END
                                                            AS activated_at_30d,
    COALESCE(t.tickets_last_30d, 0)                        AS tickets_last_30d,
    COALESCE(t.high_priority_tickets, 0)                   AS high_priority_tickets,
    COALESCE(t.avg_resolution_hours, 0.0)                  AS avg_resolution_hours,
    c.plan_tier,
    c.industry,
    CAST(c.tenure_days <= 90 AS INT)                       AS is_early_stage,
    -- Expansion-specific features
    COALESCE(e.premium_feature_trials_30d, 0)              AS premium_feature_trials_30d,
    COALESCE(t.feature_request_tickets_90d, 0)             AS feature_request_tickets_90d,
    COALESCE(eo.has_open_expansion_opp, FALSE)             AS has_open_expansion_opp,
    COALESCE(eo.expansion_opp_amount, 0.0)                 AS expansion_opp_amount,
    -- mrr_tier_ceiling_pct: how close MRR is to the top of the current tier (FREE = 0.0)
    CASE c.plan_tier
        WHEN 'free'       THEN 0.0
        WHEN 'starter'    THEN LEAST(1.0, GREATEST(0.0, (c.mrr - 500.0)   / (2000.0  - 500.0)))
        WHEN 'growth'     THEN LEAST(1.0, GREATEST(0.0, (c.mrr - 2000.0)  / (8000.0  - 2000.0)))
        WHEN 'enterprise' THEN LEAST(1.0, GREATEST(0.0, (c.mrr - 8000.0)  / (50000.0 - 8000.0)))
        ELSE 0.0
    END                                                                        AS mrr_tier_ceiling_pct,
    COALESCE(e.feature_limit_hit_30d, 0)                       AS feature_limit_hit_30d
FROM customer_base c
LEFT JOIN event_agg         e ON TRUE
LEFT JOIN integration_agg   i ON TRUE
LEFT JOIN ticket_agg        t ON TRUE
LEFT JOIN expansion_opp_agg eo ON TRUE
"""


class ExpansionFeatureExtractor:
    """Thin adapter that maps customer history → 21-feature expansion dict.

    Business Context: Mirrors ChurnFeatureExtractor exactly. Primary path
    reads from mart_customer_expansion_features (~1ms). Fallback path
    computes all 21 features inline from raw.* tables (~5ms).

    The 21 features are: 15 base churn features + 6 expansion signals:
        premium_feature_trials_30d, feature_request_tickets_90d,
        has_open_expansion_opp, expansion_opp_amount, mrr_tier_ceiling_pct,
        feature_limit_hit_30d (Feature 21 — primary free-tier signal).
    """

    def extract(self, customer: Customer) -> dict[str, float | str]:
        """Fetch the 21-feature expansion vector for a customer.

        Args:
            customer: Active Customer entity.

        Returns:
            Dict of 21 feature_name → value (numerics as float, categoricals
            as lowercase string).

        Raises:
            ValueError: If the customer is not found in raw.customers.
        """
        try:
            return self._extract_from_mart(customer)
        except Exception as mart_exc:
            logger.warning(
                "expansion_feature_extractor.mart_unavailable",
                customer_id=customer.customer_id,
                reason=str(mart_exc)[:120],
                fallback="raw_tables",
            )
            return self._extract_from_raw(customer)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_from_mart(self, customer: Customer) -> dict[str, float | str]:
        """Query the pre-built dbt expansion mart (fast path)."""
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
                    activated_at_30d,
                    tickets_last_30d,
                    high_priority_tickets,
                    avg_resolution_hours,
                    plan_tier,
                    industry,
                    is_early_stage,
                    premium_feature_trials_30d,
                    feature_request_tickets_90d,
                    has_open_expansion_opp,
                    expansion_opp_amount,
                    mrr_tier_ceiling_pct,
                    feature_limit_hit_30d
                FROM marts.mart_customer_expansion_features
                WHERE customer_id = ?
                """,
                [customer.customer_id],
            ).fetchone()

        if row is None:
            raise ValueError(
                f"Customer {customer.customer_id} not found in mart_customer_expansion_features. "
                "Run `dbt run --select mart_customer_expansion_features` to refresh."
            )

        features = self._row_to_features(row)
        logger.debug(
            "expansion_feature_extractor.mart_hit",
            customer_id=customer.customer_id,
            premium_feature_trials_30d=features["premium_feature_trials_30d"],
        )
        return features

    def _extract_from_raw(self, customer: Customer) -> dict[str, float | str]:
        """Compute features inline from raw.* tables (fallback path)."""
        cid = customer.customer_id
        with get_connection() as conn:
            row = conn.execute(
                _EXPANSION_FEATURES_FROM_RAW_SQL,
                [cid, cid, cid, cid, cid],
            ).fetchone()

        if row is None:
            raise ValueError(f"Customer {customer.customer_id} not found in raw.customers.")

        features = self._row_to_features(row)
        logger.debug(
            "expansion_feature_extractor.raw_hit",
            customer_id=customer.customer_id,
        )
        return features

    @staticmethod
    def _row_to_features(row: tuple) -> dict[str, float | str]:  # type: ignore[type-arg]
        """Parse a DB result tuple into the 21-feature dict expected by the model."""
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
            activated_at_30d,
            tickets_last_30d,
            high_priority_tickets,
            avg_resolution_hours,
            plan_tier,
            industry,
            is_early_stage,
            premium_feature_trials_30d,
            feature_request_tickets_90d,
            has_open_expansion_opp,
            expansion_opp_amount,
            mrr_tier_ceiling_pct,
            feature_limit_hit_30d,
        ) = row

        return {
            # Base churn features (15 + activated_at_30d = 16)
            "mrr": float(mrr),
            "tenure_days": float(tenure_days),
            "total_events": float(total_events),
            "events_last_30d": float(events_last_30d),
            "events_last_7d": float(events_last_7d),
            "avg_adoption_score": float(avg_adoption_score),
            "days_since_last_event": float(days_since_last_event),
            "retention_signal_count": float(retention_signal_count),
            "integration_connects_first_30d": float(integration_connects_first_30d),
            "activated_at_30d": float(int(activated_at_30d)),
            "tickets_last_30d": float(tickets_last_30d),
            "high_priority_tickets": float(high_priority_tickets),
            "avg_resolution_hours": float(avg_resolution_hours),
            "plan_tier": str(plan_tier).lower(),
            "industry": str(industry).lower(),
            "is_early_stage": float(int(is_early_stage)),
            # Expansion-specific features (6)
            "premium_feature_trials_30d": float(premium_feature_trials_30d),
            "feature_request_tickets_90d": float(feature_request_tickets_90d),
            "has_open_expansion_opp": float(int(bool(has_open_expansion_opp))),
            "expansion_opp_amount": float(expansion_opp_amount),
            "mrr_tier_ceiling_pct": float(mrr_tier_ceiling_pct),
            "feature_limit_hit_30d": float(feature_limit_hit_30d),
        }
