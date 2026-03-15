"""Phase 4 training script – XGBoost churn model.

Builds a point-in-time–correct training dataset from the DuckDB warehouse,
trains a calibrated XGBoost pipeline, evaluates accuracy, and writes
model artifacts to models/.

Usage:
    uv run python -m src.infrastructure.ml.train_churn_model

DVC stage (see DVC/dvc.yaml):
    dvc repro train_churn_model

Outputs:
    models/churn_model.pkl             — sklearn Pipeline artifact
    models/churn_model_metadata.json   — version, metrics, feature list

Design:
    - Feature engineering owned by dbt; training script uses an equivalent
      point-in-time SQL query (not the mart, which filters to active only)
    - Label: is_churned (churned vs. active discriminator — see _load_training_data docstring)
    - Time-based train/test split: train signup < 2025-06-01, test ≥ 2025-06-01
    - CalibratedClassifierCV(cv=5, method='isotonic') wraps the base pipeline
    - SHAP TreeExplainer uses the base pipeline's XGBoost step for attribution
"""

from __future__ import annotations

import json
import os
import pickle
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import shap
import structlog
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder, StandardScaler
from xgboost import XGBClassifier

logger = structlog.get_logger(__name__)

RANDOM_SEED = 42
REFERENCE_DATE = "2026-03-14"
TRAIN_CUTOFF = "2025-06-01"

DB_PATH = os.getenv("DUCKDB_PATH", "data/saasguard.duckdb")
MODELS_DIR = Path(os.getenv("MODELS_DIR", "models"))

NUMERICAL_FEATURES = [
    "mrr",
    "tenure_days",
    "total_events",
    "events_last_30d",
    "events_last_7d",
    "avg_adoption_score",
    "days_since_last_event",
    "retention_signal_count",
    "integration_connects_first_30d",
    "tickets_last_30d",
    "high_priority_tickets",
    "avg_resolution_hours",
    "is_early_stage",
]
CATEGORICAL_FEATURES = ["plan_tier", "industry"]
ALL_FEATURES = NUMERICAL_FEATURES + CATEGORICAL_FEATURES
LABEL_COL = "label"


# ── Data loading ──────────────────────────────────────────────────────────────


