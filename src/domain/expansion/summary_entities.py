"""ExpansionSummaryResult entity — output of GenerateExpansionSummaryUseCase.

Immutable dataclass that carries the LLM-generated AE brief, optional email
draft, guardrail validation outcome, and full provenance for audit logging.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class ExpansionSummaryResult:
    """Complete output of the expansion narrative generation pipeline.

    Business Context: Closes the "last mile" between a high-propensity score
    in DuckDB and an actionable, personalised pitch in the AE's hands.
    The correlation_id links each brief to its downstream outcome in
    expansion_outreach_log, enabling the data team to measure whether
    high fact_confidence briefs close at higher rates (V2 fine-tuning flywheel).

    Args:
        customer_id: UUID of the account this brief is about.
        propensity_summary: Plain-English propensity tier + score sentence.
        key_narrative_drivers: Top 3 signals in business language (from SHAP).
        ae_tactical_brief: LLM-generated brief with guardrail watermark appended.
        email_draft: Optional 3-sentence email with CTA (AE audience only).
        guardrail_status: 'PASSED' / 'FLAGGED' (1 issue) / 'REJECTED' (2+ issues).
        fact_confidence: 1.0 − (0.25 × n_flags), floored at 0.0.
        generated_at: UTC timestamp when the summary was created.
        model_used: LLM model identifier (e.g. 'llama-3.1-8b-instant').
        llm_provider: Inference provider — 'groq' or 'ollama'.
        propensity_score: Raw calibrated probability in [0, 1].
        propensity_tier: Human-readable tier — 'low' / 'medium' / 'high' / 'critical'.
        target_tier: Next upgrade target (e.g. 'enterprise'), or None at ceiling.
        expected_arr_uplift: Probability-weighted net ARR opportunity (USD).
        correlation_id: UUID hex linking this brief to GTM outreach log for V2.
    """

    customer_id: str
    propensity_summary: str
    key_narrative_drivers: list[str]
    ae_tactical_brief: str
    email_draft: str | None
    guardrail_status: Literal["PASSED", "FLAGGED", "REJECTED"]
    fact_confidence: float
    generated_at: datetime
    model_used: str
    llm_provider: str
    propensity_score: float
    propensity_tier: str
    target_tier: str | None
    expected_arr_uplift: float
    correlation_id: str
