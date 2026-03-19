"""Expansion propensity training script — XGBoost upgrade model.

Builds a point-in-time–correct training dataset from DuckDB, trains a calibrated
XGBoost pipeline targeting is_upgraded, evaluates accuracy, and writes artifacts.

Usage:
    uv run python -m src.infrastructure.ml.train_expansion_model

Outputs:
    models/expansion_model.pkl             — sklearn Pipeline artifact
    models/expansion_model_metadata.json   — version, metrics, feature list

Label design — "upgraded vs. active discriminator":
    label = 1  → customer upgraded (upgrade_date IS NOT NULL)
    label = 0  → customer is still active at REFERENCE_DATE, never upgraded

    Observation date per customer:
        - Upgraded:  obs_date = upgrade_date  (features AS OF upgrade)
        - Active:    obs_date = REFERENCE_DATE

    Point-in-time guarantee: all event/ticket aggregations windowed to
    [signup_date, obs_date), so no future data leaks into the feature vector.

Leakage guard:
    has_open_expansion_opp is included but its SHAP rank is checked after training.
    If it dominates (rank #1), it may indicate Sales opps are being created in
    response to usage signals the model should be discovering independently.
    See notebooks/expansion_propensity_modeling.ipynb Section 5.
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
    # Expansion-specific
    "premium_feature_trials_30d",
    "feature_request_tickets_90d",
    "has_open_expansion_opp",
    "expansion_opp_amount",
    "mrr_tier_ceiling_pct",
]
CATEGORICAL_FEATURES = ["plan_tier", "industry"]
ALL_FEATURES = NUMERICAL_FEATURES + CATEGORICAL_FEATURES
LABEL_COL = "label"

# Acceptance thresholds (per plan)
AUC_THRESHOLD = 0.75
BRIER_THRESHOLD = 0.10


# ── Data loading ──────────────────────────────────────────────────────────────


def _load_training_data(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Build point-in-time–correct feature matrix for all 5,000 customers.

    For upgraded customers, features are computed as of upgrade_date.
    For active non-upgraded customers, features are as of REFERENCE_DATE.
    Churned customers are EXCLUDED — they are not expansion candidates.

    Returns:
        DataFrame with ALL_FEATURES + label + signup_date columns.
    """
    logger.info("expansion_training_data.loading", db_path=DB_PATH)
    return conn.execute(
        f"""
        WITH customer_ref AS (
            SELECT
                customer_id,
                industry,
                plan_tier,
                mrr,
                signup_date::DATE                                                   AS signup_date,
                CASE WHEN upgrade_date IS NOT NULL THEN 1 ELSE 0 END               AS label,
                COALESCE(upgrade_date::DATE, DATE '{REFERENCE_DATE}')               AS obs_date,
                DATEDIFF(
                    'day',
                    signup_date::DATE,
                    COALESCE(upgrade_date::DATE, DATE '{REFERENCE_DATE}')
                )                                                                   AS tenure_days
            FROM raw.customers
            WHERE churn_date IS NULL   -- exclude churned customers
        ),
        event_agg AS (
            SELECT
                e.customer_id,
                COUNT(*)                                                            AS total_events,
                COUNT(*) FILTER (
                    WHERE e.timestamp::DATE >= cr.obs_date - INTERVAL '30 days'
                )                                                                   AS events_last_30d,
                COUNT(*) FILTER (
                    WHERE e.timestamp::DATE >= cr.obs_date - INTERVAL '7 days'
                )                                                                   AS events_last_7d,
                AVG(e.feature_adoption_score)                                       AS avg_adoption_score,
                COALESCE(
                    DATEDIFF('day', MAX(e.timestamp::DATE), cr.obs_date), 999
                )                                                                   AS days_since_last_event,
                COUNT(*) FILTER (
                    WHERE e.event_type IN (
                        'integration_connect', 'api_call', 'monitoring_run'
                    )
                )                                                                   AS retention_signal_count,
                COUNT(*) FILTER (
                    WHERE e.event_type = 'integration_connect'
                      AND e.timestamp::DATE <= cr.signup_date + INTERVAL '30 days'
                )                                                                   AS integration_connects_first_30d,
                COUNT(*) FILTER (
                    WHERE e.event_type = 'premium_feature_trial'
                      AND e.timestamp::DATE >= cr.obs_date - INTERVAL '30 days'
                )                                                                   AS premium_feature_trials_30d
            FROM raw.usage_events e
            JOIN customer_ref cr USING (customer_id)
            WHERE e.timestamp::DATE < cr.obs_date  -- point-in-time
            GROUP BY e.customer_id, cr.obs_date, cr.signup_date
        ),
        ticket_agg AS (
            SELECT
                t.customer_id,
                COUNT(*) FILTER (
                    WHERE t.created_date::DATE >= cr.obs_date - INTERVAL '30 days'
                )                                                                   AS tickets_last_30d,
                COUNT(*) FILTER (
                    WHERE t.priority IN ('high', 'critical')
                )                                                                   AS high_priority_tickets,
                AVG(t.resolution_time)                                              AS avg_resolution_hours,
                COUNT(*) FILTER (
                    WHERE t.topic = 'feature_request'
                      AND t.created_date::DATE >= cr.obs_date - INTERVAL '90 days'
                )                                                                   AS feature_request_tickets_90d
            FROM raw.support_tickets t
            JOIN customer_ref cr USING (customer_id)
            WHERE t.created_date::DATE < cr.obs_date  -- point-in-time
            GROUP BY t.customer_id, cr.obs_date
        ),
        expansion_opp_agg AS (
            SELECT
                o.customer_id,
                MAX(CASE
                    WHEN o.opportunity_type = 'expansion'
                     AND o.stage NOT IN ('closed_won', 'closed_lost')
                    THEN 1 ELSE 0
                END)::BOOLEAN                                                       AS has_open_expansion_opp,
                COALESCE(SUM(
                    CASE
                        WHEN o.opportunity_type = 'expansion'
                         AND o.stage NOT IN ('closed_won', 'closed_lost')
                        THEN CAST(o.amount AS FLOAT) ELSE 0
                    END
                ), 0.0)                                                             AS expansion_opp_amount
            FROM raw.gtm_opportunities o
            GROUP BY o.customer_id
        )
        SELECT
            cr.customer_id,
            cr.signup_date,
            cr.plan_tier,
            cr.industry,
            cr.mrr,
            cr.tenure_days,
            CASE WHEN cr.tenure_days <= 90 THEN 1 ELSE 0 END                       AS is_early_stage,
            cr.label,
            COALESCE(ea.total_events, 0)                                            AS total_events,
            COALESCE(ea.events_last_30d, 0)                                         AS events_last_30d,
            COALESCE(ea.events_last_7d, 0)                                          AS events_last_7d,
            COALESCE(ea.avg_adoption_score, 0.0)                                    AS avg_adoption_score,
            COALESCE(ea.days_since_last_event, 999)                                 AS days_since_last_event,
            COALESCE(ea.retention_signal_count, 0)                                  AS retention_signal_count,
            COALESCE(ea.integration_connects_first_30d, 0)                         AS integration_connects_first_30d,
            COALESCE(ea.premium_feature_trials_30d, 0)                              AS premium_feature_trials_30d,
            COALESCE(ta.tickets_last_30d, 0)                                        AS tickets_last_30d,
            COALESCE(ta.high_priority_tickets, 0)                                   AS high_priority_tickets,
            COALESCE(ta.avg_resolution_hours, 0.0)                                  AS avg_resolution_hours,
            COALESCE(ta.feature_request_tickets_90d, 0)                             AS feature_request_tickets_90d,
            COALESCE(eo.has_open_expansion_opp, FALSE)::INT                         AS has_open_expansion_opp,
            COALESCE(eo.expansion_opp_amount, 0.0)                                  AS expansion_opp_amount,
            -- Tier ceiling pressure
            CASE cr.plan_tier
                WHEN 'starter'    THEN LEAST(1.0, GREATEST(0.0,
                    (cr.mrr - 500.0)   / (2000.0  - 500.0)))
                WHEN 'growth'     THEN LEAST(1.0, GREATEST(0.0,
                    (cr.mrr - 2000.0)  / (8000.0  - 2000.0)))
                WHEN 'enterprise' THEN LEAST(1.0, GREATEST(0.0,
                    (cr.mrr - 8000.0)  / (50000.0 - 8000.0)))
                ELSE 0.0
            END                                                                     AS mrr_tier_ceiling_pct
        FROM customer_ref cr
        LEFT JOIN event_agg          ea USING (customer_id)
        LEFT JOIN ticket_agg         ta USING (customer_id)
        LEFT JOIN expansion_opp_agg  eo USING (customer_id)
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
                        ["starter", "growth", "enterprise", "custom"],  # plan_tier
                        [
                            "fintech", "healthtech", "legaltech", "hr tech",
                            "edtech", "insurtech", "proptech", "retailtech", "other",
                        ],  # industry
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
    """Compute AUC-ROC, Brier score, and precision at top decile."""
    y_proba = pipeline.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_proba)
    brier = brier_score_loss(y_test, y_proba)

    n_top = max(1, len(y_test) // 10)
    top_idx = np.argsort(y_proba)[-n_top:]
    precision_at_decile1 = float(y_test.iloc[top_idx].mean())

    logger.info(
        "expansion_model.evaluation",
        auc=round(auc, 4),
        brier=round(brier, 4),
        precision_at_decile1=round(precision_at_decile1, 4),
        n_test=len(y_test),
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
    """Compute global SHAP feature importances."""
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

    # Leakage guard: warn if Sales Opp signal dominates
    if top_features and top_features[0]["feature"] == "has_open_expansion_opp":
        logger.warning(
            "expansion_model.shap_leakage_risk",
            message=(
                "has_open_expansion_opp is the #1 SHAP feature. "
                "This may indicate Sales opps are lagging responses to usage signals. "
                "Consider retraining without this feature and comparing AUC."
            ),
        )

    logger.info("expansion_shap.global_importance", top_features=top_features[:5])
    return top_features


# ── Main training entry point ─────────────────────────────────────────────────


def train() -> None:
    """Full expansion model training pipeline: load → split → train → calibrate → save."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("expansion_training.started", reference_date=REFERENCE_DATE, seed=RANDOM_SEED)

    conn = duckdb.connect(database=DB_PATH, read_only=True)
    df = _load_training_data(conn)
    conn.close()

    logger.info(
        "expansion_training_data.loaded",
        n_rows=len(df),
        upgrade_rate=round(float(df[LABEL_COL].mean()), 4),
        n_upgraded=int(df[LABEL_COL].sum()),
        n_not_upgraded=int((df[LABEL_COL] == 0).sum()),
    )

    # Time-based out-of-time split
    train_mask = df["signup_date"] < pd.Timestamp(TRAIN_CUTOFF)
    df_train = df[train_mask].reset_index(drop=True)
    df_test = df[~train_mask].reset_index(drop=True)

    X_train = df_train[ALL_FEATURES]
    y_train = df_train[LABEL_COL]
    X_test = df_test[ALL_FEATURES]
    y_test = df_test[LABEL_COL]

    # Build and calibrate pipeline
    n_neg = int((y_train == 0).sum())
    n_pos = int((y_train == 1).sum())
    scale_pos_weight = n_neg / max(n_pos, 1)

    base_pipeline = _build_pipeline(scale_pos_weight=scale_pos_weight)
    base_pipeline.fit(X_train, y_train)

    calibrated = CalibratedClassifierCV(estimator=base_pipeline, method="isotonic", cv=5)
    calibrated.fit(X_train, y_train)

    # Evaluate
    metrics = _evaluate(calibrated, X_test, y_test)

    if metrics["auc"] < AUC_THRESHOLD:
        logger.warning(
            "expansion_model.auc_below_threshold",
            auc=metrics["auc"],
            threshold=AUC_THRESHOLD,
        )
    if metrics["brier"] > BRIER_THRESHOLD:
        logger.warning(
            "expansion_model.brier_above_threshold",
            brier=metrics["brier"],
            threshold=BRIER_THRESHOLD,
        )

    shap_importance = _compute_global_shap(base_pipeline, X_test.head(500))

    # Save artifacts
    model_path = MODELS_DIR / "expansion_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(calibrated, f)
    logger.info("expansion_model.saved", path=str(model_path))

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
        "upgrade_rate_train": round(float(y_train.mean()), 4),
        "upgrade_rate_test": round(float(y_test.mean()), 4),
        "scale_pos_weight": round(scale_pos_weight, 4),
        "acceptance_thresholds": {"auc_min": AUC_THRESHOLD, "brier_max": BRIER_THRESHOLD},
        "metrics": metrics,
        "shap_global_importance": shap_importance,
    }
    meta_path = MODELS_DIR / "expansion_model_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info("expansion_model_metadata.saved", path=str(meta_path), metrics=metrics)

    print("\n" + "=" * 60)
    print("Expansion Propensity Model Training Complete")
    print("=" * 60)
    print(f"  AUC-ROC:              {metrics['auc']:.4f}  (target > {AUC_THRESHOLD})")
    print(f"  Brier score:          {metrics['brier']:.4f}  (target < {BRIER_THRESHOLD})")
    print(f"  Precision @decile 1:  {metrics['precision_at_decile1']:.4f}")
    print(f"\n  Artifacts → {MODELS_DIR}/")
    print("    expansion_model.pkl")
    print("    expansion_model_metadata.json")
    print("=" * 60)


if __name__ == "__main__":
    train()
