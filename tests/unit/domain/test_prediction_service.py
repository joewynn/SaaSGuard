"""TDD tests for Prediction domain services and value objects."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.domain.prediction.risk_model_service import RiskModelService, RiskSignals
from src.domain.prediction.value_objects import ChurnProbability, RiskTier


class TestChurnProbability:
    def test_valid_probability_stored(self) -> None:
        cp = ChurnProbability(value=0.73)
        assert cp.value == 0.73

    def test_above_threshold_requires_action(self) -> None:
        assert ChurnProbability(value=0.5).requires_immediate_action is True

    def test_below_threshold_no_action_required(self) -> None:
        assert ChurnProbability(value=0.49).requires_immediate_action is False

    @pytest.mark.parametrize(
        "value,expected_tier",
        [
            (0.1, RiskTier.LOW),
            (0.3, RiskTier.MEDIUM),
            (0.6, RiskTier.HIGH),
            (0.8, RiskTier.CRITICAL),
        ],
    )
    def test_risk_tier_mapping(self, value: float, expected_tier: RiskTier) -> None:
        assert ChurnProbability(value=value).risk_tier == expected_tier

    @given(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    def test_any_valid_probability_has_a_tier(self, value: float) -> None:
        cp = ChurnProbability(value=value)
        assert cp.risk_tier in list(RiskTier)


class TestRiskModelService:
    def test_all_zero_signals_produce_zero_risk(
        self, risk_service: RiskModelService
    ) -> None:
        signals = RiskSignals(
            compliance_gap_score=0.0,
            vendor_risk_flags=0,
            usage_decay_score=0.0,
        )
        result = risk_service.compute(signals)
        assert result.value == 0.0

    def test_all_max_signals_produce_score_near_one(
        self, risk_service: RiskModelService
    ) -> None:
        signals = RiskSignals(
            compliance_gap_score=1.0,
            vendor_risk_flags=10,
            usage_decay_score=1.0,
        )
        result = risk_service.compute(signals)
        assert result.value == pytest.approx(1.0, abs=0.01)

    def test_vendor_flags_capped_at_normaliser(
        self, risk_service: RiskModelService
    ) -> None:
        """100 vendor flags should not produce a higher score than 5 flags."""
        signals_5 = RiskSignals(0.0, 5, 0.0)
        signals_100 = RiskSignals(0.0, 100, 0.0)
        assert risk_service.compute(signals_5).value == risk_service.compute(signals_100).value

    def test_usage_decay_dominates_risk_score(
        self, risk_service: RiskModelService
    ) -> None:
        """Usage decay has the highest weight (0.50) per business calibration."""
        high_usage_decay = RiskSignals(0.0, 0, 1.0)
        high_compliance = RiskSignals(1.0, 0, 0.0)
        assert (
            risk_service.compute(high_usage_decay).value
            > risk_service.compute(high_compliance).value
        )

    def test_risk_score_is_always_in_valid_range(
        self, risk_service: RiskModelService
    ) -> None:
        signals = RiskSignals(0.5, 3, 0.7)
        result = risk_service.compute(signals)
        assert 0.0 <= result.value <= 1.0
