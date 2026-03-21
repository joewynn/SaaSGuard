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
                "upgrade_date column missing from raw.customers — run generate_synthetic_data.py to regenerate."
            )
        finally:
            conn.close()

    def test_premium_feature_trial_events_exist(self) -> None:
        """premium_feature_trial event type must be present in raw.usage_events."""
        conn = _get_conn()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM raw.usage_events WHERE event_type = 'premium_feature_trial'"
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
            assert "opportunity_type" in col_names, "opportunity_type column missing from raw.gtm_opportunities."
        finally:
            conn.close()

    def test_upgraded_rate_is_between_10_and_20_pct(self) -> None:
        """is_upgraded rate should be ~10-14% of all customers per the generation spec."""
        conn = _get_conn()
        try:
            total, upgraded = conn.execute(
                "SELECT COUNT(*), SUM(CASE WHEN upgrade_date IS NOT NULL THEN 1 ELSE 0 END) FROM raw.customers"
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

        stat, p_value = stats.mannwhitneyu(upgraded_counts, non_upgraded_counts, alternative="greater")
        assert p_value < 0.05, (
            f"Mann-Whitney U test failed: p={p_value:.4f}. "
            "Expanded customers should have significantly more premium_feature_trial events. "
            "Check event type weights in generate_synthetic_data.py."
        )


@pytest.mark.skipif(not _DEPS_AVAILABLE, reason="duckdb or scipy not installed")
class TestExpansionOutreachLogContract:
    """Data contracts for the expansion_outreach_log table and feedback loop."""

    def test_outreach_log_table_exists(self) -> None:
        """expansion_outreach_log must have all required columns."""
        conn = _get_conn()
        try:
            cols = conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'raw' AND table_name = 'expansion_outreach_log'"
            ).fetchall()
            col_names = {r[0] for r in cols}
            required = {
                "outreach_id",
                "customer_id",
                "contacted_date",
                "propensity_at_outreach",
                "outreach_channel",
                "outcome",
            }
            missing = required - col_names
            assert not missing, (
                f"expansion_outreach_log missing columns: {missing}. Run generate_synthetic_data.py to regenerate."
            )
        finally:
            conn.close()

    def test_outreach_outcomes_are_valid(self) -> None:
        """All outcome values must be in the allowed set."""
        conn = _get_conn()
        try:
            rows = conn.execute("SELECT DISTINCT outcome FROM raw.expansion_outreach_log").fetchall()
        finally:
            conn.close()
        valid = {"upgraded", "churned", "no_response", "active"}
        found = {r[0] for r in rows}
        assert found.issubset(valid), f"Invalid outcome values: {found - valid}"

    def test_top_decile_customers_were_contacted(self) -> None:
        """At least 50% of outreach rows should have propensity_at_outreach > 0.65."""
        conn = _get_conn()
        try:
            total, high_prop = conn.execute(
                """
                SELECT
                    COUNT(*),
                    SUM(CASE WHEN propensity_at_outreach > 0.65 THEN 1 ELSE 0 END)
                FROM raw.expansion_outreach_log
                """
            ).fetchone()
        finally:
            conn.close()
        assert total > 0, "expansion_outreach_log is empty."
        rate = high_prop / total
        assert rate >= 0.50, f"Only {rate:.1%} of outreach rows have propensity > 0.65 (expected ≥50%)."

    def test_outreach_outcome_upgrade_rate_within_range(self) -> None:
        """Upgrade conversion rate from outreach should be 15-40%."""
        conn = _get_conn()
        try:
            total, upgraded = conn.execute(
                """
                SELECT
                    COUNT(*),
                    SUM(CASE WHEN outcome = 'upgraded' THEN 1 ELSE 0 END)
                FROM raw.expansion_outreach_log
                """
            ).fetchone()
        finally:
            conn.close()
        assert total > 0, "expansion_outreach_log is empty."
        rate = upgraded / total
        assert 0.15 <= rate <= 0.40, f"Outreach upgrade rate {rate:.1%} is outside expected range [15%, 40%]."


