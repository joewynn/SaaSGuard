"""TDD tests for PredictChurnUseCase.

Uses in-memory fakes for repositories and model – no real DB or ML artifacts.
This pattern keeps use-case tests fast and isolated.
"""

from __future__ import annotations

from collections.abc import Sequence
from unittest.mock import MagicMock

import pytest

from src.application.use_cases.predict_churn import PredictChurnRequest, PredictChurnUseCase
from src.domain.customer.entities import Customer
from src.domain.customer.repository import CustomerRepository
from src.domain.prediction.churn_model_service import ChurnModelPort, ChurnModelService
from src.domain.prediction.entities import PredictionResult, ShapFeature
from src.domain.prediction.risk_model_service import RiskModelService
from src.domain.usage.entities import UsageEvent
from src.domain.usage.repository import UsageRepository

# ── Fakes (in-memory implementations of repository ports) ────────────────────


class FakeCustomerRepository(CustomerRepository):
    def __init__(self, customers: list[Customer]) -> None:
        self._store = {c.customer_id: c for c in customers}

    def get_by_id(self, customer_id: str) -> Customer | None:
        return self._store.get(customer_id)

    def get_all_active(self) -> Sequence[Customer]:
        return [c for c in self._store.values() if c.is_active]

    def get_sample(self, n: int) -> Sequence[Customer]:
        return list(self._store.values())[:n]

    def save(self, customer: Customer) -> None:
        self._store[customer.customer_id] = customer


class FakeUsageRepository(UsageRepository):
    def __init__(self, events: list[UsageEvent] | None = None) -> None:
        self._events = events or []

    def get_events_for_customer(self, customer_id: str, since: object = None) -> Sequence[UsageEvent]:
        return [e for e in self._events if e.customer_id == customer_id]

    def get_event_count_last_n_days(self, customer_id: str, days: int) -> int:
        return len([e for e in self._events if e.customer_id == customer_id])


class FakeChurnModel(ChurnModelPort):
    def __init__(self, fixed_probability: float = 0.7) -> None:
        self._prob = fixed_probability

    def predict_proba(self, features: dict[str, float]) -> float:
        return self._prob

    def explain(self, features: dict[str, float]) -> list[ShapFeature]:
        return [ShapFeature("days_since_last_event", 14.0, 0.25)]

    @property
    def version(self) -> str:
        return "1.0.0-test"


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestPredictChurnUseCase:
    def _make_use_case(self, customer: Customer, churn_prob: float = 0.7) -> PredictChurnUseCase:
        feature_extractor = MagicMock()
        feature_extractor.extract.return_value = {}

        return PredictChurnUseCase(
            customer_repo=FakeCustomerRepository([customer]),
            usage_repo=FakeUsageRepository(),
            churn_service=ChurnModelService(
                model=FakeChurnModel(fixed_probability=churn_prob),
                feature_extractor=feature_extractor,
            ),
            risk_service=RiskModelService(),
        )

    def test_returns_prediction_result_for_active_customer(self, active_starter_customer: Customer) -> None:
        use_case = self._make_use_case(active_starter_customer)
        result = use_case.execute(PredictChurnRequest(customer_id="cust-001"))

        assert isinstance(result, PredictionResult)
        assert result.customer_id == "cust-001"

    def test_churn_probability_matches_model_output(self, active_starter_customer: Customer) -> None:
        use_case = self._make_use_case(active_starter_customer, churn_prob=0.85)
        result = use_case.execute(PredictChurnRequest(customer_id="cust-001"))

        assert result.churn_probability.value == pytest.approx(0.85)

    def test_raises_for_unknown_customer(self, active_starter_customer: Customer) -> None:
        use_case = self._make_use_case(active_starter_customer)
        with pytest.raises(ValueError, match="not found"):
            use_case.execute(PredictChurnRequest(customer_id="unknown-id"))

    def test_raises_for_already_churned_customer(self, churned_customer: Customer) -> None:
        use_case = PredictChurnUseCase(
            customer_repo=FakeCustomerRepository([churned_customer]),
            usage_repo=FakeUsageRepository(),
            churn_service=ChurnModelService(
                model=FakeChurnModel(),
                feature_extractor=MagicMock(return_value={}),
            ),
            risk_service=RiskModelService(),
        )
        with pytest.raises(ValueError, match="already churned"):
            use_case.execute(PredictChurnRequest(customer_id="cust-002"))

    def test_high_churn_probability_triggers_action(self, active_starter_customer: Customer) -> None:
        use_case = self._make_use_case(active_starter_customer, churn_prob=0.9)
        result = use_case.execute(PredictChurnRequest(customer_id="cust-001"))
        assert result.churn_probability.requires_immediate_action is True
