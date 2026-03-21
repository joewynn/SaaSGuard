"""Phase 4 model accuracy tests – XGBoost churn model + feature extractor.

All tests skip gracefully if the model artifact has not been trained yet.
Run training first:
    uv run python -m src.infrastructure.ml.train_churn_model

Then re-run:
    pytest tests/model_accuracy/test_churn_model.py -v --no-cov
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import pytest

# ── Module-level skip ────────────────────────────────────────────────────────
# All tests skip if model artifact is absent (TDD: write tests first, then train)
pytestmark = pytest.mark.skipif(
    not Path("models/churn_model.pkl").exists(),
    reason=(
        "Model artifact not found at models/churn_model.pkl. "
        "Train first: uv run python -m src.infrastructure.ml.train_churn_model"
    ),
)

_TEST_DIR = Path(__file__).parent
DB_PATH = str(_TEST_DIR.parent.parent / "data" / "saasguard.duckdb")
REFERENCE_DATE = "2026-03-14"


# ── Mart availability check ────────────────────────────────────────────────────
# The feature extractor queries marts.mart_customer_churn_features, which is
# created by dbt run (inside Docker). This flag gates tests that require it.
def _mart_available() -> bool:
    try:
        conn = duckdb.connect(DB_PATH, read_only=True)
        conn.execute("SELECT 1 FROM marts.mart_customer_churn_features LIMIT 1")
        conn.close()
        return True
    except Exception:
        return False


_MART_AVAILABLE = _mart_available()
_MART_SKIP = pytest.mark.skipif(
    not _MART_AVAILABLE,
    reason=(
        "marts.mart_customer_churn_features not found. "
        "Run dbt first: docker compose exec dbt dbt run --select mart_customer_churn_features"
    ),
)

# Canonical feature key set (matches ChurnFeatureExtractor output)
EXPECTED_FEATURE_KEYS: set[str] = {
    "mrr",
    "tenure_days",
    "total_events",
    "events_last_30d",
    "events_last_7d",
    "avg_adoption_score",
    "days_since_last_event",
    "retention_signal_count",
    "tickets_last_30d",
    "high_priority_tickets",
    "avg_resolution_hours",
    "integration_connects_first_30d",
    "plan_tier",
    "industry",
    "is_early_stage",
}


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def conn() -> duckdb.DuckDBPyConnection:  # type: ignore[misc]
    """Read-only DuckDB connection, scoped to the module."""
    connection = duckdb.connect(DB_PATH, read_only=True)
    yield connection  # type: ignore[misc]
    connection.close()


@pytest.fixture(scope="module")
def active_customer_id(conn: duckdb.DuckDBPyConnection) -> str:
    """One active customer_id for inference-path tests."""
    row = conn.execute("SELECT customer_id FROM raw.customers WHERE churn_date IS NULL LIMIT 1").fetchone()
    assert row is not None, "No active customers found in DuckDB."
    return str(row[0])


@pytest.fixture(scope="module")
def test_df(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Held-out test split: customers who signed up on/after 2025-06-01.

    Same point-in-time construction as the training script for an
    apples-to-apples evaluation.
    """
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
            WHERE signup_date::DATE >= DATE '2025-06-01'
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
            JOIN customer_ref cr ON e.customer_id = cr.customer_id
            WHERE e.timestamp::DATE < cr.obs_date
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
            JOIN customer_ref cr ON t.customer_id = cr.customer_id
            WHERE t.created_date::DATE < cr.obs_date
            GROUP BY t.customer_id, cr.obs_date
        )
        SELECT
            cr.customer_id,
            cr.industry,
            cr.plan_tier,
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


@pytest.fixture(scope="module")
def model_metadata() -> dict[str, Any]:
    """Model metadata JSON (version, training date, metrics)."""
    from src.infrastructure.ml.model_registry import get_model_metadata

    return get_model_metadata("churn_model")


# ── Feature Extractor Tests ───────────────────────────────────────────────────


