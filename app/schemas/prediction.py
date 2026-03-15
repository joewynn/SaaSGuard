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
