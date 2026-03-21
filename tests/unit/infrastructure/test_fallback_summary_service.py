"""Tests for FallbackSummaryService — primary/secondary LLM provider chain.

TDD: these tests are written first and define the expected contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest

from src.domain.ai_summary.entities import SummaryContext
from src.infrastructure.llm.fallback_summary_service import FallbackSummaryService


def _make_context() -> SummaryContext:
    # FallbackSummaryService only passes the context through to the provider —
    # it never inspects its fields. A MagicMock satisfies the type annotation.
    return MagicMock(spec=SummaryContext)


def _make_service(provider_name: str = "groq") -> MagicMock:
    svc = MagicMock()
    type(svc).provider_name = PropertyMock(return_value=provider_name)
    type(svc).model_name = PropertyMock(return_value=f"{provider_name}-model")
    return svc


class TestFallbackSummaryServiceGenerate:
    def test_returns_primary_response_when_healthy(self) -> None:
        primary = _make_service("groq")
        primary.generate.return_value = "groq answer"
        secondary = _make_service("ollama")

        svc = FallbackSummaryService(primary, secondary)
        result = svc.generate(_make_context(), "csm")

        assert result == "groq answer"
        secondary.generate.assert_not_called()

    def test_falls_back_to_secondary_on_runtime_error(self) -> None:
        primary = _make_service("groq")
        primary.generate.side_effect = RuntimeError("Groq API error: Connection error.")
        secondary = _make_service("ollama")
        secondary.generate.return_value = "ollama answer"

        svc = FallbackSummaryService(primary, secondary)
        result = svc.generate(_make_context(), "csm")

        assert result == "ollama answer"

    def test_falls_back_on_any_exception(self) -> None:
        primary = _make_service("groq")
        primary.generate.side_effect = OSError("network unreachable")
        secondary = _make_service("ollama")
        secondary.generate.return_value = "ollama fallback"

        svc = FallbackSummaryService(primary, secondary)
        result = svc.generate(_make_context(), "csm")

        assert result == "ollama fallback"

    def test_raises_if_secondary_also_fails(self) -> None:
        primary = _make_service("groq")
        primary.generate.side_effect = RuntimeError("Groq down")
        secondary = _make_service("ollama")
        secondary.generate.side_effect = RuntimeError("Ollama down")

        svc = FallbackSummaryService(primary, secondary)
        with pytest.raises(RuntimeError, match="Ollama down"):
            svc.generate(_make_context(), "csm")


class TestFallbackSummaryServiceGenerateFromPrompt:
    def test_returns_primary_on_success(self) -> None:
        primary = _make_service("groq")
        primary.generate_from_prompt.return_value = "groq prompt response"
        secondary = _make_service("ollama")

        svc = FallbackSummaryService(primary, secondary)
        result = svc.generate_from_prompt("my prompt")

        assert result == "groq prompt response"
        secondary.generate_from_prompt.assert_not_called()

    def test_falls_back_on_primary_failure(self) -> None:
        primary = _make_service("groq")
        primary.generate_from_prompt.side_effect = RuntimeError("Groq API error: Connection error.")
        secondary = _make_service("ollama")
        secondary.generate_from_prompt.return_value = "ollama prompt response"

        svc = FallbackSummaryService(primary, secondary)
        result = svc.generate_from_prompt("my prompt")

        assert result == "ollama prompt response"


class TestFallbackSummaryServiceAnswerQuestion:
    def test_delegates_to_primary_answer_question(self) -> None:
        primary = _make_service("groq")
        primary.answer_question.return_value = "groq answer"
        secondary = _make_service("ollama")

        svc = FallbackSummaryService(primary, secondary)
        result = svc.answer_question(_make_context(), "Why did they churn?")

        assert result == "groq answer"
        secondary.answer_question.assert_not_called()

    def test_falls_back_to_secondary_answer_question_on_failure(self) -> None:
        primary = _make_service("groq")
        primary.answer_question.side_effect = RuntimeError("Groq API error: Connection error.")
        secondary = _make_service("ollama")
        secondary.answer_question.return_value = "ollama answer"

        svc = FallbackSummaryService(primary, secondary)
        result = svc.answer_question(_make_context(), "Why did they churn?")

        assert result == "ollama answer"


class TestFallbackSummaryServiceProperties:
    def test_model_name_reports_primary_when_healthy(self) -> None:
        primary = _make_service("groq")
        secondary = _make_service("ollama")
        svc = FallbackSummaryService(primary, secondary)
        assert svc.model_name == "groq-model"

    def test_provider_name_reports_primary_when_healthy(self) -> None:
        primary = _make_service("groq")
        secondary = _make_service("ollama")
        svc = FallbackSummaryService(primary, secondary)
        assert svc.provider_name == "groq"