@_MART_SKIP
class TestChurnFeatureExtractor:
    """Validate ChurnFeatureExtractor schema and types.

    The extractor queries mart_customer_churn_features directly, so tests
    require dbt to have been run (marts schema must exist in DuckDB).
    """

    def test_feature_extractor_returns_correct_keys(self, active_customer_id: str) -> None:
        """extract() output must contain exactly the 15 expected feature keys."""
        from src.infrastructure.ml.churn_feature_extractor import ChurnFeatureExtractor
        from src.infrastructure.repositories.customer_repository import (
            DuckDBCustomerRepository,
        )

        customer = DuckDBCustomerRepository().get_by_id(active_customer_id)
        assert customer is not None

        features = ChurnFeatureExtractor().extract(customer)

        missing = EXPECTED_FEATURE_KEYS - set(features.keys())
        extra = set(features.keys()) - EXPECTED_FEATURE_KEYS
        assert not missing and not extra, f"Key mismatch — missing: {missing}, extra: {extra}"

    def test_feature_extractor_returns_numeric_values(self, active_customer_id: str) -> None:
        """Numeric features must be int/float (no NaN); categorical features must be non-empty str.

        plan_tier and industry are returned as raw strings for the OrdinalEncoder
        to handle — changing them to floats would break the XGBoost pipeline.
        """
        from src.infrastructure.ml.churn_feature_extractor import ChurnFeatureExtractor
        from src.infrastructure.repositories.customer_repository import (
            DuckDBCustomerRepository,
        )

        # Features deliberately returned as strings for the OrdinalEncoder
        CATEGORICAL_FEATURES = {"plan_tier", "industry"}

        customer = DuckDBCustomerRepository().get_by_id(active_customer_id)
        assert customer is not None

        features = ChurnFeatureExtractor().extract(customer)

        for name, value in features.items():
            if name in CATEGORICAL_FEATURES:
                assert isinstance(value, str) and value, (
                    f"Categorical feature '{name}' must be a non-empty string, got {value!r}"
                )
            else:
                assert isinstance(value, (int, float)), (
                    f"Feature '{name}' has non-numeric type {type(value).__name__}: {value!r}"
                )
                assert not (isinstance(value, float) and np.isnan(value)), (
                    f"Feature '{name}' is NaN — check mart COALESCE defaults."
                )


# ── XGBoost Model Inference Tests ────────────────────────────────────────────


@_MART_SKIP
class TestXGBoostChurnModel:
    """Validate XGBoostChurnModel inference and SHAP explainability."""

    def test_predict_proba_in_range(self, active_customer_id: str) -> None:
        """predict_proba() must return P(churn) ∈ [0, 1]."""
        from src.infrastructure.ml.churn_feature_extractor import ChurnFeatureExtractor
        from src.infrastructure.ml.xgboost_churn_model import XGBoostChurnModel
        from src.infrastructure.repositories.customer_repository import (
            DuckDBCustomerRepository,
        )

        customer = DuckDBCustomerRepository().get_by_id(active_customer_id)
        assert customer is not None

        features = ChurnFeatureExtractor().extract(customer)
        prob = XGBoostChurnModel().predict_proba(features)

        assert 0.0 <= prob <= 1.0, f"Probability out of range: {prob}"

    def test_explain_returns_shap_features(self, active_customer_id: str) -> None:
        """explain() must return a list of ≥ 5 ShapFeature objects."""
        from src.domain.prediction.entities import ShapFeature
        from src.infrastructure.ml.churn_feature_extractor import ChurnFeatureExtractor
        from src.infrastructure.ml.xgboost_churn_model import XGBoostChurnModel
        from src.infrastructure.repositories.customer_repository import (
            DuckDBCustomerRepository,
        )

        customer = DuckDBCustomerRepository().get_by_id(active_customer_id)
        assert customer is not None

        features = ChurnFeatureExtractor().extract(customer)
        shap_features = XGBoostChurnModel().explain(features)

        assert len(shap_features) >= 5, f"Only {len(shap_features)} SHAP features returned, expected ≥ 5."
        assert all(isinstance(sf, ShapFeature) for sf in shap_features)


# ── Model Accuracy Tests ──────────────────────────────────────────────────────


