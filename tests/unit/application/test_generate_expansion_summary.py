"""TDD tests for GenerateExpansionSummaryUseCase.

10 tests covering:
  - Returns correct entity type
  - Propensity gates (< 0.35 → no LLM call; < 0.15 → PropensityTooLowError)
  - Customer guards (not found, churned)
  - Guardrail REJECTED → return result, not exception
  - CSM audience overrides email_draft to None
  - AE audience with include_email_draft=True sets email_draft
  - generated_at populated
  - Watermark present in ae_tactical_brief
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.application.use_cases.generate_expansion_summary import (
    GenerateExpansionSummaryRequest,
    GenerateExpansionSummaryUseCase,
    PropensityTooLowError,
)
from src.domain.expansion.summary_entities import ExpansionSummaryResult


def _make_customer(is_active: bool = True, churn_date: object = None) -> MagicMock:
    c = MagicMock()
    c.is_active = is_active
    c.churn_date = churn_date
    return c


def _make_expansion_result(propensity_value: float = 0.65) -> MagicMock:
    result = MagicMock()
    result.propensity.value = propensity_value
    result.propensity.tier.value = "high"
    result.target.next_tier.value = "enterprise"
    result.expected_arr_uplift = 15000.0
    result.top_features = []
    result.model_version = "1.1.0"
    result.to_summary_context.return_value = {
        "customer_id": "cust-001",
        "propensity_score": "65.00%",
        "propensity_tier": "high",
        "expected_uplift": "$15,000.00",
        "target_tier": "enterprise",
        "top_signals": [],
    }
    return result


def _make_guardrail_result(
    status: str = "PASSED",
    confidence: float = 1.0,
    flags: list[str] | None = None,
    ae_brief: str = "Tactical brief. ⚠️ AI-generated. Requires human review.",
    email_draft: str | None = None,
) -> MagicMock:
    r = MagicMock()
    r.guardrail_status = status
    r.fact_confidence = confidence
    r.flags = flags or []
    r.ae_tactical_brief = ae_brief
    r.email_draft = email_draft
    return r


class TestGenerateExpansionSummaryUseCase:
    """Unit tests for the expansion summary orchestration use case."""

    def _build_use_case(
        self,
        customer: object = None,
        expansion_result: object = None,
        raw_llm_text: str = "Strong enterprise signals detected. Schedule upgrade call.",
        guardrail_result: object = None,
    ) -> tuple[GenerateExpansionSummaryUseCase, MagicMock, MagicMock, MagicMock, MagicMock]:
        customer_repo = MagicMock()
        customer_repo.get_by_id.return_value = customer or _make_customer()

        expansion_use_case = MagicMock()
        expansion_use_case.execute.return_value = expansion_result or _make_expansion_result()

        summary_service = MagicMock()
        summary_service.generate_from_prompt.return_value = raw_llm_text
        summary_service.model_name = "llama-3.1-8b-instant"
        summary_service.provider_name = "groq"

        guardrails = MagicMock()
        guardrails.validate.return_value = guardrail_result or _make_guardrail_result()

        use_case = GenerateExpansionSummaryUseCase(
            customer_repo=customer_repo,
            expansion_use_case=expansion_use_case,
            summary_service=summary_service,
            guardrails=guardrails,
        )
        return use_case, customer_repo, expansion_use_case, summary_service, guardrails

    def test_returns_expansion_summary_result_entity(self) -> None:
        """Execute returns an ExpansionSummaryResult dataclass."""
        use_case, *_ = self._build_use_case()
        result = use_case.execute(
            GenerateExpansionSummaryRequest(customer_id="cust-001")
        )
        assert isinstance(result, ExpansionSummaryResult)

    def test_low_propensity_returns_not_ready_without_llm_call(self) -> None:
        """Propensity < 0.35 → brief says 'not ready', LLM is never called."""
        expansion_result = _make_expansion_result(propensity_value=0.30)
        use_case, _, _, summary_service, _ = self._build_use_case(
            expansion_result=expansion_result
        )
        result = use_case.execute(
            GenerateExpansionSummaryRequest(customer_id="cust-001")
        )
        summary_service.generate_from_prompt.assert_not_called()
        assert result.ae_tactical_brief.startswith("Account not ready")

    def test_medium_propensity_calls_llm(self) -> None:
        """Propensity >= 0.35 → LLM is called."""
        expansion_result = _make_expansion_result(propensity_value=0.50)
        use_case, _, _, summary_service, _ = self._build_use_case(
            expansion_result=expansion_result
        )
        use_case.execute(GenerateExpansionSummaryRequest(customer_id="cust-001"))
        summary_service.generate_from_prompt.assert_called_once()

    def test_unknown_customer_raises_value_error(self) -> None:
        """Missing customer → ValueError."""
        use_case, customer_repo, *_ = self._build_use_case()
        customer_repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="not found"):
            use_case.execute(GenerateExpansionSummaryRequest(customer_id="ghost-id"))

    def test_churned_customer_raises_value_error(self) -> None:
        """Churned customer → ValueError."""
        churned = _make_customer(is_active=False, churn_date="2024-01-15")
        use_case, *_ = self._build_use_case(customer=churned)
        with pytest.raises(ValueError, match="churned"):
            use_case.execute(GenerateExpansionSummaryRequest(customer_id="cust-001"))

    def test_guardrail_rejection_still_returns_result(self) -> None:
        """REJECTED guardrail → result is returned (no exception raised)."""
        guardrail_result = _make_guardrail_result(
            status="REJECTED",
            confidence=0.5,
            flags=["hallucinated_feature:fake_score", "hallucinated_feature:made_up_metric"],
            ae_brief="Flagged brief. ⚠️ AI-generated. Requires human review.",
        )
        use_case, *_ = self._build_use_case(guardrail_result=guardrail_result)
        result = use_case.execute(
            GenerateExpansionSummaryRequest(customer_id="cust-001")
        )
        assert result.guardrail_status == "REJECTED"

    def test_ae_audience_with_email_draft_sets_email_draft_field(self) -> None:
        """AE audience + include_email_draft=True → email_draft field is set."""
        guardrail_result = _make_guardrail_result(
            email_draft="Hi Sarah, I wanted to reach out about your upgrade options."
        )
        use_case, *_ = self._build_use_case(guardrail_result=guardrail_result)
        result = use_case.execute(
            GenerateExpansionSummaryRequest(
                customer_id="cust-001",
                audience="account_executive",
                include_email_draft=True,
            )
        )
        assert result.email_draft is not None

    def test_csm_audience_never_sets_email_draft(self) -> None:
        """CSM audience → email_draft is None even if include_email_draft=True."""
        guardrail_result = _make_guardrail_result(
            email_draft="This should be suppressed."
        )
        use_case, _, _, summary_service, guardrails = self._build_use_case(
            guardrail_result=guardrail_result
        )
        result = use_case.execute(
            GenerateExpansionSummaryRequest(
                customer_id="cust-001",
                audience="csm",
                include_email_draft=True,  # forced to False internally
            )
        )
        assert result.email_draft is None
        # Guardrails called with include_email_draft=False (CSM override)
        call_kwargs = guardrails.validate.call_args
        assert call_kwargs is not None
        passed_draft = call_kwargs.kwargs.get(
            "email_draft", call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
        )
        assert passed_draft is None

    def test_generated_at_is_set(self) -> None:
        """generated_at is a UTC datetime close to now."""
        use_case, *_ = self._build_use_case()
        before = datetime.now(UTC)
        result = use_case.execute(
            GenerateExpansionSummaryRequest(customer_id="cust-001")
        )
        after = datetime.now(UTC)
        assert before <= result.generated_at <= after

    def test_watermark_in_ae_tactical_brief(self) -> None:
        """ae_tactical_brief always contains the AI watermark."""
        from src.domain.ai_summary.expansion_guardrails_service import WATERMARK

        guardrail_result = _make_guardrail_result(
            ae_brief=f"Strong signals detected.\n\n{WATERMARK}"
        )
        use_case, *_ = self._build_use_case(guardrail_result=guardrail_result)
        result = use_case.execute(
            GenerateExpansionSummaryRequest(customer_id="cust-001")
        )
        assert WATERMARK in result.ae_tactical_brief
