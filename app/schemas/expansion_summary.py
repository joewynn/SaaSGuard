"""Pydantic request/response schemas for POST /summaries/expansion."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GenerateExpansionSummaryRequest(BaseModel):
    """Request body for POST /summaries/expansion.

    Args:
        customer_id: UUID of the active customer to generate a brief for.
        audience: 'account_executive' (tactical brief + optional email) or
                  'csm' (nurture brief only).
        include_email_draft: If True and audience is 'account_executive',
                             response will contain a 3-sentence email draft.
    """

    customer_id: str = Field(..., min_length=1, max_length=64)
    audience: Literal["account_executive", "csm"] = "account_executive"
    include_email_draft: bool = False


class ExpansionSummaryResponse(BaseModel):
    """Response body for POST /summaries/expansion.

    Args:
        customer_id: UUID of the customer this brief is about.
        propensity_summary: Plain-English propensity tier + ARR uplift sentence.
        propensity_score: Calibrated upgrade propensity in [0, 1].
        propensity_tier: Tier label — 'low' / 'medium' / 'high' / 'critical'.
        target_tier: Next upgrade target (e.g. 'enterprise'), or None at ceiling.
        expected_arr_uplift: Probability-weighted net ARR opportunity (USD).
        key_narrative_drivers: Top 3 signals in business language.
        ae_tactical_brief: LLM-generated brief with watermark.
        email_draft: Optional 3-sentence email with CTA, or None.
        guardrail_status: 'PASSED' / 'FLAGGED' / 'REJECTED'.
        fact_confidence: 1.0 − (0.25 × hallucinated signals), in [0, 1].
        generated_at: ISO 8601 UTC timestamp.
        model_used: LLM model identifier (e.g. 'llama-3.1-8b-instant').
        llm_provider: Inference provider — 'groq' or 'ollama'.
        correlation_id: UUID hex linking this brief to GTM outreach log for lift
                        measurement. When an AE accepts or edits the draft, join
                        correlation_id → expansion_outreach_log to compute whether
                        high fact_confidence briefs close at higher rates.
    """

    customer_id: str
    propensity_summary: str
    propensity_score: float = Field(..., ge=0.0, le=1.0)
    propensity_tier: str
    target_tier: str | None
    expected_arr_uplift: float = Field(..., ge=0.0)
    key_narrative_drivers: list[str]
    ae_tactical_brief: str
    email_draft: str | None
    guardrail_status: str
    fact_confidence: float = Field(..., ge=0.0, le=1.0)
    generated_at: str
    model_used: str
    llm_provider: str
    correlation_id: str