class TestModelAccuracy:
    """Accuracy metrics on the held-out out-of-time test set."""

    _FEATURE_COLS = [
        "mrr",
        "tenure_days",
        "total_events",
        "events_last_30d",
        "events_last_7d",
        "avg_adoption_score",
        "days_since_last_event",
        "retention_signal_count",
        "tickets_last_30d",
        "high_priority_tickets",
        "avg_resolution_hours",
        "integration_connects_first_30d",
        "plan_tier",
        "industry",
        "is_early_stage",
    ]

    def _pipeline(self) -> Any:
        from src.infrastructure.ml.model_registry import load_model

        return load_model("churn_model")

    def test_model_auc_above_threshold(self, test_df: pd.DataFrame) -> None:
        """AUC-ROC on out-of-time test set must exceed 0.80.

        Business context: AUC < 0.80 means the model cannot reliably rank at-risk
        customers above safe ones — the core requirement for CS prioritisation.
        """
        from sklearn.metrics import roc_auc_score

        pipeline = self._pipeline()
        X_test = test_df[self._FEATURE_COLS]
        y_test = test_df["label"]

        y_proba = pipeline.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, y_proba)

        assert auc > 0.80, f"AUC-ROC = {auc:.4f} < 0.80. Model discrimination is below the production threshold."

    def test_model_brier_score_below_threshold(self, test_df: pd.DataFrame) -> None:
        """Brier score must be below 0.15 — validates probability calibration.

        Business context: CS teams need calibrated probabilities so risk tiers
        (CRITICAL / HIGH / MEDIUM / LOW) map reliably to actual churn rates.
        An uncalibrated model causes CS alert fatigue.
        """
        from sklearn.metrics import brier_score_loss

        pipeline = self._pipeline()
        X_test = test_df[self._FEATURE_COLS]
        y_test = test_df["label"]

        y_proba = pipeline.predict_proba(X_test)[:, 1]
        brier = brier_score_loss(y_test, y_proba)

        assert brier < 0.15, f"Brier score = {brier:.4f} ≥ 0.15. Probabilities are poorly calibrated."

    def test_model_calibration_by_tier(self, test_df: pd.DataFrame, conn: duckdb.DuckDBPyConnection) -> None:
        """Predicted churn rate per plan tier must be within 15pp of KM 1-year estimate.

        Ties the model output to the Phase 3 survival analysis baseline — the key
        business trust signal for CS leadership.
        """
        from lifelines import KaplanMeierFitter

        pipeline = self._pipeline()
        X_test = test_df[self._FEATURE_COLS]
        y_proba = pipeline.predict_proba(X_test)[:, 1]
        enriched = test_df.assign(predicted_prob=y_proba)

        survival_df = conn.execute(
            f"""
            SELECT
                plan_tier,
                CASE WHEN churn_date IS NOT NULL THEN 1 ELSE 0 END AS event,
                DATEDIFF(
                    'day',
                    signup_date::DATE,
                    COALESCE(churn_date::DATE, DATE '{REFERENCE_DATE}')
                ) AS duration_days
            FROM raw.customers
            """
        ).df()

        kmf = KaplanMeierFitter()
        tolerance = 0.15  # 15pp — accounts for test-set size and synthetic-data variance

        for tier in ["starter", "growth", "enterprise"]:
            tier_survival = survival_df[survival_df["plan_tier"] == tier]
            kmf.fit(tier_survival["duration_days"], event_observed=tier_survival["event"])
            km_churn_rate = 1.0 - float(kmf.predict(365))

            tier_preds = enriched[enriched["plan_tier"] == tier]["predicted_prob"]
            if len(tier_preds) == 0:
                continue
            model_churn_rate = float(tier_preds.mean())

            gap = abs(model_churn_rate - km_churn_rate)
            assert gap <= tolerance, (
                f"Tier '{tier}': model avg P(churn)={model_churn_rate:.3f}, "
                f"KM 1-yr churn rate={km_churn_rate:.3f}, gap={gap:.3f} > {tolerance}"
            )

    def test_top_shap_features_are_known_signals(self, test_df: pd.DataFrame) -> None:
        """Top 2 global SHAP features must include at least one known churn signal.

        Phase 3 validated events_last_30d, avg_adoption_score, retention_signal_count,
        and days_since_last_event as the strongest predictors. If the model's top
        features diverge, it may be learning spurious correlations.
        """
        import shap as shap_lib

        calibrated = self._pipeline()
        sample = test_df[self._FEATURE_COLS].head(200)  # limit for speed

        # CalibratedClassifierCV wraps the base pipeline; access via first fold
        base_pipeline = calibrated.calibrated_classifiers_[0].estimator
        preprocessor = base_pipeline[:-1]
        xgb_model = base_pipeline[-1]

        X_transformed = preprocessor.transform(sample)
        explainer = shap_lib.TreeExplainer(xgb_model)
        shap_values = explainer.shap_values(X_transformed)

        mean_abs = np.abs(shap_values).mean(axis=0)
        top_2_idx = set(np.argsort(mean_abs)[-2:].tolist())
        top_2_features = {self._FEATURE_COLS[i] for i in top_2_idx}

        known_signals = {
            "events_last_30d",
            "avg_adoption_score",
            "retention_signal_count",
            "days_since_last_event",
            "high_priority_tickets",
        }
        assert len(top_2_features & known_signals) >= 1, (
            f"Top 2 SHAP features {top_2_features} don't overlap with known signals {known_signals}."
        )


# ── API Endpoint Test ─────────────────────────────────────────────────────────


@_MART_SKIP
class TestChurnPredictionAPI:
    """End-to-end test of POST /predictions/churn via FastAPI TestClient."""

    def test_predict_churn_endpoint_returns_200(self, active_customer_id: str) -> None:
        """POST /predictions/churn returns 200 with the correct response schema."""
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            response = client.post(
                "/predictions/churn",
                json={"customer_id": active_customer_id},
            )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "churn_probability" in data
        assert "risk_tier" in data
        assert "top_shap_features" in data
        assert "recommended_action" in data
        assert "model_version" in data
        assert 0.0 <= data["churn_probability"] <= 1.0
        assert data["risk_tier"] in {"low", "medium", "high", "critical"}
