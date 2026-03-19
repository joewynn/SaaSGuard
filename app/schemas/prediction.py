"""Pydantic schemas for the Predictions router."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChurnPredictionRequest(BaseModel):
    customer_id: str = Field(..., description="UUID of the customer to score")


class ChurnPredictionResponse(BaseModel):
    customer_id: str
    churn_probability: float = Field(..., ge=0.0, le=1.0)
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_tier: str
    top_shap_features: list[dict[str, Any]]
    recommended_action: str
    model_version: str


class UpgradePredictionRequest(BaseModel):
    customer_id: str = Field(..., description="UUID of the customer to score for upgrade propensity")


class UpgradePredictionResponse(BaseModel):
    customer_id: str
    upgrade_propensity: float = Field(..., ge=0.0, le=1.0)
    propensity_tier: str
    is_expansion_candidate: bool
    target_tier: str | None
    expected_arr_uplift: float = Field(..., description="Probability-weighted net ARR uplift (USD)")
    top_shap_features: list[dict[str, Any]]
    recommended_action: str
    model_version: str


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
    expected_arr_uplift: float
    is_high_value_target: bool
    # Combined routing
    recommended_action: str
    # Top drivers from both models
    churn_top_features: list[dict[str, Any]]
    expansion_top_features: list[dict[str, Any]]
