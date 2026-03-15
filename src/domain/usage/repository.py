"""UsageRepository – abstract port for the Usage domain."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Sequence

from src.domain.usage.entities import UsageEvent


class UsageRepository(ABC):
    """Port for retrieving usage events."""

    @abstractmethod
    def get_events_for_customer(
        self,
        customer_id: str,
        since: datetime | None = None,
    ) -> Sequence[UsageEvent]:
        """Retrieve all usage events for a customer, optionally filtered by date.

        Args:
            customer_id: The customer whose events to fetch.
            since: If provided, return only events after this UTC datetime.
        """
        ...

    @abstractmethod
    def get_event_count_last_n_days(self, customer_id: str, days: int) -> int:
        """Count events in the last N days.

        Used as a feature for churn model: event decay is a leading indicator.
        """
        ...
