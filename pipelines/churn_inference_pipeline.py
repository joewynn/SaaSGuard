# pipelines/churn_inference_pipeline.py
"""
Batch churn inference pipeline.

Pre-computes churn scores for all active customers and writes them to
marts.churn_predictions in DuckDB. Superset dashboards and CS team exports
read from that table rather than hitting the FastAPI endpoint.

Run manually:
    OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES python -m pipelines.churn_inference_pipeline

Triggered automatically from GitHub Actions daily at 06:00 UTC
(see .github/workflows/data-pipeline.yml after Phase 7 update).
"""

from zenml import pipeline
from zenml.logger import get_logger
from zenml.model.model import Model

from steps.churn_inference_steps import (
    load_active_customers,
    score_customers,
    write_predictions_to_duckdb,
)

logger = get_logger(__name__)

CHURN_MODEL = Model(name="churn_model")


@pipeline(name="churn_inference", enable_cache=False, model=CHURN_MODEL)
def churn_inference_pipeline() -> None:
    """
    Batch inference DAG: load features → score → write.

    Cache disabled: always fetch fresh customer state and score with the
    current production model. The CHURN_MODEL entity links every scoring
    run to the model version that produced it — every row in
    marts.churn_predictions is auditable back to a specific training run.
    """
    active_customers = load_active_customers()
    scored_customers = score_customers(active_customers=active_customers)
    write_predictions_to_duckdb(scored_customers=scored_customers)


if __name__ == "__main__":
    churn_inference_pipeline()
