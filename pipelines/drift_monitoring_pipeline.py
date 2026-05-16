# pipelines/drift_monitoring_pipeline.py
"""
Drift monitoring pipeline.

Compares the current active-customer feature distribution against the
training baseline using PSI and KS tests. Triggers churn_training_pipeline
automatically if drift exceeds the configured thresholds (PSI > 0.20 or
KS p-value < 0.05, per ADR-004).

Run manually:
    OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES python -m pipelines.drift_monitoring_pipeline

Triggered automatically from GitHub Actions every Sunday 00:00 UTC
(see .github/workflows/drift-monitor.yml after Phase 7 update).

Prerequisite: models/churn_training_baseline.json must exist.
    Generate it with: python -m src.infrastructure.monitoring.drift_detector --export-baseline
"""

from zenml import pipeline
from zenml.logger import get_logger

from steps.drift_monitoring_steps import (
    compute_drift_report,
    evaluate_drift_and_trigger,
    load_current_features,
)

logger = get_logger(__name__)


@pipeline(name="drift_monitoring", enable_cache=False)
def drift_monitoring_pipeline() -> None:
    """
    Drift monitoring DAG: load → compute → evaluate.

    Cache disabled: drift detection must always use the current feature
    distribution — a cached snapshot from a previous run is meaningless.

    The drift_report artifact is stored as a versioned ZenML artifact so
    the drift history is queryable: "when did PSI first exceed 0.20 for mrr?"
    is answerable from the ZenML dashboard without hunting through old
    GitHub Actions logs.
    """
    current_features = load_current_features()
    drift_report = compute_drift_report(current_features=current_features)
    evaluate_drift_and_trigger(drift_report=drift_report)


if __name__ == "__main__":
    drift_monitoring_pipeline()
