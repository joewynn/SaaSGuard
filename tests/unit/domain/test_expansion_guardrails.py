"""TDD tests for ExpansionGuardrailsService — three-gate LLM output validation.

13 tests covering:
  Gate 1: fact verification (hallucinated signals → REJECTED at 2+)
  Gate 2: tone calibration (strip urgency if propensity < 0.50)
  Gate 3: PII/jargon scrub on email_draft only
  Confidence scoring: 1.0 − (0.25 × n_flags), floored at 0.0
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.domain.ai_summary.expansion_guardrails_service import (
    WATERMARK,
    ExpansionGuardrailsService,
)


def _make_expansion_result(top_feature_names: list[str] | None = None) -> MagicMock:
    """Build a minimal ExpansionResult mock with the specified top feature names."""
    if top_feature_names is None:
        top_feature_names = [
            "premium_feature_trials_30d",
            "feature_request_tickets_90d",
            "mrr_tier_ceiling_pct",
        ]
    mock_result = MagicMock()
    mock_features = []
    for name in top_feature_names:
        f = MagicMock()
        f.feature_name = name
        mock_features.append(f)
    mock_result.top_features = mock_features
    return mock_result


class TestExpansionGuardrailsService:
    """Unit tests for ExpansionGuardrailsService gate logic and confidence scoring."""

    def setup_method(self) -> None:
        self.service = ExpansionGuardrailsService()

    # ── Gate 0: baseline ──────────────────────────────────────────────────────

    def test_passes_clean_response_high_propensity(self) -> None:
        """Clean brief with known signals and high propensity passes all gates."""
        result = self.service.validate(
            ae_tactical_brief=(
                "This Growth customer shows strong premium feature adoption. "
                "Schedule the Enterprise upgrade conversation this quarter."
            ),
            email_draft=None,
            expansion_result=_make_expansion_result(),
            propensity=0.72,
        )
        assert result.guardrail_status == "PASSED"
        assert result.fact_confidence == 1.0
        assert len(result.flags) == 0

    def test_always_appends_watermark_to_tactical_brief(self) -> None:
        """Watermark is appended to ae_tactical_brief regardless of gate outcome."""
        result = self.service.validate(
            ae_tactical_brief="Clean brief with no issues.",
            email_draft=None,
            expansion_result=_make_expansion_result(),
            propensity=0.65,
        )
        assert WATERMARK in result.ae_tactical_brief

    # ── Gate 1: hallucination detection ───────────────────────────────────────

    def test_gate1_rejects_hallucinated_signal(self) -> None:
        """Two or more hallucinated snake_case signals → REJECTED."""
        result = self.service.validate(
            ae_tactical_brief=("The fake_signal_one and another_made_up_signal are driving intent."),
            email_draft=None,
            expansion_result=_make_expansion_result(["premium_feature_trials_30d"]),
            propensity=0.72,
        )
        assert result.guardrail_status == "REJECTED"

    def test_gate1_single_hallucination_is_flagged_not_rejected(self) -> None:
        """Exactly one hallucinated signal → FLAGGED (not REJECTED)."""
        result = self.service.validate(
            ae_tactical_brief="The fake_signal_xyz is showing strong expansion intent.",
            email_draft=None,
            expansion_result=_make_expansion_result(["premium_feature_trials_30d"]),
            propensity=0.72,
        )
        assert result.guardrail_status == "FLAGGED"
        assert result.fact_confidence < 1.0
        assert len(result.flags) == 1

    def test_gate1_two_hallucinations_triggers_rejection(self) -> None:
        """Two distinct hallucinated signals → status is REJECTED."""
        result = self.service.validate(
            ae_tactical_brief=("Seeing high_usage_velocity_rate and increased churn_risk_indicator_score."),
            email_draft=None,
            expansion_result=_make_expansion_result([]),
            propensity=0.72,
        )
        assert result.guardrail_status == "REJECTED"

    # ── Gate 2: urgency calibration ───────────────────────────────────────────

    def test_gate2_strips_urgency_language_for_medium_propensity(self) -> None:
        """Urgency words stripped from ae_tactical_brief when propensity < 0.50."""
        result = self.service.validate(
            ae_tactical_brief=("This is critical and urgent. Immediately schedule the upgrade call."),
            email_draft=None,
            expansion_result=_make_expansion_result(),
            propensity=0.42,
        )
        body = result.ae_tactical_brief.split("\n\n" + WATERMARK)[0]
        assert "critical" not in body.lower()
        assert "urgent" not in body.lower()
        assert "immediately" not in body.lower()

    def test_gate2_does_not_strip_urgency_for_high_propensity(self) -> None:
        """Urgency words preserved when propensity >= 0.50."""
        brief = "This is critical and urgent. Immediately schedule the upgrade call."
        result = self.service.validate(
            ae_tactical_brief=brief,
            email_draft=None,
            expansion_result=_make_expansion_result(),
            propensity=0.62,
        )
        body = result.ae_tactical_brief.split("\n\n" + WATERMARK)[0]
        assert "critical" in body.lower()
        assert "urgent" in body.lower()
        assert "immediately" in body.lower()

    # ── Gate 3: PII + jargon scrub (email_draft only) ─────────────────────────

    def test_gate3_removes_uuid_from_email_draft(self) -> None:
        """UUID patterns are removed from email_draft."""
        result = self.service.validate(
            ae_tactical_brief="Solid brief here.",
            email_draft=("Dear team, customer abc12345-6789-0000-abcd-ef1234567890 is ready."),
            expansion_result=_make_expansion_result(),
            propensity=0.65,
        )
        assert result.email_draft is not None
        assert "abc12345-6789-0000-abcd-ef1234567890" not in result.email_draft

    def test_gate3_removes_technical_terms_from_email_draft(self) -> None:
        """Technical ML terms are removed from email_draft."""
        result = self.service.validate(
            ae_tactical_brief="Solid brief here.",
            email_draft=("Our xgboost model and shap analysis indicate high propensity_score."),
            expansion_result=_make_expansion_result(),
            propensity=0.65,
        )
        assert result.email_draft is not None
        assert "xgboost" not in result.email_draft
        assert "shap" not in result.email_draft
        assert "propensity_score" not in result.email_draft

    def test_gate3_does_not_scrub_ae_tactical_brief(self) -> None:
        """Gate 3 scrubs email_draft only — ae_tactical_brief is not modified by it."""
        result = self.service.validate(
            ae_tactical_brief="Based on xgboost signals this account is ready to upgrade.",
            email_draft=None,
            expansion_result=_make_expansion_result(),
            propensity=0.65,
        )
        # "xgboost" is not snake_case so Gate 1 won't flag it either;
        # Gate 3 only touches email_draft, so it must remain in ae_tactical_brief.
        assert "xgboost" in result.ae_tactical_brief

    def test_no_email_draft_when_none(self) -> None:
        """email_draft=None passes through unchanged."""
        result = self.service.validate(
            ae_tactical_brief="Brief text here.",
            email_draft=None,
            expansion_result=_make_expansion_result(),
            propensity=0.65,
        )
        assert result.email_draft is None

    # ── Confidence scoring ────────────────────────────────────────────────────

    def test_confidence_degrades_0_25_per_flag(self) -> None:
        """Each Gate 1 flag reduces fact_confidence by 0.25."""
        result = self.service.validate(
            ae_tactical_brief="The fake_signal_xyz is showing strong intent.",
            email_draft=None,
            expansion_result=_make_expansion_result(["premium_feature_trials_30d"]),
            propensity=0.72,
        )
        # 1 flag → 1.0 − 0.25 = 0.75
        assert result.fact_confidence == pytest.approx(0.75, abs=0.001)

    def test_confidence_floored_at_zero(self) -> None:
        """fact_confidence never goes below 0.0, even with many flags."""
        result = self.service.validate(
            ae_tactical_brief=(
                "fake_signal_alpha and fake_signal_beta and fake_signal_gamma "
                "and fake_signal_delta and fake_signal_epsilon driving this score."
            ),
            email_draft=None,
            expansion_result=_make_expansion_result([]),
            propensity=0.72,
        )
        assert result.fact_confidence == 0.0
