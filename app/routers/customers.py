"""Customers router – Customer 360 profile endpoint."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_customer_360_use_case
from app.schemas.customer import Customer360Response, CustomerSummary, ShapFeatureSummary
from src.application.use_cases.get_customer_360 import (
    GetCustomer360Request,
    GetCustomer360UseCase,
)
from src.infrastructure.db.duckdb_adapter import get_connection

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("", response_model=list[CustomerSummary])
async def list_customers(limit: int = 20) -> list[CustomerSummary]:
    """Return a random sample of customers for demo and load-test seeding.

    Args:
        limit: Number of customers to return (default 20, max 100).

    Returns:
        List of lightweight CustomerSummary records.
    """
    n = min(limit, 100)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT customer_id, plan_tier, industry, mrr,
                   churn_date IS NOT NULL AS is_churned
            FROM raw.customers
            USING SAMPLE reservoir(? ROWS) REPEATABLE(42)
            """,
            [n],
        ).fetchall()
    return [
        CustomerSummary(
            customer_id=str(r[0]),
            plan_tier=str(r[1]),
            industry=str(r[2]),
            mrr=float(r[3]),
            is_churned=bool(r[4]),
        )
        for r in rows
    ]


@router.get("/{customer_id}", response_model=Customer360Response)
async def get_customer_360(
    customer_id: str,
    use_case: GetCustomer360UseCase = Depends(get_customer_360_use_case),
) -> Customer360Response:
    """Return a full Customer 360 profile for a single customer.

    Combines churn prediction, SHAP explanations, usage velocity,
    support health, and GTM stage into a single response.

    Args:
        customer_id: UUID of the customer to profile.

    Returns:
        Customer360Response with all health signals populated.

    Raises:
        HTTPException: 404 if the customer_id is not found.
    """
    try:
        profile = use_case.execute(GetCustomer360Request(customer_id=customer_id))
    except ValueError as exc:
        logger.warning("customer_360.not_found", customer_id=customer_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Customer360Response(
        customer_id=profile.customer_id,
        plan_tier=profile.plan_tier,
        industry=profile.industry,
        mrr=profile.mrr,
        tenure_days=profile.tenure_days,
        churn_probability=profile.churn_probability,
        risk_tier=profile.risk_tier,
        top_shap_features=[
            ShapFeatureSummary(
                feature=f.feature,
                value=f.value,
                shap_impact=f.shap_impact,
            )
            for f in profile.top_shap_features
        ],
        events_last_30d=profile.events_last_30d,
        open_ticket_count=profile.open_ticket_count,
        gtm_stage=profile.gtm_stage,
        latest_prediction_at=profile.latest_prediction_at,
    )
