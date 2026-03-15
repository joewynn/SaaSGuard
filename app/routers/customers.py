"""Customers router – Customer 360 profile endpoint."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_customer_360_use_case
from app.schemas.customer import Customer360Response, ShapFeatureSummary
from src.application.use_cases.get_customer_360 import (
    GetCustomer360Request,
    GetCustomer360UseCase,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


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
