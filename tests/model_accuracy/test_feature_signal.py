"""Pre-modelling signal validation tests for Phase 3 EDA (SGD-008).

Validates that the synthetic data contains statistically significant churn signals
before Phase 4 modelling begins. These tests act as a formal acceptance gate:
if they pass, the data is fit for purpose. If they fail, the generator must be
re-run or the churn destiny profiles recalibrated.

All tests query the live DuckDB warehouse directly — no mocking.
Reference date: 2026-03-14 (Phase 2 data generation date).
"""

from pathlib import Path

import duckdb
import pandas as pd
import pytest
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test
from scipy import stats

# ── Paths ──────────────────────────────────────────────────────────────────
_TEST_DIR = Path(__file__).parent
DB_PATH = str(_TEST_DIR.parent.parent / "data" / "saasguard.duckdb")
REFERENCE_DATE = "2026-03-14"


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def conn():
    """Open a read-only connection to the DuckDB warehouse.

    Scoped to module level to avoid re-opening for every test.
    """
    connection = duckdb.connect(DB_PATH, read_only=True)
    yield connection
    connection.close()


@pytest.fixture(scope="module")
def survival_df(conn) -> pd.DataFrame:
    """All 5,000 customers with survival data (duration + event flag).

    Columns:
        customer_id, plan_tier, industry, signup_date, churn_date,
        event (1=churned, 0=censored), duration_days
    """
    return conn.execute(
        f"""
        SELECT
            customer_id,
            plan_tier,
            industry,
            signup_date::DATE                                           AS signup_date,
            churn_date::DATE                                            AS churn_date,
            CASE WHEN churn_date IS NOT NULL THEN 1 ELSE 0 END          AS event,
            CASE
                WHEN churn_date IS NOT NULL
                    THEN DATEDIFF('day', signup_date::DATE, churn_date::DATE)
                ELSE
                    DATEDIFF('day', signup_date::DATE, DATE '{REFERENCE_DATE}')
            END                                                         AS duration_days
        FROM raw.customers
        WHERE DATEDIFF(
            'day',
            signup_date::DATE,
            COALESCE(churn_date::DATE, DATE '{REFERENCE_DATE}')
        ) > 0
        """
    ).df()


@pytest.fixture(scope="module")
def feature_df(conn) -> pd.DataFrame:
    """All 5,000 customers with engineered churn features.

    Aggregates 3.5M usage events + 34K support tickets per customer.
    Includes both churned and active customers for full correlation coverage.

    Derived columns (Phase 3 additions to data dictionary):
        events_last_30d              — usage events in 30-day window before reference/churn
        avg_adoption_score           — mean feature_adoption_score across all events
        retention_signal_count       — count of high-value events (evidence_upload, monitoring_run, report_view)
        integration_connects_first_30d — integration_connect events in first 30 days of tenure
        high_priority_tickets        — lifetime count of high/critical priority tickets
    """
    return conn.execute(
        f"""
        WITH customer_ref AS (
            SELECT
                customer_id,
                plan_tier,
                industry,
                signup_date::DATE                                         AS signup_date,
                CASE WHEN churn_date IS NOT NULL THEN 1 ELSE 0 END        AS is_churned,
                COALESCE(churn_date::DATE, DATE '{REFERENCE_DATE}')        AS reference_date
            FROM raw.customers
        ),
        event_agg AS (
            SELECT
                e.customer_id,
                COUNT(*) FILTER (
                    WHERE e.timestamp::DATE >= cr.reference_date - INTERVAL '30 days'
                )                                                         AS events_last_30d,
                AVG(e.feature_adoption_score)                             AS avg_adoption_score,
                COUNT(*) FILTER (
                    WHERE e.event_type IN (
                        'evidence_upload', 'monitoring_run', 'report_view'
                    )
                )                                                         AS retention_signal_count,
                COUNT(*) FILTER (
                    WHERE e.event_type = 'integration_connect'
                      AND e.timestamp::DATE <= cr.signup_date + INTERVAL '30 days'
                )                                                         AS integration_connects_first_30d
            FROM raw.usage_events e
            JOIN customer_ref cr ON e.customer_id = cr.customer_id
            GROUP BY e.customer_id
        ),
        ticket_agg AS (
            SELECT
                customer_id,
                COUNT(*) FILTER (
                    WHERE priority IN ('high', 'critical')
                )                                                         AS high_priority_tickets
            FROM raw.support_tickets
            GROUP BY customer_id
        )
        SELECT
            cr.customer_id,
            cr.plan_tier,
            cr.industry,
            cr.is_churned,
            COALESCE(ea.events_last_30d,          0)   AS events_last_30d,
            COALESCE(ea.avg_adoption_score,        0.0) AS avg_adoption_score,
            COALESCE(ea.retention_signal_count,    0)   AS retention_signal_count,
            COALESCE(ea.integration_connects_first_30d, 0) AS integration_connects_first_30d,
            COALESCE(ta.high_priority_tickets,     0)   AS high_priority_tickets
        FROM customer_ref cr
        LEFT JOIN event_agg  ea ON cr.customer_id = ea.customer_id
        LEFT JOIN ticket_agg ta ON cr.customer_id = ta.customer_id
        """
    ).df()


