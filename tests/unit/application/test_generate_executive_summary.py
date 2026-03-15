"""Unit tests for GenerateExecutiveSummaryUseCase – mocks LLM backend.

TDD: these tests were written before the implementation.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from src.application.use_cases.generate_executive_summary import (
    GenerateExecutiveSummaryUseCase,
    GenerateSummaryRequest,
)
from src.domain.ai_summary.entities import ExecutiveSummary
from src.domain.ai_summary.guardrails_service import WATERMARK, GuardrailsService
from src.domain.ai_summary.summary_port import SummaryPort
from src.domain.customer.entities import Customer
from src.domain.customer.repository import CustomerRepository
from src.domain.customer.value_objects import MRR, Industry, PlanTier
from src.domain.prediction.entities import PredictionResult, ShapFeature
from src.domain.prediction.value_objects import ChurnProbability, RiskScore
from src.domain.usage.repository import UsageRepository


def _make_customer(customer_id: str = "cust-001") -> Customer:
    return Customer(
        customer_id=customer_id,
        industry=Industry.FINTECH,
        plan_tier=PlanTier.GROWTH,
        signup_date=date(2023, 6, 1),
        mrr=MRR.from_float(4500.0),
    )


def _make_prediction(customer_id: str = "cust-001", prob: float = 0.72) -> PredictionResult:
    return PredictionResult(
        customer_id=customer_id,
        churn_probability=ChurnProbability(prob),
        risk_score=RiskScore(0.65),
        top_shap_features=[
            ShapFeature("events_last_30d", 3.0, 0.42),
            ShapFeature("avg_adoption_score", 0.21, 0.31),
            ShapFeature("mrr", 4500.0, 0.18),
        ],
    )


def _make_use_case(
    customer: Customer | None = None,
    prediction: PredictionResult | None = None,
    llm_response: str = "Customer is at 72% churn risk driven by events_last_30d.",
) -> GenerateExecutiveSummaryUseCase:
    cust = customer or _make_customer()
    pred = prediction or _make_prediction()

    customer_repo = MagicMock(spec=CustomerRepository)
    customer_repo.get_by_id.return_value = cust

    predict_use_case = MagicMock()
    predict_use_case.execute.return_value = pred

    usage_repo = MagicMock(spec=UsageRepository)
    usage_repo.get_events_for_customer.return_value = []

    summary_service = MagicMock(spec=SummaryPort)
    summary_service.generate.return_value = llm_response
    summary_service.model_name = "llama-3.1-8b-instant"
    summary_service.provider_name = "groq"

    guardrails = GuardrailsService()

    return GenerateExecutiveSummaryUseCase(
        customer_repo=customer_repo,
        predict_use_case=predict_use_case,
        usage_repo=usage_repo,
        summary_service=summary_service,
        guardrails=guardrails,
    )


class TestGenerateExecutiveSummaryUseCase:
    """Unit tests for GenerateExecutiveSummaryUseCase with mocked LLM."""

    def test_returns_executive_summary_entity(self) -> None:
        """Use case should return a fully populated ExecutiveSummary."""
        uc = _make_use_case()
        result = uc.execute(GenerateSummaryRequest(customer_id="cust-001", audience="csm"))

        assert isinstance(result, ExecutiveSummary)
        assert result.customer_id == "cust-001"
        assert result.audience == "csm"
        assert result.content
        assert result.model_used == "llama-3.1-8b-instant"
        assert result.llm_provider == "groq"

    def test_csm_audience_summary_contains_watermark(self) -> None:
        """CSM summary must always include the AI watermark."""
        uc = _make_use_case()
        result = uc.execute(GenerateSummaryRequest(customer_id="cust-001", audience="csm"))
        assert WATERMARK in result.content

    def test_executive_audience_summary_contains_watermark(self) -> None:
        """Executive summary must also include the AI watermark."""
        uc = _make_use_case()
        result = uc.execute(GenerateSummaryRequest(customer_id="cust-001", audience="executive"))
        assert WATERMARK in result.content

    def test_unknown_customer_raises_value_error(self) -> None:
        """CustomerRepository returning None should cause ValueError to propagate."""
        uc = _make_use_case()
        uc._customer_repo.get_by_id.return_value = None  # type: ignore[attr-defined]

        with pytest.raises(ValueError, match="not found"):
            uc.execute(GenerateSummaryRequest(customer_id="ghost-999", audience="csm"))

    def test_guardrail_failure_still_returns_with_flags(self) -> None:
        """Guardrail failure should not raise — returns summary with flags set."""
        # LLM gives a wrong probability (actual is 0.72, states 99%)
        uc = _make_use_case(llm_response="This customer has a 99% churn probability.")
        result = uc.execute(GenerateSummaryRequest(customer_id="cust-001", audience="csm"))

        assert isinstance(result, ExecutiveSummary)
        assert result.guardrail.passed is False
        assert "probability_mismatch" in result.guardrail.flags

    def test_guardrail_passed_on_clean_response(self) -> None:
        """A factually grounded LLM response should pass guardrails."""
        uc = _make_use_case(
            llm_response=(
                "Customer cust-001 has a 72% churn probability driven by low events_last_30d. "
                "Recommend CS outreach within 48 hours. Revenue at risk: $54,000 ARR."
            )
        )
        result = uc.execute(GenerateSummaryRequest(customer_id="cust-001", audience="csm"))
        assert result.guardrail.passed is True

    def test_summary_generated_at_is_set(self) -> None:
        """generated_at field must be populated."""
        uc = _make_use_case()
        result = uc.execute(GenerateSummaryRequest(customer_id="cust-001", audience="csm"))
        assert result.generated_at is not None
