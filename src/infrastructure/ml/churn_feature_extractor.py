"""ChurnFeatureExtractor – infrastructure adapter for the ChurnFeatureVector protocol.

Queries marts.mart_customer_churn_features (built by dbt) to produce
the flat feature dict expected by ChurnModelPort.predict_proba().
"""

from __future__ import annotations

import structlog

from src.domain.customer.entities import Customer
from src.infrastructure.db.duckdb_adapter import get_connection

logger = structlog.get_logger(__name__)

# Ordinal encoding maps — must stay in sync with OrdinalEncoder fit in train_churn_model.py
_PLAN_TIER_ORDINAL: dict[str, float] = {"starter": 0.0, "growth": 1.0, "enterprise": 2.0}
_INDUSTRY_ORDINAL: dict[str, float] = {
    "fintech": 0.0,
    "healthtech": 1.0,
    "legaltech": 2.0,
    "proptech": 3.0,
    "saas": 4.0,
}


class ChurnFeatureExtractor:
    """Thin adapter that maps mart_customer_churn_features → model feature dict.

    Business Context: All feature engineering (event aggregations, ticket
    summaries, integration gates) is owned by dbt. This class is a pure
    infrastructure adapter — no business logic lives here. This ensures that
    the feature logic in production inference and dbt batch scoring are
    always identical (single source of truth).

    The mart is materialized as a table in the 'marts' schema by dbt.
    Run `dbt run --select mart_customer_churn_features` before using this class.
    """

    def extract(self, customer: Customer) -> dict[str, float]:
        """Fetch the feature vector for a customer from the dbt mart.

        Args:
            customer: Active Customer entity. The customer_id is used as the
                      lookup key against mart_customer_churn_features.

        Returns:
            Flat dict of 15 feature_name → numeric value, ready to pass
            directly to ChurnModelPort.predict_proba().

        Raises:
            ValueError: If the customer is not present in the mart (e.g. the
                        mart has not been refreshed, or the customer has churned
                        and is filtered out by the mart's WHERE clause).
        """
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
                "Run `dbt run --select mart_customer_churn_features` to refresh the mart, "
                "or verify the customer is active (churned customers are excluded)."
            )

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

        features = {
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
            # Categorical features encoded as ordinals (matches OrdinalEncoder fit)
            "plan_tier": _PLAN_TIER_ORDINAL.get(str(plan_tier).lower(), 0.0),
            "industry": _INDUSTRY_ORDINAL.get(str(industry).lower(), 0.0),
            "is_early_stage": float(int(is_early_stage)),
        }

        logger.debug(
            "feature_extractor.extracted",
            customer_id=customer.customer_id,
            events_last_30d=features["events_last_30d"],
            avg_adoption_score=features["avg_adoption_score"],
        )
        return features
