"""Pydantic schemas for the /summaries API endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GenerateSummaryRequest(BaseModel):
    """Request body for POST /summaries/customer."""

    customer_id: str = Field(..., description="UUID of the active customer to summarise.")
    audience: Literal["csm", "executive"] = Field(
        default="csm",
        description="'csm' for a Customer Success Manager briefing, 'executive' for a VP summary.",
    )


class ShapFeatureSummary(BaseModel):
    """A single SHAP feature contribution included in the summary response."""

    feature: str
    value: float
    shap_impact: float


class GenerateSummaryResponse(BaseModel):
    """Response body for POST /summaries/customer."""

    customer_id: str
    audience: str
    summary: str = Field(..., description="LLM-generated narrative with guardrail watermark.")
    churn_probability: float = Field(..., ge=0.0, le=1.0)
    risk_tier: str
    top_shap_features: list[ShapFeatureSummary]
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="1.0 = all guardrails passed; degrades 0.2 per flag."
    )
    guardrail_flags: list[str] = Field(
        default_factory=list, description="List of guardrail violations detected."
    )
    generated_at: str
    model_used: str
    llm_provider: str


class AskCustomerRequest(BaseModel):
    """Request body for POST /summaries/customer/ask."""

    customer_id: str = Field(..., description="UUID of the customer to ask about.")
    question: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Free-text question about the customer (5–500 characters).",
    )


class AskCustomerResponse(BaseModel):
    """Response body for POST /summaries/customer/ask."""

    customer_id: str
    question: str
    answer: str = Field(..., description="LLM-generated answer with guardrail watermark.")
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    guardrail_flags: list[str] = Field(default_factory=list)
    scope_exceeded: bool = Field(
        ...,
        description="True if the question could not be answered from available customer data.",
    )
    generated_at: str
    model_used: str
    llm_provider: str
