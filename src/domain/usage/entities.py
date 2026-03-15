"""UsageEvent entity – core of the Usage bounded context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.usage.value_objects import EventType, FeatureAdoptionScore


@dataclass
class UsageEvent:
    """A single product interaction by a customer.

    Args:
        event_id: UUID primary key.
        customer_id: FK to Customer entity.
        timestamp: UTC datetime of the event.
        event_type: The type of product action taken.
        feature_adoption_score: Adoption score snapshot at the time of the event.
    """

    event_id: str
    customer_id: str
    timestamp: datetime
    event_type: EventType
    feature_adoption_score: FeatureAdoptionScore

    @property
    def is_retention_signal(self) -> bool:
        """True if this event type is a known strong retention indicator.

        Integration connects and API calls indicate deep product embedding,
        which significantly reduces churn probability.
        """
        return self.event_type in {
            EventType.INTEGRATION_CONNECT,
            EventType.API_CALL,
            EventType.MONITORING_RUN,
        }
