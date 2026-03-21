"""Pydantic schemas for the Predictions router."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChurnPredictionRequest(BaseModel):
    customer_id: str = Field(..., min_length=1, max_length=64, description="UUID of the customer to score")


class ShapFeatureDTO(BaseModel):
    """A single SHAP feature contribution serialised for API consumers.

    Replaces ``list[dict[str, Any]]`` in all prediction responses to give
    downstream clients a stable, typed contract for model explainability data.
    """

    feature_name: str
    feature_value: float
    shap_impact: float = Field(..., description="Positive = increases risk. Negative = decreases risk.")


class ChurnPredictionResponse(BaseModel):
    customer_id: str
    churn_probability: float = Field(..., ge=0.0, le=1.0)
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_tier: str
    top_shap_features: list[ShapFeatureDTO]
    recommended_action: str
    model_version: str


class UpgradePredictionRequest(BaseModel):
    customer_id: str = Field(
        ..., min_length=1, max_length=64, description="UUID of the customer to score for upgrade propensity"
    )


class UpgradePredictionResponse(BaseModel):
    customer_id: str
    upgrade_propensity: float = Field(..., ge=0.0, le=1.0)
    propensity_tier: str
    is_expansion_candidate: bool
    target_tier: str | None
    expected_arr_uplift: float = Field(..., ge=0.0, description="Probability-weighted net ARR uplift (USD)")
    top_shap_features: list[ShapFeatureDTO]
    recommended_action: str
    model_version: str
    # Flight risk — always False on /upgrade (no churn context available)
    is_flight_risk: bool = False
    flight_risk_reason: str | None = None


class Customer360Response(BaseModel):
    """Full NRR lifecycle view — churn risk + expansion propensity in one response."""

    customer_id: str
    # Churn signals
    churn_probability: float = Field(..., ge=0.0, le=1.0)
    churn_risk_tier: str
    # Expansion signals
    upgrade_propensity: float = Field(..., ge=0.0, le=1.0)
    propensity_tier: str
    target_tier: str | None
    expected_arr_uplift: float = Field(..., ge=0.0, description="Probability-weighted net ARR uplift (USD)")
    is_high_value_target: bool
    # Combined routing
    recommended_action: str
    # Top drivers from both models
    churn_top_features: list[ShapFeatureDTO]
    expansion_top_features: list[ShapFeatureDTO]
    # Machine-readable flight risk signal (churn≥0.5 AND expansion≥0.5)
    is_flight_risk: bool = False
    flight_risk_reason: str | None = None
