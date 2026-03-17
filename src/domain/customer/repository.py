"""CustomerRepository – abstract port (interface) for the Customer domain.

Infrastructure implementations live in src/infrastructure/repositories/.
The domain layer depends only on this interface, never on DuckDB directly.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from src.domain.customer.entities import Customer


class CustomerRepository(ABC):
    """Port (interface) for persisting and retrieving Customer entities."""

    @abstractmethod
    def get_by_id(self, customer_id: str) -> Customer | None:
        """Retrieve a customer by their unique ID.

        Returns:
            Customer entity, or None if not found.
        """
        ...

    @abstractmethod
    def get_all_active(self) -> Sequence[Customer]:
        """Return all customers who have not yet churned.

        Used for batch churn scoring runs.
        """
        ...

    @abstractmethod
    def get_sample(self, n: int) -> Sequence[Customer]:
        """Return a random sample of n customers (any churn status).

        Business Context:
            Used by the demo list endpoint to seed load-test tooling and
            the UI customer picker. Deterministic seed (REPEATABLE 42) ensures
            the same customers are returned across requests for reproducibility.

        Args:
            n: Number of customers to sample (caller must clamp to safe max).
        """
        ...

    @abstractmethod
    def save(self, customer: Customer) -> None:
        """Persist a new or updated Customer entity."""
        ...
