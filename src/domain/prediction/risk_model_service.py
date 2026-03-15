"""RiskModelService – domain service for compliance + usage risk scoring."""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.prediction.value_objects import RiskScore


@dataclass(frozen=True)
class RiskSignals:
    """Raw risk inputs from the risk_signals table.

    Args:
        compliance_gap_score: 0–1 score of open compliance gaps.
        vendor_risk_flags: Count of third-party vendor risk alerts.
        usage_decay_score: 0–1 score of recent usage decline (computed from events).
    """

    compliance_gap_score: float
    vendor_risk_flags: int
    usage_decay_score: float


class RiskModelService:
    """Computes a composite risk score from compliance and usage signals.

    Weights are calibrated to business impact:
    - Usage decay is the strongest leading indicator of near-term churn
    - Compliance gaps drive risk but not always churn (contractual stickiness)
    - Vendor risk flags have lower weight but non-zero contribution

    These weights should be revisited quarterly using SHAP analysis on
    the full churn model to ensure they remain calibrated to observed outcomes.
    """

    USAGE_WEIGHT: float = 0.50
    COMPLIANCE_WEIGHT: float = 0.35
    VENDOR_WEIGHT: float = 0.15
    VENDOR_FLAG_NORMALISER: float = 5.0  # treat 5+ flags as max risk

    def compute(self, signals: RiskSignals) -> RiskScore:
        """Compute a composite RiskScore from raw signals.

        Args:
            signals: The three risk signal components.

        Returns:
            RiskScore value object in [0, 1].
        """
        vendor_normalised = min(
            signals.vendor_risk_flags / self.VENDOR_FLAG_NORMALISER, 1.0
        )
        composite = (
            self.USAGE_WEIGHT * signals.usage_decay_score
            + self.COMPLIANCE_WEIGHT * signals.compliance_gap_score
            + self.VENDOR_WEIGHT * vendor_normalised
        )
        return RiskScore(value=round(composite, 4))
