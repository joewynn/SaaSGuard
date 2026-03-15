"""Pydantic schemas for the Customers router – Customer 360 response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ShapFeatureSummary(BaseModel):
    """A single SHAP feature contribution surfaced in the API response."""

    feature: str
    value: float
    shap_impact: float = Field(..., description="Positive = increases churn risk")


class Customer360Response(BaseModel):
    """Full Customer 360 profile returned by GET /customers/{customer_id}.

    Combines customer master data, real-time churn prediction, usage signals,
    support health, and GTM context into a single response for CS teams.
    """

    customer_id: str
    plan_tier: str
    industry: str
    mrr: float = Field(..., ge=0.0, description="Monthly Recurring Revenue (USD)")
    tenure_days: int = Field(..., ge=0, description="Days since signup")
    churn_probability: float = Field(..., ge=0.0, le=1.0)
    risk_tier: str = Field(..., description="LOW | MEDIUM | HIGH | CRITICAL")
    top_shap_features: list[ShapFeatureSummary]
    events_last_30d: int = Field(..., ge=0)
    open_ticket_count: int = Field(..., ge=0)
    gtm_stage: str | None = None
    latest_prediction_at: str
