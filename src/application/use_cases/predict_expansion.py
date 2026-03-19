"""PredictExpansionUseCase — application layer use case.

Orchestrates domain objects to produce an expansion propensity prediction.
Symmetric mirror of PredictChurnUseCase — same structure, no FastAPI awareness.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.customer.repository import CustomerRepository
from src.domain.expansion.entities import ExpansionResult
from src.domain.expansion.expansion_service import ExpansionModelService


@dataclass
class PredictExpansionRequest:
    """Input DTO for the PredictExpansionUseCase."""

    customer_id: str


class PredictExpansionUseCase:
    """Coordinates customer retrieval and expansion propensity prediction.

    Business Context: Expansion depends on usage signals and GTM intent —
    not compliance risk. The use case is intentionally leaner than
    PredictChurnUseCase (no risk signals repo needed). One DB read per
    layer; total latency < 5ms.

    Args:
        customer_repo: Repository for fetching Customer entities.
        expansion_service: Domain service that runs the expansion model.
    """

    def __init__(
        self,
        customer_repo: CustomerRepository,
        expansion_service: ExpansionModelService,
    ) -> None:
        self._customer_repo = customer_repo
        self._expansion_service = expansion_service

    def execute(self, request: PredictExpansionRequest) -> ExpansionResult:
        """Run the end-to-end expansion propensity pipeline for a single customer.

        Business Context: Fetches customer state and delegates to
        ExpansionModelService which queries mart_customer_expansion_features
        for all 20 ML features. Already-churned customers are excluded
        because they are not expansion candidates.

        Args:
            request: Contains the customer_id to score.

        Returns:
            ExpansionResult with calibrated upgrade propensity, target tier,
            top-5 SHAP feature drivers, and a deterministic GTM action.

        Raises:
            ValueError: If the customer is not found or has already churned.
        """
        customer = self._customer_repo.get_by_id(request.customer_id)
        if customer is None:
            raise ValueError(f"Customer {request.customer_id} not found.")
        if not customer.is_active:
            raise ValueError(
                f"Customer {request.customer_id} has already churned on {customer.churn_date}."
            )

        return self._expansion_service.predict(customer)
