"""Value objects for the Prediction domain."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RiskTier(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ChurnProbability:
    """P(churn in next 90 days) output from the churn model.

    Calibrated probability in [0, 1]. The 0.5 threshold is the default
    operating point; business impact analysis should inform the actual
    threshold used for CS outreach triggers.
    """

    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"ChurnProbability must be in [0, 1], got {self.value}")

    @property
    def risk_tier(self) -> RiskTier:
        if self.value >= 0.75:
            return RiskTier.CRITICAL
        if self.value >= 0.5:
            return RiskTier.HIGH
        if self.value >= 0.25:
            return RiskTier.MEDIUM
        return RiskTier.LOW

    @property
    def requires_immediate_action(self) -> bool:
        """True if CS outreach should be triggered within 48 hours."""
        return self.value >= 0.5


@dataclass(frozen=True)
class RiskScore:
    """Composite compliance + usage risk score in [0, 1].

    Combines compliance_gap_score, vendor_risk_flags, and usage_decay_score.
    Distinct from churn probability — a customer can have high risk score
    but low churn probability if they are contractually locked in.
    """

    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"RiskScore must be in [0, 1], got {self.value}")

    @property
    def tier(self) -> RiskTier:
        if self.value >= 0.75:
            return RiskTier.CRITICAL
        if self.value >= 0.5:
            return RiskTier.HIGH
        if self.value >= 0.25:
            return RiskTier.MEDIUM
        return RiskTier.LOW
