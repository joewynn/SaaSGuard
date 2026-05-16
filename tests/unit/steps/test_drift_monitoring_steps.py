# tests/unit/steps/test_drift_monitoring_steps.py
"""
Unit tests for ZenML drift monitoring steps.

Steps are tested by calling .entrypoint() directly — no ZenML server, no
real DuckDB connection, no baseline JSON file required for logic tests.
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _no_zenml_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent log_metadata from making ZenML server calls during unit tests."""
    monkeypatch.setattr(
        "steps.drift_monitoring_steps.log_metadata", lambda *args, **kwargs: None
    )


@pytest.fixture
def no_drift_report() -> dict:
    return {
        "has_drift": False,
        "max_psi": 0.05,
        "min_ks_pvalue": 0.31,
        "drifted_features": [],
        "checked_at": "2026-05-16T06:00:00+00:00",
        "features": [],
    }


@pytest.fixture
def drift_report() -> dict:
    return {
        "has_drift": True,
        "max_psi": 0.28,
        "min_ks_pvalue": 0.01,
        "drifted_features": ["mrr", "tenure_days"],
        "checked_at": "2026-05-16T06:00:00+00:00",
        "features": [],
    }


@pytest.fixture
def sample_features() -> pd.DataFrame:
    return pd.DataFrame({
        "mrr": [1000.0, 2000.0, 3000.0],
        "tenure_days": [30.0, 60.0, 90.0],
    })


class TestLoadCurrentFeatures:
    def test_returns_dataframe(self) -> None:
        from steps.drift_monitoring_steps import load_current_features

        sample_df = pd.DataFrame({"mrr": [1000.0], "tenure_days": [30.0]})
        mock_conn = MagicMock()
        mock_conn.execute.return_value.df.return_value = sample_df
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("steps.drift_monitoring_steps.get_connection", return_value=mock_ctx):
            result = load_current_features.entrypoint()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    def test_logs_row_count(self) -> None:
        from steps.drift_monitoring_steps import load_current_features

        sample_df = pd.DataFrame({"mrr": [1000.0, 2000.0]})
        mock_conn = MagicMock()
        mock_conn.execute.return_value.df.return_value = sample_df
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        logged: dict = {}

        def _capture(d: dict, **_: object) -> None:
            logged.update(d)

        with patch("steps.drift_monitoring_steps.get_connection", return_value=mock_ctx), \
             patch("steps.drift_monitoring_steps.log_metadata", side_effect=_capture):
            load_current_features.entrypoint()

        assert logged.get("n_current_rows") == 2


class TestComputeDriftReport:
    def _make_mock_detector(self, report_dict: dict) -> MagicMock:
        mock_report = MagicMock()
        mock_report.to_dict.return_value = report_dict
        mock_detector_instance = MagicMock()
        mock_detector_instance.run.return_value = mock_report
        return mock_detector_instance

    def test_returns_dict_with_required_keys(
        self, sample_features: pd.DataFrame, no_drift_report: dict
    ) -> None:
        from steps.drift_monitoring_steps import compute_drift_report

        mock_instance = self._make_mock_detector(no_drift_report)

        with patch("steps.drift_monitoring_steps.DriftDetector", return_value=mock_instance):
            result = compute_drift_report.entrypoint(current_features=sample_features)

        required = {"has_drift", "max_psi", "min_ks_pvalue", "drifted_features"}
        assert required.issubset(set(result.keys()))

    def test_passes_dataframe_to_run(
        self, sample_features: pd.DataFrame, no_drift_report: dict
    ) -> None:
        from steps.drift_monitoring_steps import compute_drift_report

        mock_instance = self._make_mock_detector(no_drift_report)

        with patch("steps.drift_monitoring_steps.DriftDetector", return_value=mock_instance):
            compute_drift_report.entrypoint(current_features=sample_features)

        mock_instance.run.assert_called_once()
        call_df = mock_instance.run.call_args[0][0]
        assert isinstance(call_df, pd.DataFrame)

    def test_has_drift_false_propagated(
        self, sample_features: pd.DataFrame, no_drift_report: dict
    ) -> None:
        from steps.drift_monitoring_steps import compute_drift_report

        mock_instance = self._make_mock_detector(no_drift_report)

        with patch("steps.drift_monitoring_steps.DriftDetector", return_value=mock_instance):
            result = compute_drift_report.entrypoint(current_features=sample_features)

        assert result["has_drift"] is False

    def test_has_drift_true_propagated(
        self, sample_features: pd.DataFrame, drift_report: dict
    ) -> None:
        from steps.drift_monitoring_steps import compute_drift_report

        mock_instance = self._make_mock_detector(drift_report)

        with patch("steps.drift_monitoring_steps.DriftDetector", return_value=mock_instance):
            result = compute_drift_report.entrypoint(current_features=sample_features)

        assert result["has_drift"] is True
        assert result["drifted_features"] == ["mrr", "tenure_days"]


class TestEvaluateDriftAndTrigger:
    def test_returns_false_when_no_drift(self, no_drift_report: dict) -> None:
        from steps.drift_monitoring_steps import evaluate_drift_and_trigger

        with patch("steps.drift_monitoring_steps.subprocess.run") as mock_run:
            result = evaluate_drift_and_trigger.entrypoint(drift_report=no_drift_report)

        assert result is False
        mock_run.assert_not_called()

    def test_returns_true_when_drift_detected(self, drift_report: dict) -> None:
        from steps.drift_monitoring_steps import evaluate_drift_and_trigger

        with patch("steps.drift_monitoring_steps.subprocess.run"):
            result = evaluate_drift_and_trigger.entrypoint(drift_report=drift_report)

        assert result is True

    def test_triggers_retraining_pipeline_on_drift(self, drift_report: dict) -> None:
        from steps.drift_monitoring_steps import evaluate_drift_and_trigger

        with patch("steps.drift_monitoring_steps.subprocess.run") as mock_run:
            evaluate_drift_and_trigger.entrypoint(drift_report=drift_report)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "pipelines.churn_training_pipeline" in " ".join(cmd)

    def test_does_not_trigger_retraining_when_no_drift(self, no_drift_report: dict) -> None:
        from steps.drift_monitoring_steps import evaluate_drift_and_trigger

        with patch("steps.drift_monitoring_steps.subprocess.run") as mock_run:
            evaluate_drift_and_trigger.entrypoint(drift_report=no_drift_report)

        mock_run.assert_not_called()
