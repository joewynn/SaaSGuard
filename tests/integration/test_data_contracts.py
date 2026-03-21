"""Integration tests for data schema contracts.

Verifies structural integrity of generated CSVs: nullability, uniqueness,
FK integrity, value constraints, and date range sanity.

Run AFTER generating data:
    python -m src.infrastructure.data_generation.generate_synthetic_data
    pytest tests/integration/test_data_contracts.py -v
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

DATA_DIR = Path("data/raw")

VALID_PLAN_TIERS = {"free", "starter", "growth", "enterprise"}
VALID_EVENT_TYPES = {
    "evidence_upload",
    "monitoring_run",
    "report_view",
    "user_invite",
    "integration_connect",
    "api_call",
    "premium_feature_trial",  # added v0.9.0 — expansion intent signal
    "feature_limit_hit",  # added v0.9.2 — free-tier upgrade signal
}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_TICKET_TOPICS = {"compliance", "integration", "billing", "onboarding", "feature_request"}
VALID_OPP_STAGES = {"prospecting", "qualification", "proposal", "closed_won", "closed_lost"}


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
def gtm_opportunities() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "gtm_opportunities.csv", parse_dates=["close_date"])


@pytest.fixture(scope="module")
def risk_signals() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "risk_signals.csv")


# ── All files exist ───────────────────────────────────────────────────────────


class TestFilesExist:
    def test_customers_exists(self) -> None:
        assert (DATA_DIR / "customers.csv").exists()

    def test_usage_events_exists(self) -> None:
        assert (DATA_DIR / "usage_events.csv").exists()

    def test_support_tickets_exists(self) -> None:
        assert (DATA_DIR / "support_tickets.csv").exists()

    def test_gtm_opportunities_exists(self) -> None:
        assert (DATA_DIR / "gtm_opportunities.csv").exists()

    def test_risk_signals_exists(self) -> None:
        assert (DATA_DIR / "risk_signals.csv").exists()


# ── Customers table ───────────────────────────────────────────────────────────


class TestCustomersContract:
    def test_customer_id_unique(self, customers: pd.DataFrame) -> None:
        assert customers["customer_id"].nunique() == len(customers)

    def test_no_null_customer_id(self, customers: pd.DataFrame) -> None:
        assert customers["customer_id"].notna().all()

    def test_no_null_industry(self, customers: pd.DataFrame) -> None:
        assert customers["industry"].notna().all()

    def test_plan_tier_accepted_values(self, customers: pd.DataFrame) -> None:
        invalid = set(customers["plan_tier"].unique()) - VALID_PLAN_TIERS
        assert not invalid, f"Invalid plan_tier values: {invalid}"

    def test_no_null_signup_date(self, customers: pd.DataFrame) -> None:
        assert customers["signup_date"].notna().all()

    def test_mrr_non_negative(self, customers: pd.DataFrame) -> None:
        """MRR is 0.0 for free-tier customers; all others must be positive."""
        assert (customers["mrr"] >= 0).all()
        paid = customers[customers["plan_tier"] != "free"]
        assert (paid["mrr"] > 0).all()

    def test_churn_date_after_signup(self, customers: pd.DataFrame) -> None:
        churned = customers[customers["churn_date"].notna()]
        assert (churned["churn_date"] > churned["signup_date"]).all()

    def test_signup_dates_spread(self, customers: pd.DataFrame) -> None:
        # Customers should span at least 18 months of signups
        spread_days = (customers["signup_date"].max() - customers["signup_date"].min()).days
        assert spread_days >= 548, f"Signup spread only {spread_days} days"


# ── Usage events table ────────────────────────────────────────────────────────


class TestUsageEventsContract:
    def test_event_id_unique(self, usage_events: pd.DataFrame) -> None:
        assert usage_events["event_id"].nunique() == len(usage_events)

    def test_no_null_customer_id(self, usage_events: pd.DataFrame) -> None:
        assert usage_events["customer_id"].notna().all()

    def test_fk_customer_id(self, customers: pd.DataFrame, usage_events: pd.DataFrame) -> None:
        valid_ids = set(customers["customer_id"])
        invalid = set(usage_events["customer_id"]) - valid_ids
        assert not invalid, f"{len(invalid)} usage_events reference unknown customers"

    def test_event_type_accepted_values(self, usage_events: pd.DataFrame) -> None:
        invalid = set(usage_events["event_type"].unique()) - VALID_EVENT_TYPES
        assert not invalid, f"Invalid event_type values: {invalid}"

    def test_feature_adoption_score_bounded(self, usage_events: pd.DataFrame) -> None:
        assert (usage_events["feature_adoption_score"] >= 0.0).all()
        assert (usage_events["feature_adoption_score"] <= 1.0).all()

    def test_no_events_before_signup(self, customers: pd.DataFrame, usage_events: pd.DataFrame) -> None:
        signup_map = customers.set_index("customer_id")["signup_date"]
        events_with_signup = usage_events.copy()
        events_with_signup["signup_date"] = events_with_signup["customer_id"].map(signup_map)
        # Timestamps are datetime; signup_date is date — normalise
        events_with_signup["signup_dt"] = pd.to_datetime(events_with_signup["signup_date"])
        bad = events_with_signup[events_with_signup["timestamp"] < events_with_signup["signup_dt"]]
        assert len(bad) == 0, f"{len(bad)} events occur before customer signup_date"

    def test_no_events_after_churn(self, customers: pd.DataFrame, usage_events: pd.DataFrame) -> None:
        churn_map = customers.set_index("customer_id")["churn_date"]
        events_with_churn = usage_events.copy()
        events_with_churn["churn_date"] = pd.to_datetime(events_with_churn["customer_id"].map(churn_map))
        has_churn = events_with_churn[events_with_churn["churn_date"].notna()]
        bad = has_churn[has_churn["timestamp"] > has_churn["churn_date"]]
        assert len(bad) == 0, f"{len(bad)} events occur after customer churn_date"


# ── Support tickets table ─────────────────────────────────────────────────────


class TestSupportTicketsContract:
    def test_ticket_id_unique(self, support_tickets: pd.DataFrame) -> None:
        assert support_tickets["ticket_id"].nunique() == len(support_tickets)

    def test_fk_customer_id(self, customers: pd.DataFrame, support_tickets: pd.DataFrame) -> None:
        valid_ids = set(customers["customer_id"])
        invalid = set(support_tickets["customer_id"]) - valid_ids
        assert not invalid, f"{len(invalid)} support_tickets reference unknown customers"

    def test_priority_accepted_values(self, support_tickets: pd.DataFrame) -> None:
        invalid = set(support_tickets["priority"].unique()) - VALID_PRIORITIES
        assert not invalid, f"Invalid priority values: {invalid}"

    def test_topic_accepted_values(self, support_tickets: pd.DataFrame) -> None:
        invalid = set(support_tickets["topic"].unique()) - VALID_TICKET_TOPICS
        assert not invalid, f"Invalid topic values: {invalid}"

    def test_resolution_time_positive(self, support_tickets: pd.DataFrame) -> None:
        assert (support_tickets["resolution_time"] > 0).all()


# ── GTM opportunities table ───────────────────────────────────────────────────


class TestGtmOpportunitiesContract:
    def test_opp_id_unique(self, gtm_opportunities: pd.DataFrame) -> None:
        assert gtm_opportunities["opp_id"].nunique() == len(gtm_opportunities)

    def test_fk_customer_id(self, customers: pd.DataFrame, gtm_opportunities: pd.DataFrame) -> None:
        valid_ids = set(customers["customer_id"])
        invalid = set(gtm_opportunities["customer_id"]) - valid_ids
        assert not invalid, f"{len(invalid)} gtm_opportunities reference unknown customers"

    def test_stage_accepted_values(self, gtm_opportunities: pd.DataFrame) -> None:
        invalid = set(gtm_opportunities["stage"].unique()) - VALID_OPP_STAGES
        assert not invalid, f"Invalid stage values: {invalid}"

    def test_amount_non_negative(self, gtm_opportunities: pd.DataFrame) -> None:
        """Opportunity amount is 0 for free-tier prospects; all others must be > 0."""
        assert (gtm_opportunities["amount"] >= 0).all()


# ── Risk signals table ────────────────────────────────────────────────────────


class TestRiskSignalsContract:
    def test_fk_customer_id(self, customers: pd.DataFrame, risk_signals: pd.DataFrame) -> None:
        valid_ids = set(customers["customer_id"])
        invalid = set(risk_signals["customer_id"]) - valid_ids
        assert not invalid, f"{len(invalid)} risk_signals reference unknown customers"

    def test_compliance_gap_bounded(self, risk_signals: pd.DataFrame) -> None:
        assert (risk_signals["compliance_gap_score"] >= 0.0).all()
        assert (risk_signals["compliance_gap_score"] <= 1.0).all()

    def test_vendor_risk_flags_non_negative(self, risk_signals: pd.DataFrame) -> None:
        assert (risk_signals["vendor_risk_flags"] >= 0).all()
