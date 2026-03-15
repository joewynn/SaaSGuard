"""Shared pytest fixtures for all test layers.

Fixtures at this level are available to unit, integration, and e2e tests.
Domain-layer tests should use in-memory fakes, never real infrastructure.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from src.domain.customer.entities import Customer
from src.domain.customer.value_objects import Industry, MRR, PlanTier
from src.domain.prediction.risk_model_service import RiskModelService
from src.domain.usage.entities import UsageEvent
from src.domain.usage.value_objects import EventType, FeatureAdoptionScore


@pytest.fixture
def active_starter_customer() -> Customer:
    """A starter-tier customer in their first 30 days (high churn risk profile)."""
    return Customer(
        customer_id="cust-001",
        industry=Industry.FINTECH,
        plan_tier=PlanTier.STARTER,
        signup_date=date(2026, 2, 12),
        mrr=MRR(amount=Decimal("500.00")),
        churn_date=None,
    )


@pytest.fixture
def churned_customer() -> Customer:
    """A customer who has already churned."""
    return Customer(
        customer_id="cust-002",
        industry=Industry.HEALTHTECH,
        plan_tier=PlanTier.GROWTH,
        signup_date=date(2025, 1, 1),
        mrr=MRR(amount=Decimal("2000.00")),
        churn_date=date(2026, 1, 15),
    )


@pytest.fixture
def enterprise_customer() -> Customer:
    """A high-value enterprise customer (lower base churn rate)."""
    return Customer(
        customer_id="cust-003",
        industry=Industry.LEGALTECH,
        plan_tier=PlanTier.ENTERPRISE,
        signup_date=date(2024, 6, 1),
        mrr=MRR(amount=Decimal("15000.00")),
        churn_date=None,
    )


@pytest.fixture
def low_adoption_event(active_starter_customer: Customer) -> UsageEvent:
    """A usage event with critically low adoption score."""
    return UsageEvent(
        event_id="evt-001",
        customer_id=active_starter_customer.customer_id,
        timestamp=datetime(2026, 3, 10, 9, 0, 0),
        event_type=EventType.REPORT_VIEW,
        feature_adoption_score=FeatureAdoptionScore(value=0.08),
    )


@pytest.fixture
def retention_event(active_starter_customer: Customer) -> UsageEvent:
    """A strong retention signal event (integration connect)."""
    return UsageEvent(
        event_id="evt-002",
        customer_id=active_starter_customer.customer_id,
        timestamp=datetime(2026, 3, 12, 14, 30, 0),
        event_type=EventType.INTEGRATION_CONNECT,
        feature_adoption_score=FeatureAdoptionScore(value=0.65),
    )


@pytest.fixture
def risk_service() -> RiskModelService:
    """A RiskModelService with default production weights."""
    return RiskModelService()
