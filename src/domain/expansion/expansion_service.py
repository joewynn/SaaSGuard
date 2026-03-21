"""ExpansionModelService — domain service for upgrade propensity prediction.

Symmetric mirror of ChurnModelService in the prediction domain.
Ports and protocols follow the same pattern: domain has no direct knowledge
of infrastructure (no file I/O, no DuckDB, no pickle files here).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from src.domain.customer.entities import Customer
from src.domain.expansion.entities import ExpansionResult
from src.domain.expansion.value_objects import TargetTier, UpgradePropensity
from src.domain.prediction.entities import ShapFeature


class ExpansionFeatureVector(Protocol):
    """Protocol for expansion feature extraction — implemented in infrastructure layer.

    Queries the mart_customer_expansion_features dbt mart for the 20-feature
    vector (15 churn features + 5 expansion signals).
    """

    def extract(self, customer: Customer) -> dict[str, float | str]:
        """Extract the 20-feature expansion vector for a customer.

        Args:
            customer: Active Customer entity with plan_tier and MRR.

        Returns:
            Flat dict of feature_name → value (numeric as float, categorical as str).
            All feature engineering lives in mart_customer_expansion_features.

        Raises:
            ValueError: If the customer is not found in the mart or has already upgraded.
        """
        ...


class ExpansionModelPort(ABC):
    """Abstract port for the underlying expansion ML model.

    Concrete implementations in src/infrastructure/ml/ load the trained
    XGBoost expansion model artifact.
    """

    @abstractmethod
    def predict_proba(self, features: dict[str, float | str]) -> float:
        """Return P(upgrade to next tier within 90 days)."""
        ...

    @abstractmethod
    def explain(self, features: dict[str, float | str]) -> list[ShapFeature]:
        """Return SHAP feature contributions for explainability."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Semantic version of the loaded model artifact."""
        ...


class ExpansionModelService:
    """Orchestrates feature extraction → model inference → result construction.

    Business Context: Mirrors ChurnModelService exactly. Feature extraction,
    model inference, and SHAP computation are all delegated to injected
    dependencies — this service only owns the assembly logic.

    Args:
        model: Concrete expansion ML model (injected from infrastructure layer).
        feature_extractor: Queries the dbt expansion mart for the feature vector.
    """

    def __init__(
        self,
        model: ExpansionModelPort,
        feature_extractor: ExpansionFeatureVector,
    ) -> None:
        self._model = model
        self._feature_extractor = feature_extractor

    def predict(self, customer: Customer) -> ExpansionResult:
        """Generate a full ExpansionResult for a customer.

        Business Context: Expansion depends on usage signals and GTM intent,
        not compliance risk — so no RiskScore is needed here. The domain
        service is intentionally leaner than ChurnModelService.

        Args:
            customer: Active Customer entity that has not yet upgraded.

        Returns:
            ExpansionResult with calibrated upgrade propensity, target tier,
            SHAP explanations, and a deterministic GTM action recommendation.
        """
        features = self._feature_extractor.extract(customer)
        propensity_value = self._model.predict_proba(features)
        shap_features = self._model.explain(features)

        return ExpansionResult(
            customer_id=customer.customer_id,
            current_mrr=float(customer.mrr.amount),
            propensity=UpgradePropensity(value=propensity_value),
            target=TargetTier(current_tier=customer.plan_tier),
            top_features=sorted(shap_features, key=lambda f: abs(f.shap_impact), reverse=True)[:5],
            model_version=self._model.version,
        )
