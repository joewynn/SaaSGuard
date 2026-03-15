"""TDD tests for Usage domain entities and value objects."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.domain.usage.value_objects import EventType, FeatureAdoptionScore


class TestFeatureAdoptionScore:
    def test_valid_score_stores_value(self) -> None:
        score = FeatureAdoptionScore(value=0.5)
        assert score.value == 0.5

    def test_zero_is_valid(self) -> None:
        assert FeatureAdoptionScore(value=0.0).value == 0.0

    def test_one_is_valid(self) -> None:
        assert FeatureAdoptionScore(value=1.0).value == 1.0

    def test_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="must be in"):
            FeatureAdoptionScore(value=1.01)

    def test_below_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="must be in"):
            FeatureAdoptionScore(value=-0.01)

    def test_is_low_below_threshold(self) -> None:
        assert FeatureAdoptionScore(value=0.19).is_low is True

    def test_is_not_low_at_threshold(self) -> None:
        assert FeatureAdoptionScore(value=0.2).is_low is False

    @pytest.mark.parametrize(
        "value,expected_label",
        [
            (0.1, "critical"),
            (0.3, "low"),
            (0.6, "moderate"),
            (0.9, "high"),
        ],
    )
    def test_label_mapping(self, value: float, expected_label: str) -> None:
        assert FeatureAdoptionScore(value=value).label == expected_label

    @given(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    def test_valid_range_always_accepted(self, value: float) -> None:
        score = FeatureAdoptionScore(value=value)
        assert 0.0 <= score.value <= 1.0


class TestUsageEventRetentionSignal:
    def test_integration_connect_is_retention_signal(
        self, retention_event  # type: ignore[no-untyped-def]
    ) -> None:
        assert retention_event.is_retention_signal is True

    def test_report_view_is_not_retention_signal(
        self, low_adoption_event  # type: ignore[no-untyped-def]
    ) -> None:
        assert low_adoption_event.is_retention_signal is False
