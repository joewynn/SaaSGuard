# tests/unit/steps/test_churn_training_steps.py
"""
Unit tests for ZenML training steps.

Steps are tested by calling .entrypoint() directly — no ZenML server, no
DuckDB fixture required for logic tests.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from steps.churn_training_steps import evaluate_model, train_base_pipeline


@pytest.fixture(autouse=True)
def _no_zenml_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent log_metadata from making ZenML server calls during unit tests."""
    monkeypatch.setattr("steps.churn_training_steps.log_metadata", lambda *args, **kwargs: None)


@pytest.fixture
def sample_feature_data() -> tuple[pd.DataFrame, pd.Series]:
    """Minimal feature matrix matching ALL_FEATURES (16 features).

    Column names must match ALL_FEATURES from train_churn_model.py.
    The ColumnTransformer selects by name, so insertion order does not matter.
    plan_tier / industry values outside the OrdinalEncoder's known categories
    are encoded as -1 (unknown) — acceptable for unit tests.
    """
    rng = np.random.default_rng(42)
    n = 200
    X = pd.DataFrame({
        "mrr": rng.uniform(100, 5000, n),
        "plan_tier": rng.choice(["starter", "pro", "enterprise"], n),
        "tenure_days": rng.integers(1, 1000, n),
        "days_since_last_event": rng.integers(0, 90, n),
        "total_events": rng.integers(0, 500, n),
        "events_last_30d": rng.integers(0, 100, n),
        "events_last_7d": rng.integers(0, 50, n),
        "avg_adoption_score": rng.uniform(0, 1, n),
        "retention_signal_count": rng.integers(0, 20, n),
        "tickets_last_30d": rng.integers(0, 10, n),
        "high_priority_tickets": rng.integers(0, 5, n),
        "avg_resolution_hours": rng.uniform(0, 72, n),
        "activated_at_30d": rng.integers(0, 2, n),
        "integration_connects_first_30d": rng.integers(0, 5, n),
        "is_early_stage": rng.integers(0, 2, n),
        "industry": rng.choice(["fintech", "healthcare", "retail"], n),
    })
    y = pd.Series(rng.integers(0, 2, n).astype(int), name="churned")
    return X, y


class TestTrainBasePipeline:
    def test_returns_fitted_pipeline(self, sample_feature_data: tuple) -> None:
        X, y = sample_feature_data
        pipeline = train_base_pipeline.entrypoint(X_train=X, y_train=y)
        proba = pipeline.predict_proba(X)
        assert proba.shape == (len(X), 2)
        assert 0.0 <= proba.min() and proba.max() <= 1.0


class TestEvaluateModel:
    def test_all_required_metric_keys_present(self, sample_feature_data: tuple) -> None:
        from steps.churn_training_steps import calibrate_model

        X, y = sample_feature_data
        base = train_base_pipeline.entrypoint(X_train=X, y_train=y)
        cal = calibrate_model.entrypoint(base_pipeline=base, X_train=X, y_train=y)
        metrics = evaluate_model.entrypoint(calibrated_model=cal, X_test=X, y_test=y)
        required = {"auc_roc", "brier_score", "precision_at_top_decile", "n_test"}
        assert required.issubset(set(metrics.keys()))

    def test_auc_is_within_valid_range(self, sample_feature_data: tuple) -> None:
        from steps.churn_training_steps import calibrate_model

        X, y = sample_feature_data
        base = train_base_pipeline.entrypoint(X_train=X, y_train=y)
        cal = calibrate_model.entrypoint(base_pipeline=base, X_train=X, y_train=y)
        metrics = evaluate_model.entrypoint(calibrated_model=cal, X_test=X, y_test=y)
        assert 0.0 <= metrics["auc_roc"] <= 1.0
