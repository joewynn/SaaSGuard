"""FallbackSummaryService — primary/secondary LLM provider chain.

When the primary provider (Groq) fails with any exception, this service
transparently retries the same call on the secondary provider (Ollama).
Both providers must implement SummaryPort.
"""

from __future__ import annotations

import structlog

from src.domain.ai_summary.entities import SummaryContext
from src.domain.ai_summary.summary_port import SummaryPort

log = structlog.get_logger(__name__)


class FallbackSummaryService(SummaryPort):
    """SummaryPort implementation that chains a primary and secondary LLM provider.

    Business Context: Groq is the production provider (sub-3s, free tier). When
    Groq is unreachable (connection error, rate limit, outage), requests fall back
    to a local Ollama instance automatically — no 503 surfaced to the CS team.
    The fallback is transparent: the caller receives a valid response regardless
    of which provider served it.

    Args:
        primary: Primary SummaryPort implementation (e.g. GroqSummaryService).
        secondary: Secondary SummaryPort implementation (e.g. OllamaSummaryService).
    """

    def __init__(self, primary: SummaryPort, secondary: SummaryPort) -> None:
        self._primary = primary
        self._secondary = secondary

    def generate(self, context: SummaryContext, audience: str) -> str:
        """Generate a narrative, falling back to secondary if primary fails.

        Business Context: CS teams trigger this on every pre-call brief. A
        connection blip to Groq must not block the brief — Ollama absorbs
        the request instead.

        Args:
            context: Structured customer facts from DuckDB.
            audience: 'csm' or 'executive'.

        Returns:
            Raw LLM-generated text from whichever provider responded.
        """
        try:
            return self._primary.generate(context, audience)
        except Exception as exc:
            log.warning(
                "llm.primary_failed.fallback_to_secondary",
                primary=self._primary.provider_name,
                secondary=self._secondary.provider_name,
                error=str(exc),
            )
            return self._secondary.generate(context, audience)

    def generate_from_prompt(self, prompt: str) -> str:
        """Generate from a pre-assembled prompt, falling back to secondary if primary fails.

        Business Context: Used by the expansion narrative pipeline. Same fallback
        guarantee as generate() — AE briefs must not block on a Groq outage.

        Args:
            prompt: Fully assembled prompt string.

        Returns:
            Raw LLM-generated text from whichever provider responded.
        """
        try:
            return self._primary.generate_from_prompt(prompt)
        except Exception as exc:
            log.warning(
                "llm.primary_failed.fallback_to_secondary",
                primary=self._primary.provider_name,
                secondary=self._secondary.provider_name,
                error=str(exc),
            )
            return self._secondary.generate_from_prompt(prompt)

    def answer_question(self, context: SummaryContext, question: str) -> str:
        """Answer a free-text question, falling back to secondary if primary fails.

        Business Context: Used by the RAG chatbot endpoint. Delegates to
        answer_question() on each provider so question-specific prompting
        is preserved through the fallback chain.

        Args:
            context: All structured facts for the customer from DuckDB.
            question: CSM's free-text question.

        Returns:
            LLM answer string from whichever provider responded.
        """
        try:
            return self._primary.answer_question(context, question)  # type: ignore[attr-defined]
        except Exception as exc:
            log.warning(
                "llm.primary_failed.fallback_to_secondary",
                primary=self._primary.provider_name,
                secondary=self._secondary.provider_name,
                error=str(exc),
            )
            return self._secondary.answer_question(context, question)  # type: ignore[attr-defined]

    @property
    def model_name(self) -> str:
        """Primary model name — reported in response provenance."""
        return self._primary.model_name

    @property
    def provider_name(self) -> str:
        """Primary provider name — reported in response provenance."""
        return self._primary.provider_name
