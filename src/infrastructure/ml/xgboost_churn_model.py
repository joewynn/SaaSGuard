"""XGBoostChurnModel – infrastructure implementation of ChurnModelPort.

Loads the Phase 4 trained sklearn Pipeline from the model registry and
serves calibrated churn predictions + SHAP explanations.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import shap
import structlog

from src.domain.prediction.churn_model_service import ChurnModelPort
from src.domain.prediction.entities import ShapFeature
from src.infrastructure.ml import model_registry

logger = structlog.get_logger(__name__)

# Must match ALL_FEATURES order in train_churn_model.py
_FEATURE_ORDER = [
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
]


class XGBoostChurnModel(ChurnModelPort):
    """Wraps the Phase 4 XGBoost churn model pipeline for domain-layer use.

    Business Context: Hides the sklearn / XGBoost / SHAP implementation
    details from the domain layer. The domain service only depends on the
    ChurnModelPort ABC. Swapping to a different algorithm in Phase 7 requires
    only a new infrastructure class — no domain changes needed.

    The SHAP explainer is initialised once at construction and cached.
    It uses the base XGBoost model (inside the calibrated pipeline) so that
    TreeExplainer can compute exact Shapley values without approximation.
    """

    def __init__(self) -> None:
        """Load the trained model artifact and initialise the SHAP explainer."""
        self._calibrated: Any = model_registry.load_model("churn_model")
        self._metadata: dict[str, Any] = model_registry.get_model_metadata("churn_model")

        # Access the base (uncalibrated) pipeline's XGBoost step for SHAP.
        # CalibratedClassifierCV stores one fitted clone per CV fold; we use
        # the first fold's base estimator, which has the same tree structure.
        base_pipeline = self._calibrated.calibrated_classifiers_[0].estimator
        self._base_pipeline = base_pipeline
        xgb_step = base_pipeline.named_steps["xgboost"]
        self._explainer = shap.TreeExplainer(xgb_step)

        logger.info(
            "xgboost_churn_model.loaded",
            version=self.version,
            n_features=len(_FEATURE_ORDER),
        )

    def predict_proba(self, features: dict[str, float | str]) -> float:
        """Return calibrated P(churn in 90 days) ∈ [0, 1].

        Uses the full CalibratedClassifierCV pipeline so that the returned
        probability reflects isotonic regression calibration.

        Args:
            features: Feature dict from ChurnFeatureExtractor.extract().

        Returns:
            Calibrated churn probability (float in [0, 1]).
        """
        X = self._to_dataframe(features)
        prob = float(self._calibrated.predict_proba(X)[0, 1])
        logger.debug("predict_proba", probability=round(prob, 4))
        return prob

    def explain(self, features: dict[str, float | str]) -> list[ShapFeature]:
        """Return SHAP feature contributions for one customer.

        Uses TreeExplainer on the uncalibrated XGBoost base model.
        The calibration layer is a monotonic transformation so SHAP
        feature importance rankings are preserved end-to-end.

        Args:
            features: Feature dict from ChurnFeatureExtractor.extract().

        Returns:
            List of ShapFeature objects for all 16 features (sorted by
            |shap_impact| descending in ChurnModelService.predict()).
        """
        X = self._to_dataframe(features)
        # Transform through the base pipeline's preprocessor step only
        X_transformed = self._base_pipeline[:-1].transform(X)
        shap_values = self._explainer.shap_values(X_transformed)

        # shap_values shape: (1, n_features) — single sample, class 1 (churn)
        sv = np.asarray(shap_values).flatten()

        return [
            ShapFeature(
                feature_name=feat,
                feature_value=self._to_display_float(features.get(feat, 0.0)),
                shap_impact=float(sv[i]),
            )
            for i, feat in enumerate(_FEATURE_ORDER)
        ]

    @property
    def version(self) -> str:
        """Semantic version from model metadata JSON."""
        return str(self._metadata.get("version", "0.0.0"))

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _to_display_float(value: float | str | None) -> float:
        """Convert any feature value to float for SHAP display.

        Categorical string features (plan_tier, industry) are passed through
        the OrdinalEncoder at prediction time; for SHAP display purposes we
        just return 0.0 rather than crashing on a string-to-float conversion.
        """
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0

    def _to_dataframe(self, features: dict[str, float | str]) -> pd.DataFrame:
        """Convert feature dict to a single-row DataFrame in the correct column order.

        Args:
            features: Feature dict from ChurnFeatureExtractor.

        Returns:
            1-row DataFrame with columns matching _FEATURE_ORDER.
        """
        return pd.DataFrame([{feat: features.get(feat, 0.0) for feat in _FEATURE_ORDER}])
