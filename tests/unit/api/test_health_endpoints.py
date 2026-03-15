"""Unit tests for /health and /ready endpoints.

TDD: these tests were written before the implementation.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    """TestClient – no dependency overrides needed for health endpoints."""
    return TestClient(app)


class TestHealthEndpoints:
    """Tests for liveness (/health) and readiness (/ready) probes."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """GET /health should always return 200 when the service is running."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_readiness_returns_200_when_model_loaded(self, client: TestClient) -> None:
        """GET /ready should return 200 when model artifacts are present."""
        with patch("app.main.model_registry_loaded", return_value=True):
            response = client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_readiness_returns_503_when_model_not_loaded(  # noqa: E501
        self, client: TestClient
    ) -> None:
        """GET /ready should return 503 when model artifacts are missing."""
        with patch("app.main.model_registry_loaded", return_value=False):
            response = client.get("/ready")

        assert response.status_code == 503
        assert "Model not loaded" in response.json()["detail"]
