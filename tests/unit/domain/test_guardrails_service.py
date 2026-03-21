"""Unit tests for GuardrailsService – validates LLM outputs before returning to callers.

TDD: these tests were written before the implementation.
"""

from __future__ import annotations

from datetime import date

from src.domain.ai_summary.entities import SummaryContext
from src.domain.ai_summary.guardrails_service import WATERMARK, GuardrailsService
from src.domain.customer.entities import Customer
from src.domain.customer.value_objects import MRR, Industry, PlanTier
from src.domain.prediction.entities import PredictionResult, ShapFeature
from src.domain.prediction.value_objects import ChurnProbability, RiskScore


def _make_context(churn_prob: float = 0.72) -> SummaryContext:
    customer = Customer(
        customer_id="cust-001",
        industry=Industry.FINTECH,
        plan_tier=PlanTier.GROWTH,
        signup_date=date(2023, 6, 1),
        mrr=MRR.from_float(4500.0),
    )
    prediction = PredictionResult(
        customer_id="cust-001",
        churn_probability=ChurnProbability(churn_prob),
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


class TestGuardrailsService:
    """Unit tests for GuardrailsService."""

    def setup_method(self) -> None:
        self.svc = GuardrailsService()

    def test_passes_clean_summary(self) -> None:
        """A well-formed summary with correct facts should pass all guardrails."""
        context = _make_context(churn_prob=0.72)
        clean_text = (
            "Customer cust-001 has a 72% churn probability driven by low events_last_30d "
            "and declining avg_adoption_score. Recommend immediate CS outreach. "
            "Revenue at risk: $54,000 ARR."
        )
        _, result = self.svc.validate(clean_text, context)
        assert result.passed is True
        assert result.flags == []
        assert result.confidence_score == 1.0

    def test_always_appends_watermark(self) -> None:
        """Watermark must be appended to ALL summaries, including clean ones."""
        context = _make_context()
        text = "Customer has 72% churn probability driven by events_last_30d."
        final, _ = self.svc.validate(text, context)
        assert WATERMARK in final

    def test_flags_hallucinated_feature(self) -> None:
        """Summary mentioning a feature not in KNOWN_FEATURES should be flagged."""
        context = _make_context(churn_prob=0.72)
        # "days_until_renewal" is NOT in KNOWN_FEATURES
        bad_text = (
            "The customer's days_until_renewal is critically low, indicating high churn. Churn probability is 72%."
        )
        _, result = self.svc.validate(bad_text, context)
        assert result.passed is False
        hallucination_flags = [f for f in result.flags if f.startswith("hallucinated_feature:")]
        assert len(hallucination_flags) >= 1

    def test_flags_wrong_probability(self) -> None:
        """Summary stating a probability >2pp off from model output should be flagged."""
        context = _make_context(churn_prob=0.45)
        bad_text = "This customer has a 78% churn probability according to the model. Immediate action needed."
        _, result = self.svc.validate(bad_text, context)
        assert result.passed is False
        assert "probability_mismatch" in result.flags

    def test_probability_within_tolerance_passes(self) -> None:
        """Probability stated within ±2pp of model should NOT be flagged."""
        context = _make_context(churn_prob=0.72)
        # 72% stated, 72% in model → exactly matches
        ok_text = "The model predicts a 72% churn probability for this customer."
        _, result = self.svc.validate(ok_text, context)
        assert "probability_mismatch" not in result.flags

    def test_confidence_score_degrades_with_flags(self) -> None:
        """Each guardrail flag should reduce confidence_score by 0.2."""
        context = _make_context(churn_prob=0.45)
        # Will flag probability_mismatch (78% vs 45%)
        bad_text = "This customer has a 78% churn probability and days_until_renewal is low."
        _, result = self.svc.validate(bad_text, context)
        assert result.confidence_score < 1.0

    def test_confidence_score_zero_on_multiple_failures(self) -> None:
        """Multiple flags should drive confidence_score toward 0."""
        context = _make_context(churn_prob=0.20)
        # 78% vs 20% = probability_mismatch + hallucinated_feature
        bad_text = (
            "This customer has a 78% churn probability. "
            "Their days_until_renewal and contract_renewal_score are critically low."
        )
        _, result = self.svc.validate(bad_text, context)
        assert result.confidence_score < 0.5
        assert result.passed is False

    def test_no_percentage_in_summary_does_not_flag_probability(self) -> None:
        """If summary contains no percentage, probability check is skipped."""
        context = _make_context(churn_prob=0.72)
        text = "This customer is at high risk. Immediate outreach recommended."
        _, result = self.svc.validate(text, context)
        assert "probability_mismatch" not in result.flags