def _load_training_data(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Build point-in-time–correct feature matrix for all 5 000 customers.

    Label design — "churned vs. active discriminator":
      This model learns PRE-CHURN SIGNAL PATTERNS (usage decay, ticket spikes,
      low adoption) from labeled historical examples and applies them to active
      customers to score churn risk.

      label = 1  → customer churned (at any time in the dataset)
      label = 0  → customer is still active at REFERENCE_DATE

      Observation date per customer:
        - Churned:  obs_date = churn_date   (features computed AS OF cancellation)
        - Active:   obs_date = REFERENCE_DATE (features computed as of today)

      Point-in-time guarantee: all event/ticket aggregations are windowed to
      [signup_date, obs_date), so no future data leaks into the feature vector.

    Why not a strict "churned_within_90d" forward label?
      That requires choosing one fixed observation date and only capturing the
      ~180 churns in the last 90-day window (≈ 3.6% base rate), which creates
      severe class imbalance and discards 1,300+ informative churned examples.
      The discriminator approach uses all 1,471 churned examples and still
      captures the pre-churn decay patterns that CS teams act on.
      The "90 days" in the product description is the INTERVENTION HORIZON
      communicated to CS teams, not the training label definition.

    Time-based train/test split on signup_date (not obs_date):
      - Train: signup < TRAIN_CUTOFF (2025-06-01) — ~18 months of cohorts
      - Test:  signup ≥ TRAIN_CUTOFF             — ~9 months of cohorts
      Rigid because the data is fixed (RANDOM_SEED=42). This is correct:
      we're validating on customers we'd have seen LATER in a real deployment.

    Returns:
        DataFrame with ALL_FEATURES + label + signup_date columns.
    """
    logger.info("training_data.loading", db_path=DB_PATH)
    return conn.execute(
        f"""
        WITH customer_ref AS (
            SELECT
                customer_id,
                industry,
                plan_tier,
                mrr,
                signup_date::DATE                                               AS signup_date,
                CASE WHEN churn_date IS NOT NULL THEN 1 ELSE 0 END             AS label,
                COALESCE(churn_date::DATE, DATE '{REFERENCE_DATE}')             AS obs_date,
                DATEDIFF(
                    'day',
                    signup_date::DATE,
                    COALESCE(churn_date::DATE, DATE '{REFERENCE_DATE}')
                )                                                               AS tenure_days
            FROM raw.customers
        ),
        event_agg AS (
            SELECT
                e.customer_id,
                COUNT(*)                                                        AS total_events,
                COUNT(*) FILTER (
                    WHERE e.timestamp::DATE >= cr.obs_date - INTERVAL '30 days'
                )                                                               AS events_last_30d,
                COUNT(*) FILTER (
                    WHERE e.timestamp::DATE >= cr.obs_date - INTERVAL '7 days'
                )                                                               AS events_last_7d,
                AVG(e.feature_adoption_score)                                   AS avg_adoption_score,
                COALESCE(
                    DATEDIFF('day', MAX(e.timestamp::DATE), cr.obs_date), 999
                )                                                               AS days_since_last_event,
                COUNT(*) FILTER (
                    WHERE e.event_type IN (
                        'integration_connect', 'api_call', 'monitoring_run'
                    )
                )                                                               AS retention_signal_count,
                COUNT(*) FILTER (
                    WHERE e.event_type = 'integration_connect'
                      AND e.timestamp::DATE <= cr.signup_date + INTERVAL '30 days'
                )                                                               AS integration_connects_first_30d
            FROM raw.usage_events e
            JOIN customer_ref cr USING (customer_id)
            WHERE e.timestamp::DATE < cr.obs_date  -- point-in-time: no look-ahead
            GROUP BY e.customer_id, cr.obs_date, cr.signup_date
        ),
        ticket_agg AS (
            SELECT
                t.customer_id,
                COUNT(*) FILTER (
                    WHERE t.created_date::DATE >= cr.obs_date - INTERVAL '30 days'
                )                                                               AS tickets_last_30d,
                COUNT(*) FILTER (
                    WHERE t.priority IN ('high', 'critical')
                )                                                               AS high_priority_tickets,
                AVG(t.resolution_time)                                          AS avg_resolution_hours
            FROM raw.support_tickets t
            JOIN customer_ref cr USING (customer_id)
            WHERE t.created_date::DATE < cr.obs_date  -- point-in-time
            GROUP BY t.customer_id, cr.obs_date
        )
        SELECT
            cr.customer_id,
            cr.signup_date,
            cr.plan_tier,
            cr.industry,
            cr.mrr,
            cr.tenure_days,
            CASE WHEN cr.tenure_days <= 90 THEN 1 ELSE 0 END                   AS is_early_stage,
            cr.label,
            COALESCE(ea.total_events, 0)                                        AS total_events,
            COALESCE(ea.events_last_30d, 0)                                     AS events_last_30d,
            COALESCE(ea.events_last_7d, 0)                                      AS events_last_7d,
            COALESCE(ea.avg_adoption_score, 0.0)                                AS avg_adoption_score,
            COALESCE(ea.days_since_last_event, 999)                             AS days_since_last_event,
            COALESCE(ea.retention_signal_count, 0)                              AS retention_signal_count,
            COALESCE(ea.integration_connects_first_30d, 0)                     AS integration_connects_first_30d,
            COALESCE(ta.tickets_last_30d, 0)                                    AS tickets_last_30d,
            COALESCE(ta.high_priority_tickets, 0)                               AS high_priority_tickets,
            COALESCE(ta.avg_resolution_hours, 0.0)                              AS avg_resolution_hours
        FROM customer_ref cr
        LEFT JOIN event_agg  ea USING (customer_id)
        LEFT JOIN ticket_agg ta USING (customer_id)
        """
    ).df()


# ── Pipeline construction ─────────────────────────────────────────────────────


def _build_pipeline(scale_pos_weight: float) -> Pipeline:
    """Construct the sklearn Pipeline: preprocessing + XGBoostClassifier.

    Args:
        scale_pos_weight: n_negative / n_positive — corrects class imbalance.

    Returns:
        Unfitted sklearn Pipeline.
    """
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERICAL_FEATURES),
            (
                "cat",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value",
                    unknown_value=-1,
                    categories=[
                        ["starter", "growth", "enterprise"],  # plan_tier
                        ["fintech", "healthtech", "legaltech", "proptech", "saas"],  # industry
                    ],
                ),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )

    xgb = XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
        use_label_encoder=False,
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )

    return Pipeline(steps=[("preprocessor", preprocessor), ("xgboost", xgb)])


# ── Evaluation ────────────────────────────────────────────────────────────────


def _evaluate(
    pipeline: Pipeline,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict[str, float]:
    """Compute AUC-ROC, Brier score, and precision at top decile.

    Args:
        pipeline: Fitted sklearn Pipeline.
        X_test: Test feature matrix.
        y_test: True binary labels.

    Returns:
        Dict with 'auc', 'brier', 'precision_at_decile1' metrics.
    """
    y_proba = pipeline.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_proba)
    brier = brier_score_loss(y_test, y_proba)

    # Precision at top decile: fraction of churners in the top 10% by predicted risk
    n_top = max(1, len(y_test) // 10)
    top_idx = np.argsort(y_proba)[-n_top:]
    precision_at_decile1 = float(y_test.iloc[top_idx].mean())

    logger.info(
        "model.evaluation",
        auc=round(auc, 4),
        brier=round(brier, 4),
        precision_at_decile1=round(precision_at_decile1, 4),
        n_test=len(y_test),
        churn_rate_test=round(float(y_test.mean()), 4),
    )
    return {
        "auc": float(auc),
        "brier": float(brier),
        "precision_at_decile1": float(precision_at_decile1),
    }


def _compute_global_shap(
    pipeline: Pipeline,
    X_sample: pd.DataFrame,
    top_n: int = 10,
) -> list[dict[str, object]]:
    """Compute global SHAP feature importances on a sample of the test set.

    Args:
        pipeline: Fitted pipeline (preprocessor + XGBoost step).
        X_sample: Feature matrix sample for SHAP computation.
        top_n: Number of top features to return.

    Returns:
        List of {feature, mean_abs_shap} dicts, sorted descending.
    """
    preprocessor = pipeline[:-1]
    xgb_model = pipeline[-1]

    X_transformed = preprocessor.transform(X_sample)
    explainer = shap.TreeExplainer(xgb_model)
    shap_values = explainer.shap_values(X_transformed)

    mean_abs = np.abs(shap_values).mean(axis=0)
    ranked = sorted(
        zip(ALL_FEATURES, mean_abs.tolist(), strict=False),
        key=lambda x: x[1],
        reverse=True,
    )
    top_features = [{"feature": f, "mean_abs_shap": round(v, 6)} for f, v in ranked[:top_n]]
    logger.info("shap.global_importance", top_features=top_features[:5])
    return top_features


# ── Main training entry point ─────────────────────────────────────────────────


def train() -> None:
    """Full training pipeline: load → split → train → calibrate → evaluate → save."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("training.started", reference_date=REFERENCE_DATE, seed=RANDOM_SEED)

    conn = duckdb.connect(database=DB_PATH, read_only=True)
    df = _load_training_data(conn)
    conn.close()

    logger.info(
        "training_data.loaded",
        n_rows=len(df),
        churn_rate=round(float(df[LABEL_COL].mean()), 4),
        n_churned=int(df[LABEL_COL].sum()),
        n_active=int((df[LABEL_COL] == 0).sum()),
    )

    # ── Time-based out-of-time split ──────────────────────────────────────────
    train_mask = df["signup_date"] < pd.Timestamp(TRAIN_CUTOFF)
    df_train = df[train_mask].reset_index(drop=True)
    df_test = df[~train_mask].reset_index(drop=True)

    X_train = df_train[ALL_FEATURES]
    y_train = df_train[LABEL_COL]
    X_test = df_test[ALL_FEATURES]
    y_test = df_test[LABEL_COL]

    logger.info(
        "train_test_split",
        n_train=len(df_train),
        n_test=len(df_test),
        train_churn_rate=round(float(y_train.mean()), 4),
        test_churn_rate=round(float(y_test.mean()), 4),
    )

    # ── Build and calibrate pipeline ─────────────────────────────────────────
    n_neg = int((y_train == 0).sum())
    n_pos = int((y_train == 1).sum())
    scale_pos_weight = n_neg / max(n_pos, 1)

    base_pipeline = _build_pipeline(scale_pos_weight=scale_pos_weight)
    base_pipeline.fit(X_train, y_train)

    # Probability calibration via isotonic regression (5-fold CV)
    calibrated = CalibratedClassifierCV(
        estimator=base_pipeline,
        method="isotonic",
        cv=5,
    )
    calibrated.fit(X_train, y_train)

    # ── Evaluate ──────────────────────────────────────────────────────────────
    metrics = _evaluate(calibrated, X_test, y_test)

    # Validate accuracy thresholds
    if metrics["auc"] < 0.80:
        logger.warning("model.auc_below_threshold", auc=metrics["auc"], threshold=0.80)
    if metrics["brier"] > 0.15:
        logger.warning("model.brier_above_threshold", brier=metrics["brier"], threshold=0.15)

    # SHAP on test sample (use base pipeline, not calibrated, for TreeExplainer)
    shap_importance = _compute_global_shap(base_pipeline, X_test.head(500))

    # ── Save artifacts ────────────────────────────────────────────────────────
    model_path = MODELS_DIR / "churn_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(calibrated, f)
    logger.info("model.saved", path=str(model_path))

    metadata = {
        "version": "1.0.0",
        "model_type": "XGBoostClassifier + CalibratedClassifierCV(isotonic, cv=5)",
        "training_date": datetime.now(UTC).isoformat(),
        "training_data_cutoff": TRAIN_CUTOFF,
        "reference_date": REFERENCE_DATE,
        "random_seed": RANDOM_SEED,
        "features": ALL_FEATURES,
        "n_features": len(ALL_FEATURES),
        "n_train": len(df_train),
        "n_test": len(df_test),
        "train_churn_rate": round(float(y_train.mean()), 4),
        "test_churn_rate": round(float(y_test.mean()), 4),
        "scale_pos_weight": round(scale_pos_weight, 4),
        "metrics": metrics,
        "shap_global_importance": shap_importance,
    }
    meta_path = MODELS_DIR / "churn_model_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info("model_metadata.saved", path=str(meta_path), metrics=metrics)

    print("\n" + "=" * 60)
    print("Phase 4 – XGBoost Churn Model Training Complete")
    print("=" * 60)
    print(f"  AUC-ROC:              {metrics['auc']:.4f}  (target > 0.80)")
    print(f"  Brier score:          {metrics['brier']:.4f}  (target < 0.15)")
    print(f"  Precision @decile 1:  {metrics['precision_at_decile1']:.4f}  (target > 0.60)")
    print(f"\n  Artifacts → {MODELS_DIR}/")
    print("    churn_model.pkl")
    print("    churn_model_metadata.json")
    print("=" * 60)


if __name__ == "__main__":
    train()
