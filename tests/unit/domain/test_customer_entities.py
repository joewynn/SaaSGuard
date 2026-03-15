"""TDD tests for Customer entity and value objects.

Tests are written before (or alongside) the implementation.
All tests are pure Python – no database, no filesystem, no network.
"""

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.domain.customer.entities import Customer
from src.domain.customer.value_objects import Industry, MRR, PlanTier


# ── MRR Value Object ──────────────────────────────────────────────────────────

class TestMRR:
    def test_valid_mrr_stores_amount(self) -> None:
        mrr = MRR(amount=Decimal("1500.00"))
        assert mrr.amount == Decimal("1500.00")

    def test_zero_mrr_is_valid(self) -> None:
        mrr = MRR(amount=Decimal("0"))
        assert mrr.amount == Decimal("0")

    def test_negative_mrr_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="MRR cannot be negative"):
            MRR(amount=Decimal("-1"))

    def test_annual_revenue_at_risk_is_mrr_times_12(self) -> None:
        mrr = MRR(amount=Decimal("1000.00"))
        assert mrr.revenue_at_risk == Decimal("12000.00")

    def test_from_float_rounds_to_two_decimals(self) -> None:
        mrr = MRR.from_float(1234.567)
        assert mrr.amount == Decimal("1234.57")

    def test_str_formats_as_currency(self) -> None:
        mrr = MRR(amount=Decimal("2500.00"))
        assert str(mrr) == "$2,500.00"

    @given(st.decimals(min_value=Decimal("0"), max_value=Decimal("1000000"), allow_nan=False))
    @settings(max_examples=50)
    def test_non_negative_mrr_always_valid(self, amount: Decimal) -> None:
        mrr = MRR(amount=amount)
        assert mrr.amount >= Decimal("0")


# ── Customer Entity ───────────────────────────────────────────────────────────

class TestCustomerEntity:
    def test_active_customer_has_no_churn_date(
        self, active_starter_customer: Customer
    ) -> None:
        assert active_starter_customer.is_active is True
        assert active_starter_customer.churn_date is None

    def test_churned_customer_is_not_active(
        self, churned_customer: Customer
    ) -> None:
        assert churned_customer.is_active is False

    def test_tenure_days_for_active_customer_grows_over_time(
        self, active_starter_customer: Customer
    ) -> None:
        # Tenure should be positive and increase over time
        assert active_starter_customer.tenure_days > 0

    def test_tenure_days_for_churned_customer_is_fixed(
        self, churned_customer: Customer
    ) -> None:
        expected = (churned_customer.churn_date - churned_customer.signup_date).days  # type: ignore[operator]
        assert churned_customer.tenure_days == expected

    def test_early_stage_customer_within_90_days(self) -> None:
        customer = Customer(
            customer_id="x",
            industry=Industry.FINTECH,
            plan_tier=PlanTier.STARTER,
            signup_date=date.today(),
            mrr=MRR(amount=Decimal("500")),
        )
        assert customer.is_early_stage is True

    def test_mark_churned_sets_churn_date(
        self, active_starter_customer: Customer
    ) -> None:
        churn_date = date(2026, 4, 1)
        active_starter_customer.mark_churned(churn_date)
        assert active_starter_customer.churn_date == churn_date
        assert active_starter_customer.is_active is False

    def test_mark_churned_raises_if_already_churned(
        self, churned_customer: Customer
    ) -> None:
        with pytest.raises(ValueError, match="already churned"):
            churned_customer.mark_churned(date(2026, 4, 1))

    def test_mark_churned_raises_if_before_signup(
        self, active_starter_customer: Customer
    ) -> None:
        with pytest.raises(ValueError, match="cannot precede signup_date"):
            active_starter_customer.mark_churned(date(2020, 1, 1))
