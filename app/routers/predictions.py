"""Predictions router – thin wrapper over PredictChurnUseCase and PredictExpansionUseCase."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_predict_churn_use_case, get_predict_expansion_use_case
from app.schemas.prediction import (
    ChurnPredictionRequest,
    ChurnPredictionResponse,
    Customer360Response,
    ShapFeatureDTO,
    UpgradePredictionRequest,
    UpgradePredictionResponse,
)
from src.application.use_cases.predict_churn import PredictChurnRequest, PredictChurnUseCase
from src.application.use_cases.predict_expansion import (
    PredictExpansionRequest,
    PredictExpansionUseCase,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/churn", response_model=ChurnPredictionResponse)
async def predict_churn(
    body: ChurnPredictionRequest,
    use_case: PredictChurnUseCase = Depends(get_predict_churn_use_case),
) -> ChurnPredictionResponse:
    """Predict P(churn in 90 days) for a customer.

    Returns churn probability, risk score, top SHAP feature drivers,
    and a recommended CS action.
    """
    logger.info("predict_churn.request", customer_id=body.customer_id)
    try:
        result = use_case.execute(PredictChurnRequest(customer_id=body.customer_id))
    except ValueError as exc:
        detail = str(exc)
        status = 404 if "not found" in detail.lower() else 422
        raise HTTPException(status_code=status, detail=detail) from exc
    except Exception as exc:
        logger.error("predict_churn.error", customer_id=body.customer_id, error=str(exc))
        raise HTTPException(status_code=503, detail=f"Prediction service error: {exc}") from exc

    return ChurnPredictionResponse(
        customer_id=result.customer_id,
        churn_probability=result.churn_probability.value,
        risk_score=result.risk_score.value,
        risk_tier=result.risk_score.tier.value,
        top_shap_features=[
            ShapFeatureDTO(feature_name=f.feature_name, feature_value=f.feature_value, shap_impact=f.shap_impact)
            for f in result.top_shap_features
        ],
        recommended_action=result.recommended_action,
        model_version=result.model_version,
    )


@router.post("/upgrade", response_model=UpgradePredictionResponse)
async def predict_upgrade(
    body: UpgradePredictionRequest,
    use_case: PredictExpansionUseCase = Depends(get_predict_expansion_use_case),
) -> UpgradePredictionResponse:
    """Predict P(upgrade to next plan tier within 90 days) for a customer.

    Returns upgrade propensity, target tier, probability-weighted ARR uplift,
    top SHAP feature drivers, and a deterministic GTM action recommendation.
    The recommended_action implements the Churn-Expansion conflict matrix when
    both scores are available (see /customers/{customer_id}/360).
    """
    logger.info("predict_upgrade.request", customer_id=body.customer_id)
    try:
        result = use_case.execute(PredictExpansionRequest(customer_id=body.customer_id))
    except ValueError as exc:
        detail = str(exc)
        status = 404 if "not found" in detail.lower() else 422
        raise HTTPException(status_code=status, detail=detail) from exc
    except Exception as exc:
        logger.error("predict_upgrade.error", customer_id=body.customer_id, error=str(exc))
        raise HTTPException(status_code=503, detail=f"Expansion service error: {exc}") from exc

    return UpgradePredictionResponse(
        customer_id=result.customer_id,
        upgrade_propensity=result.propensity.value,
        propensity_tier=result.propensity.tier.value,
        is_expansion_candidate=result.propensity.value >= 0.25,
        target_tier=result.target.next_tier.value if result.target.next_tier else None,
        expected_arr_uplift=result.expected_arr_uplift,
        top_shap_features=[
            ShapFeatureDTO(feature_name=f.feature_name, feature_value=f.feature_value, shap_impact=f.shap_impact)
            for f in result.top_features
        ],
        recommended_action=result.recommended_action(),
        model_version=result.model_version,
        # No churn context on /upgrade — flight risk is always False
        is_flight_risk=False,
        flight_risk_reason=None,
    )


@router.get("/customers/{customer_id}/360", response_model=Customer360Response)
async def get_customer_360(
    customer_id: str,
    churn_use_case: PredictChurnUseCase = Depends(get_predict_churn_use_case),
    expansion_use_case: PredictExpansionUseCase = Depends(get_predict_expansion_use_case),
) -> Customer360Response:
    """Full NRR lifecycle view — churn risk + expansion propensity in one response.

    Calls both models and applies the Churn-Expansion conflict matrix to produce
    a single recommended_action. This is the primary entry point for the
    Propensity Quadrant dashboard visualisation:

    | Churn Risk  | Expansion    | Quadrant         |
    |-------------|--------------|------------------|
    | Low (<0.25) | High (≥0.50) | Growth Engine    |
    | High (≥0.50)| High (≥0.50) | Flight Risk      |
    | High (≥0.50)| Low (<0.25)  | Churn Candidate  |
    | Low (<0.25) | Low (<0.25)  | Stable Base      |
    """
    logger.info("customer_360.request", customer_id=customer_id)

    # Run both use cases — both are @lru_cache singletons so no extra model loading
    try:
        churn_result = churn_use_case.execute(PredictChurnRequest(customer_id=customer_id))
    except ValueError as exc:
        detail = str(exc)
        status = 404 if "not found" in detail.lower() else 422
        raise HTTPException(status_code=status, detail=detail) from exc
    except Exception as exc:
        logger.error("customer_360.churn_error", customer_id=customer_id, error=str(exc))
        raise HTTPException(status_code=503, detail=f"Churn prediction error: {exc}") from exc

    try:
        expansion_result = expansion_use_case.execute(PredictExpansionRequest(customer_id=customer_id))
    except ValueError as exc:
        # Customer may be active for churn but excluded from expansion mart
        # (e.g. already upgraded) — return churn result only with placeholder expansion
        logger.warning(
            "customer_360.expansion_unavailable",
            customer_id=customer_id,
            reason=str(exc)[:120],
        )
        raise HTTPException(
            status_code=422,
            detail=f"Expansion score unavailable: {exc}",
        ) from exc
    except Exception as exc:
        logger.error("customer_360.expansion_error", customer_id=customer_id, error=str(exc))
        raise HTTPException(status_code=503, detail=f"Expansion service error: {exc}") from exc

    # Apply conflict matrix
    churn_prob = churn_result.churn_probability.value
    expansion_prop = expansion_result.propensity.value
    recommended_action = expansion_result.recommended_action(churn_probability=churn_prob)

    # Machine-readable flight risk signal — both scores must exceed 50%
    is_flight_risk = churn_prob >= 0.50 and expansion_prop >= 0.50
    flight_risk_reason = (
        f"Churn probability {churn_prob:.0%} and upgrade propensity "
        f"{expansion_prop:.0%} both exceed 50% threshold. "
        "Restore account health before any upsell motion."
        if is_flight_risk
        else None
    )

    return Customer360Response(
        customer_id=customer_id,
        churn_probability=churn_prob,
        churn_risk_tier=churn_result.churn_probability.risk_tier.value,
        upgrade_propensity=expansion_prop,
        propensity_tier=expansion_result.propensity.tier.value,
        target_tier=(expansion_result.target.next_tier.value if expansion_result.target.next_tier else None),
        expected_arr_uplift=expansion_result.expected_arr_uplift,
        is_high_value_target=expansion_result.is_high_value_target,
        recommended_action=recommended_action,
        churn_top_features=[
            ShapFeatureDTO(feature_name=f.feature_name, feature_value=f.feature_value, shap_impact=f.shap_impact)
            for f in churn_result.top_shap_features
        ],
        expansion_top_features=[
            ShapFeatureDTO(feature_name=f.feature_name, feature_value=f.feature_value, shap_impact=f.shap_impact)
            for f in expansion_result.top_features
        ],
        is_flight_risk=is_flight_risk,
        flight_risk_reason=flight_risk_reason,
    )
