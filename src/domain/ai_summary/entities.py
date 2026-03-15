"""AI Summary domain entities.

Defines the core data structures for the AI/LLM layer:
- SummaryContext: all facts retrieved from DuckDB that ground the LLM prompt
- GuardrailResult: outcome of the hallucination + fact-grounding validation pass
- ExecutiveSummary: the final entity returned by the use case, with full audit trail
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.customer.entities import Customer
from src.domain.prediction.entities import PredictionResult


@dataclass
class SummaryContext:
    """All structured facts retrieved from DuckDB that will ground the LLM prompt.

    Business Context: This is the "retrieval" step of our RAG strategy.
    A single B2B customer's full history fits comfortably in Llama-3's 128k
    context window, so we use context-stuffing rather than a vector database.
    The LLM is explicitly constrained to only reference facts present here.

    Args:
        customer: The Customer entity with profile and MRR data.
        prediction: The PredictionResult including churn probability and SHAP features.
        events_last_30d_by_type: Count of usage events by type in the last 30 days.
        open_tickets: List of open support tickets with priority, topic, and age.
        gtm_opportunity: Active GTM opportunity dict (stage, amount) if one exists.
        cohort_churn_rate: Churn rate for customers in the same tier + industry cohort.
    """

    customer: Customer
    prediction: PredictionResult
    events_last_30d_by_type: dict[str, int]
    open_tickets: list[dict[str, object]]
    gtm_opportunity: dict[str, object] | None
    cohort_churn_rate: float


@dataclass(frozen=True)
class GuardrailResult:
    """Outcome of the GuardrailsService validation pass.

    Business Context: All LLM outputs must pass a validation layer before
    reaching CS teams or executives. A flawed summary (wrong probability,
    hallucinated feature) could trigger the wrong CS action or damage trust.

    Args:
        passed: True if all checks passed.
        flags: List of specific violations detected (e.g. 'probability_mismatch').
        confidence_score: 1.0 if fully clean; decreases 0.2 per flag. Minimum 0.0.
    """

    passed: bool
    flags: list[str]
    confidence_score: float


@dataclass
class ExecutiveSummary:
    """The final output entity of the AI Summary bounded context.

    Contains the LLM-generated narrative, guardrail validation result,
    and full provenance metadata for audit and human review.

    Business Context: CSMs use this for pre-meeting prep (~30 sec vs 15 min
    manual writing). Executives use it for portfolio risk reviews. The
    guardrail result and watermark ensure human-in-the-loop accountability.

    Args:
        customer_id: UUID of the customer this summary is about.
        audience: Target audience — 'csm' (tactical) or 'executive' (strategic).
        content: LLM-generated narrative with guardrail watermark appended.
        guardrail: Validation result including flags and confidence score.
        generated_at: UTC timestamp of when the summary was created.
        model_used: Name of the LLM model used (e.g. 'llama-3.1-8b-instant').
        llm_provider: Inference provider — 'groq' or 'ollama'.
    """

    customer_id: str
    audience: str
    content: str
    guardrail: GuardrailResult
    generated_at: datetime
    model_used: str
    llm_provider: str
    prediction: PredictionResult | None = None
