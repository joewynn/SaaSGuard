"""RiskSignalsRepository – abstract port for fetching risk signal data.

Infrastructure implementations live in src/infrastructure/repositories/.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.prediction.risk_model_service import RiskSignals


class RiskSignalsRepository(ABC):
    """Fetches and computes RiskSignals for a given customer.

    Business Context: Risk signals come from three sources — compliance gap
    data (raw.risk_signals table), vendor risk flags (same table), and usage
    decay (computed from recent event history). This port decouples the
    application layer from the DuckDB query implementation.
    """

    @abstractmethod
    def get_signals(self, customer_id: str) -> RiskSignals:
        """Return RiskSignals for the given customer.

        Args:
            customer_id: UUID of the customer to fetch signals for.

        Returns:
            RiskSignals with compliance_gap_score, vendor_risk_flags,
            and usage_decay_score (computed from event recency).
            Returns zeroed signals if no data exists for the customer.
        """
        ...
