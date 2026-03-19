"""FastAPI dependency injection – wires infrastructure to use cases.

All dependency construction happens here. The domain and application layers
are never aware of FastAPI or this file.
"""

from __future__ import annotations

import os
from functools import lru_cache

from src.application.use_cases.ask_customer_question import AskCustomerQuestionUseCase
from src.application.use_cases.generate_executive_summary import (
    GenerateExecutiveSummaryUseCase,
)
from src.application.use_cases.get_customer_360 import GetCustomer360UseCase
from src.application.use_cases.predict_churn import PredictChurnUseCase
from src.application.use_cases.predict_expansion import PredictExpansionUseCase
from src.domain.ai_summary.guardrails_service import GuardrailsService
from src.domain.prediction.risk_model_service import RiskModelService
from src.infrastructure.repositories.customer_repository import DuckDBCustomerRepository
from src.infrastructure.repositories.risk_signals_repository import (
    DuckDBRiskSignalsRepository,
)
from src.infrastructure.repositories.usage_repository import DuckDBUsageRepository


def get_customer_repository() -> DuckDBCustomerRepository:
    """Provide a DuckDBCustomerRepository instance for request-scoped injection.

    Not cached — DuckDB connections are managed via context managers inside
    each repository method, so a fresh instance per request is lightweight.
    """
    return DuckDBCustomerRepository()


@lru_cache(maxsize=1)
def get_predict_churn_use_case() -> PredictChurnUseCase:
    """Build and cache the PredictChurnUseCase with real infrastructure.

    Caching ensures DuckDB connections and model loading happen once per
    worker process, not per request.
    """
    from src.domain.prediction.churn_model_service import ChurnModelService
    from src.infrastructure.ml.churn_feature_extractor import ChurnFeatureExtractor
    from src.infrastructure.ml.xgboost_churn_model import XGBoostChurnModel

    return PredictChurnUseCase(
        customer_repo=DuckDBCustomerRepository(),
        usage_repo=DuckDBUsageRepository(),
        churn_service=ChurnModelService(
            model=XGBoostChurnModel(),
            feature_extractor=ChurnFeatureExtractor(),
        ),
        risk_service=RiskModelService(),
        risk_signals_repo=DuckDBRiskSignalsRepository(),
    )


def _build_summary_service() -> object:
    """Instantiate the configured LLM backend (Groq or Ollama).

    Reads LLM_PROVIDER from environment (default: groq).
    Groq requires GROQ_API_KEY. Ollama uses OLLAMA_HOST.
    """
    provider = os.getenv("LLM_PROVIDER", "groq").lower()

    if provider == "ollama":
        from src.infrastructure.llm.ollama_summary_service import OllamaSummaryService

        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        model = os.getenv("LLM_MODEL", "llama3.1:8b")
        return OllamaSummaryService(host=host, model=model)

    # Default: Groq
    from src.infrastructure.llm.groq_summary_service import GroqSummaryService

    api_key = os.getenv("GROQ_API_KEY", "")
    model = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
    return GroqSummaryService(api_key=api_key, model=model)


@lru_cache(maxsize=1)
def get_summary_use_case() -> GenerateExecutiveSummaryUseCase:
    """Build and cache the GenerateExecutiveSummaryUseCase.

    Wires the LLM backend (Groq or Ollama) based on LLM_PROVIDER env var.
    Caching ensures the LLM client is initialised once per worker.
    """
    from src.domain.ai_summary.summary_port import SummaryPort

    summary_service = _build_summary_service()
    assert isinstance(summary_service, SummaryPort)

    return GenerateExecutiveSummaryUseCase(
        customer_repo=DuckDBCustomerRepository(),
        predict_use_case=get_predict_churn_use_case(),
        usage_repo=DuckDBUsageRepository(),
        summary_service=summary_service,
        guardrails=GuardrailsService(),
    )


@lru_cache(maxsize=1)
def get_predict_expansion_use_case() -> PredictExpansionUseCase:
    """Build and cache the PredictExpansionUseCase with real infrastructure.

    Lazy imports inside function body — same pattern as get_predict_churn_use_case.
    Model is loaded once per worker process via @lru_cache.
    """
    from src.domain.expansion.expansion_service import ExpansionModelService
    from src.infrastructure.ml.expansion_feature_extractor import ExpansionFeatureExtractor
    from src.infrastructure.ml.xgboost_expansion_model import XGBoostExpansionModel

    return PredictExpansionUseCase(
        customer_repo=DuckDBCustomerRepository(),
        expansion_service=ExpansionModelService(
            model=XGBoostExpansionModel(),
            feature_extractor=ExpansionFeatureExtractor(),
        ),
    )


@lru_cache(maxsize=1)
def get_customer_360_use_case() -> GetCustomer360UseCase:
    """Build and cache the GetCustomer360UseCase.

    Reuses the cached PredictChurnUseCase to avoid duplicate model loading.
    """
    return GetCustomer360UseCase(
        customer_repo=DuckDBCustomerRepository(),
        predict_use_case=get_predict_churn_use_case(),
    )


@lru_cache(maxsize=1)
def get_ask_use_case() -> AskCustomerQuestionUseCase:
    """Build and cache the AskCustomerQuestionUseCase.

    Reuses the same LLM backend and repositories as the summary use case.
    """
    from src.domain.ai_summary.summary_port import SummaryPort

    summary_service = _build_summary_service()
    assert isinstance(summary_service, SummaryPort)

    return AskCustomerQuestionUseCase(
        customer_repo=DuckDBCustomerRepository(),
        predict_use_case=get_predict_churn_use_case(),
        usage_repo=DuckDBUsageRepository(),
        summary_service=summary_service,
        guardrails=GuardrailsService(),
    )
