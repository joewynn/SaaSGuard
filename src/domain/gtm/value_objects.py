"""Value objects for the GTM domain."""

from enum import StrEnum


class SalesStage(StrEnum):
    """CRM pipeline stage for an opportunity."""

    PROSPECTING = "prospecting"
    QUALIFICATION = "qualification"
    PROPOSAL = "proposal"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"

    @property
    def is_open(self) -> bool:
        return self not in {SalesStage.CLOSED_WON, SalesStage.CLOSED_LOST}
