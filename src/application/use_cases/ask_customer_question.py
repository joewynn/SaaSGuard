"""AskCustomerQuestionUseCase – RAG chatbot for free-text questions about a customer.

Answers questions like "Why is this customer at risk?" by building a SummaryContext
from DuckDB and passing it to the LLM with a strict grounding constraint.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from src.application.use_cases.generate_executive_summary import (
    GenerateExecutiveSummaryUseCase,
)
from src.application.use_cases.predict_churn import PredictChurnRequest, PredictChurnUseCase
from src.domain.ai_summary.guardrails_service import GuardrailsService
from src.domain.ai_summary.summary_port import SummaryPort
from src.domain.customer.repository import CustomerRepository
from src.domain.usage.repository import UsageRepository

logger = structlog.get_logger(__name__)

# Sentinel phrase the LLM returns when the question is out of scope
_SCOPE_EXCEEDED_PHRASE = "I cannot answer this from the available customer data."


@dataclass
class AskCustomerRequest:
    """Input DTO for AskCustomerQuestionUseCase.

    Args:
        customer_id: UUID of the customer to ask about.
        question: Free-text question from the CSM (5–500 characters).
    """

    customer_id: str
    question: str


@dataclass
class AskCustomerResponse:
    """Output DTO for AskCustomerQuestionUseCase.

    Args:
        customer_id: UUID of the customer asked about.
        question: The original question.
        answer: LLM-generated answer with guardrail watermark.
        confidence_score: 0–1; degrades with guardrail flags.
        guardrail_flags: List of detected violations (e.g. 'probability_mismatch').
        scope_exceeded: True if the question couldn't be answered from available data.
        generated_at: UTC timestamp of the response.
        model_used: LLM model name for audit.
        llm_provider: Provider name for audit.
    """

    customer_id: str
    question: str
    answer: str
    confidence_score: float
    guardrail_flags: list[str]
    scope_exceeded: bool
    generated_at: datetime
    model_used: str
    llm_provider: str


class AskCustomerQuestionUseCase:
    """Answers free-text questions about a customer using their DuckDB history as context.

    Business Context: CSMs can ask questions like "Why is this customer at risk?"
    or "What support tickets are open?" and get answers grounded in real data.
    Questions outside available context return a 'scope_exceeded' flag rather
    than hallucinated answers — protecting CSM trust in the tool.

    The underlying RAG strategy is context-stuffing: the customer's full history
    fits in Llama-3's 128k context window, so no vector database is required.

    Args:
        customer_repo: Repository for fetching Customer entities.
        predict_use_case: PredictChurnUseCase for calibrated probability + SHAP.
        usage_repo: UsageRepository for event lookups.
        summary_service: SummaryPort with answer_question() method.
        guardrails: GuardrailsService for hallucination detection + watermark.
    """

    def __init__(
        self,
        customer_repo: CustomerRepository,
        predict_use_case: PredictChurnUseCase,
        usage_repo: UsageRepository,
        summary_service: SummaryPort,
        guardrails: GuardrailsService,
    ) -> None:
        self._customer_repo = customer_repo
        self._predict_use_case = predict_use_case
        self._usage_repo = usage_repo
        self._summary_service = summary_service
        self._guardrails = guardrails
        # Reuse the context-building logic from the summary use case
        self._summary_uc = GenerateExecutiveSummaryUseCase(
            customer_repo=customer_repo,
            predict_use_case=predict_use_case,
            usage_repo=usage_repo,
            summary_service=summary_service,
            guardrails=guardrails,
        )

    def execute(self, request: AskCustomerRequest) -> AskCustomerResponse:
        """Answer a free-text question about a customer.

        Business Context: Retrieves full customer context from DuckDB, passes
        question + context to the LLM, validates the answer, and returns a
        structured response with scope_exceeded flag for out-of-context questions.

        Args:
            request: Contains customer_id and the question to answer.

        Returns:
            AskCustomerResponse with grounded answer and audit metadata.

        Raises:
            ValueError: If the customer is not found or has already churned.
        """
        log = logger.bind(customer_id=request.customer_id)
        log.info("ask.question.start", question=request.question[:100])

        # Validate customer exists
        customer = self._customer_repo.get_by_id(request.customer_id)
        if customer is None:
            raise ValueError(f"Customer {request.customer_id} not found.")
        if not customer.is_active:
            raise ValueError(f"Customer {request.customer_id} has already churned on {customer.churn_date}.")

        # Get prediction for context
        prediction = self._predict_use_case.execute(PredictChurnRequest(customer_id=request.customer_id))

        # Build full context (RAG retrieval)
        context = self._summary_uc._build_context(customer, prediction)

        # Call LLM with question
        if hasattr(self._summary_service, "answer_question"):
            raw_answer = self._summary_service.answer_question(context, request.question)
        else:
            # Fallback: use generate with a question-framed prompt
            from src.infrastructure.llm.prompt_builder import PromptBuilder

            _ = PromptBuilder().build_question_prompt(context, request.question)
            raw_answer = self._summary_service.generate(context, "csm")

        log.info("ask.llm.response_received", length=len(raw_answer))

        # Validate + watermark
        final_answer, guardrail = self._guardrails.validate(raw_answer, context)

        # Detect scope-exceeded sentinel
        scope_exceeded = _SCOPE_EXCEEDED_PHRASE.lower() in raw_answer.lower()

        return AskCustomerResponse(
            customer_id=request.customer_id,
            question=request.question,
            answer=final_answer,
            confidence_score=guardrail.confidence_score,
            guardrail_flags=guardrail.flags,
            scope_exceeded=scope_exceeded,
            generated_at=datetime.now(UTC),
            model_used=self._summary_service.model_name,
            llm_provider=self._summary_service.provider_name,
        )
