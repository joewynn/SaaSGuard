# steps/data_steps.py
"""
ZenML steps for the data ingestion and feature engineering pipeline.

These wrap the existing infrastructure scripts without changing their logic.
The dbt step calls the CLI directly — dbt itself is not a ZenML concept and
does not need to be restructured.

Business context: Raw data refresh is currently driven by raw Python/dbt commands
in .github/workflows/data-pipeline.yml with no artifact lineage. Migrating to
ZenML steps gives every data refresh a versioned artifact and links it to the
downstream training runs that consumed it — enabling questions like
"which data version trained the model currently in production?"
"""

import subprocess
from pathlib import Path
from typing import Annotated

import duckdb
import pandas as pd
from zenml import log_metadata, step
from zenml.logger import get_logger

from src.infrastructure.data_generation.generate_synthetic_data import (
    OUTPUT_DIR,
    generate_all,
)
from src.infrastructure.db.build_warehouse import build

logger = get_logger(__name__)

DB_PATH = Path("data/saasguard.duckdb")


@step(enable_cache=False)
def generate_synthetic_data() -> Annotated[int, "n_customers"]:
    """
    Generate fresh synthetic customer data and write to data/raw/.

    enable_cache=False because data generation uses a fixed random seed for
    reproducibility but we always want a fresh set of CSVs on each pipeline run
    (the seed can be changed in generate_synthetic_data.py for experiments).

    Returns:
        Number of customers written to data/raw/customers.csv.
    """
    logger.info("Generating synthetic customer data...")
    generate_all()

    n = len(pd.read_csv(OUTPUT_DIR / "customers.csv"))
    log_metadata({"n_customers_generated": n})
    logger.info("Generated %d customers", n)
    return n


@step
def build_warehouse(n_customers: int) -> Annotated[int, "n_rows"]:
    """
    Load all raw CSVs into the DuckDB warehouse.

    Takes n_customers as an explicit input so ZenML records the dependency:
    if generate_synthetic_data re-runs, this step re-runs too. Without the
    explicit dependency, ZenML might serve a cached warehouse built from the
    previous generation run.

    Returns:
        Number of rows in raw.customers after loading.
    """
    logger.info("Building DuckDB warehouse from %d generated customers...", n_customers)
    build()

    with duckdb.connect(str(DB_PATH)) as conn:
        row = conn.execute("SELECT COUNT(*) FROM raw.customers").fetchone()
        n = row[0] if row else 0

    log_metadata({"n_raw_customers": n})
    logger.info("Warehouse built — %d rows in raw.customers", n)
    return n


@step
def run_dbt(n_rows: int) -> Annotated[dict, "dbt_results"]:
    """
    Run dbt build to refresh all staging models and marts.

    Takes n_rows as an explicit input to record the dependency on build_warehouse.
    Raises RuntimeError on dbt failure so ZenML marks the step as failed and
    stops the pipeline before downstream steps run on stale or empty data.

    Returns:
        Dict with mart row counts and the dbt exit code.
    """
    logger.info("Running dbt build (warehouse has %d raw rows)...", n_rows)

    result = subprocess.run(
        ["dbt", "build", "--project-dir", "dbt_project", "--profiles-dir", "dbt_project"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"dbt build failed:\n{result.stderr}")

    logger.info("dbt build complete")

    with duckdb.connect(str(DB_PATH)) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM mart_customer_churn_features"
        ).fetchone()
        mart_rows = row[0] if row else 0

    results = {
        "mart_customer_churn_features_rows": mart_rows,
        "dbt_exit_code": 0,
    }
    log_metadata(results)
    return results


@step
def validate_marts(dbt_results: dict) -> None:
    """
    Assert that the key mart table is non-empty after dbt build.

    Raises ValueError if the mart is empty — ZenML marks the step as failed
    and halts the pipeline before training runs on an empty feature matrix.

    The training pipeline depends on mart_customer_churn_features being
    populated. An empty mart means a silent wrong-count bug at training time.
    """
    mart_rows = dbt_results.get("mart_customer_churn_features_rows", 0)
    if mart_rows == 0:
        raise ValueError(
            "mart_customer_churn_features is empty after dbt build. "
            "Check dbt logs for model failures before running training."
        )
    logger.info("Mart validation passed — %d rows in mart_customer_churn_features", mart_rows)
