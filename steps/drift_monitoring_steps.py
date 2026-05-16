# steps/drift_monitoring_steps.py
"""
ZenML steps for the drift monitoring pipeline.

Wraps the existing PSI + KS drift detector in src/infrastructure/monitoring/
without changing any detection logic. The only additions are:
  - ZenML artifact tracking: every drift report is a versioned artifact linked
    to the pipeline run that produced it.
  - Automated retraining: if drift exceeds thresholds, the training pipeline
    is triggered immediately rather than waiting for the next scheduled run.

Business context: The existing detector already has well-calibrated thresholds
(PSI > 0.20, KS p < 0.05 per ADR-004). This phase makes its output durable and
actionable — today the drift_report.json disappears after 30 days in GitHub
Actions; after this phase it's a queryable ZenML artifact with a full lineage
edge to the model version it monitored.
"""

import subprocess
import sys
from typing import Annotated

import pandas as pd
from zenml import log_metadata, step
from zenml.logger import get_logger

from src.infrastructure.db.duckdb_adapter import get_connection
from src.infrastructure.monitoring.drift_detector import DriftDetector

logger = get_logger(__name__)


@step(enable_cache=False)
def load_current_features() -> Annotated[pd.DataFrame, "current_features"]:
    """
    Load the current production feature distribution from the mart.

    Uses mart_customer_churn_features (active customers only, pre-aggregated
    by dbt) as the "current" distribution to compare against the training
    baseline. This is the same table scored daily by churn_inference_pipeline,
    so drift detection reflects the actual inference population.

    enable_cache=False: always fetch a fresh snapshot before comparing.

    Returns:
        DataFrame with all MONITORED_FEATURES columns for active customers.
    """
    with get_connection() as conn:
        df = conn.execute(
            "SELECT * FROM marts.mart_customer_churn_features"
        ).df()

    log_metadata({"n_current_rows": len(df)})
    logger.info("Loaded %d rows for drift comparison", len(df))
    return df


@step
def compute_drift_report(
    current_features: pd.DataFrame,
) -> Annotated[dict, "drift_report"]:
    """
    Compare current feature distribution against the training baseline.

    Instantiates DriftDetector which loads the baseline from
    models/churn_training_baseline.json (co-versioned with the model via DVC).
    Raises FileNotFoundError if the baseline doesn't exist — a pipeline failure
    here is correct behaviour; drift monitoring without a reference is undefined.

    Returns:
        JSON-serialisable dict from DriftReport.to_dict() with keys:
        has_drift, max_psi, min_ks_pvalue, drifted_features, checked_at,
        and per-feature PSI/KS results.

    Raises:
        FileNotFoundError: If models/churn_training_baseline.json is missing.
            Run: python -m src.infrastructure.monitoring.drift_detector --export-baseline
    """
    detector = DriftDetector()
    report = detector.run(current_features)
    report_dict = report.to_dict()

    log_metadata({
        "has_drift": report_dict["has_drift"],
        "max_psi": report_dict["max_psi"],
        "min_ks_pvalue": report_dict["min_ks_pvalue"],
        "n_drifted_features": len(report_dict["drifted_features"]),
        "drifted_features": ", ".join(report_dict["drifted_features"]),
    })

    if report_dict["has_drift"]:
        logger.warning(
            "Drift detected: %d features exceeded thresholds "
            "(max_psi=%.4f, min_ks_pvalue=%.4f). Features: %s",
            len(report_dict["drifted_features"]),
            report_dict["max_psi"],
            report_dict["min_ks_pvalue"],
            report_dict["drifted_features"],
        )
    else:
        logger.info(
            "No significant drift detected (max_psi=%.4f, min_ks_pvalue=%.4f)",
            report_dict["max_psi"],
            report_dict["min_ks_pvalue"],
        )

    return report_dict


@step
def evaluate_drift_and_trigger(
    drift_report: dict,
) -> Annotated[bool, "drift_detected"]:
    """
    Evaluate the drift report and trigger retraining if thresholds are exceeded.

    When drift is detected, calls the training pipeline as a subprocess so
    a new ZenML pipeline run is registered on the Railway server — the retrain
    is auditable as a separate run linked to the drift event that triggered it.

    Why subprocess over direct import? Calling churn_training_pipeline()
    inside a running ZenML step creates a nested pipeline context that can
    conflict with the outer run's artifact store writes. A subprocess starts
    a clean Python process with its own ZenML client context.

    Returns:
        True if drift was detected (and retraining triggered), False otherwise.
    """
    has_drift = drift_report.get("has_drift", False)

    if not has_drift:
        logger.info("No drift detected — no retraining triggered.")
        return False

    logger.warning(
        "Drift confirmed in %d feature(s). Triggering churn_training_pipeline...",
        len(drift_report.get("drifted_features", [])),
    )

    subprocess.run(
        [sys.executable, "-m", "pipelines.churn_training_pipeline"],
        check=True,
    )

    logger.info("Retraining pipeline triggered successfully.")
    return True
