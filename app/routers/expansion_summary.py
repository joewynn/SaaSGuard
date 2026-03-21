"""FastAPI router for expansion narrative endpoint.

Provides:
  POST /summaries/expansion  — generate an AE tactical brief for a high-propensity
                               account, with optional 3-sentence email draft.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_expansion_summary_use_case
from app.schemas.expansion_summary import (
    ExpansionSummaryResponse,
    GenerateExpansionSummaryRequest,
)
from src.application.use_cases.generate_expansion_summary import (
    GenerateExpansionSummaryRequest as DomainRequest,
)
from src.application.use_cases.generate_expansion_summary import (
    GenerateExpansionSummaryUseCase,
    PropensityTooLowError,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post(
    "/expansion",
    response_model=ExpansionSummaryResponse,
    summary="Generate AE expansion brief for a high-propensity account",
    description=(
        "Translates a high-propensity ExpansionResult into a personalised AE tactical "
        "brief and optional outreach email, validated by a three-gate guardrail. "
        "Accounts with propensity < 0.35 return a 'not ready' message without an LLM "
        "call. Accounts with propensity < 0.15 return HTTP 422. "
        "The correlation_id in the response links this brief to expansion_outreach_log "
        "for downstream lift measurement."
    ),
)
async def generate_expansion_brief(
    request: GenerateExpansionSummaryRequest,
    use_case: GenerateExpansionSummaryUseCase = Depends(get_expansion_summary_use_case),
) -> ExpansionSummaryResponse:
    """Generate a personalised expansion brief for a high-propensity account.

    Business Context: Reduces AE prep time from ~20 minutes to 30 seconds.
    Personalisation via SHAP drivers drives 10–15% conversion lift vs generic
    outreach. The correlation_id enables V2 fine-tuning data collection.
    """
    try:
        result = use_case.execute(
            DomainRequest(
                customer_id=request.customer_id,
                audience=request.audience,
                include_email_draft=request.include_email_draft,
            )
        )
    except PropensityTooLowError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(
            "expansion_brief.error",
            customer_id=request.customer_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=503,
            detail=f"Expansion brief service error: {exc}",
        ) from exc

    return ExpansionSummaryResponse(
        customer_id=result.customer_id,
        propensity_summary=result.propensity_summary,
        propensity_score=result.propensity_score,
        propensity_tier=result.propensity_tier,
        target_tier=result.target_tier,
        expected_arr_uplift=result.expected_arr_uplift,
        key_narrative_drivers=result.key_narrative_drivers,
        ae_tactical_brief=result.ae_tactical_brief,
        email_draft=result.email_draft,
        guardrail_status=result.guardrail_status,
        fact_confidence=result.fact_confidence,
        generated_at=result.generated_at.isoformat(),
        model_used=result.model_used,
        llm_provider=result.llm_provider,
        correlation_id=result.correlation_id,
    )
