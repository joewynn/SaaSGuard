"""ChurnModelService – domain service for churn probability prediction.

Domain services encapsulate operations that don't naturally belong to a single entity.
The model artifact is injected as a dependency (no direct file I/O here).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from src.domain.customer.entities import Customer
from src.domain.prediction.entities import PredictionResult, ShapFeature
from src.domain.prediction.value_objects import ChurnProbability, RiskScore


class ChurnFeatureVector(Protocol):
    """Protocol for feature extraction – implemented in infrastructure layer.

    Phase 4 update: the extractor queries the dbt mart directly (single DuckDB
    read), so events no longer need to be passed from the use case layer.
    This keeps the protocol minimal and moves feature logic into dbt.
    """

    def extract(self, customer: Customer) -> dict[str, float]:
        """Extract the model's feature vector for a customer.

        Args:
            customer: Active Customer entity (used to look up mart row by ID).

        Returns:
            Flat dict of feature_name → numeric value (15 features total).
            All feature engineering lives in mart_customer_churn_features.

        Raises:
            ValueError: If the customer is not found in the mart (e.g. churned
                        customers are excluded from the mart).
        """
        ...


class ChurnModelPort(ABC):
    """Abstract port for the underlying ML model.

    Concrete implementations in src/infrastructure/ml/
    load the trained XGBoost/survival model artifact.
    """

    @abstractmethod
    def predict_proba(self, features: dict[str, float]) -> float:
        """Return P(churn in 90 days) for the given feature vector."""
        ...

    @abstractmethod
    def explain(self, features: dict[str, float]) -> list[ShapFeature]:
        """Return SHAP feature contributions for explainability."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Semantic version of the loaded model artifact."""
        ...


class ChurnModelService:
    """Orchestrates feature extraction → model inference → result construction.

    Args:
        model: Concrete ML model (injected from infrastructure layer).
        feature_extractor: Queries the dbt mart for the customer's feature vector.
    """

    def __init__(self, model: ChurnModelPort, feature_extractor: ChurnFeatureVector) -> None:
        self._model = model
        self._feature_extractor = feature_extractor

    def predict(
        self,
        customer: Customer,
        risk_score: RiskScore,
    ) -> PredictionResult:
        """Generate a full PredictionResult for a customer.

        Business Context: Feature extraction, model inference, and SHAP
        computation are all delegated to injected dependencies. This service
        only owns the assembly logic, keeping it testable in isolation.

        Args:
            customer: Active Customer entity.
            risk_score: Pre-computed composite risk score (from RiskModelService).

        Returns:
            PredictionResult with calibrated churn probability, SHAP explanations,
            and a deterministic recommended CS action.
        """
        features = self._feature_extractor.extract(customer)
        churn_prob = self._model.predict_proba(features)
        shap_features = self._model.explain(features)

        return PredictionResult(
            customer_id=customer.customer_id,
            churn_probability=ChurnProbability(value=churn_prob),
            risk_score=risk_score,
            top_shap_features=sorted(shap_features, key=lambda f: abs(f.shap_impact), reverse=True)[:5],
            model_version=self._model.version,
        )
