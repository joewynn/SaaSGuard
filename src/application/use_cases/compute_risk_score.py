"""ComputeRiskScoreUseCase – application layer use case."""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.prediction.risk_model_service import RiskModelService, RiskSignals
from src.domain.prediction.value_objects import RiskScore


@dataclass
class ComputeRiskScoreRequest:
    """Input DTO for the ComputeRiskScoreUseCase."""

    customer_id: str
    compliance_gap_score: float
    vendor_risk_flags: int
    usage_decay_score: float


class ComputeRiskScoreUseCase:
    """Computes a composite risk score from pre-fetched signal values.

    Args:
        risk_service: Domain service that applies the weighting formula.
    """

    def __init__(self, risk_service: RiskModelService) -> None:
        self._risk_service = risk_service

    def execute(self, request: ComputeRiskScoreRequest) -> RiskScore:
        """Compute and return a RiskScore for the given signals.

        Args:
            request: Pre-fetched signal values for the customer.

        Returns:
            RiskScore value object in [0, 1] with risk tier.
        """
        signals = RiskSignals(
            compliance_gap_score=request.compliance_gap_score,
            vendor_risk_flags=request.vendor_risk_flags,
            usage_decay_score=request.usage_decay_score,
        )
        return self._risk_service.compute(signals)
