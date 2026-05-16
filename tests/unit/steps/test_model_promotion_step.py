# tests/unit/steps/test_model_promotion_step.py
"""
Unit tests for the model promotion step.

get_step_context() raises RuntimeError outside a ZenML pipeline run, so we
patch it at the module namespace to inject a mock model handle.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from zenml.enums import ModelStages


@pytest.fixture(autouse=True)
def _no_zenml_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent log_metadata from making ZenML server calls during unit tests."""
    monkeypatch.setattr(
        "steps.model_promotion_step.log_metadata", lambda *args, **kwargs: None
    )


def _mock_step_context(mock_model: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.model = mock_model
    return ctx


class TestPromoteModelIfPassing:
    def test_promotes_to_production_when_auc_meets_threshold(self) -> None:
        from steps.model_promotion_step import promote_model_if_passing

        mock_model = MagicMock()
        mock_model.version = "2026.05.16"

        with patch(
            "steps.model_promotion_step.get_step_context",
            return_value=_mock_step_context(mock_model),
        ):
            promoted = promote_model_if_passing.entrypoint(
                evaluation_metrics={"auc_roc": 0.85},
                model_version="2026.05.16",
            )

        assert promoted is True
        mock_model.set_stage.assert_called_once_with(
            stage=ModelStages.PRODUCTION, force=True
        )

    def test_keeps_in_staging_when_auc_below_threshold(self) -> None:
        from steps.model_promotion_step import promote_model_if_passing

        mock_model = MagicMock()
        mock_model.version = "2026.05.16"

        with patch(
            "steps.model_promotion_step.get_step_context",
            return_value=_mock_step_context(mock_model),
        ):
            promoted = promote_model_if_passing.entrypoint(
                evaluation_metrics={"auc_roc": 0.72},
                model_version="2026.05.16",
            )

        assert promoted is False
        mock_model.set_stage.assert_called_once_with(stage=ModelStages.STAGING)

    def test_promotes_at_exact_threshold(self) -> None:
        from steps.model_promotion_step import promote_model_if_passing

        mock_model = MagicMock()
        with patch(
            "steps.model_promotion_step.get_step_context",
            return_value=_mock_step_context(mock_model),
        ):
            promoted = promote_model_if_passing.entrypoint(
                evaluation_metrics={"auc_roc": 0.80},
                model_version="2026.05.16",
            )

        assert promoted is True

    def test_returns_bool_type(self) -> None:
        from steps.model_promotion_step import promote_model_if_passing

        mock_model = MagicMock()
        with patch(
            "steps.model_promotion_step.get_step_context",
            return_value=_mock_step_context(mock_model),
        ):
            result = promote_model_if_passing.entrypoint(
                evaluation_metrics={"auc_roc": 0.91},
                model_version="2026.05.16",
            )

        assert isinstance(result, bool)
