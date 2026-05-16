# steps/churn_training_steps.py
"""
ZenML steps for the churn model training pipeline.

Each function here is a single, cacheable unit of work. ZenML stores the
output of each step as a typed artifact. If you re-run the pipeline and the
inputs haven't changed, ZenML returns the cached output instantly.

Business context: These steps mirror the stages in train_churn_model.py
but are now individually versioned, observable, and retryable.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Tuple

import numpy as np
import pandas as pd
import shap
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from zenml import log_metadata, step
from zenml.logger import get_logger

from src.infrastructure.ml.churn_feature_extractor import ChurnFeatureExtractor
from src.infrastructure.ml.train_churn_model import ALL_FEATURES, _build_pipeline

logger = get_logger(__name__)

# The date that separates training cohorts from test cohorts.
# Customers who signed up before this date are used for training.
TRAIN_CUTOFF = "2025-06-01"

# Minimum AUC-ROC required for a model to be considered production-ready.
MIN_ACCEPTABLE_AUC = 0.80

# Path to the DuckDB warehouse (DVC-tracked, so this is always the right version).
DB_PATH = Path("data/saasguard.duckdb")


@step
def load_training_data() -> Tuple[
    Annotated[pd.DataFrame, "X_train"],
    Annotated[pd.DataFrame, "X_test"],
    Annotated[pd.Series, "y_train"],
    Annotated[pd.Series, "y_test"],
]:
    """
    Load and split the feature matrix from DuckDB using a time-based split.

    Why time-based split? Because random splits leak future information into
    training data. If customer A signed up in Jan 2025 and churned in Aug 2025,
    a random split might put Aug 2025 data in training and Jan 2025 data in test
    — the model learns from the future. Time-based splits prevent this.

    ⚠️  Do this before implementing this step: extract the SQL below into
    `ChurnFeatureExtractor.build_feature_matrix(db_path, cutoff_date)` in
    `src/infrastructure/ml/churn_feature_extractor.py`, then call that method
    here instead of writing inline SQL. Two reasons this is Phase 1 work, not
    future work: (1) the same 16-column query must appear identically in
    `load_active_customers` in Phase 4 — divergence here causes silent feature
    mismatch bugs at inference time; (2) it keeps steps thin and testable.

    Returns:
        Four DataFrames/Series: X_train, X_test, y_train, y_test.
    """
    logger.info("Connecting to DuckDB at %s", DB_PATH)

    X_train, X_test, y_train, y_test = ChurnFeatureExtractor.build_feature_matrix(
        db_path=DB_PATH, 
        cutoff_date=TRAIN_CUTOFF
    )
    
    logger.info(
        "Split: %d train rows (churn rate: %.1f%%), %d test rows (churn rate: %.1f%%)",
        len(X_train), y_train.mean() * 100,
        len(X_test), y_test.mean() * 100,
    )
    return X_train, X_test, y_train, y_test


@step
def train_base_pipeline(
    X_train: pd.DataFrame,
    y_train: pd.Series,
) -> Annotated[Pipeline, "base_pipeline"]:
    """
    Build and train the XGBoost preprocessing + classifier pipeline.

    Why a sklearn Pipeline? It bundles the StandardScaler and OrdinalEncoder
    with the model so they're always applied consistently. When you save and
    load the model, the preprocessing is included — no risk of applying the
    wrong scaler to new data.

    Returns:
        Fitted sklearn Pipeline (StandardScaler + OrdinalEncoder + XGBoost).
    """
    logger.info("Building XGBoost pipeline...")

    # _build_pipeline() is your existing function from train_churn_model.py.
    # It returns a Pipeline with preprocessing + XGBoost, configured with
    # scale_pos_weight to handle class imbalance.
    pipeline = _build_pipeline(
        scale_pos_weight=float((y_train == 0).sum() / (y_train == 1).sum())
    )

    logger.info("Training on %d samples...", len(X_train))
    pipeline.fit(X_train, y_train)
    logger.info("Training complete.")

    return pipeline


@step
def calibrate_model(
    base_pipeline: Pipeline,
    X_train: pd.DataFrame,
    y_train: pd.Series,
) -> Annotated[CalibratedClassifierCV, "calibrated_model"]:
    """
    Wrap the base pipeline with isotonic calibration.

    Why calibrate? Raw XGBoost outputs are not true probabilities. A score of
    0.8 does not mean 80% probability of churn — it's just a relative ranking.
    Isotonic calibration maps these scores to actual empirical probabilities.
    After calibration, 0.8 really does mean ~80% of these customers churned.

    Returns:
        CalibratedClassifierCV wrapping the base pipeline.
    """
    logger.info("Calibrating model with isotonic regression (cv=5)...")

    calibrated = CalibratedClassifierCV(
        estimator=base_pipeline,
        method="isotonic",
        cv=5,
    )
    calibrated.fit(X_train, y_train)

    logger.info("Calibration complete.")
    return calibrated


@step
def evaluate_model(
    calibrated_model: CalibratedClassifierCV,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> Annotated[dict, "evaluation_metrics"]:
    """
    Evaluate the calibrated model on the held-out test set.

    Logs metrics to the ZenML server so they appear in the pipeline run
    dashboard at https://zenml-server-77.up.railway.app/.

    Returns:
        Dictionary of evaluation metrics.
    """
    y_proba = calibrated_model.predict_proba(X_test)[:, 1]

    auc = float(roc_auc_score(y_test, y_proba))
    brier = float(brier_score_loss(y_test, y_proba))

    # Precision at top decile: of the 10% of customers we flag as highest
    # risk, what fraction actually churned? This is the business metric CS
    # teams care about most.
    top_decile_mask = y_proba >= np.percentile(y_proba, 90)
    precision_at_decile = float(y_test[top_decile_mask].mean())

    metrics = {
        "auc_roc": auc,
        "brier_score": brier,
        "precision_at_top_decile": precision_at_decile,
        "n_test": len(y_test),
        "n_train_churn_rate": float(y_test.mean()),
    }

    # Attach metrics to this step run — visible in the ZenML dashboard.
    log_metadata(metrics)

    logger.info(
        "Evaluation: AUC=%.4f, Brier=%.4f, Precision@Decile=%.4f",
        auc, brier, precision_at_decile,
    )

    if auc < MIN_ACCEPTABLE_AUC:
        logger.warning(
            "AUC %.4f is below the minimum threshold of %.2f. "
            "This model will NOT be promoted to production.",
            auc, MIN_ACCEPTABLE_AUC,
        )

    return metrics


@step
def compute_global_shap(
    base_pipeline: Pipeline,
    X_train: pd.DataFrame,
) -> Annotated[dict, "shap_importances"]:
    """
    Compute global SHAP feature importances from the base (uncalibrated) model.

    Why use the uncalibrated model for SHAP? TreeExplainer works with the raw
    XGBoost tree structure. The calibration wrapper adds an isotonic layer on
    top, which doesn't expose tree internals. The feature rankings are
    monotonically preserved through calibration, so SHAP values are still valid.

    Returns:
        Dictionary mapping feature names to mean absolute SHAP values.
    """
    logger.info("Computing global SHAP feature importances...")

    # Extract the XGBoost model from inside the pipeline's preprocessor.
    # The pipeline has two steps: 'preprocessor' (ColumnTransformer) and
    # 'classifier' (XGBoost). We need the preprocessor to transform X first.
    preprocessor = base_pipeline[:-1]  # all steps except the last (XGBoost)
    xgb_model = base_pipeline[-1]      # just the XGBoost classifier

    X_transformed = preprocessor.transform(X_train)
    explainer = shap.TreeExplainer(xgb_model)
    shap_values = explainer.shap_values(X_transformed)

    # ALL_FEATURES matches the ColumnTransformer output order: numerical first,
    # then categorical — same as the pipeline defined in _build_pipeline().
    feature_names = ALL_FEATURES
    importances = {
        name: float(np.abs(shap_values[:, i]).mean())
        for i, name in enumerate(feature_names)
    }

    # Sort by importance descending.
    importances = dict(
        sorted(importances.items(), key=lambda x: x[1], reverse=True)
    )

    logger.info("Top 5 SHAP features: %s", list(importances.keys())[:5])
    return importances


@step
def register_model_artifact(
    calibrated_model: CalibratedClassifierCV,
    evaluation_metrics: dict,
    shap_importances: dict,
) -> Annotated[str, "model_version"]:
    """
    Save the model artifact and register it in the ZenML Model Control Plane.

    Why register? Instead of saving a pkl and hoping nobody overwrites it,
    ZenML's Model Control Plane keeps a versioned history of every model.
    You can see which metrics each version achieved and promote it through
    staging → production with a CLI command or a quality gate.

    On serialization: ZenML's SklearnMaterializer already handles the
    `calibrated_model` artifact when it flows between steps (no pickle needed
    at the ZenML layer). The joblib.dump below writes a *deployment* artifact
    to `models/` for the FastAPI fallback. Once ZenML MCP is the sole source
    of truth (post Phase 3 smoke test), this file can be removed.

    Returns:
        The semantic version string for this model (e.g., "2026.05.15").
    """
    import joblib  # sklearn's recommended serializer — handles large numpy arrays efficiently

    # Write deployment artifact for FastAPI's local fallback.
    # joblib is preferred over raw pickle for sklearn/XGBoost objects.
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)

    model_path = models_dir / "churn_model.pkl"
    joblib.dump(calibrated_model, model_path)

    # Save metadata JSON (same format as before).
    metadata = {
        "metrics": evaluation_metrics,
        "shap_importances": shap_importances,
        "feature_order": list(shap_importances.keys()),
        "min_auc_threshold": MIN_ACCEPTABLE_AUC,
        "train_cutoff": TRAIN_CUTOFF,
    }
    metadata_path = models_dir / "churn_model_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    auc = evaluation_metrics["auc_roc"]
    is_production_ready = auc >= MIN_ACCEPTABLE_AUC

    logger.info(
        "Model registered in ZenML artifact store. Deployment artifact: %s. "
        "Production-ready: %s (AUC: %.4f)",
        model_path, is_production_ready, auc,
    )

    version = datetime.utcnow().strftime("%Y.%m.%d")
    return version