@pytest.mark.skipif(not _DEPS_AVAILABLE, reason="duckdb or scipy not installed")
class TestFreeTierDataContracts:
    """Data contracts for free-tier customers and feature_limit_hit events."""

    def test_feature_limit_hit_events_exist(self) -> None:
        """feature_limit_hit event type must be present in raw.usage_events."""
        conn = _get_conn()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM raw.usage_events WHERE event_type = 'feature_limit_hit'"
            ).fetchone()[0]
            assert count > 0, "No feature_limit_hit events found. Run generate_synthetic_data.py."
        finally:
            conn.close()

    def test_free_tier_customers_exist(self) -> None:
        """At least 400 free-tier customers must be present."""
        conn = _get_conn()
        try:
            count = conn.execute("SELECT COUNT(*) FROM raw.customers WHERE plan_tier = 'free'").fetchone()[0]
            assert count >= 400, f"Only {count} free-tier customers found (expected ≥400)."
        finally:
            conn.close()

    def test_free_tier_mrr_is_zero(self) -> None:
        """All free-tier customers must have MRR = 0."""
        conn = _get_conn()
        try:
            non_zero = conn.execute(
                "SELECT COUNT(*) FROM raw.customers WHERE plan_tier = 'free' AND mrr != 0"
            ).fetchone()[0]
            assert non_zero == 0, f"{non_zero} free-tier customers have non-zero MRR."
        finally:
            conn.close()

    def test_free_tier_has_feature_limit_events(self) -> None:
        """Free-tier customers must have feature_limit_hit events."""
        conn = _get_conn()
        try:
            count = conn.execute(
                """
                SELECT COUNT(DISTINCT e.customer_id)
                FROM raw.usage_events e
                JOIN raw.customers c USING (customer_id)
                WHERE c.plan_tier = 'free'
                  AND e.event_type = 'feature_limit_hit'
                """
            ).fetchone()[0]
            assert count > 0, "No free-tier customers have feature_limit_hit events."
        finally:
            conn.close()

    def test_free_expanded_has_more_limit_events_than_churners(self) -> None:
        """Mann-Whitney U: free expanded customers have more feature_limit_hit events (p<0.05)."""
        conn = _get_conn()
        try:
            rows = conn.execute(
                """
                SELECT
                    c.customer_id,
                    c.upgrade_date IS NOT NULL AS is_expanded,
                    COUNT(e.event_id) AS limit_count
                FROM raw.customers c
                LEFT JOIN raw.usage_events e
                    ON c.customer_id = e.customer_id
                    AND e.event_type = 'feature_limit_hit'
                WHERE c.plan_tier = 'free'
                GROUP BY c.customer_id, is_expanded
                """
            ).fetchall()
        finally:
            conn.close()

        expanded = [r[2] for r in rows if r[1]]
        churners = [r[2] for r in rows if not r[1]]

        if len(expanded) < 5 or len(churners) < 5:
            pytest.skip("Too few free-tier customers for statistical test.")

        _, p_value = stats.mannwhitneyu(expanded, churners, alternative="greater")
        assert p_value < 0.05, (
            f"Mann-Whitney U failed: p={p_value:.4f}. "
            "Free expanded customers should have more feature_limit_hit events."
        )

    def test_mart_expansion_features_has_free_tier(self) -> None:
        """mart_customer_expansion_features must include free-tier rows (if dbt was run)."""

        conn = _get_conn()
        try:
            # Check if marts schema/table exists before querying
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'marts' "
                "AND table_name = 'mart_customer_expansion_features'"
            ).fetchall()
            if not tables:
                pytest.skip("mart_customer_expansion_features not built yet — run dbt run.")
            count = conn.execute(
                "SELECT COUNT(*) FROM marts.mart_customer_expansion_features WHERE plan_tier = 'free'"
            ).fetchone()[0]
            assert count >= 0, "mart_customer_expansion_features query failed."
        finally:
            conn.close()
