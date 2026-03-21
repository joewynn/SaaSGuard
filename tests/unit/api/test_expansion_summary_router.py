"""TDD tests for expansion summary router — POST /summaries/expansion.

9 tests covering:
  - Request/response schema validation
  - Very low propensity → HTTP 422
  - Unknown customer → HTTP 404
  - LLM error → HTTP 503
  - email_draft presence/absence based on request flags
  - guardrail_status in response
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.schemas.expansion_summary import (
    ExpansionSummaryResponse,
    GenerateExpansionSummaryRequest,
)


class TestExpansionSummarySchemas:
    """Schema-level tests — no HTTP round-trip required."""

    def test_request_schema_valid_account_executive_audience(self) -> None:
        req = GenerateExpansionSummaryRequest(
            customer_id="cust-001",
            audience="account_executive",
            include_email_draft=True,
        )
        assert req.customer_id == "cust-001"
        assert req.audience == "account_executive"
        assert req.include_email_draft is True

    def test_request_schema_valid_csm_audience(self) -> None:
        req = GenerateExpansionSummaryRequest(
            customer_id="cust-002",
            audience="csm",
        )
        assert req.audience == "csm"
        assert req.include_email_draft is False  # default

    def test_response_schema_has_all_required_fields(self) -> None:
        resp = ExpansionSummaryResponse(
            customer_id="cust-001",
            propensity_summary="This Growth customer has HIGH expansion propensity (65%).",
            propensity_score=0.65,
            propensity_tier="high",
            target_tier="enterprise",
            expected_arr_uplift=15000.0,
            key_narrative_drivers=["Premium feature adoption", "Feature requests"],
            ae_tactical_brief="Schedule upgrade call this quarter. ⚠️ AI-generated. Requires human review.",
            email_draft=None,
            guardrail_status="PASSED",
            fact_confidence=1.0,
            generated_at="2026-03-21T10:00:00+00:00",
            model_used="llama-3.1-8b-instant",
            llm_provider="groq",
            correlation_id="abc123def456",
        )
        assert resp.guardrail_status == "PASSED"
        assert resp.fact_confidence == 1.0
        assert resp.correlation_id == "abc123def456"


def _make_use_case_result(
    propensity_score: float = 0.65,
    guardrail_status: str = "PASSED",
    email_draft: str | None = None,
) -> MagicMock:
    """Build a mock ExpansionSummaryResult."""
    from src.domain.ai_summary.expansion_guardrails_service import WATERMARK

    result = MagicMock()
    result.customer_id = "cust-001"
    result.propensity_summary = "HIGH expansion propensity (65%)."
    result.propensity_score = propensity_score
    result.propensity_tier = "high"
    result.target_tier = "enterprise"
    result.expected_arr_uplift = 15000.0
    result.key_narrative_drivers = ["Premium feature adoption"]
    result.ae_tactical_brief = f"Schedule upgrade.\n\n{WATERMARK}"
    result.email_draft = email_draft
    result.guardrail_status = guardrail_status
    result.fact_confidence = 1.0
    result.generated_at = datetime(2026, 3, 21, 10, 0, 0, tzinfo=UTC)
    result.model_used = "llama-3.1-8b-instant"
    result.llm_provider = "groq"
    result.correlation_id = "abc123def456"
    return result


class TestExpansionSummaryRouter:
    """HTTP-level tests using FastAPI TestClient."""

    @pytest.fixture()
    def client(self) -> TestClient:
        from app.dependencies import get_expansion_summary_use_case
        from app.main import app

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = _make_use_case_result()

        app.dependency_overrides[get_expansion_summary_use_case] = lambda: mock_use_case
        yield TestClient(app)
        app.dependency_overrides.clear()

    def test_very_low_propensity_returns_422(self) -> None:
        """Propensity < 0.15 → HTTP 422 Unprocessable Entity."""
        from app.dependencies import get_expansion_summary_use_case
        from app.main import app
        from src.application.use_cases.generate_expansion_summary import (
            PropensityTooLowError,
        )

        mock_use_case = MagicMock()
        mock_use_case.execute.side_effect = PropensityTooLowError("Propensity 0.10 below minimum threshold 0.15")
        app.dependency_overrides[get_expansion_summary_use_case] = lambda: mock_use_case
        client = TestClient(app)
        response = client.post(
            "/summaries/expansion",
            json={"customer_id": "low-prop-id"},
        )
        app.dependency_overrides.clear()
        assert response.status_code == 422

    def test_unknown_customer_returns_404(self) -> None:
        """Unknown customer → HTTP 404."""
        from app.dependencies import get_expansion_summary_use_case
        from app.main import app

        mock_use_case = MagicMock()
        mock_use_case.execute.side_effect = ValueError("Customer ghost-id not found.")
        app.dependency_overrides[get_expansion_summary_use_case] = lambda: mock_use_case
        client = TestClient(app)
        response = client.post(
            "/summaries/expansion",
            json={"customer_id": "ghost-id"},
        )
        app.dependency_overrides.clear()
        assert response.status_code == 404

    def test_llm_error_returns_503(self) -> None:
        """LLM backend failure → HTTP 503."""
        from app.dependencies import get_expansion_summary_use_case
        from app.main import app

        mock_use_case = MagicMock()
        mock_use_case.execute.side_effect = RuntimeError("Groq API error: connection refused")
        app.dependency_overrides[get_expansion_summary_use_case] = lambda: mock_use_case
        client = TestClient(app)
        response = client.post(
            "/summaries/expansion",
            json={"customer_id": "cust-001"},
        )
        app.dependency_overrides.clear()
        assert response.status_code == 503

    def test_email_draft_absent_when_not_requested(self, client: TestClient) -> None:
        """email_draft is null in response when include_email_draft=False."""
        response = client.post(
            "/summaries/expansion",
            json={"customer_id": "cust-001", "include_email_draft": False},
        )
        assert response.status_code == 200
        assert response.json()["email_draft"] is None

    def test_email_draft_present_when_requested_with_ae_audience(self) -> None:
        """email_draft is set when include_email_draft=True and audience=account_executive."""
        from app.dependencies import get_expansion_summary_use_case
        from app.main import app

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = _make_use_case_result(
            email_draft="Hi Sarah, your account is ready for an upgrade."
        )
        app.dependency_overrides[get_expansion_summary_use_case] = lambda: mock_use_case
        client = TestClient(app)
        response = client.post(
            "/summaries/expansion",
            json={
                "customer_id": "cust-001",
                "audience": "account_executive",
                "include_email_draft": True,
            },
        )
        app.dependency_overrides.clear()
        assert response.status_code == 200
        assert response.json()["email_draft"] is not None

    def test_guardrail_status_present_in_response(self, client: TestClient) -> None:
        """guardrail_status field is present in every response."""
        response = client.post(
            "/summaries/expansion",
            json={"customer_id": "cust-001"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "guardrail_status" in data
        assert data["guardrail_status"] in ("PASSED", "FLAGGED", "REJECTED")
