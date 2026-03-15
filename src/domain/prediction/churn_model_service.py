"""ChurnModelService – domain service for churn probability prediction.

Domain services encapsulate operations that don't naturally belong to a single entity.
The model artifact is injected as a dependency (no direct file I/O here).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, Sequence

from src.domain.customer.entities import Customer
from src.domain.prediction.entities import PredictionResult, ShapFeature
from src.domain.prediction.value_objects import ChurnProbability, RiskScore
from src.domain.usage.entities import UsageEvent


class ChurnFeatureVector(Protocol):
    """Protocol for feature extraction – implemented in infrastructure layer."""

    def extract(
        self, customer: Customer, events: Sequence[UsageEvent]
    ) -> dict[str, float]:
        """Extract model features from domain entities.

        Returns a flat dict of feature_name → numeric value.
        Infrastructure layer handles the actual computation.
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
        feature_extractor: Extracts features from domain entities.
    """

    def __init__(self, model: ChurnModelPort, feature_extractor: ChurnFeatureVector) -> None:
        self._model = model
        self._feature_extractor = feature_extractor

    def predict(
        self,
        customer: Customer,
        recent_events: Sequence[UsageEvent],
        risk_score: RiskScore,
    ) -> PredictionResult:
        """Generate a full PredictionResult for a customer.

        Args:
            customer: Customer entity with current state.
            recent_events: Usage events for feature engineering.
            risk_score: Pre-computed risk score (from RiskModelService).

        Returns:
            PredictionResult with churn probability, SHAP explanations,
            and recommended CS action.
        """
        features = self._feature_extractor.extract(customer, recent_events)
        churn_prob = self._model.predict_proba(features)
        shap_features = self._model.explain(features)

        return PredictionResult(
            customer_id=customer.customer_id,
            churn_probability=ChurnProbability(value=churn_prob),
            risk_score=risk_score,
            top_shap_features=sorted(
                shap_features, key=lambda f: abs(f.shap_impact), reverse=True
            )[:5],
            model_version=self._model.version,
        )
