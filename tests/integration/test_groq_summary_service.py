"""Integration tests for GroqSummaryService – skipped if no GROQ_API_KEY.

TDD: these tests were written before the implementation.
Requires: GROQ_API_KEY environment variable to be set.
"""

from __future__ import annotations

import os
from datetime import date

import pytest

from src.domain.ai_summary.entities import SummaryContext
from src.domain.customer.entities import Customer
from src.domain.customer.value_objects import MRR, Industry, PlanTier
from src.domain.prediction.entities import PredictionResult, ShapFeature
from src.domain.prediction.value_objects import ChurnProbability, RiskScore

pytestmark = pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="No GROQ_API_KEY set — skipping Groq integration tests",
)


@pytest.fixture()
def sample_context() -> SummaryContext:
    customer = Customer(
        customer_id="integration-test-001",
        industry=Industry.FINTECH,
        plan_tier=PlanTier.GROWTH,
        signup_date=date(2023, 6, 1),
        mrr=MRR.from_float(4500.0),
    )
    prediction = PredictionResult(
        customer_id="integration-test-001",
        churn_probability=ChurnProbability(0.72),
        risk_score=RiskScore(0.65),
        top_shap_features=[
            ShapFeature("events_last_30d", 3.0, 0.42),
            ShapFeature("avg_adoption_score", 0.21, 0.31),
        ],
    )
    return SummaryContext(
        customer=customer,
        prediction=prediction,
        events_last_30d_by_type={"monitoring_run": 3, "report_view": 1},
        open_tickets=[{"priority": "high", "topic": "integration", "age_days": 12}],
        gtm_opportunity=None,
        cohort_churn_rate=0.18,
    )


@pytest.fixture()
def groq_service() -> GroqSummaryService:  # noqa: F821
    from src.infrastructure.llm.groq_summary_service import GroqSummaryService

    api_key = os.environ["GROQ_API_KEY"]
    return GroqSummaryService(api_key=api_key)


def test_real_groq_call_returns_non_empty_summary(
    groq_service: GroqSummaryService,  # noqa: F821
    sample_context: SummaryContext,
) -> None:
    """Groq API should return a non-empty string for a valid context."""
    result = groq_service.generate(sample_context, audience="csm")
    assert isinstance(result, str)
    assert len(result.strip()) > 50


def test_groq_response_is_grounded_in_context(
    groq_service: GroqSummaryService,  # noqa: F821
    sample_context: SummaryContext,
) -> None:
    """Groq response should reference facts from the context (customer_id or feature names)."""
    result = groq_service.generate(sample_context, audience="csm")
    # At least one of the top SHAP features should appear in the output
    known_facts = ["events_last_30d", "avg_adoption_score", "fintech", "growth", "4500"]
    lower_result = result.lower()
    assert any(fact.lower() in lower_result for fact in known_facts), (
        f"Response appears ungrounded. Got: {result[:200]}"
    )


def test_groq_provider_and_model_names(
    groq_service: GroqSummaryService,  # noqa: F821
) -> None:
    """GroqSummaryService should report correct provider and model names."""
    assert groq_service.provider_name == "groq"
    assert "llama" in groq_service.model_name.lower()
