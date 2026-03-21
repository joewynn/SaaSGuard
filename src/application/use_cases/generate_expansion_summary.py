"""GenerateExpansionSummaryUseCase — orchestrates the expansion narrative pipeline.

Translates a high-propensity ExpansionResult into an AE tactical brief and
optional email draft, validated by ExpansionGuardrailsService before returning.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

import structlog

from src.application.use_cases.predict_expansion import (
    PredictExpansionRequest,
    PredictExpansionUseCase,
)
from src.domain.ai_summary.expansion_guardrails_service import (
    ExpansionGuardrailResult,
    ExpansionGuardrailsService,
)
from src.domain.ai_summary.guardrails_service import WATERMARK
from src.domain.ai_summary.summary_port import SummaryPort
from src.domain.customer.repository import CustomerRepository
from src.domain.expansion.entities import ExpansionResult
from src.domain.expansion.summary_entities import ExpansionSummaryResult
from src.infrastructure.llm.prompt_builder import _FEATURE_LABELS, PromptBuilder

logger = structlog.get_logger(__name__)

# Below this propensity the API returns HTTP 422 (use case raises PropensityTooLowError).
_MIN_PROPENSITY_FOR_API: float = 0.15

# Below this propensity the LLM is not called; a "not ready" message is returned.
_MIN_PROPENSITY_FOR_LLM: float = 0.35


class PropensityTooLowError(ValueError):
    """Raised when propensity is below the API-layer minimum threshold (0.15).

    Business Context: Accounts with propensity < 0.15 are not expansion candidates.
    Calling the LLM for these accounts wastes tokens and produces misleading briefs.
    The API layer maps this to HTTP 422 so callers know the account is not ready.
    """


@dataclass
class GenerateExpansionSummaryRequest:
    """Input DTO for GenerateExpansionSummaryUseCase.

    Args:
        customer_id: UUID of the active customer to generate a brief for.
        audience: 'account_executive' (tactical brief + optional email) or
                  'csm' (nurture brief only; email_draft forced to None).
        include_email_draft: If True and audience is 'account_executive',
                             the response will include a 3-sentence email draft.
    """

    customer_id: str
    audience: Literal["account_executive", "csm"] = field(
        default="account_executive"
    )
    include_email_draft: bool = False


class GenerateExpansionSummaryUseCase:
    """Generates a personalised AE brief grounded in the expansion propensity model.

    Business Context: Reduces AE prep time from ~20 minutes to 30 seconds.
    Personalisation via SHAP signals drives 10–15% conversion lift vs generic
    outreach. The correlation_id in each result enables the data team to join
    brief quality (fact_confidence) to close rates in the V2 fine-tuning flywheel.

    Pipeline:
      1. Fetch Customer entity (raises ValueError if not found / churned)
      2. Run PredictExpansionUseCase → ExpansionResult
      3. Propensity < 0.15 → raise PropensityTooLowError (API → 422)
      4. Propensity < 0.35 → return "not ready" result without LLM call
      5. CSM audience override: force include_email_draft=False
      6. Build expansion prompt via PromptBuilder
      7. Call LLM via SummaryPort.generate_from_prompt()
      8. Validate + transform via ExpansionGuardrailsService
      9. Return ExpansionSummaryResult

    Args:
        customer_repo: Repository for fetching Customer entities.
        expansion_use_case: PredictExpansionUseCase for propensity + SHAP.
        summary_service: SummaryPort implementation (Groq or Ollama).
        guardrails: ExpansionGuardrailsService for validation + watermark.
    """

    def __init__(
        self,
        customer_repo: CustomerRepository,
        expansion_use_case: PredictExpansionUseCase,
        summary_service: SummaryPort,
        guardrails: ExpansionGuardrailsService,
    ) -> None:
        self._customer_repo = customer_repo
        self._expansion_use_case = expansion_use_case
        self._summary_service = summary_service
        self._guardrails = guardrails
        self._prompt_builder = PromptBuilder()

    def execute(self, request: GenerateExpansionSummaryRequest) -> ExpansionSummaryResult:
        """Run the full expansion narrative pipeline for a single customer.

        Business Context: All LLM calls are grounded in verified model outputs
        (ExpansionResult SHAP features). The guardrail layer ensures hallucinated
        signals are caught before the brief reaches an AE's CRM.

        Args:
            request: Contains customer_id, audience, and email draft flag.

        Returns:
            ExpansionSummaryResult with brief, guardrail result, and provenance.

        Raises:
            ValueError: If the customer is not found or has already churned.
            PropensityTooLowError: If propensity < 0.15 (API maps this to 422).
        """
        log = logger.bind(
            customer_id=request.customer_id,
            audience=request.audience,
        )
        log.info("expansion_summary.generate.start")

        # Step 1 — fetch customer
        customer = self._customer_repo.get_by_id(request.customer_id)
        if customer is None:
            raise ValueError(f"Customer {request.customer_id} not found.")
        if not customer.is_active:
            raise ValueError(
                f"Customer {request.customer_id} has already churned on {customer.churn_date}."
            )

        # Step 2 — run expansion prediction
        expansion_result = self._expansion_use_case.execute(
            PredictExpansionRequest(customer_id=request.customer_id)
        )
        propensity = expansion_result.propensity.value

        # Step 3 — API-layer propensity gate
        if propensity < _MIN_PROPENSITY_FOR_API:
            raise PropensityTooLowError(
                f"Propensity {propensity:.2f} is below minimum threshold "
                f"{_MIN_PROPENSITY_FOR_API} for expansion brief generation."
            )

        correlation_id = uuid.uuid4().hex

        # Step 4 — LLM propensity gate: return "not ready" without calling the LLM
        if propensity < _MIN_PROPENSITY_FOR_LLM:
            log.info(
                "expansion_summary.not_ready",
                propensity=propensity,
                threshold=_MIN_PROPENSITY_FOR_LLM,
            )
            return self._not_ready_result(expansion_result, correlation_id)

        # Step 5 — CSM audience override: suppress email draft
        include_draft = request.include_email_draft
        if request.audience == "csm":
            if include_draft:
                log.warning(
                    "expansion_summary.csm_email_suppressed",
                    hint="email_draft is not available for csm audience",
                )
            include_draft = False

        # Step 6 — build expansion prompt
        prompt = self._prompt_builder.build_expansion_prompt(
            expansion_result=expansion_result,
            audience=request.audience,
            include_email_draft=include_draft,
        )

        # Step 7 — call LLM
        raw_text = self._summary_service.generate_from_prompt(prompt)
        log.info("expansion_summary.llm.response_received", length=len(raw_text))

        # Step 8 — parse email draft from LLM output (if requested)
        ae_brief_raw, email_draft_raw = self._split_llm_output(
            raw_text, include_draft
        )

        # Step 9 — validate + transform via guardrails
        guardrail_result = self._guardrails.validate(
            ae_tactical_brief=ae_brief_raw,
            email_draft=email_draft_raw,
            expansion_result=expansion_result,
            propensity=propensity,
        )
        if guardrail_result.guardrail_status != "PASSED":
            log.warning(
                "expansion_summary.guardrail.flags",
                status=guardrail_result.guardrail_status,
                flags=guardrail_result.flags,
                confidence=guardrail_result.fact_confidence,
            )

        return self._build_result(
            request=request,
            expansion_result=expansion_result,
            guardrail_result=guardrail_result,
            correlation_id=correlation_id,
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _not_ready_result(
        self, expansion_result: ExpansionResult, correlation_id: str
    ) -> ExpansionSummaryResult:
        """Return a 'not ready' result without invoking the LLM."""
        propensity = expansion_result.propensity.value
        tier = str(expansion_result.propensity.tier.value)
        target = (
            expansion_result.target.next_tier.value
            if expansion_result.target.next_tier
            else "N/A"
        )
        return ExpansionSummaryResult(
            customer_id=expansion_result.customer_id,
            propensity_summary=(
                f"Account not ready for outreach — propensity {propensity:.0%} "
                f"is below the {_MIN_PROPENSITY_FOR_LLM:.0%} threshold."
            ),
            key_narrative_drivers=[],
            ae_tactical_brief=(
                f"Account not ready for outreach. "
                f"Propensity {propensity:.0%} ({tier}) is below the activation "
                f"threshold. Monitor for rising usage signals before scheduling "
                f"an upgrade conversation toward {target}.\n\n{WATERMARK}"
            ),
            email_draft=None,
            guardrail_status="PASSED",
            fact_confidence=1.0,
            generated_at=datetime.now(UTC),
            model_used=self._summary_service.model_name,
            llm_provider=self._summary_service.provider_name,
            propensity_score=propensity,
            propensity_tier=tier,
            target_tier=target if target != "N/A" else None,
            expected_arr_uplift=expansion_result.expected_arr_uplift,
            correlation_id=correlation_id,
        )

    def _split_llm_output(
        self, raw_text: str, include_draft: bool
    ) -> tuple[str, str | None]:
        """Split LLM output into ae_brief and optional email_draft.

        The prompt instructs the LLM to label the email section as [EMAIL_DRAFT]:
        when include_email_draft=True. If the section is absent, email_draft is None.
        """
        if not include_draft or "[EMAIL_DRAFT]" not in raw_text:
            return raw_text.strip(), None

        parts = raw_text.split("[EMAIL_DRAFT]", maxsplit=1)
        ae_brief = parts[0].strip()
        email_draft = parts[1].strip() if len(parts) > 1 else None
        return ae_brief, email_draft

    def _build_result(
        self,
        request: GenerateExpansionSummaryRequest,
        expansion_result: ExpansionResult,
        guardrail_result: ExpansionGuardrailResult,
        correlation_id: str,
    ) -> ExpansionSummaryResult:
        """Assemble the final ExpansionSummaryResult from pipeline outputs."""
        propensity = expansion_result.propensity.value
        tier = str(expansion_result.propensity.tier.value)
        target = (
            expansion_result.target.next_tier.value
            if expansion_result.target.next_tier
            else None
        )

        key_drivers = [
            _FEATURE_LABELS.get(f.feature_name, f.feature_name)
            for f in expansion_result.top_features[:3]
        ]

        propensity_summary = (
            f"This account has {tier.upper()} expansion propensity "
            f"({propensity:.0%}) toward {target or 'the next tier'}. "
            f"Expected ARR uplift: ${expansion_result.expected_arr_uplift:,.0f}."
        )

        # CSM audience never includes an email draft — enforce at result level.
        email_draft = (
            guardrail_result.email_draft
            if request.audience == "account_executive"
            else None
        )

        return ExpansionSummaryResult(
            customer_id=request.customer_id,
            propensity_summary=propensity_summary,
            key_narrative_drivers=key_drivers,
            ae_tactical_brief=guardrail_result.ae_tactical_brief,
            email_draft=email_draft,
            guardrail_status=guardrail_result.guardrail_status,
            fact_confidence=guardrail_result.fact_confidence,
            generated_at=datetime.now(UTC),
            model_used=self._summary_service.model_name,
            llm_provider=self._summary_service.provider_name,
            propensity_score=propensity,
            propensity_tier=tier,
            target_tier=target,
            expected_arr_uplift=expansion_result.expected_arr_uplift,
            correlation_id=correlation_id,
        )
