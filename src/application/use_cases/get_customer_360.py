"""GetCustomer360UseCase – assembles a full Customer 360 profile.

Orchestrates the customer domain, prediction domain, and raw DuckDB queries
to produce a single rich response for the Customer 360 API endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.application.use_cases.predict_churn import (
    PredictChurnRequest,
    PredictChurnUseCase,
)
from src.domain.customer.repository import CustomerRepository
from src.infrastructure.db.duckdb_adapter import get_connection


@dataclass
class ShapFeatureSummary:
    """Application-layer DTO for a single SHAP feature contribution.

    Args:
        feature: Feature name as returned by the model.
        value: Raw feature value.
        shap_impact: Signed SHAP contribution (positive = increases churn risk).
    """

    feature: str
    value: float
    shap_impact: float


@dataclass
class Customer360Profile:
    """Application-layer DTO returned by GetCustomer360UseCase.

    This DTO is mapped to Customer360Response by the delivery layer (FastAPI router).
    Keeping it here ensures the application layer has no dependency on app/schemas/.

    Args:
        customer_id: Unique customer identifier.
        plan_tier: Commercial tier (starter / growth / enterprise).
        industry: Vertical segment.
        mrr: Monthly Recurring Revenue in USD.
        tenure_days: Days since signup.
        churn_probability: Calibrated P(churn in 90 days), 0–1.
        risk_tier: LOW | MEDIUM | HIGH | CRITICAL.
        top_shap_features: Top SHAP drivers (sorted by |impact|).
        events_last_30d: Product events in the last 30 days.
        open_ticket_count: Currently open support tickets.
        gtm_stage: Most recent GTM opportunity stage, if any.
        latest_prediction_at: ISO-8601 UTC timestamp of the prediction.
    """

    customer_id: str
    plan_tier: str
    industry: str
    mrr: float
    tenure_days: int
    churn_probability: float
    risk_tier: str
    top_shap_features: list[ShapFeatureSummary] = field(default_factory=list)
    events_last_30d: int = 0
    open_ticket_count: int = 0
    gtm_stage: str | None = None
    latest_prediction_at: str = ""


@dataclass
class GetCustomer360Request:
    """Input DTO for GetCustomer360UseCase.

    Args:
        customer_id: UUID of the customer to profile.
    """

    customer_id: str


class GetCustomer360UseCase:
    """Assembles a Customer 360 profile from multiple domain sources.

    Business Context: CS teams spend 10–15 min per customer pulling data from
    3+ tools before each call. This use case collapses that into a single <50ms
    API response — enabling same-day at-risk customer triage.

    Args:
        customer_repo: Reads customer master data.
        predict_use_case: Reuses the existing churn prediction pipeline.
    """

    def __init__(
        self,
        customer_repo: CustomerRepository,
        predict_use_case: PredictChurnUseCase,
    ) -> None:
        self._customer_repo = customer_repo
        self._predict_use_case = predict_use_case

    def execute(self, request: GetCustomer360Request) -> Customer360Profile:
        """Build and return the Customer 360 profile.

        Business Context: Single entrypoint for all customer health data —
        churn score, feature drivers, usage velocity, support load, and
        GTM pipeline stage.

        Args:
            request: Contains customer_id.

        Returns:
            Customer360Profile DTO with all fields populated.

        Raises:
            ValueError: If the customer is not found.
        """
        customer = self._customer_repo.get_by_id(request.customer_id)
        if customer is None:
            raise ValueError(f"Customer {request.customer_id} not found.")

        prediction = self._predict_use_case.execute(PredictChurnRequest(customer_id=request.customer_id))

        events_last_30d, open_ticket_count, gtm_stage = self._query_supplemental(request.customer_id)

        shap_features = [
            ShapFeatureSummary(
                feature=f.feature_name,
                value=f.feature_value,
                shap_impact=f.shap_impact,
            )
            for f in prediction.top_shap_features
        ]

        return Customer360Profile(
            customer_id=customer.customer_id,
            plan_tier=customer.plan_tier.value,
            industry=customer.industry.value,
            mrr=float(customer.mrr.amount),
            tenure_days=customer.tenure_days,
            churn_probability=prediction.churn_probability.value,
            risk_tier=prediction.risk_score.tier,
            top_shap_features=shap_features,
            events_last_30d=events_last_30d,
            open_ticket_count=open_ticket_count,
            gtm_stage=gtm_stage,
            latest_prediction_at=prediction.predicted_at.isoformat(),
        )

    def _query_supplemental(self, customer_id: str) -> tuple[int, int, str | None]:
        """Fetch events_last_30d, open_ticket_count, and GTM stage from DuckDB.

        Business Context: These signals are leading indicators of churn risk —
        low event velocity + high ticket volume = imminent churn pattern.

        Args:
            customer_id: The customer to query supplemental data for.

        Returns:
            Tuple of (events_last_30d, open_ticket_count, gtm_stage).
        """
        try:
            with get_connection() as conn:
                event_row = conn.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM raw.usage_events
                    WHERE customer_id = ?
                      AND timestamp >= CURRENT_DATE - INTERVAL 30 DAY
                    """,
                    [customer_id],
                ).fetchone()

                ticket_row = conn.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM raw.support_tickets
                    WHERE customer_id = ?
                      AND resolution_time IS NULL
                    """,
                    [customer_id],
                ).fetchone()

                gtm_row = conn.execute(
                    """
                    SELECT stage
                    FROM raw.gtm_opportunities
                    WHERE customer_id = ?
                    ORDER BY close_date DESC
                    LIMIT 1
                    """,
                    [customer_id],
                ).fetchone()

            events_last_30d = int(event_row[0]) if event_row else 0
            open_ticket_count = int(ticket_row[0]) if ticket_row else 0
            gtm_stage = str(gtm_row[0]) if gtm_row else None
        except Exception:
            # Graceful degradation — return zeros if DuckDB unavailable
            events_last_30d = 0
            open_ticket_count = 0
            gtm_stage = None

        return events_last_30d, open_ticket_count, gtm_stage
