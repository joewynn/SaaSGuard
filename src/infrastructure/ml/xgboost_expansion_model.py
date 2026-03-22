"""XGBoostExpansionModel – infrastructure implementation of ExpansionModelPort.

Loads the trained expansion model artifact from the model registry and serves
calibrated upgrade propensity predictions + SHAP explanations.

Mirrors XGBoostChurnModel exactly — same CalibratedClassifierCV + TreeExplainer pattern.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import shap
import structlog

from src.domain.expansion.expansion_service import ExpansionModelPort
from src.domain.prediction.entities import ShapFeature
from src.infrastructure.ml import model_registry

logger = structlog.get_logger(__name__)

# Must match ALL_FEATURES order in train_expansion_model.py (22 features)
_EXPANSION_FEATURE_ORDER = [
    "mrr",
    "tenure_days",
    "total_events",
    "events_last_30d",
    "events_last_7d",
    "avg_adoption_score",
    "days_since_last_event",
    "retention_signal_count",
    "integration_connects_first_30d",
    "activated_at_30d",
    "tickets_last_30d",
    "high_priority_tickets",
    "avg_resolution_hours",
    "is_early_stage",
    "plan_tier",
    "industry",
    # Expansion-specific (5)
    "premium_feature_trials_30d",
    "feature_request_tickets_90d",
    "has_open_expansion_opp",
    "expansion_opp_amount",
    "mrr_tier_ceiling_pct",
    "feature_limit_hit_30d",
]


class XGBoostExpansionModel(ExpansionModelPort):
    """Wraps the trained XGBoost expansion model pipeline for domain-layer use.

    Business Context: Hides sklearn / XGBoost / SHAP implementation details
    from the domain layer. Swapping the algorithm requires only this class.

    Note on SHAP leakage guard: has_open_expansion_opp should NOT rank as the
    top SHAP feature. If it does, re-train with it removed — it is a leakage
    risk (the Sales team creating opps based on signals the model should be
    discovering, not consuming). See notebooks/expansion_propensity_modeling.ipynb.
    """

    def __init__(self) -> None:
        """Load the trained expansion model artifact and initialise SHAP explainer."""
        self._calibrated: Any = model_registry.load_model("expansion_model")
        self._metadata: dict[str, Any] = model_registry.get_model_metadata("expansion_model")

        base_pipeline = self._calibrated.calibrated_classifiers_[0].estimator
        self._base_pipeline = base_pipeline
        xgb_step = base_pipeline.named_steps["xgboost"]
        self._explainer = shap.TreeExplainer(xgb_step)

        logger.info(
            "xgboost_expansion_model.loaded",
            version=self.version,
            n_features=len(_EXPANSION_FEATURE_ORDER),
        )

    def predict_proba(self, features: dict[str, float | str]) -> float:
        """Return calibrated P(upgrade to next tier within 90 days) ∈ [0, 1].

        Args:
            features: Feature dict from ExpansionFeatureExtractor.extract().

        Returns:
            Calibrated upgrade propensity (float in [0, 1]).
        """
        X = self._to_dataframe(features)
        prob = float(self._calibrated.predict_proba(X)[0, 1])
        logger.debug("expansion_predict_proba", probability=round(prob, 4))
        return prob

    def explain(self, features: dict[str, float | str]) -> list[ShapFeature]:
        """Return SHAP feature contributions for one customer.

        Args:
            features: Feature dict from ExpansionFeatureExtractor.extract().

        Returns:
            List of ShapFeature objects for all 22 features.
        """
        X = self._to_dataframe(features)
        X_transformed = self._base_pipeline[:-1].transform(X)
        shap_values = self._explainer.shap_values(X_transformed)
        sv = np.asarray(shap_values).flatten()

        return [
            ShapFeature(
                feature_name=feat,
                feature_value=self._to_display_float(features.get(feat, 0.0)),
                shap_impact=float(sv[i]),
            )
            for i, feat in enumerate(_EXPANSION_FEATURE_ORDER)
        ]

    @property
    def version(self) -> str:
        """Semantic version from expansion model metadata JSON."""
        return str(self._metadata.get("version", "0.0.0"))

    @staticmethod
    def _to_display_float(value: float | str | None) -> float:
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0

    def _to_dataframe(self, features: dict[str, float | str]) -> pd.DataFrame:
        return pd.DataFrame([{feat: features.get(feat, 0.0) for feat in _EXPANSION_FEATURE_ORDER}])
