"""PredictChurnUseCase – application layer use case.

Orchestrates domain objects to produce a churn prediction.
This layer has no knowledge of FastAPI, DuckDB, or pickle files.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.customer.repository import CustomerRepository
from src.domain.prediction.churn_model_service import ChurnModelService
from src.domain.prediction.entities import PredictionResult
from src.domain.prediction.risk_model_service import RiskModelService, RiskSignals
from src.domain.prediction.risk_signals_repository import RiskSignalsRepository
from src.domain.usage.repository import UsageRepository


@dataclass
class PredictChurnRequest:
    """Input DTO for the PredictChurnUseCase."""

    customer_id: str
    lookback_days: int = field(default=30)


class PredictChurnUseCase:
    """Coordinates retrieval, feature engineering, and prediction for one customer.

    Args:
        customer_repo: Repository for fetching Customer entities.
        usage_repo: Repository for fetching UsageEvent sequences (retained for
                    future use; feature extraction now happens inside the extractor).
        churn_service: Domain service that runs the churn model.
        risk_service: Domain service that computes the composite risk score.
        risk_signals_repo: Optional repository for real risk signal data.
                           Falls back to zeroed signals when not provided,
                           which preserves backward compatibility for unit tests.
    """

    def __init__(
        self,
        customer_repo: CustomerRepository,
        usage_repo: UsageRepository,
        churn_service: ChurnModelService,
        risk_service: RiskModelService,
        risk_signals_repo: RiskSignalsRepository | None = None,
    ) -> None:
        self._customer_repo = customer_repo
        self._usage_repo = usage_repo
        self._churn_service = churn_service
        self._risk_service = risk_service
        self._risk_signals_repo = risk_signals_repo

    def execute(self, request: PredictChurnRequest) -> PredictionResult:
        """Run the end-to-end churn prediction pipeline for a single customer.

        Business Context: Fetches customer state, resolves real risk signals
        from raw.risk_signals (compliance gaps + vendor flags + usage decay),
        and delegates to ChurnModelService which queries the dbt feature mart
        for all ML features. One DB read per layer, < 5ms total.

        Args:
            request: Contains customer_id and optional lookback window.

        Returns:
            PredictionResult with calibrated churn probability, composite risk
            score, top-5 SHAP feature drivers, and a recommended CS action.

        Raises:
            ValueError: If the customer is not found or has already churned.
        """
        customer = self._customer_repo.get_by_id(request.customer_id)
        if customer is None:
            raise ValueError(f"Customer {request.customer_id} not found.")
        if not customer.is_active:
            raise ValueError(f"Customer {request.customer_id} has already churned on {customer.churn_date}.")

        # Resolve real risk signals when the infrastructure repo is available
        if self._risk_signals_repo is not None:
            risk_signals = self._risk_signals_repo.get_signals(request.customer_id)
        else:
            # Fallback for unit tests that don't wire up real infrastructure
            risk_signals = RiskSignals(
                compliance_gap_score=0.0,
                vendor_risk_flags=0,
                usage_decay_score=0.0,
            )

        risk_score = self._risk_service.compute(risk_signals)
        return self._churn_service.predict(customer, risk_score)
