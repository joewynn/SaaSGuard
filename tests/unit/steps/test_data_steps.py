# tests/unit/steps/test_data_steps.py
"""
Unit tests for ZenML data pipeline steps.

Steps are tested by calling .entrypoint() directly — no ZenML server, no
real file I/O required for logic tests.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _no_zenml_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent log_metadata from making ZenML server calls during unit tests."""
    monkeypatch.setattr("steps.data_steps.log_metadata", lambda *args, **kwargs: None)


class TestValidateMarts:
    def test_passes_with_nonempty_mart(self) -> None:
        from steps.data_steps import validate_marts

        validate_marts.entrypoint(
            dbt_results={"mart_customer_churn_features_rows": 4800, "dbt_exit_code": 0}
        )

    def test_raises_when_mart_is_empty(self) -> None:
        from steps.data_steps import validate_marts

        with pytest.raises(ValueError, match="empty"):
            validate_marts.entrypoint(
                dbt_results={"mart_customer_churn_features_rows": 0, "dbt_exit_code": 0}
            )

    def test_raises_when_row_key_missing(self) -> None:
        from steps.data_steps import validate_marts

        with pytest.raises(ValueError, match="empty"):
            validate_marts.entrypoint(dbt_results={"dbt_exit_code": 0})


class TestRunDbt:
    def test_raises_on_nonzero_exit_code(self) -> None:
        from steps.data_steps import run_dbt

        with patch("steps.data_steps.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="Model failed")
            with pytest.raises(RuntimeError, match="dbt build failed"):
                run_dbt.entrypoint(n_rows=5000)

    def test_returns_dict_on_success(self) -> None:
        from steps.data_steps import run_dbt

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = (4800,)
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("steps.data_steps.subprocess.run") as mock_run, \
             patch("steps.data_steps.duckdb.connect", return_value=mock_ctx):
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = run_dbt.entrypoint(n_rows=5000)

        assert result["dbt_exit_code"] == 0
        assert result["mart_customer_churn_features_rows"] == 4800

    def test_result_keys_are_present(self) -> None:
        from steps.data_steps import run_dbt

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = (5000,)
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("steps.data_steps.subprocess.run") as mock_run, \
             patch("steps.data_steps.duckdb.connect", return_value=mock_ctx):
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = run_dbt.entrypoint(n_rows=1000)

        assert {"dbt_exit_code", "mart_customer_churn_features_rows"}.issubset(result)


class TestGenerateSyntheticData:
    def test_returns_positive_int(self) -> None:
        from steps.data_steps import generate_synthetic_data

        mock_df = MagicMock()
        mock_df.__len__ = MagicMock(return_value=5500)

        with patch("steps.data_steps.generate_all"), \
             patch("steps.data_steps.pd.read_csv", return_value=mock_df):
            n = generate_synthetic_data.entrypoint()

        assert n == 5500

    def test_calls_generate_all(self) -> None:
        from steps.data_steps import generate_synthetic_data

        mock_df = MagicMock()
        mock_df.__len__ = MagicMock(return_value=5500)

        with patch("steps.data_steps.generate_all") as mock_gen, \
             patch("steps.data_steps.pd.read_csv", return_value=mock_df):
            generate_synthetic_data.entrypoint()

        mock_gen.assert_called_once()


class TestBuildWarehouse:
    def test_returns_row_count(self) -> None:
        from steps.data_steps import build_warehouse

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = (5500,)
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("steps.data_steps.build") as mock_build, \
             patch("steps.data_steps.duckdb.connect", return_value=mock_ctx):
            n = build_warehouse.entrypoint(n_customers=5500)

        mock_build.assert_called_once()
        assert n == 5500
