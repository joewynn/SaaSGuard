# tests/unit/steps/test_churn_inference_steps.py
"""
Unit tests for ZenML batch inference steps.

Steps are tested by calling .entrypoint() directly — no ZenML server, no
real DuckDB connection required for logic tests.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.infrastructure.ml.train_churn_model import ALL_FEATURES


@pytest.fixture(autouse=True)
def _no_zenml_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent log_metadata from making ZenML server calls during unit tests."""
    monkeypatch.setattr(
        "steps.churn_inference_steps.log_metadata", lambda *args, **kwargs: None
    )


@pytest.fixture
def sample_active_customers() -> pd.DataFrame:
    """Feature matrix for 10 active customers, matching ALL_FEATURES column order."""
    rng = np.random.default_rng(0)
    n = 10
    data = {
        "customer_id": [f"C{i:03d}" for i in range(n)],
        "mrr": rng.uniform(500, 5000, n),
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
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_scored() -> pd.DataFrame:
    """Pre-scored DataFrame matching the output of score_customers."""
    return pd.DataFrame({
        "customer_id": ["C001", "C002", "C003"],
        "churn_probability": [0.9, 0.3, 0.6],
        "risk_tier": ["critical", "low", "high"],
        "requires_action": [True, False, True],
        "scored_at": ["2026-05-16T00:00:00+00:00"] * 3,
        "model_version": ["2026.05.16"] * 3,
    })


class TestLoadActiveCustomers:
    def test_returns_dataframe(self) -> None:
        from steps.churn_inference_steps import load_active_customers

        sample_df = pd.DataFrame({
            "customer_id": ["C001", "C002"],
            **{f: [0.0, 0.0] for f in ALL_FEATURES},
        })
        mock_conn = MagicMock()
        mock_conn.execute.return_value.df.return_value = sample_df
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("steps.churn_inference_steps.get_connection", return_value=mock_ctx):
            result = load_active_customers.entrypoint()

        assert isinstance(result, pd.DataFrame)
        assert "customer_id" in result.columns

    def test_logs_customer_count(self) -> None:
        from steps.churn_inference_steps import load_active_customers

        sample_df = pd.DataFrame({
            "customer_id": ["C001", "C002", "C003"],
            **{f: [0.0, 0.0, 0.0] for f in ALL_FEATURES},
        })
        mock_conn = MagicMock()
        mock_conn.execute.return_value.df.return_value = sample_df
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        logged: dict = {}

        def _capture_metadata(d: dict, **_: object) -> None:
            logged.update(d)

        with patch("steps.churn_inference_steps.get_connection", return_value=mock_ctx), \
             patch("steps.churn_inference_steps.log_metadata", side_effect=_capture_metadata):
            load_active_customers.entrypoint()

        assert logged.get("n_active_customers") == 3


class TestScoreCustomers:
    def test_output_has_required_columns(self, sample_active_customers: pd.DataFrame) -> None:
        from steps.churn_inference_steps import score_customers

        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.column_stack([
            np.zeros(len(sample_active_customers)),
            np.ones(len(sample_active_customers)) * 0.7,
        ])

        with patch("steps.churn_inference_steps.load_model", return_value=mock_model), \
             patch("steps.churn_inference_steps.get_model_metadata", return_value={"version": "2026.05.16"}):
            result = score_customers.entrypoint(active_customers=sample_active_customers)

        required = {"customer_id", "churn_probability", "risk_tier", "requires_action", "scored_at", "model_version"}
        assert required.issubset(set(result.columns))

    def test_high_probability_triggers_action(self, sample_active_customers: pd.DataFrame) -> None:
        from steps.churn_inference_steps import score_customers

        # All customers at 0.9 probability → all require action
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.column_stack([
            np.full(len(sample_active_customers), 0.1),
            np.full(len(sample_active_customers), 0.9),
        ])

        with patch("steps.churn_inference_steps.load_model", return_value=mock_model), \
             patch("steps.churn_inference_steps.get_model_metadata", return_value={"version": "2026.05.16"}):
            result = score_customers.entrypoint(active_customers=sample_active_customers)

        assert result["requires_action"].all()

    def test_low_probability_does_not_trigger_action(self, sample_active_customers: pd.DataFrame) -> None:
        from steps.churn_inference_steps import score_customers

        # All customers at 0.1 probability → none require action
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.column_stack([
            np.full(len(sample_active_customers), 0.9),
            np.full(len(sample_active_customers), 0.1),
        ])

        with patch("steps.churn_inference_steps.load_model", return_value=mock_model), \
             patch("steps.churn_inference_steps.get_model_metadata", return_value={"version": "2026.05.16"}):
            result = score_customers.entrypoint(active_customers=sample_active_customers)

        assert not result["requires_action"].any()

    def test_row_count_matches_input(self, sample_active_customers: pd.DataFrame) -> None:
        from steps.churn_inference_steps import score_customers

        n = len(sample_active_customers)
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.column_stack([
            np.full(n, 0.5),
            np.full(n, 0.5),
        ])

        with patch("steps.churn_inference_steps.load_model", return_value=mock_model), \
             patch("steps.churn_inference_steps.get_model_metadata", return_value={"version": "2026.05.16"}):
            result = score_customers.entrypoint(active_customers=sample_active_customers)

        assert len(result) == n

    def test_risk_tier_values_are_valid(self, sample_active_customers: pd.DataFrame) -> None:
        from steps.churn_inference_steps import score_customers

        rng = np.random.default_rng(1)
        n = len(sample_active_customers)
        probs = rng.uniform(0, 1, n)
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.column_stack([1 - probs, probs])

        with patch("steps.churn_inference_steps.load_model", return_value=mock_model), \
             patch("steps.churn_inference_steps.get_model_metadata", return_value={"version": "2026.05.16"}):
            result = score_customers.entrypoint(active_customers=sample_active_customers)

        valid_tiers = {"low", "medium", "high", "critical"}
        assert set(result["risk_tier"].unique()).issubset(valid_tiers)


class TestWritePredictionsToDuckdb:
    def test_creates_schema_and_table(self, sample_scored: pd.DataFrame) -> None:
        from steps.churn_inference_steps import write_predictions_to_duckdb

        mock_conn = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("steps.churn_inference_steps.get_connection", return_value=mock_ctx):
            write_predictions_to_duckdb.entrypoint(scored_customers=sample_scored)

        calls = [str(c) for c in mock_conn.execute.call_args_list]
        # Schema and table creation + register + insert should all be called
        assert mock_conn.execute.called
        assert mock_conn.register.called

    def test_registers_dataframe_before_insert(self, sample_scored: pd.DataFrame) -> None:
        from steps.churn_inference_steps import write_predictions_to_duckdb

        mock_conn = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("steps.churn_inference_steps.get_connection", return_value=mock_ctx):
            write_predictions_to_duckdb.entrypoint(scored_customers=sample_scored)

        # register() is called with the DataFrame before INSERT
        mock_conn.register.assert_called_once()
        registered_df = mock_conn.register.call_args[0][1]
        assert isinstance(registered_df, pd.DataFrame)
        assert len(registered_df) == len(sample_scored)
