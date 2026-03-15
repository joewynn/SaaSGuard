"""FastAPI router for AI summary endpoints.

Provides two endpoints:
  - POST /summaries/customer        – generate an executive summary for a customer
  - POST /summaries/customer/ask    – answer a free-text question about a customer
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_ask_use_case, get_summary_use_case
from app.schemas.summary import (
    AskCustomerRequest,
    AskCustomerResponse,
    GenerateSummaryRequest,
    GenerateSummaryResponse,
    ShapFeatureSummary,
)
from src.application.use_cases.ask_customer_question import (
    AskCustomerRequest as DomainAskRequest,
    AskCustomerQuestionUseCase,
)
from src.application.use_cases.generate_executive_summary import (
    GenerateSummaryRequest as DomainSummaryRequest,
    GenerateExecutiveSummaryUseCase,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post(
    "/customer",
    response_model=GenerateSummaryResponse,
    summary="Generate AI executive summary for a customer",
    description=(
        "Generates a 3–5 sentence AI narrative grounded in the customer's churn prediction, "
        "SHAP feature drivers, usage events, support tickets, and GTM signals. "
        "All outputs include a guardrail confidence score and AI watermark. "
        "Audience: 'csm' (tactical briefing) or 'executive' (revenue-focused)."
    ),
)
async def generate_customer_summary(
    request: GenerateSummaryRequest,
    use_case: GenerateExecutiveSummaryUseCase = Depends(get_summary_use_case),
) -> GenerateSummaryResponse:
    """Generate an AI executive summary for a customer.

    Business Context: Replaces ~15 min of manual CSM research with a 30-second
    API call. The summary is grounded in verified DuckDB data and validated
    by GuardrailsService before being returned.
    """
    try:
        summary = use_case.execute(
            DomainSummaryRequest(
                customer_id=request.customer_id,
                audience=request.audience,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Extract prediction details stored on the summary entity
    churn_prob = 0.0
    risk_tier = "unknown"
    shap_features: list[ShapFeatureSummary] = []

    if summary.prediction is not None:
        churn_prob = summary.prediction.churn_probability.value
        risk_tier = str(summary.prediction.churn_probability.risk_tier)
        shap_features = [
            ShapFeatureSummary(
                feature=f.feature_name,
                value=f.feature_value,
                shap_impact=f.shap_impact,
            )
            for f in summary.prediction.top_shap_features
        ]

    return GenerateSummaryResponse(
        customer_id=summary.customer_id,
        audience=summary.audience,
        summary=summary.content,
        churn_probability=churn_prob,
        risk_tier=risk_tier,
        top_shap_features=shap_features,
        confidence_score=summary.guardrail.confidence_score,
        guardrail_flags=summary.guardrail.flags,
        generated_at=summary.generated_at.isoformat(),
        model_used=summary.model_used,
        llm_provider=summary.llm_provider,
    )


@router.post(
    "/customer/ask",
    response_model=AskCustomerResponse,
    summary="Ask a free-text question about a customer",
    description=(
        "Answers a free-text question about a customer using their full DuckDB history "
        "(events, tickets, opportunities, churn prediction) as context. "
        "Questions outside available data return scope_exceeded=true rather than hallucinated answers."
    ),
)
async def ask_about_customer(
    request: AskCustomerRequest,
    use_case: AskCustomerQuestionUseCase = Depends(get_ask_use_case),
) -> AskCustomerResponse:
    """Answer a free-text question about a customer.

    Business Context: CSMs can ask "Why is this customer at risk?" or
    "What support tickets are open?" and get grounded, auditable answers.
    Out-of-scope questions are caught and flagged rather than hallucinated.
    """
    try:
        response = use_case.execute(
            DomainAskRequest(
                customer_id=request.customer_id,
                question=request.question,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return AskCustomerResponse(
        customer_id=response.customer_id,
        question=response.question,
        answer=response.answer,
        confidence_score=response.confidence_score,
        guardrail_flags=response.guardrail_flags,
        scope_exceeded=response.scope_exceeded,
        generated_at=response.generated_at.isoformat(),
        model_used=response.model_used,
        llm_provider=response.llm_provider,
    )
