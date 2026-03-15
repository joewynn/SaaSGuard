"""FastAPI dependency injection – wires infrastructure to use cases.

All dependency construction happens here. The domain and application layers
are never aware of FastAPI or this file.
"""

from __future__ import annotations

from functools import lru_cache

from src.application.use_cases.predict_churn import PredictChurnUseCase
from src.domain.prediction.risk_model_service import RiskModelService
from src.infrastructure.repositories.customer_repository import DuckDBCustomerRepository
from src.infrastructure.repositories.usage_repository import DuckDBUsageRepository


@lru_cache(maxsize=1)
def get_predict_churn_use_case() -> PredictChurnUseCase:
    """Build and cache the PredictChurnUseCase with real infrastructure.

    Caching ensures DuckDB connections and model loading happen once per
    worker process, not per request.
    """
    from src.domain.prediction.churn_model_service import ChurnModelService
    from src.infrastructure.ml.xgboost_churn_model import XGBoostChurnModel  # Phase 4
    from src.infrastructure.ml.churn_feature_extractor import ChurnFeatureExtractor  # Phase 4

    return PredictChurnUseCase(
        customer_repo=DuckDBCustomerRepository(),
        usage_repo=DuckDBUsageRepository(),
        churn_service=ChurnModelService(
            model=XGBoostChurnModel(),
            feature_extractor=ChurnFeatureExtractor(),
        ),
        risk_service=RiskModelService(),
    )
