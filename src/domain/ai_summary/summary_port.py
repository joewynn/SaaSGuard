"""SummaryPort – abstract base class for LLM backend adapters.

Both GroqSummaryService and OllamaSummaryService implement this port,
making the LLM backend swappable without touching domain or application code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.ai_summary.entities import SummaryContext


class SummaryPort(ABC):
    """Abstract port for LLM text generation.

    Business Context: This port decouples the domain from any specific LLM
    provider. The application layer only knows about SummaryPort — swapping
    Groq for Ollama (or a future provider) requires only a config change,
    not a code change in the use case.

    Implementations must be stateless and thread-safe; FastAPI may call
    generate() concurrently from multiple request handlers.
    """

    @abstractmethod
    def generate(self, context: SummaryContext, audience: str) -> str:
        """Generate a raw LLM narrative grounded in the provided context.

        Business Context: Guardrails are applied by the caller (GuardrailsService)
        after this method returns. This method is responsible only for making
        the API call and returning the raw text.

        Args:
            context: Structured facts from DuckDB that ground the prompt.
            audience: Target audience — 'csm' (tactical) or 'executive' (strategic).

        Returns:
            Raw LLM-generated text string (watermark NOT yet appended).
        """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the underlying LLM model (e.g. 'llama-3.1-8b-instant')."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the inference provider (e.g. 'groq' or 'ollama')."""
