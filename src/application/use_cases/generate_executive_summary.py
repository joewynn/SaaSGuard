"""GenerateExecutiveSummaryUseCase – orchestrates the AI summary pipeline.

Fetches customer + prediction data, builds SummaryContext from DuckDB,
calls the LLM via SummaryPort, and validates output with GuardrailsService.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import structlog

from src.application.use_cases.predict_churn import PredictChurnRequest, PredictChurnUseCase
from src.domain.ai_summary.entities import ExecutiveSummary, SummaryContext
from src.domain.ai_summary.guardrails_service import GuardrailsService
from src.domain.ai_summary.summary_port import SummaryPort
from src.domain.customer.repository import CustomerRepository
from src.domain.usage.repository import UsageRepository

logger = structlog.get_logger(__name__)


@dataclass
class GenerateSummaryRequest:
    """Input DTO for GenerateExecutiveSummaryUseCase.

    Args:
        customer_id: UUID of the active customer to summarise.
        audience: 'csm' (tactical briefing) or 'executive' (revenue-focused).
    """

    customer_id: str
    audience: str = field(default="csm")


class GenerateExecutiveSummaryUseCase:
    """Generates an AI executive summary grounded in DuckDB customer data.

    Business Context: Replaces ~15 min of manual CSM research with a 30-second
    API call. The output is grounded in the Phase 4 prediction pipeline (churn
    probability, SHAP drivers) and enriched with usage events, support tickets,
    and GTM signals from DuckDB.

    Pipeline:
      1. Fetch Customer entity (raises ValueError if not found / churned)
      2. Run PredictChurnUseCase to get calibrated probability + SHAP features
      3. Query DuckDB for events, tickets, GTM context
      4. Build SummaryContext (the RAG "retrieval" step)
      5. Call LLM via SummaryPort (no DB access in LLM layer)
      6. Validate output + append watermark via GuardrailsService
      7. Return ExecutiveSummary entity

    Args:
        customer_repo: Repository for fetching Customer entities.
        predict_use_case: PredictChurnUseCase for calibrated probability + SHAP.
        usage_repo: UsageRepository for event lookups.
        summary_service: SummaryPort implementation (Groq or Ollama).
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

    def execute(self, request: GenerateSummaryRequest) -> ExecutiveSummary:
        """Run the full AI summary pipeline for a single customer.

        Business Context: All LLM calls are grounded in verified DuckDB data.
        The guardrail layer ensures hallucinated features or wrong probabilities
        are flagged before the summary reaches a CS workflow.

        Args:
            request: Contains customer_id and target audience.

        Returns:
            ExecutiveSummary with content, guardrail result, and provenance metadata.

        Raises:
            ValueError: If the customer is not found or has already churned.
        """
        log = logger.bind(customer_id=request.customer_id, audience=request.audience)
        log.info("summary.generate.start")

        # Step 1 — fetch customer
        customer = self._customer_repo.get_by_id(request.customer_id)
        if customer is None:
            raise ValueError(f"Customer {request.customer_id} not found.")
        if not customer.is_active:
            raise ValueError(
                f"Customer {request.customer_id} has already churned on {customer.churn_date}."
            )

        # Step 2 — run churn prediction (Phase 4 pipeline)
        prediction = self._predict_use_case.execute(
            PredictChurnRequest(customer_id=request.customer_id)
        )

        # Step 3 — build context (RAG retrieval from DuckDB)
        context = self._build_context(customer, prediction)  # type: ignore[arg-type]

        # Step 4 — call LLM
        raw_text = self._summary_service.generate(context, request.audience)
        log.info("summary.llm.response_received", length=len(raw_text))

        # Step 5 — validate + watermark
        final_text, guardrail = self._guardrails.validate(raw_text, context)
        if not guardrail.passed:
            log.warning(
                "summary.guardrail.flags",
                flags=guardrail.flags,
                confidence=guardrail.confidence_score,
            )

        return ExecutiveSummary(
            customer_id=request.customer_id,
            audience=request.audience,
            content=final_text,
            guardrail=guardrail,
            generated_at=datetime.now(timezone.utc),
            model_used=self._summary_service.model_name,
            llm_provider=self._summary_service.provider_name,
            prediction=prediction,
        )

    def _build_context(self, customer: object, prediction: object) -> SummaryContext:
        """Fetch all context data from DuckDB and assemble SummaryContext.

        Business Context: This is the "retrieval" step — pulls events, tickets,
        and GTM signals for the customer. All data is fetched fresh per request
        to ensure the LLM sees current state.

        Args:
            customer: The Customer entity.
            prediction: The PredictionResult from the churn pipeline.

        Returns:
            A SummaryContext with all structured facts for the customer.
        """
        from src.domain.customer.entities import Customer
        from src.domain.prediction.entities import PredictionResult

        assert isinstance(customer, Customer)
        assert isinstance(prediction, PredictionResult)

        # Fetch events in last 30 days and aggregate by type
        since_30d = datetime.now(timezone.utc) - timedelta(days=30)
        events = self._usage_repo.get_events_for_customer(
            customer.customer_id, since=since_30d
        )
        events_by_type: dict[str, int] = {}
        for event in events:
            key = str(event.event_type)
            events_by_type[key] = events_by_type.get(key, 0) + 1

        # Fetch open tickets and GTM from DuckDB if the repos are available
        open_tickets = self._fetch_open_tickets(customer.customer_id)
        gtm_opportunity = self._fetch_gtm_opportunity(customer.customer_id)
        cohort_churn_rate = self._fetch_cohort_churn_rate(customer)

        return SummaryContext(
            customer=customer,
            prediction=prediction,
            events_last_30d_by_type=events_by_type,
            open_tickets=open_tickets,
            gtm_opportunity=gtm_opportunity,
            cohort_churn_rate=cohort_churn_rate,
        )

    def _fetch_open_tickets(self, customer_id: str) -> list[dict[str, object]]:
        """Query DuckDB for open support tickets for this customer.

        Falls back to empty list if the infrastructure is unavailable
        (e.g. unit tests without a real DuckDB).
        """
        try:
            from src.infrastructure.db.duckdb_adapter import get_connection

            with get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT priority, topic,
                           DATEDIFF('day', created_date, CURRENT_DATE) AS age_days
                    FROM raw.support_tickets
                    WHERE customer_id = ?
                      AND resolution_time IS NULL
                    ORDER BY
                        CASE priority
                            WHEN 'critical' THEN 0
                            WHEN 'high' THEN 1
                            WHEN 'medium' THEN 2
                            ELSE 3
                        END
                    LIMIT 5
                    """,
                    [customer_id],
                ).fetchall()
            return [
                {"priority": r[0], "topic": r[1], "age_days": r[2]} for r in rows
            ]
        except Exception:
            return []

    def _fetch_gtm_opportunity(self, customer_id: str) -> dict[str, object] | None:
        """Query DuckDB for the most recent active GTM opportunity."""
        try:
            from src.infrastructure.db.duckdb_adapter import get_connection

            with get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT stage, amount, sales_owner, close_date
                    FROM raw.gtm_opportunities
                    WHERE customer_id = ?
                      AND stage NOT IN ('closed_won', 'closed_lost')
                    ORDER BY close_date DESC
                    LIMIT 1
                    """,
                    [customer_id],
                ).fetchone()
            if row:
                return {
                    "stage": row[0],
                    "amount": row[1],
                    "sales_owner": row[2],
                    "close_date": str(row[3]),
                }
            return None
        except Exception:
            return None

    def _fetch_cohort_churn_rate(self, customer: object) -> float:
        """Query the dbt mart for churn rate in the same tier + industry cohort."""
        from src.domain.customer.entities import Customer

        assert isinstance(customer, Customer)
        try:
            from src.infrastructure.db.duckdb_adapter import get_connection

            with get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT AVG(CASE WHEN churn_date IS NOT NULL THEN 1.0 ELSE 0.0 END)
                    FROM raw.customers
                    WHERE plan_tier = ?
                      AND industry = ?
                    """,
                    [str(customer.plan_tier), str(customer.industry)],
                ).fetchone()
            if row and row[0] is not None:
                return float(row[0])
            return 0.0
        except Exception:
            return 0.0
