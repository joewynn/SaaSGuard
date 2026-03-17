"""Predictions router – thin wrapper over PredictChurnUseCase."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_predict_churn_use_case
from app.schemas.prediction import ChurnPredictionRequest, ChurnPredictionResponse
from src.application.use_cases.predict_churn import PredictChurnRequest, PredictChurnUseCase

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
            {"feature": f.feature_name, "value": f.feature_value, "shap_impact": f.shap_impact}
            for f in result.top_shap_features
        ],
        recommended_action=result.recommended_action,
        model_version=result.model_version,
    )
