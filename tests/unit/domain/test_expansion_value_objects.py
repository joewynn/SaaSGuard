"""TDD tests for Expansion domain value objects.

Tests are written first, then implementation. These cover:
- UpgradePropensity validation, tier mapping, and property-based edge cases
- TargetTier next-tier mapping, ARR uplift multipliers, expected uplift calculation
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.domain.customer.value_objects import PlanTier
from src.domain.expansion.value_objects import TargetTier, UpgradePropensity
from src.domain.prediction.value_objects import RiskTier


class TestUpgradePropensity:
    """Tests for UpgradePropensity value object."""

    def test_valid_propensity_stored(self) -> None:
        p = UpgradePropensity(value=0.74)
        assert p.value == pytest.approx(0.74)

    def test_zero_is_valid(self) -> None:
        assert UpgradePropensity(value=0.0).value == 0.0

    def test_one_is_valid(self) -> None:
        assert UpgradePropensity(value=1.0).value == 1.0

    def test_below_zero_raises(self) -> None:
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            UpgradePropensity(value=-0.01)

    def test_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            UpgradePropensity(value=1.001)

    @pytest.mark.parametrize(
        "value,expected_tier",
        [
            (0.05, RiskTier.LOW),
            (0.24, RiskTier.LOW),
            (0.25, RiskTier.MEDIUM),
            (0.49, RiskTier.MEDIUM),
            (0.50, RiskTier.HIGH),
            (0.74, RiskTier.HIGH),
            (0.75, RiskTier.CRITICAL),
            (0.99, RiskTier.CRITICAL),
        ],
    )
    def test_tier_mapping(self, value: float, expected_tier: RiskTier) -> None:
        assert UpgradePropensity(value=value).tier == expected_tier

    @given(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    def test_any_valid_propensity_has_a_tier(self, value: float) -> None:
        """Property-based: every value in [0, 1] maps to a valid tier."""
        p = UpgradePropensity(value=value)
        assert p.tier in list(RiskTier)

    def test_frozen_dataclass_is_immutable(self) -> None:
        p = UpgradePropensity(value=0.5)
        with pytest.raises((AttributeError, TypeError)):
            p.value = 0.9  # type: ignore[misc]


class TestTargetTier:
    """Tests for TargetTier value object."""

    def test_starter_next_is_growth(self) -> None:
        assert TargetTier(PlanTier.STARTER).next_tier == PlanTier.GROWTH

    def test_growth_next_is_enterprise(self) -> None:
        assert TargetTier(PlanTier.GROWTH).next_tier == PlanTier.ENTERPRISE

    def test_enterprise_next_is_custom(self) -> None:
        assert TargetTier(PlanTier.ENTERPRISE).next_tier == PlanTier.CUSTOM

    def test_custom_next_is_none(self) -> None:
        assert TargetTier(PlanTier.CUSTOM).next_tier is None

    def test_starter_multiplier(self) -> None:
        assert TargetTier(PlanTier.STARTER).arr_uplift_multiplier == pytest.approx(3.0)

    def test_growth_multiplier(self) -> None:
        assert TargetTier(PlanTier.GROWTH).arr_uplift_multiplier == pytest.approx(5.0)

    def test_enterprise_multiplier(self) -> None:
        assert TargetTier(PlanTier.ENTERPRISE).arr_uplift_multiplier == pytest.approx(1.2)

    def test_custom_multiplier_is_zero(self) -> None:
        assert TargetTier(PlanTier.CUSTOM).arr_uplift_multiplier == pytest.approx(0.0)

    def test_expected_uplift_starter(self) -> None:
        # MRR=1000, multiplier=3.0, propensity=0.5
        # (1000 * 12) * (3.0 - 1) * 0.5 = 12000 * 2 * 0.5 = 12000
        result = TargetTier(PlanTier.STARTER).calculate_expected_uplift(1000.0, 0.5)
        assert result == pytest.approx(12_000.0)

    def test_expected_uplift_growth(self) -> None:
        # MRR=5000, multiplier=5.0, propensity=0.8
        # (5000 * 12) * (5.0 - 1) * 0.8 = 60000 * 4 * 0.8 = 192000
        result = TargetTier(PlanTier.GROWTH).calculate_expected_uplift(5000.0, 0.8)
        assert result == pytest.approx(192_000.0)

    def test_expected_uplift_enterprise_seat_expansion(self) -> None:
        # MRR=20000, multiplier=1.2, propensity=0.6
        # (20000 * 12) * (1.2 - 1) * 0.6 = 240000 * 0.2 * 0.6 = 28800
        result = TargetTier(PlanTier.ENTERPRISE).calculate_expected_uplift(20_000.0, 0.6)
        assert result == pytest.approx(28_800.0)

    def test_expected_uplift_custom_is_zero(self) -> None:
        assert TargetTier(PlanTier.CUSTOM).calculate_expected_uplift(50_000.0, 0.9) == 0.0

    def test_expected_uplift_zero_propensity(self) -> None:
        assert TargetTier(PlanTier.STARTER).calculate_expected_uplift(1000.0, 0.0) == 0.0

    @given(
        mrr=st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
        propensity=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    def test_expected_uplift_always_non_negative(self, mrr: float, propensity: float) -> None:
        """Property-based: uplift is always >= 0 for any valid MRR and propensity."""
        result = TargetTier(PlanTier.STARTER).calculate_expected_uplift(mrr, propensity)
        assert result >= 0.0


class TestTargetTierFreeTier:
    """Tests for FREE tier — zero-MRR freemium-to-Starter conversion path."""

    def test_free_next_tier_is_starter(self) -> None:
        assert TargetTier(PlanTier.FREE).next_tier == PlanTier.STARTER

    def test_free_expected_uplift_uses_starter_floor(self) -> None:
        # MRR=0.0, propensity=0.5 → 500 * 12 * 0.5 = 3000
        result = TargetTier(PlanTier.FREE).calculate_expected_uplift(0.0, 0.5)
        assert result == pytest.approx(3000.0)

    def test_free_expected_uplift_ignores_passed_mrr(self) -> None:
        # MRR arg is ignored for FREE; always uses Starter floor $500
        result = TargetTier(PlanTier.FREE).calculate_expected_uplift(999.0, 0.5)
        assert result == pytest.approx(3000.0)

    def test_free_full_propensity(self) -> None:
        # 500 * 12 * 1.0 = 6000
        result = TargetTier(PlanTier.FREE).calculate_expected_uplift(0.0, 1.0)
        assert result == pytest.approx(6000.0)

    def test_free_zero_propensity(self) -> None:
        result = TargetTier(PlanTier.FREE).calculate_expected_uplift(0.0, 0.0)
        assert result == 0.0

    def test_free_critical_propensity_is_high_value_target(self) -> None:
        from src.domain.expansion.entities import ExpansionResult
        from src.domain.prediction.value_objects import RiskTier

        result = ExpansionResult(
            customer_id="cust-free-001",
            current_mrr=0.0,
            propensity=__import__(
                "src.domain.expansion.value_objects", fromlist=["UpgradePropensity"]
            ).UpgradePropensity(value=0.80),
            target=TargetTier(PlanTier.FREE),
        )
        assert result.propensity.tier == RiskTier.CRITICAL
        assert result.is_high_value_target is True

    def test_free_low_propensity_is_not_high_value_target(self) -> None:
        from src.domain.expansion.entities import ExpansionResult

        result = ExpansionResult(
            customer_id="cust-free-002",
            current_mrr=0.0,
            propensity=__import__(
                "src.domain.expansion.value_objects", fromlist=["UpgradePropensity"]
            ).UpgradePropensity(value=0.30),
            target=TargetTier(PlanTier.FREE),
        )
        assert result.is_high_value_target is False

    @given(
        propensity=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    def test_free_uplift_always_non_negative(self, propensity: float) -> None:
        """Property-based: FREE tier uplift is always >= 0."""
        result = TargetTier(PlanTier.FREE).calculate_expected_uplift(0.0, propensity)
        assert result >= 0.0
