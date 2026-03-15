# AI Summary Domain

Phase 5 AI/LLM layer — executive summaries and RAG Q&A grounded in DuckDB customer data.

## Domain Entities

::: src.domain.ai_summary.entities

## Summary Port (ABC)

::: src.domain.ai_summary.summary_port

## Guardrails Service

::: src.domain.ai_summary.guardrails_service

## Application Use Cases

::: src.application.use_cases.generate_executive_summary

::: src.application.use_cases.ask_customer_question

## Infrastructure — LLM Adapters

::: src.infrastructure.llm.groq_summary_service

::: src.infrastructure.llm.ollama_summary_service

::: src.infrastructure.llm.prompt_builder
