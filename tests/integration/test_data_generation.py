"""Integration tests for synthetic data generation — correlation validation.

These tests verify that the generated data is statistically representative
(causally coherent), not just randomly populated. A model trained on data
that fails these tests would learn no real signal.

Run AFTER generating data:
    python -m src.infrastructure.data_generation.generate_synthetic_data
    pytest tests/integration/test_data_generation.py -v
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from scipy import stats

DATA_DIR = Path("data/raw")


@pytest.fixture(scope="module")
def customers() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "customers.csv", parse_dates=["signup_date", "churn_date"])


@pytest.fixture(scope="module")
def usage_events() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "usage_events.csv", parse_dates=["timestamp"])


@pytest.fixture(scope="module")
def support_tickets() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "support_tickets.csv", parse_dates=["created_date"])


@pytest.fixture(scope="module")
def risk_signals() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "risk_signals.csv")


# ── Row counts ────────────────────────────────────────────────────────────────


class TestRowCounts:
    def test_customer_count(self, customers: pd.DataFrame) -> None:
        assert len(customers) == 5_500

    def test_usage_events_minimum(self, usage_events: pd.DataFrame) -> None:
        # At least 50 events per customer on average
        assert len(usage_events) >= 5_500 * 50

    def test_risk_signals_one_per_customer(self, customers: pd.DataFrame, risk_signals: pd.DataFrame) -> None:
        assert len(risk_signals) == len(customers)


# ── Plan-tier churn rates ─────────────────────────────────────────────────────


class TestChurnRates:
    """Observed churn rates should be within ±5pp of the target probabilities.

    Target (churner profiles combined):
        starter:    ~45%  (25% early + 20% mid)
        growth:     ~20%  (8% early + 12% mid)
        enterprise: ~8%   (3% early + 5% mid)
    """

    def _churn_rate(self, customers: pd.DataFrame, tier: str) -> float:
        tier_df = customers[customers["plan_tier"] == tier]
        return tier_df["churn_date"].notna().mean()

    def test_starter_churn_rate(self, customers: pd.DataFrame) -> None:
        rate = self._churn_rate(customers, "starter")
        assert 0.35 <= rate <= 0.55, f"starter churn rate {rate:.2%} out of [35%, 55%]"

    def test_growth_churn_rate(self, customers: pd.DataFrame) -> None:
        rate = self._churn_rate(customers, "growth")
        assert 0.12 <= rate <= 0.28, f"growth churn rate {rate:.2%} out of [12%, 28%]"

    def test_enterprise_churn_rate(self, customers: pd.DataFrame) -> None:
        rate = self._churn_rate(customers, "enterprise")
        assert 0.04 <= rate <= 0.15, f"enterprise churn rate {rate:.2%} out of [4%, 15%]"

    def test_enterprise_churns_less_than_starter(self, customers: pd.DataFrame) -> None:
        starter_rate = self._churn_rate(customers, "starter")
        enterprise_rate = self._churn_rate(customers, "enterprise")
        assert enterprise_rate < starter_rate


# ── Usage decay signal ────────────────────────────────────────────────────────


class TestUsageDecay:
    """Churned customers must have measurably lower recent event counts.

    This is the primary churn signal — if this test fails, the model has
    nothing meaningful to learn from.
    """

    @pytest.fixture(scope="class")
    def events_last_30d(self, customers: pd.DataFrame, usage_events: pd.DataFrame) -> pd.DataFrame:
        cutoff = usage_events["timestamp"].max() - pd.Timedelta(days=30)
        recent = usage_events[usage_events["timestamp"] >= cutoff]
        event_counts = recent.groupby("customer_id").size().reset_index(name="events_last_30d")
        merged = customers[["customer_id", "churn_date"]].merge(event_counts, on="customer_id", how="left")
        merged["events_last_30d"] = merged["events_last_30d"].fillna(0)
        return merged

    def test_churned_lower_recent_events(self, events_last_30d: pd.DataFrame) -> None:
        churned = events_last_30d[events_last_30d["churn_date"].notna()]["events_last_30d"]
        active = events_last_30d[events_last_30d["churn_date"].isna()]["events_last_30d"]
        stat, p_value = stats.mannwhitneyu(churned, active, alternative="less")
        assert p_value < 0.001, (
            f"Churned customers do not have significantly lower recent events "
            f"(p={p_value:.4f}). Data lacks churn signal."
        )

    def test_mean_events_ratio(self, events_last_30d: pd.DataFrame) -> None:
        churned_mean = events_last_30d[events_last_30d["churn_date"].notna()]["events_last_30d"].mean()
        active_mean = events_last_30d[events_last_30d["churn_date"].isna()]["events_last_30d"].mean()
        # Churned customers should have at least 40% fewer events than active
        assert churned_mean < active_mean * 0.6, (
            f"Mean event ratio too close: churned={churned_mean:.1f}, active={active_mean:.1f}"
        )


# ── Integration connect retention signal ──────────────────────────────────────


class TestIntegrationSignal:
    """Retained customers must have significantly more integration_connect events."""

    @pytest.fixture(scope="class")
    def integration_counts(self, customers: pd.DataFrame, usage_events: pd.DataFrame) -> pd.DataFrame:
        integrations = usage_events[usage_events["event_type"] == "integration_connect"]
        counts = integrations.groupby("customer_id").size().reset_index(name="integration_count")
        return (
            customers[["customer_id", "churn_date"]]
            .merge(counts, on="customer_id", how="left")
            .assign(integration_count=lambda df: df["integration_count"].fillna(0))
        )

    def test_retained_higher_integration_count(self, integration_counts: pd.DataFrame) -> None:
        churned = integration_counts[integration_counts["churn_date"].notna()]["integration_count"]
        retained = integration_counts[integration_counts["churn_date"].isna()]["integration_count"]
        _, p_value = stats.ttest_ind(retained, churned, alternative="greater")
        assert p_value < 0.01, (
            f"Retained customers do not have significantly more integration events (p={p_value:.4f})."
        )


# ── Support ticket spike signal ───────────────────────────────────────────────


class TestSupportTicketSignal:
    """Churned customers must have more high/critical support tickets."""

    @pytest.fixture(scope="class")
    def ticket_counts(self, customers: pd.DataFrame, support_tickets: pd.DataFrame) -> pd.DataFrame:
        high_priority = support_tickets[support_tickets["priority"].isin(["high", "critical"])]
        counts = high_priority.groupby("customer_id").size().reset_index(name="high_priority_tickets")
        return (
            customers[["customer_id", "churn_date"]]
            .merge(counts, on="customer_id", how="left")
            .assign(high_priority_tickets=lambda df: df["high_priority_tickets"].fillna(0))
        )

    def test_churned_higher_ticket_count(self, ticket_counts: pd.DataFrame) -> None:
        churned = ticket_counts[ticket_counts["churn_date"].notna()]["high_priority_tickets"]
        active = ticket_counts[ticket_counts["churn_date"].isna()]["high_priority_tickets"]
        _, p_value = stats.ttest_ind(churned, active, alternative="greater")
        assert p_value < 0.05, (
            f"Churned customers do not have significantly more high-priority tickets (p={p_value:.4f})."
        )


# ── Feature adoption score separation ────────────────────────────────────────


class TestAdoptionScoreSeparation:
    """Average feature_adoption_score must correlate with active status."""

    @pytest.fixture(scope="class")
    def avg_scores(self, customers: pd.DataFrame, usage_events: pd.DataFrame) -> pd.DataFrame:
        scores = (
            usage_events.groupby("customer_id")["feature_adoption_score"].mean().reset_index(name="avg_adoption_score")
        )
        return (
            customers[["customer_id", "churn_date"]]
            .merge(scores, on="customer_id", how="left")
            .assign(
                avg_adoption_score=lambda df: df["avg_adoption_score"].fillna(0),
                is_active=lambda df: df["churn_date"].isna().astype(int),
            )
        )

    def test_point_biserial_correlation(self, avg_scores: pd.DataFrame) -> None:
        corr, p_value = stats.pointbiserialr(avg_scores["is_active"], avg_scores["avg_adoption_score"])
        assert corr > 0.35, (
            f"Point-biserial correlation between is_active and avg_adoption_score "
            f"is only {corr:.3f} (need >0.35). Data lacks adoption signal."
        )
        assert p_value < 0.001


# ── Risk signal coherence ─────────────────────────────────────────────────────


class TestRiskSignals:
    """Churned customers must have higher compliance_gap_score."""

    @pytest.fixture(scope="class")
    def risk_with_churn(self, customers: pd.DataFrame, risk_signals: pd.DataFrame) -> pd.DataFrame:
        return customers[["customer_id", "churn_date"]].merge(risk_signals, on="customer_id", how="left")

    def test_churned_higher_compliance_gap(self, risk_with_churn: pd.DataFrame) -> None:
        churned = risk_with_churn[risk_with_churn["churn_date"].notna()]["compliance_gap_score"]
        active = risk_with_churn[risk_with_churn["churn_date"].isna()]["compliance_gap_score"]
        _, p_value = stats.ttest_ind(churned, active, alternative="greater")
        assert p_value < 0.001, f"compliance_gap_score not higher for churned customers (p={p_value:.4f})."
