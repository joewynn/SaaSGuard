"""Unit tests for GET /customers list and GET /customers/{customer_id} endpoints.

TDD: these tests were written before the implementation.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_customer_360_use_case, get_customer_repository
from app.main import app
from src.application.use_cases.get_customer_360 import (
    Customer360Profile,
    ShapFeatureSummary,
)

MOCK_PROFILE = Customer360Profile(
    customer_id="cust-test-001",
    plan_tier="enterprise",
    industry="fintech",
    mrr=12500.0,
    tenure_days=420,
    churn_probability=0.72,
    risk_tier="HIGH",
    top_shap_features=[
        ShapFeatureSummary(feature="events_last_30d", value=3.0, shap_impact=0.41),
        ShapFeatureSummary(feature="open_ticket_count", value=4.0, shap_impact=0.28),
    ],
    events_last_30d=3,
    open_ticket_count=4,
    gtm_stage="Renewal",
    latest_prediction_at="2026-03-14T12:00:00",
)


@pytest.fixture()
def client() -> TestClient:
    """TestClient with clean dependency overrides reset after each test."""
    return TestClient(app)


MOCK_CUSTOMERS = [
    {
        "customer_id": "cust-001",
        "plan_tier": "enterprise",
        "industry": "fintech",
        "mrr": 12500.0,
        "is_churned": False,
    },
    {
        "customer_id": "cust-002",
        "plan_tier": "growth",
        "industry": "healthcare",
        "mrr": 4200.0,
        "is_churned": True,
    },
]


class TestCustomerListEndpoint:
    """Unit tests for GET /customers (list endpoint)."""

    def setup_method(self) -> None:
        app.dependency_overrides.clear()

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_list_customers_returns_200(self, client: TestClient) -> None:
        """GET /customers returns 200 with a list of CustomerSummary records."""
        mock_repo = MagicMock()
        mock_repo.get_sample.return_value = [
            MagicMock(
                customer_id=r["customer_id"],
                plan_tier=MagicMock(value=r["plan_tier"]),
                industry=MagicMock(value=r["industry"]),
                mrr=MagicMock(amount=r["mrr"]),
                churn_date=None if not r["is_churned"] else "2024-01-01",
            )
            for r in MOCK_CUSTOMERS
        ]
        app.dependency_overrides[get_customer_repository] = lambda: mock_repo

        response = client.get("/customers")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["customer_id"] == "cust-001"

    def test_list_customers_default_limit_is_20(self, client: TestClient) -> None:
        """GET /customers calls get_sample with n=20 by default."""
        mock_repo = MagicMock()
        mock_repo.get_sample.return_value = []
        app.dependency_overrides[get_customer_repository] = lambda: mock_repo

        client.get("/customers")

        mock_repo.get_sample.assert_called_once_with(20)

    def test_list_customers_clamps_limit_to_100(self, client: TestClient) -> None:
        """GET /customers?limit=9999 clamps n to 100."""
        mock_repo = MagicMock()
        mock_repo.get_sample.return_value = []
        app.dependency_overrides[get_customer_repository] = lambda: mock_repo

        client.get("/customers?limit=9999")

        mock_repo.get_sample.assert_called_once_with(100)


class TestCustomersRouter:
    """Unit tests for GET /customers/{customer_id}."""

    def setup_method(self) -> None:
        """Clear any leftover dependency overrides before each test."""
        app.dependency_overrides.clear()

    def teardown_method(self) -> None:
        """Clean up dependency overrides after each test."""
        app.dependency_overrides.clear()

    def test_get_customer_returns_200_with_profile(self, client: TestClient) -> None:
        """GET /customers/{customer_id} returns 200 with full Customer 360 profile."""
        mock_uc = MagicMock()
        mock_uc.execute.return_value = MOCK_PROFILE
        app.dependency_overrides[get_customer_360_use_case] = lambda: mock_uc

        response = client.get("/customers/cust-test-001")

        assert response.status_code == 200
        data = response.json()
        assert data["customer_id"] == "cust-test-001"
        assert data["plan_tier"] == "enterprise"
        assert data["industry"] == "fintech"
        assert data["mrr"] == 12500.0

    def test_get_customer_unknown_id_returns_404(self, client: TestClient) -> None:
        """GET /customers/{customer_id} with unknown ID should return 404."""
        mock_uc = MagicMock()
        mock_uc.execute.side_effect = ValueError("Customer ghost-999 not found.")
        app.dependency_overrides[get_customer_360_use_case] = lambda: mock_uc

        response = client.get("/customers/ghost-999")

        assert response.status_code == 404
        assert "ghost-999" in response.json()["detail"]

    def test_customer_360_includes_churn_score(self, client: TestClient) -> None:
        """Response must include churn_probability between 0 and 1."""
        mock_uc = MagicMock()
        mock_uc.execute.return_value = MOCK_PROFILE
        app.dependency_overrides[get_customer_360_use_case] = lambda: mock_uc

        response = client.get("/customers/cust-test-001")

        assert response.status_code == 200
        data = response.json()
        assert 0.0 <= data["churn_probability"] <= 1.0
        assert data["risk_tier"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_customer_360_includes_recent_events_summary(  # noqa: E501
        self, client: TestClient
    ) -> None:
        """Response must include events_last_30d and open_ticket_count."""
        mock_uc = MagicMock()
        mock_uc.execute.return_value = MOCK_PROFILE
        app.dependency_overrides[get_customer_360_use_case] = lambda: mock_uc

        response = client.get("/customers/cust-test-001")

        assert response.status_code == 200
        data = response.json()
        assert "events_last_30d" in data
        assert "open_ticket_count" in data
        assert isinstance(data["events_last_30d"], int)
        assert isinstance(data["open_ticket_count"], int)
