"""OllamaSummaryService – local LLM backend via Ollama for offline/dev use.

Ollama runs as a Docker sidecar (dev profile). Zero API cost, fully offline.
Latency target: < 15s p95 on CPU. Used when LLM_PROVIDER=ollama.
"""

from __future__ import annotations

import httpx

from src.domain.ai_summary.entities import SummaryContext
from src.domain.ai_summary.summary_port import SummaryPort
from src.infrastructure.llm.prompt_builder import PromptBuilder

_SYSTEM_PROMPT = (
    "You are a B2B SaaS customer success analyst. "
    "Be concise, factual, and actionable. "
    "Only reference information explicitly provided to you."
)


class OllamaSummaryService(SummaryPort):
    """Implements SummaryPort using a local Ollama instance.

    Business Context: Ollama is the local fallback for development environments
    without Groq API access. It runs the same Llama-3 family model, ensuring
    prompt/response behaviour is consistent across environments.

    Args:
        host: Ollama API base URL. Defaults to http://localhost:11434.
        model: Ollama model tag. Defaults to 'llama3.1:8b'.
        timeout: HTTP timeout in seconds for the synchronous API call.
    """

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        timeout: float = 60.0,
    ) -> None:
        self._host = host.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._prompt_builder = PromptBuilder()

    def generate(self, context: SummaryContext, audience: str) -> str:
        """Call local Ollama API and return the raw LLM-generated narrative.

        Business Context: Ollama uses the /api/generate endpoint with stream=False
        for simplicity. The same prompt structure as Groq is used to ensure
        output quality is comparable across providers.

        Args:
            context: Structured facts from DuckDB that ground the prompt.
            audience: 'csm' or 'executive' — controls tone and focus.

        Returns:
            Raw LLM text string (no watermark; guardrails applied by caller).

        Raises:
            httpx.HTTPError: If the Ollama service is unreachable.
        """
        prompt = self._prompt_builder.build_summary_prompt(context, audience)
        full_prompt = f"{_SYSTEM_PROMPT}\n\n{prompt}"
        return self._call_ollama(full_prompt)

    def generate_from_prompt(self, prompt: str) -> str:
        """Call local Ollama API with a pre-assembled prompt and return raw LLM text.

        Business Context: Used by the expansion narrative pipeline. Delegates to
        _call_ollama with the system prompt prepended for consistent behaviour
        across providers.

        Args:
            prompt: Fully assembled prompt string.

        Returns:
            Raw LLM-generated text string (no watermark; guardrails applied by caller).
        """
        full_prompt = f"{_SYSTEM_PROMPT}\n\n{prompt}"
        return self._call_ollama(full_prompt)

    def answer_question(self, context: SummaryContext, question: str) -> str:
        """Answer a free-text question using local Ollama inference.

        Args:
            context: All structured facts for the customer from DuckDB.
            question: CSM's free-text question.

        Returns:
            LLM answer string constrained to available context.
        """
        prompt = self._prompt_builder.build_question_prompt(context, question)
        full_prompt = f"{_SYSTEM_PROMPT}\n\n{prompt}"
        return self._call_ollama(full_prompt)

    def _call_ollama(self, prompt: str) -> str:
        """Make a synchronous POST to the Ollama /api/generate endpoint.

        Args:
            prompt: Full prompt string including system instructions.

        Returns:
            Generated text from the model response.
        """
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 400,
            },
        }
        response = httpx.post(
            f"{self._host}/api/generate",
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        data = response.json()
        return str(data.get("response", ""))

    @property
    def model_name(self) -> str:
        """LLM model identifier reported in ExecutiveSummary provenance."""
        return self._model

    @property
    def provider_name(self) -> str:
        """Inference provider name reported in ExecutiveSummary provenance."""
        return "ollama"
