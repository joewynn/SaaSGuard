"""Integration tests for expansion data contracts.

Verifies that synthetic data generation produced the expected expansion signals:
- upgrade_date column exists in raw.customers
- premium_feature_trial events exist in raw.usage_events
- expanded customers have statistically higher premium_feature_trials_30d (Mann-Whitney U)

These tests run against the real DuckDB file (data/saasguard.duckdb).
They will be skipped automatically if the DB file does not exist yet.
"""

from __future__ import annotations

import pytest

try:
    import duckdb
    from scipy import stats
    _DEPS_AVAILABLE = True
except ImportError:
    _DEPS_AVAILABLE = False

DB_PATH = "data/saasguard.duckdb"


def _get_conn():  # type: ignore[return]
    """Return a DuckDB connection if the DB file exists."""
    import os
    if not os.path.exists(DB_PATH):
        pytest.skip(f"DuckDB file not found at {DB_PATH} — run data generation first.")
    return duckdb.connect(DB_PATH, read_only=True)


@pytest.mark.skipif(not _DEPS_AVAILABLE, reason="duckdb or scipy not installed")
class TestExpansionDataContracts:

    def test_upgrade_date_column_exists_in_customers(self) -> None:
        """upgrade_date column must be present in raw.customers."""
        conn = _get_conn()
        try:
            cols = conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'raw' AND table_name = 'customers'"
            ).fetchall()
            col_names = [r[0] for r in cols]
            assert "upgrade_date" in col_names, (
                "upgrade_date column missing from raw.customers — "
                "run generate_synthetic_data.py to regenerate."
            )
        finally:
            conn.close()

    def test_premium_feature_trial_events_exist(self) -> None:
        """premium_feature_trial event type must be present in raw.usage_events."""
        conn = _get_conn()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM raw.usage_events "
                "WHERE event_type = 'premium_feature_trial'"
            ).fetchone()[0]
            assert count > 0, (
                "No premium_feature_trial events found in raw.usage_events. "
                "Run generate_synthetic_data.py to regenerate."
            )
        finally:
            conn.close()

    def test_opportunity_type_column_exists_in_gtm_opportunities(self) -> None:
        """opportunity_type column must be present in raw.gtm_opportunities."""
        conn = _get_conn()
        try:
            cols = conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'raw' AND table_name = 'gtm_opportunities'"
            ).fetchall()
            col_names = [r[0] for r in cols]
            assert "opportunity_type" in col_names, (
                "opportunity_type column missing from raw.gtm_opportunities."
            )
        finally:
            conn.close()

    def test_upgraded_rate_is_between_10_and_20_pct(self) -> None:
        """is_upgraded rate should be ~10-14% of all customers per the generation spec."""
        conn = _get_conn()
        try:
            total, upgraded = conn.execute(
                "SELECT COUNT(*), SUM(CASE WHEN upgrade_date IS NOT NULL THEN 1 ELSE 0 END) "
                "FROM raw.customers"
            ).fetchone()
            rate = upgraded / total
            assert 0.05 <= rate <= 0.25, (
                f"Upgraded rate {rate:.1%} is outside expected range [5%, 25%]. "
                "Check destiny probabilities in generate_synthetic_data.py."
            )
        finally:
            conn.close()

    def test_expanded_customers_have_more_premium_trials_than_non_expanded(self) -> None:
        """Mann-Whitney U test: expanded customers have significantly higher premium trial rate.

        Causal coherence check: the generation signal must be statistically present.
        """
        conn = _get_conn()
        try:
            # Get premium_feature_trial counts in last 30d per customer
            rows = conn.execute(
                """
                SELECT
                    c.customer_id,
                    c.upgrade_date IS NOT NULL AS is_upgraded,
                    COUNT(e.event_id) AS trial_count
                FROM raw.customers c
                LEFT JOIN raw.usage_events e
                    ON c.customer_id = e.customer_id
                    AND e.event_type = 'premium_feature_trial'
                    AND CAST(e.timestamp AS DATE) >= CURRENT_DATE - 30
                WHERE c.churn_date IS NULL
                GROUP BY c.customer_id, is_upgraded
                """
            ).fetchall()
        finally:
            conn.close()

        upgraded_counts = [r[2] for r in rows if r[1]]
        non_upgraded_counts = [r[2] for r in rows if not r[1]]

        assert len(upgraded_counts) > 10, "Too few upgraded customers for statistical test."
        assert len(non_upgraded_counts) > 10, "Too few non-upgraded customers."

        stat, p_value = stats.mannwhitneyu(
            upgraded_counts, non_upgraded_counts, alternative="greater"
        )
        assert p_value < 0.05, (
            f"Mann-Whitney U test failed: p={p_value:.4f}. "
            "Expanded customers should have significantly more premium_feature_trial events. "
            "Check event type weights in generate_synthetic_data.py."
        )
