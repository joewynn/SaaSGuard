"""GroqSummaryService – primary LLM backend via Groq Cloud API.

Uses llama-3.1-8b-instant by default: fast inference, free tier, 128k context.
Temperature is kept low (0.2) for factual grounding in production.
"""

from __future__ import annotations

import groq as groq_sdk

from src.domain.ai_summary.entities import SummaryContext
from src.domain.ai_summary.summary_port import SummaryPort
from src.infrastructure.llm.prompt_builder import PromptBuilder

_SYSTEM_PROMPT = (
    "You are a B2B SaaS customer success analyst writing for business audiences. "
    "Be concise, factual, and actionable. "
    "Only reference information explicitly provided to you. "
    "Never invent statistics, feature names, or customer details. "
    "Never use technical ML terms such as SHAP, shap_impact, feature importance, "
    "or model internals. "
    "Never repeat a customer's UUID or internal ID — refer to them by industry and plan tier. "
    "Translate all signals into plain business language a non-technical executive can understand."
)


class GroqSummaryService(SummaryPort):
    """Implements SummaryPort using Groq Cloud inference API.

    Business Context: Groq provides sub-3-second inference for Llama-3 models
    on free tier, making it cost-effective for per-request executive summaries.
    No infrastructure to manage — just an API key.

    Args:
        api_key: Groq API key (from GROQ_API_KEY environment variable).
        model: Groq model ID. Defaults to 'llama-3.1-8b-instant' for speed;
               use 'llama-3.1-70b-versatile' for higher quality at higher cost.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.1-8b-instant",
    ) -> None:
        self._client = groq_sdk.Groq(api_key=api_key)
        self._model = model
        self._prompt_builder = PromptBuilder()

    def generate(self, context: SummaryContext, audience: str) -> str:
        """Call Groq API and return the raw LLM-generated narrative.

        Business Context: Low temperature (0.2) keeps the output factual and
        consistent. max_tokens=400 enforces the 3-5 sentence length constraint
        for CSM briefings. Guardrails are applied by the caller.

        Args:
            context: Structured facts from DuckDB that ground the prompt.
            audience: 'csm' or 'executive' — controls tone and focus.

        Returns:
            Raw LLM text string (no watermark; guardrails applied by caller).
        """
        prompt = self._prompt_builder.build_summary_prompt(context, audience)
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=400,
                temperature=0.2,
            )
        except groq_sdk.AuthenticationError as exc:
            raise RuntimeError(
                "Groq API key is missing or invalid. Set GROQ_API_KEY in your environment (Railway Variables or .env)."
            ) from exc
        except groq_sdk.APIError as exc:
            raise RuntimeError(f"Groq API error: {exc}") from exc
        return response.choices[0].message.content or ""

    def generate_from_prompt(self, prompt: str) -> str:
        """Call Groq API with a pre-assembled prompt and return raw LLM text.

        Business Context: Used by the expansion narrative pipeline where the
        full prompt is built by PromptBuilder.build_expansion_prompt() before
        the LLM call. max_tokens=600 accommodates brief + optional email draft.

        Args:
            prompt: Fully assembled prompt string.

        Returns:
            Raw LLM-generated text string (no watermark; guardrails applied by caller).
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=600,
                temperature=0.2,
            )
        except groq_sdk.AuthenticationError as exc:
            raise RuntimeError(
                "Groq API key is missing or invalid. Set GROQ_API_KEY in your environment."
            ) from exc
        except groq_sdk.APIError as exc:
            raise RuntimeError(f"Groq API error: {exc}") from exc
        return response.choices[0].message.content or ""

    def answer_question(self, context: SummaryContext, question: str) -> str:
        """Answer a free-text question about a customer, constrained to DuckDB context.

        Business Context: Used by the RAG chatbot endpoint. The prompt includes
        a strict [CONSTRAINT] block that prevents the LLM from fabricating answers
        to questions outside the available customer data.

        Args:
            context: All structured facts for the customer from DuckDB.
            question: CSM's free-text question (5–500 chars).

        Returns:
            LLM answer string, or the scope-exceeded sentinel phrase.
        """
        prompt = self._prompt_builder.build_question_prompt(context, question)
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=300,
                temperature=0.1,
            )
        except groq_sdk.AuthenticationError as exc:
            raise RuntimeError(
                "Groq API key is missing or invalid. Set GROQ_API_KEY in your environment (Railway Variables or .env)."
            ) from exc
        except groq_sdk.APIError as exc:
            raise RuntimeError(f"Groq API error: {exc}") from exc
        return response.choices[0].message.content or ""

    @property
    def model_name(self) -> str:
        """LLM model identifier reported in ExecutiveSummary provenance."""
        return self._model

    @property
    def provider_name(self) -> str:
        """Inference provider name reported in ExecutiveSummary provenance."""
        return "groq"
