"""Value objects for the Usage domain."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EventType(StrEnum):
    """Product event types tracked in usage_events.

    `integration_connect` events are strong retention signals.
    Absence of `monitoring_run` events is an early churn indicator.
    """

    EVIDENCE_UPLOAD = "evidence_upload"
    MONITORING_RUN = "monitoring_run"
    REPORT_VIEW = "report_view"
    USER_INVITE = "user_invite"
    INTEGRATION_CONNECT = "integration_connect"
    API_CALL = "api_call"


@dataclass(frozen=True)
class FeatureAdoptionScore:
    """Composite 0–1 score reflecting breadth and depth of feature usage.

    Scores below 0.2 combined with declining event frequency are the
    strongest leading indicators of churn in the first 90 days.
    """

    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"FeatureAdoptionScore must be in [0, 1], got {self.value}")

    @property
    def is_low(self) -> bool:
        """True if adoption is critically low (below 0.2)."""
        return self.value < 0.2

    @property
    def label(self) -> str:
        if self.value < 0.2:
            return "critical"
        if self.value < 0.5:
            return "low"
        if self.value < 0.75:
            return "moderate"
        return "high"
