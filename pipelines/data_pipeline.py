# pipelines/data_pipeline.py
"""
Data ingestion and feature engineering pipeline.

Replaces the raw Python/dbt commands in .github/workflows/data-pipeline.yml
with a ZenML pipeline that gives every data refresh a versioned artifact
and a lineage edge to the training runs that consumed it.

Run manually:
    OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES python -m pipelines.data_pipeline

Triggered automatically from GitHub Actions on Monday 02:00 UTC
(see .github/workflows/data-pipeline.yml).
"""

from zenml import pipeline
from zenml.logger import get_logger

from steps.data_steps import (
    build_warehouse,
    generate_synthetic_data,
    run_dbt,
    validate_marts,
)

logger = get_logger(__name__)


@pipeline(name="data_ingestion", enable_cache=False)
def data_pipeline() -> None:
    """
    Data refresh DAG: generate → warehouse → dbt → validate.

    Cache disabled at the pipeline level: data generation writes CSVs with
    a fixed seed, but the intent on each run is always fresh output files.
    The explicit dependency chain (n_customers → n_rows → dbt_results) ensures
    ZenML re-runs all downstream steps whenever an upstream step re-runs.
    """
    n_customers = generate_synthetic_data()
    n_rows = build_warehouse(n_customers=n_customers)
    dbt_results = run_dbt(n_rows=n_rows)
    validate_marts(dbt_results=dbt_results)


if __name__ == "__main__":
    data_pipeline()
