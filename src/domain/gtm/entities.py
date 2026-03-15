"""Opportunity entity for the GTM bounded context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.domain.gtm.value_objects import SalesStage


@dataclass
class Opportunity:
    """A sales or expansion opportunity linked to a customer.

    Args:
        opp_id: UUID primary key.
        customer_id: FK to Customer entity.
        stage: Current CRM pipeline stage.
        close_date: Actual or expected close date.
        amount: USD opportunity value.
        sales_owner: Anonymised sales rep identifier.
    """

    opp_id: str
    customer_id: str
    stage: SalesStage
    close_date: date
    amount: Decimal
    sales_owner: str

    @property
    def is_at_risk(self) -> bool:
        """True if an open opportunity exists for a customer who may churn.

        Used in the GTM domain to flag revenue at risk in the sales pipeline.
        """
        return self.stage.is_open and self.close_date >= date.today()
