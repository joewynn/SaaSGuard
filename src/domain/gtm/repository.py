"""OpportunityRepository – abstract port for the GTM domain."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from src.domain.gtm.entities import Opportunity


class OpportunityRepository(ABC):
    """Port for persisting and retrieving Opportunity entities."""

    @abstractmethod
    def get_open_for_customer(self, customer_id: str) -> Sequence[Opportunity]:
        """Return all open opportunities for a given customer."""
        ...
