# steps/churn_inference_steps.py
"""
ZenML steps for the batch churn inference pipeline.

Runs daily to score all active customers and write predictions to DuckDB.
Superset dashboards and CS team exports read from marts.churn_predictions.

Design note: load_active_customers returns the full feature matrix (not just
customer IDs) because mart_customer_churn_features already contains all 16
model features for every active customer. Pulling the full matrix here avoids
a second per-customer DB round-trip in score_customers.
"""

from datetime import datetime, timezone
from typing import Annotated

import pandas as pd
from zenml import log_metadata, step
from zenml.logger import get_logger
from zenml.model.model import Model

from src.domain.prediction.value_objects import ChurnProbability
from src.infrastructure.db.duckdb_adapter import get_connection
from src.infrastructure.ml.model_registry import get_model_metadata, load_model
from src.infrastructure.ml.train_churn_model import ALL_FEATURES

logger = get_logger(__name__)

CHURN_MODEL = Model(name="churn_model")


@step(enable_cache=False)
def load_active_customers() -> Annotated[pd.DataFrame, "active_customers"]:
    """
    Load all active customers with their current feature vectors.

    Queries mart_customer_churn_features which already filters to active-only
    (churn_date IS NULL) and contains all 16 model features pre-aggregated
    by dbt. Returns the full feature matrix so score_customers needs no
    second database query.

    enable_cache=False: always fetch fresh customer state before scoring.

    Returns:
        DataFrame with customer_id + 16 feature columns (matches ALL_FEATURES).
    """
    with get_connection() as conn:
        df = conn.execute(
            f"""
            SELECT
                customer_id,
                {", ".join(ALL_FEATURES)}
            FROM marts.mart_customer_churn_features
            """
        ).df()

    log_metadata({"n_active_customers": len(df)})
    logger.info("Loaded %d active customers with features from mart", len(df))
    return df


@step(enable_cache=False)
def score_customers(
    active_customers: pd.DataFrame,
) -> Annotated[pd.DataFrame, "scored_customers"]:
    """
    Score all active customers using the production model.

    Loads the model from model_registry (ZenML MCP → pkl fallback) so the
    inference path is decoupled from how and where the model was stored.
    Attaches model_version to every prediction row for full auditability —
    "which model version scored this customer on this date" is always answerable
    from the predictions table alone.

    Returns:
        DataFrame: customer_id, churn_probability, risk_tier,
                   requires_action, scored_at, model_version.
    """
    model = load_model("churn_model")
    X = active_customers[ALL_FEATURES]
    probabilities = model.predict_proba(X)[:, 1]

    metadata = get_model_metadata("churn_model")
    model_ver_str = str(metadata.get("version", "unknown"))

    scored_at = datetime.now(timezone.utc).isoformat()

    results = pd.DataFrame({
        "customer_id": active_customers["customer_id"].tolist(),
        "churn_probability": probabilities,
        "risk_tier": [
            ChurnProbability(float(p)).risk_tier.value for p in probabilities
        ],
        "requires_action": [
            ChurnProbability(float(p)).requires_immediate_action for p in probabilities
        ],
        "scored_at": scored_at,
        "model_version": model_ver_str,
    })

    n_high_risk = int(results["requires_action"].sum())
    log_metadata({
        "n_scored": len(results),
        "n_high_risk": n_high_risk,
        "pct_high_risk": round(n_high_risk / max(len(results), 1), 4),
        "avg_churn_probability": round(float(probabilities.mean()), 4),
        "model_version": model_ver_str,
    })
    logger.info(
        "Scored %d customers. High-risk (≥0.5): %d (%.1f%%)",
        len(results),
        n_high_risk,
        100 * n_high_risk / max(len(results), 1),
    )
    return results


@step
def write_predictions_to_duckdb(scored_customers: pd.DataFrame) -> None:
    """
    Persist predictions to marts.churn_predictions in DuckDB.

    Each run appends a timestamped batch — historical scores are preserved
    so Superset can show churn risk trends over time. The scored_at column
    lets you reconstruct the risk distribution as of any past scoring date.
    """
    with get_connection(read_only=False) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS marts")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS marts.churn_predictions (
                customer_id       VARCHAR,
                churn_probability DOUBLE,
                risk_tier         VARCHAR,
                requires_action   BOOLEAN,
                scored_at         VARCHAR,
                model_version     VARCHAR
            )
        """)
        conn.register("scored_df", scored_customers)
        conn.execute(
            "INSERT INTO marts.churn_predictions SELECT * FROM scored_df"
        )

    logger.info(
        "Wrote %d predictions to marts.churn_predictions", len(scored_customers)
    )
