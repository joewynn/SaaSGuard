"""TDD tests for PredictExpansionUseCase.

Mirrors test_predict_churn_use_case.py exactly — fake repositories,
no DuckDB dependency, exercising the application layer in isolation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.application.use_cases.predict_expansion import (
    PredictExpansionRequest,
    PredictExpansionUseCase,
)
from src.domain.customer.entities import Customer
from src.domain.customer.repository import CustomerRepository
from src.domain.customer.value_objects import MRR, Industry, PlanTier
from src.domain.expansion.entities import ExpansionResult
from src.domain.expansion.expansion_service import ExpansionModelPort, ExpansionModelService
from src.domain.prediction.entities import ShapFeature

# ── Fakes ─────────────────────────────────────────────────────────────────────

class FakeCustomerRepository(CustomerRepository):
    """In-memory customer store for unit tests."""

    def __init__(self, customers: list[Customer]) -> None:
        self._store = {c.customer_id: c for c in customers}

    def get_by_id(self, customer_id: str) -> Customer | None:
        return self._store.get(customer_id)

    def get_all_active(self):  # type: ignore[override]
        return [c for c in self._store.values() if c.is_active]

    def get_sample(self, n: int):  # type: ignore[override]
        return list(self._store.values())[:n]

    def save(self, customer: Customer) -> None:
        self._store[customer.customer_id] = customer


class FakeExpansionModel(ExpansionModelPort):
    def __init__(self, fixed_probability: float = 0.65) -> None:
        self._prob = fixed_probability

    def predict_proba(self, features: dict[str, float | str]) -> float:
        return self._prob

    def explain(self, features: dict[str, float | str]) -> list[ShapFeature]:
        return [ShapFeature("premium_feature_trials_30d", 5.0, 0.30)]

    @property
    def version(self) -> str:
        return "1.0.0"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def active_growth_customer() -> Customer:
    return Customer(
        customer_id="cust-exp-001",
        industry=Industry.FINTECH,
        plan_tier=PlanTier.GROWTH,
        signup_date=date(2024, 3, 1),
        mrr=MRR(amount=Decimal("5000.00")),
    )


@pytest.fixture()
def churned_customer() -> Customer:
    return Customer(
        customer_id="cust-exp-002",
        industry=Industry.HEALTHTECH,
        plan_tier=PlanTier.STARTER,
        signup_date=date(2023, 1, 1),
        mrr=MRR(amount=Decimal("800.00")),
        churn_date=date(2023, 6, 1),
    )


def _make_use_case(
    customer: Customer,
    probability: float = 0.65,
) -> PredictExpansionUseCase:
    feature_extractor = MagicMock()
    feature_extractor.extract.return_value = {
        "mrr": float(customer.mrr.amount),
        "premium_feature_trials_30d": 5.0,
        "plan_tier": customer.plan_tier.value,
    }
    return PredictExpansionUseCase(
        customer_repo=FakeCustomerRepository([customer]),
        expansion_service=ExpansionModelService(
            model=FakeExpansionModel(fixed_probability=probability),
            feature_extractor=feature_extractor,
        ),
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestPredictExpansionUseCase:

    def test_returns_expansion_result_for_active_customer(
        self, active_growth_customer: Customer
    ) -> None:
        use_case = _make_use_case(active_growth_customer)
        result = use_case.execute(PredictExpansionRequest(customer_id="cust-exp-001"))
        assert isinstance(result, ExpansionResult)
        assert result.customer_id == "cust-exp-001"

    def test_propensity_matches_model_output(
        self, active_growth_customer: Customer
    ) -> None:
        use_case = _make_use_case(active_growth_customer, probability=0.72)
        result = use_case.execute(PredictExpansionRequest(customer_id="cust-exp-001"))
        assert result.propensity.value == pytest.approx(0.72)

    def test_raises_for_unknown_customer(
        self, active_growth_customer: Customer
    ) -> None:
        use_case = _make_use_case(active_growth_customer)
        with pytest.raises(ValueError, match="not found"):
            use_case.execute(PredictExpansionRequest(customer_id="does-not-exist"))

    def test_raises_for_already_churned_customer(
        self, active_growth_customer: Customer, churned_customer: Customer
    ) -> None:
        use_case = _make_use_case(churned_customer)
        with pytest.raises(ValueError, match="already churned"):
            use_case.execute(PredictExpansionRequest(customer_id="cust-exp-002"))

    def test_mrr_passed_to_result(self, active_growth_customer: Customer) -> None:
        use_case = _make_use_case(active_growth_customer)
        result = use_case.execute(PredictExpansionRequest(customer_id="cust-exp-001"))
        assert result.current_mrr == pytest.approx(5000.0)

    def test_plan_tier_propagated_to_target(
        self, active_growth_customer: Customer
    ) -> None:
        use_case = _make_use_case(active_growth_customer)
        result = use_case.execute(PredictExpansionRequest(customer_id="cust-exp-001"))
        assert result.target.current_tier == PlanTier.GROWTH
        assert result.target.next_tier == PlanTier.ENTERPRISE


@pytest.fixture()
def active_free_customer() -> Customer:
    return Customer(
        customer_id="cust-free-app-001",
        industry=Industry.FINTECH,
        plan_tier=PlanTier.FREE,
        signup_date=date(2025, 11, 1),
        mrr=MRR(amount=Decimal("0.00")),
    )


class TestPredictExpansionUseCaseFreeTier:

    def test_returns_expansion_result_for_free_customer(
        self, active_free_customer: Customer
    ) -> None:
        use_case = _make_use_case(active_free_customer, probability=0.78)
        result = use_case.execute(PredictExpansionRequest(customer_id="cust-free-app-001"))
        assert isinstance(result, ExpansionResult)
        assert result.customer_id == "cust-free-app-001"

    def test_free_customer_arr_uplift_non_zero(
        self, active_free_customer: Customer
    ) -> None:
        # propensity=0.78, floor 500*12*0.78 = 4680
        use_case = _make_use_case(active_free_customer, probability=0.78)
        result = use_case.execute(PredictExpansionRequest(customer_id="cust-free-app-001"))
        assert result.expected_arr_uplift > 0.0

    def test_free_customer_target_is_starter(
        self, active_free_customer: Customer
    ) -> None:
        use_case = _make_use_case(active_free_customer)
        result = use_case.execute(PredictExpansionRequest(customer_id="cust-free-app-001"))
        assert result.target.current_tier == PlanTier.FREE
        assert result.target.next_tier == PlanTier.STARTER
