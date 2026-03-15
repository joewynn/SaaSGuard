"""DuckDB implementation of UsageRepository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from src.domain.usage.entities import UsageEvent
from src.domain.usage.repository import UsageRepository
from src.domain.usage.value_objects import EventType, FeatureAdoptionScore
from src.infrastructure.db.duckdb_adapter import get_connection


class DuckDBUsageRepository(UsageRepository):
    """Reads UsageEvent entities from the DuckDB warehouse."""

    def get_events_for_customer(
        self,
        customer_id: str,
        since: datetime | None = None,
    ) -> Sequence[UsageEvent]:
        since_clause = "AND timestamp >= ?" if since else ""
        params = [customer_id] + ([since] if since else [])

        with get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT event_id, customer_id, timestamp, event_type, feature_adoption_score
                FROM usage_events
                WHERE customer_id = ? {since_clause}
                ORDER BY timestamp DESC
                """,
                params,
            ).fetchall()

        return [self._row_to_entity(row) for row in rows]

    def get_event_count_last_n_days(self, customer_id: str, days: int) -> int:
        with get_connection() as conn:
            result = conn.execute(
                """
                SELECT COUNT(*) FROM usage_events
                WHERE customer_id = ?
                  AND timestamp >= CURRENT_TIMESTAMP - INTERVAL (?) DAY
                """,
                [customer_id, days],
            ).fetchone()
        return int(result[0]) if result else 0

    @staticmethod
    def _row_to_entity(row: tuple) -> UsageEvent:  # type: ignore[type-arg]
        event_id, customer_id, timestamp, event_type, adoption_score = row
        return UsageEvent(
            event_id=str(event_id),
            customer_id=str(customer_id),
            timestamp=timestamp if isinstance(timestamp, datetime) else datetime.fromisoformat(str(timestamp)),
            event_type=EventType(event_type),
            feature_adoption_score=FeatureAdoptionScore(value=float(adoption_score)),
        )
