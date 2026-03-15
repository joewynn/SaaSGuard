"""Value objects for the Customer domain.

Value objects are immutable and compared by value, not identity.
They encapsulate business rules about what constitutes a valid value.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class PlanTier(StrEnum):
    """The commercial tier a customer is on.

    Tier correlates with feature access, support SLA, and churn risk profile.
    Enterprise customers have dedicated CSMs and lower base churn rates.
    """

    STARTER = "starter"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"


class Industry(StrEnum):
    """Vertical industry segment.

    Used for cohort segmentation and industry-specific churn benchmarking.
    """

    FINTECH = "FinTech"
    HEALTHTECH = "HealthTech"
    LEGALTECH = "LegalTech"
    HR_TECH = "HR Tech"
    OTHER = "Other"


@dataclass(frozen=True)
class MRR:
    """Monthly Recurring Revenue in USD.

    Enforces non-negative constraint. Used for business impact calculations
    (e.g. revenue at risk = MRR × churn_probability).
    """

    amount: Decimal

    def __post_init__(self) -> None:
        if self.amount < Decimal("0"):
            raise ValueError(f"MRR cannot be negative, got {self.amount}")

    @classmethod
    def from_float(cls, value: float) -> MRR:
        """Create MRR from a float, rounding to 2 decimal places."""
        return cls(amount=Decimal(str(round(value, 2))))

    @property
    def revenue_at_risk(self) -> Decimal:
        """Annual revenue at risk if customer churns (MRR × 12)."""
        return self.amount * Decimal("12")

    def __str__(self) -> str:
        return f"${self.amount:,.2f}"
