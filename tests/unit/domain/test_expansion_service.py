"""TDD tests for ExpansionModelService.

Uses a FakeExpansionModel so the domain service can be tested in isolation
without any file I/O or DuckDB dependency.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.domain.customer.entities import Customer
from src.domain.customer.value_objects import MRR, Industry, PlanTier
from src.domain.expansion.entities import ExpansionResult
from src.domain.expansion.expansion_service import ExpansionModelPort, ExpansionModelService
from src.domain.prediction.entities import ShapFeature

# ── Fakes ─────────────────────────────────────────────────────────────────────

class FakeExpansionModel(ExpansionModelPort):
    """Fixed-output model for unit testing — no file I/O."""

    def __init__(self, fixed_probability: float = 0.75) -> None:
        self._prob = fixed_probability

    def predict_proba(self, features: dict[str, float | str]) -> float:
        return self._prob

    def explain(self, features: dict[str, float | str]) -> list[ShapFeature]:
        return [
            ShapFeature("premium_feature_trials_30d", 8.0, 0.42),
            ShapFeature("mrr_tier_ceiling_pct", 0.85, 0.31),
            ShapFeature("feature_request_tickets_90d", 3.0, 0.18),
            ShapFeature("has_open_expansion_opp", 1.0, 0.10),
            ShapFeature("events_last_30d", 45.0, -0.05),
        ]

    @property
    def version(self) -> str:
        return "1.0.0"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def growth_customer() -> Customer:
    from datetime import date
    return Customer(
        customer_id="cust-expansion-001",
        industry=Industry.FINTECH,
        plan_tier=PlanTier.GROWTH,
        signup_date=date(2024, 6, 1),
        mrr=MRR(amount=Decimal("5500.00")),
    )


def _make_service(probability: float = 0.75) -> ExpansionModelService:
    feature_extractor = MagicMock()
    feature_extractor.extract.return_value = {
        "mrr": 5500.0, "premium_feature_trials_30d": 8.0,
        "mrr_tier_ceiling_pct": 0.85, "plan_tier": "growth",
    }
    return ExpansionModelService(
        model=FakeExpansionModel(fixed_probability=probability),
        feature_extractor=feature_extractor,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestExpansionModelService:

    def test_returns_expansion_result(self, growth_customer: Customer) -> None:
        service = _make_service()
        result = service.predict(growth_customer)
        assert isinstance(result, ExpansionResult)

    def test_customer_id_propagated(self, growth_customer: Customer) -> None:
        result = _make_service().predict(growth_customer)
        assert result.customer_id == "cust-expansion-001"

    def test_propensity_matches_model_output(self, growth_customer: Customer) -> None:
        result = _make_service(probability=0.83).predict(growth_customer)
        assert result.propensity.value == pytest.approx(0.83)

    def test_top_features_sorted_by_abs_shap(self, growth_customer: Customer) -> None:
        result = _make_service().predict(growth_customer)
        impacts = [abs(f.shap_impact) for f in result.top_features]
        assert impacts == sorted(impacts, reverse=True)

    def test_at_most_5_shap_features_returned(self, growth_customer: Customer) -> None:
        result = _make_service().predict(growth_customer)
        assert len(result.top_features) <= 5

    def test_target_tier_reflects_customer_plan(self, growth_customer: Customer) -> None:
        from src.domain.customer.value_objects import PlanTier
        result = _make_service().predict(growth_customer)
        assert result.target.current_tier == PlanTier.GROWTH
        assert result.target.next_tier == PlanTier.ENTERPRISE

    def test_arr_uplift_computed_correctly(self, growth_customer: Customer) -> None:
        # MRR=5500, multiplier=5.0 (growth), propensity=0.75
        # (5500 * 12) * (5.0 - 1) * 0.75 = 66000 * 4 * 0.75 = 198000
        result = _make_service(probability=0.75).predict(growth_customer)
        assert result.expected_arr_uplift == pytest.approx(198_000.0)

    def test_is_high_value_target_for_high_propensity(self, growth_customer: Customer) -> None:
        result = _make_service(probability=0.75).predict(growth_customer)
        # Expected uplift >> 10k AND tier is HIGH/CRITICAL
        assert result.is_high_value_target is True

    def test_recommended_action_critical_tier(self, growth_customer: Customer) -> None:
        result = _make_service(probability=0.80).predict(growth_customer)
        assert "EXPANSION PRIORITY" in result.recommended_action()

    def test_recommended_action_conflict_matrix_flight_risk(
        self, growth_customer: Customer
    ) -> None:
        result = _make_service(probability=0.75).predict(growth_customer)
        action = result.recommended_action(churn_probability=0.65)
        assert "Flight Risk" in action or "\u26a0" in action

    def test_recommended_action_conflict_matrix_growth_engine(
        self, growth_customer: Customer
    ) -> None:
        result = _make_service(probability=0.75).predict(growth_customer)
        action = result.recommended_action(churn_probability=0.10)
        assert "Growth Engine" in action

    def test_to_summary_context_shape(self, growth_customer: Customer) -> None:
        result = _make_service().predict(growth_customer)
        ctx = result.to_summary_context()
        assert "propensity_score" in ctx
        assert "expected_uplift" in ctx
        assert "target_tier" in ctx
        assert "top_signals" in ctx

    def test_model_version_propagated(self, growth_customer: Customer) -> None:
        result = _make_service().predict(growth_customer)
        assert result.model_version == "1.0.0"


class TestExpansionModelServiceFreeTier:
    """Tests for FREE-tier customers — zero-MRR freemium conversion path."""

    @pytest.fixture()
    def free_customer(self) -> Customer:
        from datetime import date
        return Customer(
            customer_id="cust-free-svc-001",
            industry=Industry.FINTECH,
            plan_tier=PlanTier.FREE,
            signup_date=date(2025, 12, 1),
            mrr=MRR(amount=Decimal("0.00")),
        )

    def _make_free_service(self, probability: float = 0.80) -> ExpansionModelService:
        feature_extractor = MagicMock()
        feature_extractor.extract.return_value = {
            "mrr": 0.0, "premium_feature_trials_30d": 3.0,
            "feature_limit_hit_30d": 2.0,
            "mrr_tier_ceiling_pct": 0.0, "plan_tier": "free",
        }
        return ExpansionModelService(
            model=FakeExpansionModel(fixed_probability=probability),
            feature_extractor=feature_extractor,
        )

    def test_free_tier_target_is_starter(self, free_customer: Customer) -> None:
        result = self._make_free_service().predict(free_customer)
        assert result.target.current_tier == PlanTier.FREE
        assert result.target.next_tier == PlanTier.STARTER

    def test_free_tier_arr_uplift_uses_starter_floor(self, free_customer: Customer) -> None:
        # propensity=0.80, floor=500, 500*12*0.80 = 4800
        result = self._make_free_service(probability=0.80).predict(free_customer)
        assert result.expected_arr_uplift == pytest.approx(4800.0)

    def test_free_critical_propensity_is_high_value_target(self, free_customer: Customer) -> None:
        result = self._make_free_service(probability=0.80).predict(free_customer)
        assert result.is_high_value_target is True
