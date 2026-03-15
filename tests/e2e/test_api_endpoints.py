"""End-to-end tests for the FastAPI delivery layer.

These tests use httpx.AsyncClient to call the API and assert on HTTP responses.
They require the full application stack (app + use cases + faked infrastructure).
"""

import pytest

# E2E tests are added in Phase 7 once FastAPI routers are implemented.
# Placeholder to establish the test file structure for TDD.

@pytest.mark.skip(reason="Implement in Phase 7 – FastAPI routers not yet built")
class TestHealthEndpoint:
    async def test_health_returns_200(self) -> None:
        pass


@pytest.mark.skip(reason="Implement in Phase 7 – FastAPI routers not yet built")
class TestPredictChurnEndpoint:
    async def test_valid_customer_returns_prediction(self) -> None:
        pass

    async def test_unknown_customer_returns_404(self) -> None:
        pass

    async def test_churned_customer_returns_422(self) -> None:
        pass
