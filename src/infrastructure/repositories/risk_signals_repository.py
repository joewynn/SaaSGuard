"""DuckDB implementation of RiskSignalsRepository."""

from __future__ import annotations

import structlog

from src.domain.prediction.risk_model_service import RiskSignals
from src.domain.prediction.risk_signals_repository import RiskSignalsRepository
from src.infrastructure.db.duckdb_adapter import get_connection

logger = structlog.get_logger(__name__)


class DuckDBRiskSignalsRepository(RiskSignalsRepository):
    """Fetches compliance signals and computes usage decay from DuckDB.

    Business Context: Risk signals come from three sources:
      - compliance_gap_score and vendor_risk_flags: raw.risk_signals table
      - usage_decay_score: computed inline as recent vs. prior event ratio

    Usage decay = max(0, 1 - (events_last_30d / events_prev_30d)), capped at 1.
    A customer with zero events in the previous 30 days receives max decay (1.0)
    — they were already disengaged.
    """

    def get_signals(self, customer_id: str) -> RiskSignals:
        """Query DuckDB for risk signals for a single customer.

        Args:
            customer_id: UUID of the customer.

        Returns:
            RiskSignals. Returns zeroed signals if no record exists.
        """
        with get_connection() as conn:
            row = conn.execute(
                """
                WITH event_counts AS (
                    SELECT
                        COUNT(*) FILTER (
                            WHERE timestamp::DATE >= CURRENT_DATE - INTERVAL '30 days'
                        )                                       AS events_last_30d,
                        COUNT(*) FILTER (
                            WHERE timestamp::DATE >= CURRENT_DATE - INTERVAL '60 days'
                              AND timestamp::DATE <  CURRENT_DATE - INTERVAL '30 days'
                        )                                       AS events_prev_30d
                    FROM raw.usage_events
                    WHERE customer_id = ?
                ),
                risk_row AS (
                    SELECT compliance_gap_score, vendor_risk_flags
                    FROM raw.risk_signals
                    WHERE customer_id = ?
                )
                SELECT
                    COALESCE(r.compliance_gap_score, 0.0)       AS compliance_gap_score,
                    COALESCE(r.vendor_risk_flags, 0)            AS vendor_risk_flags,
                    CASE
                        WHEN e.events_prev_30d = 0 THEN 1.0
                        ELSE GREATEST(
                            0.0,
                            1.0 - CAST(e.events_last_30d AS DOUBLE)
                                / GREATEST(e.events_prev_30d, 1)
                        )
                    END                                         AS usage_decay_score
                FROM event_counts e
                LEFT JOIN risk_row r ON TRUE
                """,
                [customer_id, customer_id],
            ).fetchone()

        if row is None:
            logger.warning("risk_signals.not_found", customer_id=customer_id)
            return RiskSignals(
                compliance_gap_score=0.0,
                vendor_risk_flags=0,
                usage_decay_score=0.0,
            )

        compliance_gap_score, vendor_risk_flags, usage_decay_score = row
        logger.debug(
            "risk_signals.fetched",
            customer_id=customer_id,
            compliance_gap_score=compliance_gap_score,
            vendor_risk_flags=vendor_risk_flags,
            usage_decay_score=usage_decay_score,
        )
        return RiskSignals(
            compliance_gap_score=float(compliance_gap_score),
            vendor_risk_flags=int(vendor_risk_flags),
            usage_decay_score=float(usage_decay_score),
        )
