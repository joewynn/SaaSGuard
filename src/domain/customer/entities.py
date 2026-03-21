"""Customer entity – core of the Customer bounded context.

An Entity has a unique identity (customer_id) and mutable lifecycle state.
Business rules about customers live here, not in the API or infrastructure layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from src.domain.customer.value_objects import MRR, Industry, PlanTier


@dataclass
class Customer:
    """Represents a B2B SaaS customer account.

    The customer entity owns lifecycle state (active vs churned) and exposes
    domain methods that encapsulate churn-relevant business rules.

    Args:
        customer_id: Unique identifier (UUID string).
        industry: Vertical segment, used for cohort analysis.
        plan_tier: Commercial tier (starter / growth / enterprise).
        signup_date: Date of first contract activation.
        mrr: Monthly Recurring Revenue value object.
        churn_date: Date of cancellation; None means still active (right-censored).
    """

    customer_id: str
    industry: Industry
    plan_tier: PlanTier
    signup_date: date
    mrr: MRR
    churn_date: date | None = field(default=None)

    @property
    def is_active(self) -> bool:
        """True if the customer has not churned."""
        return self.churn_date is None

    @property
    def tenure_days(self) -> int:
        """Days from signup to churn (or today if still active).

        Used as the time axis in survival analysis models.
        """
        end_date = self.churn_date if self.churn_date else date.today()
        return (end_date - self.signup_date).days

    @property
    def is_early_stage(self) -> bool:
        """True if customer is within the critical first-90-day onboarding window.

        20–25% of voluntary churn occurs in this window (per Forrester data).
        """
        return self.tenure_days <= 90

    @property
    def annual_revenue_at_risk(self) -> str:
        """Human-readable annual revenue that would be lost if this customer churns."""
        return str(self.mrr.revenue_at_risk)

    def mark_churned(self, churn_date: date) -> None:
        """Record the churn event.

        Args:
            churn_date: The date cancellation was confirmed.

        Raises:
            ValueError: If churn_date precedes signup_date or customer already churned.
        """
        if not self.is_active:
            raise ValueError(f"Customer {self.customer_id} has already churned.")
        if churn_date < self.signup_date:
            raise ValueError(f"churn_date {churn_date} cannot precede signup_date {self.signup_date}")
        self.churn_date = churn_date