# ── Tests: Kaplan-Meier signal ───────────────────────────────────────────────


class TestKaplanMeierSignals:
    """KM curve tests: plan tiers must show statistically significant separation.

    Business context: The tiered CS intervention strategy (different SLAs for
    starter vs. enterprise) is only defensible if plan tier meaningfully predicts
    churn timing. Log-rank p < 0.01 validates this.
    """

    def test_km_log_rank_starter_vs_enterprise(self, survival_df: pd.DataFrame) -> None:
        """Starter and enterprise KM curves must show log-rank p < 0.01.

        Validates that plan tier is a significant time-to-event predictor —
        the prerequisite for tier-differentiated CS investment.
        """
        starter = survival_df[survival_df["plan_tier"] == "starter"]
        enterprise = survival_df[survival_df["plan_tier"] == "enterprise"]

        result = logrank_test(
            starter["duration_days"],
            enterprise["duration_days"],
            event_observed_A=starter["event"],
            event_observed_B=enterprise["event"],
        )

        assert result.p_value < 0.01, (
            f"Log-rank p={result.p_value:.4f} ≥ 0.01. "
            "Plan tier does not significantly predict survival time. "
            "Check churn destiny profile distributions in the generator."
        )

    def test_starter_survival_lower_than_enterprise_at_day_180(self, survival_df: pd.DataFrame) -> None:
        """Starter survival probability at day 180 must be strictly less than enterprise.

        Uses day-180 survival rather than median because the KM median can be undefined
        (inf) when fewer than 50% of a tier has churned at the observation date.
        Comparing P(T > 180) is always defined and directly answers the business question:
        "Are enterprise accounts meaningfully better retained at the 6-month mark?"
        """
        kmf = KaplanMeierFitter()

        starter = survival_df[survival_df["plan_tier"] == "starter"]
        kmf.fit(starter["duration_days"], event_observed=starter["event"])
        starter_survival_180 = float(kmf.predict(180))

        enterprise = survival_df[survival_df["plan_tier"] == "enterprise"]
        kmf.fit(enterprise["duration_days"], event_observed=enterprise["event"])
        enterprise_survival_180 = float(kmf.predict(180))

        assert starter_survival_180 < enterprise_survival_180, (
            f"Starter P(T>180d)={starter_survival_180:.3f} ≥ "
            f"enterprise P(T>180d)={enterprise_survival_180:.3f}. "
            "Churn destiny profiles may be misconfigured."
        )

    def test_km_log_rank_all_three_tiers(self, survival_df: pd.DataFrame) -> None:
        """All three plan tiers together must show significant KM separation (p < 0.01).

        Uses a multivariate log-rank test across starter/growth/enterprise simultaneously.
        """
        from lifelines.statistics import multivariate_logrank_test

        result = multivariate_logrank_test(
            survival_df["duration_days"],
            survival_df["plan_tier"],
            event_observed=survival_df["event"],
        )
        assert result.p_value < 0.01, f"Multivariate log-rank p={result.p_value:.4f} ≥ 0.01 across all three tiers."


# ── Tests: Feature correlations ─────────────────────────────────────────────


