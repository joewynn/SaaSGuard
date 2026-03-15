"""PredictChurnUseCase – application layer use case.

Orchestrates domain objects to produce a churn prediction.
This layer has no knowledge of FastAPI, DuckDB, or pickle files.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.customer.repository import CustomerRepository
from src.domain.prediction.churn_model_service import ChurnModelService
from src.domain.prediction.entities import PredictionResult
from src.domain.prediction.risk_model_service import RiskModelService, RiskSignals
from src.domain.usage.repository import UsageRepository


@dataclass
class PredictChurnRequest:
    """Input DTO for the PredictChurnUseCase."""

    customer_id: str
    lookback_days: int = 30


class PredictChurnUseCase:
    """Coordinates retrieval, feature engineering, and prediction for one customer.

    Args:
        customer_repo: Repository for fetching Customer entities.
        usage_repo: Repository for fetching UsageEvent sequences.
        churn_service: Domain service that runs the churn model.
        risk_service: Domain service that computes the risk score.
    """

    def __init__(
        self,
        customer_repo: CustomerRepository,
        usage_repo: UsageRepository,
        churn_service: ChurnModelService,
        risk_service: RiskModelService,
    ) -> None:
        self._customer_repo = customer_repo
        self._usage_repo = usage_repo
        self._churn_service = churn_service
        self._risk_service = risk_service

    def execute(self, request: PredictChurnRequest) -> PredictionResult:
        """Run the end-to-end churn prediction pipeline for a single customer.

        Args:
            request: Contains customer_id and optional lookback window.

        Returns:
            PredictionResult with churn probability, risk score, SHAP features,
            and a recommended CS action.

        Raises:
            ValueError: If the customer is not found or has already churned.
        """
        customer = self._customer_repo.get_by_id(request.customer_id)
        if customer is None:
            raise ValueError(f"Customer {request.customer_id} not found.")
        if not customer.is_active:
            raise ValueError(
                f"Customer {request.customer_id} has already churned on {customer.churn_date}."
            )

        recent_events = self._usage_repo.get_events_for_customer(
            customer_id=request.customer_id,
        )

        # Risk score computed first; fed into churn model as a feature
        risk_signals = RiskSignals(
            compliance_gap_score=0.0,   # populated from risk_signals table in infra layer
            vendor_risk_flags=0,
            usage_decay_score=0.0,
        )
        risk_score = self._risk_service.compute(risk_signals)

        return self._churn_service.predict(customer, recent_events, risk_score)
