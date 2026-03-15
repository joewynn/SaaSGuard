"""E2E tests for /summaries endpoints – uses TestClient with overridden dependencies.

TDD: these tests were written before the implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_ask_use_case, get_summary_use_case
from app.main import app
from src.domain.ai_summary.entities import ExecutiveSummary, GuardrailResult
from src.domain.ai_summary.guardrails_service import WATERMARK

MOCK_SUMMARY = ExecutiveSummary(
    customer_id="cust-e2e-001",
    audience="csm",
    content=(
        "Customer cust-e2e-001 has a 72% churn probability driven by low events_last_30d. "
        "Recommend CS outreach within 48 hours.\n\n" + WATERMARK
    ),
    guardrail=GuardrailResult(passed=True, flags=[], confidence_score=1.0),
    generated_at=datetime(2026, 3, 14, 12, 0, 0, tzinfo=UTC),
    model_used="llama-3.1-8b-instant",
    llm_provider="groq",
)


def _make_ask_response_dict() -> dict[str, object]:
    return {
        "customer_id": "cust-e2e-001",
        "question": "Why is this customer at risk?",
        "answer": "Based on available data, low product engagement (events_last_30d=3) is the primary driver.\n\n" + WATERMARK,
        "confidence_score": 1.0,
        "guardrail_flags": [],
        "scope_exceeded": False,
        "generated_at": "2026-03-14T12:00:00+00:00",
        "model_used": "llama-3.1-8b-instant",
        "llm_provider": "groq",
    }


@pytest.fixture()
def client() -> TestClient:
    """TestClient with clean dependency overrides reset after each test."""
    return TestClient(app)


class TestSummaryEndpoints:
    """E2E tests for POST /summaries/customer and POST /summaries/customer/ask."""

    def setup_method(self) -> None:
        """Clear any leftover dependency overrides before each test."""
        app.dependency_overrides.clear()

    def teardown_method(self) -> None:
        """Clean up dependency overrides after each test."""
        app.dependency_overrides.clear()

    def test_post_summaries_customer_returns_200(self, client: TestClient) -> None:
        """POST /summaries/customer should return 200 with mocked use case."""
        mock_uc = MagicMock()
        mock_uc.execute.return_value = MOCK_SUMMARY
        app.dependency_overrides[get_summary_use_case] = lambda: mock_uc

        response = client.post(
            "/summaries/customer",
            json={"customer_id": "cust-e2e-001", "audience": "csm"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["customer_id"] == "cust-e2e-001"
        assert data["audience"] == "csm"

    def test_post_summaries_customer_ask_returns_answer(self, client: TestClient) -> None:
        """POST /summaries/customer/ask should return 200 with answer."""
        from datetime import datetime

        from src.application.use_cases.ask_customer_question import AskCustomerResponse

        ask_resp = AskCustomerResponse(
            customer_id="cust-e2e-001",
            question="Why is this customer at risk?",
            answer="Based on available data, low events_last_30d is the primary driver.\n\n" + WATERMARK,
            confidence_score=1.0,
            guardrail_flags=[],
            scope_exceeded=False,
            generated_at=datetime(2026, 3, 14, 12, 0, 0, tzinfo=UTC),
            model_used="llama-3.1-8b-instant",
            llm_provider="groq",
        )
        mock_uc = MagicMock()
        mock_uc.execute.return_value = ask_resp
        app.dependency_overrides[get_ask_use_case] = lambda: mock_uc

        response = client.post(
            "/summaries/customer/ask",
            json={
                "customer_id": "cust-e2e-001",
                "question": "Why is this customer at risk?",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert data["customer_id"] == "cust-e2e-001"

    def test_post_summaries_missing_customer_returns_404(self, client: TestClient) -> None:
        """POST /summaries/customer with unknown customer_id should return 404."""
        mock_uc = MagicMock()
        mock_uc.execute.side_effect = ValueError("Customer ghost-999 not found.")
        app.dependency_overrides[get_summary_use_case] = lambda: mock_uc

        response = client.post(
            "/summaries/customer",
            json={"customer_id": "ghost-999", "audience": "csm"},
        )

        assert response.status_code == 404

    def test_response_contains_watermark(self, client: TestClient) -> None:
        """The summary content must always include the AI watermark."""
        mock_uc = MagicMock()
        mock_uc.execute.return_value = MOCK_SUMMARY
        app.dependency_overrides[get_summary_use_case] = lambda: mock_uc

        response = client.post(
            "/summaries/customer",
            json={"customer_id": "cust-e2e-001", "audience": "executive"},
        )

        assert response.status_code == 200
        data = response.json()
        assert WATERMARK in data["summary"]

    def test_audience_validation_rejects_invalid_value(self, client: TestClient) -> None:
        """Audience must be 'csm' or 'executive' — other values should return 422."""
        response = client.post(
            "/summaries/customer",
            json={"customer_id": "cust-001", "audience": "analyst"},
        )
        assert response.status_code == 422

    def test_ask_question_too_short_returns_422(self, client: TestClient) -> None:
        """Question shorter than 5 characters should return 422."""
        response = client.post(
            "/summaries/customer/ask",
            json={"customer_id": "cust-001", "question": "hi"},
        )
        assert response.status_code == 422