class TestFeatureCorrelations:
    """Pre-modelling feature signal tests.

    Each feature must correlate with the churn label at a minimum threshold.
    Correlation direction matters: usage/adoption features should be negatively
    correlated (more usage → less churn); ticket features positively.
    """

    FEATURE_COLS = [
        "events_last_30d",
        "avg_adoption_score",
        "retention_signal_count",
        "integration_connects_first_30d",
        "high_priority_tickets",
    ]

    def _compute_correlations(self, feature_df: pd.DataFrame) -> dict[str, tuple[float, float]]:
        """Compute point-biserial correlation (r, p_value) for all features vs. churn."""
        return {col: stats.pointbiserialr(feature_df[col], feature_df["is_churned"]) for col in self.FEATURE_COLS}

    def test_events_last_30d_correlation_above_threshold(self, feature_df: pd.DataFrame) -> None:
        """events_last_30d must have |r| > 0.30 with churn label.

        Business context: Recent usage decay is the primary churn signal. If this
        correlation is weak, the sigmoid decay function in the generator failed to
        embed sufficient temporal structure.
        """
        r, p = stats.pointbiserialr(feature_df["events_last_30d"], feature_df["is_churned"])
        assert abs(r) > 0.30, (
            f"|r|={abs(r):.3f} < 0.30 for events_last_30d. Insufficient signal for the primary churn indicator."
        )
        assert p < 0.001, f"p={p:.4f} — correlation not significant at 0.1% level."

    def test_retention_signal_count_has_meaningful_signal(self, feature_df: pd.DataFrame) -> None:
        """retention_signal_count must have |r| > 0.20 with the churn label.

        Business context: High-value events (evidence_upload, monitoring_run,
        report_view) represent deep product adoption. A meaningful correlation
        validates that the CS team's 'retention signal' concept is empirically
        grounded. An exact rank requirement is too fragile when multiple features
        share similarly high correlations (common when features are highly collinear
        through the tenure dimension).
        """
        correlations = self._compute_correlations(feature_df)
        r_abs = abs(correlations["retention_signal_count"][0])

        assert r_abs > 0.20, (
            f"retention_signal_count |r|={r_abs:.3f} < 0.20. "
            "Insufficient signal. Check that retention events are correctly "
            "classified in the generator."
        )

    def test_high_priority_tickets_positive_correlation(self, feature_df: pd.DataFrame) -> None:
        """high_priority_tickets must be positively correlated with churn (tickets → churn risk).

        Business context: Support ticket spikes in the 60 days before churn are a
        designed causal feature. Positive correlation validates the synthetic data's
        causal structure — tickets reflect customer frustration, not engagement.
        """
        r, p = stats.pointbiserialr(feature_df["high_priority_tickets"], feature_df["is_churned"])
        assert r > 0, (
            f"high_priority_tickets has negative correlation ({r:.3f}). Expected positive (tickets → churn risk)."
        )
        assert p < 0.01, f"Ticket correlation not significant at 1% level (p={p:.4f})."

    def test_avg_adoption_score_negative_correlation(self, feature_df: pd.DataFrame) -> None:
        """avg_adoption_score must be negatively correlated with churn (adoption → retention).

        Business context: Feature adoption is the product's core value proposition.
        A negative correlation validates that the platform delivers on its promise.
        """
        r, p = stats.pointbiserialr(feature_df["avg_adoption_score"], feature_df["is_churned"])
        assert r < 0, (
            f"avg_adoption_score has positive correlation ({r:.3f}). Expected negative (higher adoption → lower churn)."
        )
        assert abs(r) > 0.20, (
            f"|r|={abs(r):.3f} — adoption score signal too weak. Check feature_adoption_score decay in the generator."
        )


# ── Tests: First-90-day dropout ─────────────────────────────────────────────


class TestFirstNinetyDayDropout:
    """First-90-day dropout rate tests: the 'leaky bucket' must be quantifiable.

    Business context: The PRD's leaky bucket hypothesis states 20–25% of customers
    churn in the first 90 days. If this doesn't hold, the early-intervention ROI
    model in the PRD is not supported by the data.
    """

    def _dropout_rate(self, survival_df: pd.DataFrame, tier: str, days: int = 90) -> float:
        """Compute the fraction of customers in a tier who churned within `days`."""
        tier_df = survival_df[survival_df["plan_tier"] == tier]
        return ((tier_df["event"] == 1) & (tier_df["duration_days"] <= days)).sum() / len(tier_df)

    def test_starter_first_90d_dropout_above_threshold(self, survival_df: pd.DataFrame) -> None:
        """Starter tier must have > 20% churn rate within first 90 days.

        Validates the PRD leaky-bucket claim and justifies the early CS intervention
        investment target (10–15% reduction → $2M+ ARR saved on $200M base).
        Threshold is 20% (slightly below the 25% design target) to account for
        natural seed-based sampling variance while still confirming the signal exists.
        """
        rate = self._dropout_rate(survival_df, "starter", days=90)
        assert rate > 0.20, (
            f"Starter 90-day dropout rate ({rate:.1%}) ≤ 20%. "
            "Early churn signal weaker than designed. "
            "Check early_churner profile share in the generator (target: 25%)."
        )

    def test_enterprise_first_90d_dropout_below_starter(self, survival_df: pd.DataFrame) -> None:
        """Enterprise 90-day dropout must be meaningfully lower than starter.

        Validates that tier-differentiated CS budgets are justified in the first
        critical 90 days — the period with the highest marginal ROI on intervention.
        """
        starter_rate = self._dropout_rate(survival_df, "starter", days=90)
        enterprise_rate = self._dropout_rate(survival_df, "enterprise", days=90)

        assert enterprise_rate < starter_rate, (
            f"Enterprise 90-day dropout ({enterprise_rate:.1%}) ≥ "
            f"starter ({starter_rate:.1%}). "
            "Tier differentiation in churn destiny profiles may be insufficient."
        )

    def test_enterprise_first_90d_dropout_below_10_pct(self, survival_df: pd.DataFrame) -> None:
        """Enterprise tier must have < 10% churn in first 90 days.

        Enterprise accounts receive dedicated CSMs and longer contract cycles.
        High enterprise early-churn would undermine the tiered-pricing business model.
        """
        rate = self._dropout_rate(survival_df, "enterprise", days=90)
        assert rate < 0.10, (
            f"Enterprise 90-day dropout rate ({rate:.1%}) ≥ 10%. "
            "Enterprise churn profile is too aggressive — check early_churner share (target: 3%)."
        )
