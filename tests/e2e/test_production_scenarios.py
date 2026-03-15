"""E2E tests for production hardening scenarios – CORS and full prediction flow.

TDD: these tests were written before the implementation.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_customer_360_use_case
from app.main import app
from src.application.use_cases.get_customer_360 import (
    Customer360Profile,
    ShapFeatureSummary,
)

MOCK_PROFILE = Customer360Profile(
    customer_id="cust-prod-001",
    plan_tier="growth",
    industry="healthtech",
    mrr=4200.0,
    tenure_days=180,
    churn_probability=0.45,
    risk_tier="MEDIUM",
    top_shap_features=[
        ShapFeatureSummary(feature="events_last_30d", value=8.0, shap_impact=0.22),
    ],
    events_last_30d=8,
    open_ticket_count=1,
    gtm_stage=None,
    latest_prediction_at="2026-03-14T12:00:00",
)


@pytest.fixture()
def client() -> TestClient:
    """TestClient configured for production scenario tests."""
    return TestClient(app, raise_server_exceptions=True)


class TestProductionScenarios:
    """E2E tests for CORS lockdown and full prediction + summary flow."""

    def setup_method(self) -> None:
        app.dependency_overrides.clear()

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_cors_rejects_unknown_origin(self, client: TestClient) -> None:
        """Requests from unknown origins must NOT receive CORS allow headers."""
        response = client.get(
            "/health",
            headers={"Origin": "http://evil.com"},
        )

        # The response itself may be 200 (FastAPI always responds),
        # but the CORS header must not grant access to the evil origin.
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") != "http://evil.com"

    def test_cors_accepts_allowed_origin(self, client: TestClient) -> None:
        """Requests from configured origins must receive the CORS allow header."""
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:8088"},
        )

        assert response.status_code == 200
        # Superset origin is in the default ALLOWED_ORIGINS list
        assert response.headers.get("access-control-allow-origin") == "http://localhost:8088"

    def test_full_prediction_and_summary_flow(self, client: TestClient) -> None:
        """Customer 360 endpoint returns full profile including churn score."""
        mock_uc = MagicMock()
        mock_uc.execute.return_value = MOCK_PROFILE
        app.dependency_overrides[get_customer_360_use_case] = lambda: mock_uc

        response = client.get("/customers/cust-prod-001")

        assert response.status_code == 200
        data = response.json()
        assert data["customer_id"] == "cust-prod-001"
        assert data["churn_probability"] == 0.45
        assert data["risk_tier"] == "MEDIUM"
        assert len(data["top_shap_features"]) >= 1

    @pytest.mark.skip(reason="Rate limiting not yet implemented – future enhancement")
    def test_rate_limit_headers_present(self, client: TestClient) -> None:
        """Response headers should include X-RateLimit-* with rate limiting active."""
        response = client.get("/health")
        assert "x-ratelimit-limit" in response.headers
