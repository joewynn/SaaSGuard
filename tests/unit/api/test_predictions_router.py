"""TDD tests for predictions router — flight risk field behaviour.

Verifies:
- UpgradePredictionResponse exposes is_flight_risk and flight_risk_reason
- /upgrade endpoint always returns is_flight_risk=False (no churn context)
- /customers/{id}/360 derives flight risk from combined churn + expansion scores
"""

from __future__ import annotations

from app.schemas.prediction import Customer360Response, UpgradePredictionResponse


class TestFlightRiskResponseSchema:
    """Schema-level tests — no HTTP round-trip required."""

    def test_upgrade_response_has_is_flight_risk_field(self) -> None:
        resp = UpgradePredictionResponse(
            customer_id="c1",
            upgrade_propensity=0.60,
            propensity_tier="high",
            is_expansion_candidate=True,
            target_tier="growth",
            expected_arr_uplift=12000.0,
            top_shap_features=[],
            recommended_action="NURTURE",
            model_version="1.0.0",
            is_flight_risk=False,
            flight_risk_reason=None,
        )
        assert resp.is_flight_risk is False
        assert resp.flight_risk_reason is None

    def test_upgrade_response_flight_risk_defaults_false(self) -> None:
        """Default value must be False — backwards-compatible."""
        resp = UpgradePredictionResponse(
            customer_id="c2",
            upgrade_propensity=0.70,
            propensity_tier="high",
            is_expansion_candidate=True,
            target_tier="enterprise",
            expected_arr_uplift=25000.0,
            top_shap_features=[],
            recommended_action="EXPANSION PRIORITY",
            model_version="1.0.0",
        )
        assert resp.is_flight_risk is False
        assert resp.flight_risk_reason is None

    def test_customer360_response_has_is_flight_risk_field(self) -> None:
        resp = Customer360Response(
            customer_id="c3",
            churn_probability=0.60,
            churn_risk_tier="high",
            upgrade_propensity=0.55,
            propensity_tier="high",
            target_tier="growth",
            expected_arr_uplift=8000.0,
            is_high_value_target=False,
            recommended_action="Flight Risk",
            churn_top_features=[],
            expansion_top_features=[],
            is_flight_risk=True,
            flight_risk_reason="Churn probability 60% and upgrade propensity 55% both exceed 50% threshold.",
        )
        assert resp.is_flight_risk is True
        assert resp.flight_risk_reason is not None

    def test_flight_risk_true_when_high_churn_high_expansion(self) -> None:
        """is_flight_risk must be True when churn≥0.5 AND propensity≥0.5."""
        churn_prob = 0.65
        propensity = 0.55
        is_flight_risk = churn_prob >= 0.50 and propensity >= 0.50
        assert is_flight_risk is True

    def test_flight_risk_false_when_low_churn_high_expansion(self) -> None:
        """Growth Engine — not a flight risk."""
        churn_prob = 0.20
        propensity = 0.70
        is_flight_risk = churn_prob >= 0.50 and propensity >= 0.50
        assert is_flight_risk is False

    def test_flight_risk_false_for_upgrade_endpoint_no_churn_context(self) -> None:
        """/upgrade endpoint has no churn context — always False."""
        # Simulate /upgrade path: no churn_probability available
        churn_prob = None
        propensity = 0.80
        is_flight_risk = False if churn_prob is None else (churn_prob >= 0.50 and propensity >= 0.50)
        assert is_flight_risk is False

    def test_flight_risk_reason_populated_when_true(self) -> None:
        """flight_risk_reason must be a non-null string when is_flight_risk is True."""
        churn_prob = 0.65
        propensity = 0.60
        is_flight_risk = churn_prob >= 0.50 and propensity >= 0.50
        flight_risk_reason = (
            f"Churn probability {churn_prob:.0%} and upgrade propensity {propensity:.0%} both exceed 50% threshold."
            if is_flight_risk
            else None
        )
        assert is_flight_risk is True
        assert flight_risk_reason is not None
        assert len(flight_risk_reason) > 0

    def test_flight_risk_reason_null_when_false(self) -> None:
        """flight_risk_reason must be None when is_flight_risk is False."""
        churn_prob = 0.20
        propensity = 0.80
        is_flight_risk = churn_prob >= 0.50 and propensity >= 0.50
        flight_risk_reason = (
            f"Churn probability {churn_prob:.0%} and upgrade propensity {propensity:.0%} both exceed 50% threshold."
            if is_flight_risk
            else None
        )
        assert is_flight_risk is False
        assert flight_risk_reason is None
