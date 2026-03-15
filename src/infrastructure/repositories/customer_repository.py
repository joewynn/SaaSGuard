"""DuckDB implementation of CustomerRepository."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, Sequence

from src.domain.customer.entities import Customer
from src.domain.customer.repository import CustomerRepository
from src.domain.customer.value_objects import Industry, MRR, PlanTier
from src.infrastructure.db.duckdb_adapter import get_connection


class DuckDBCustomerRepository(CustomerRepository):
    """Reads Customer entities from the DuckDB warehouse."""

    def get_by_id(self, customer_id: str) -> Optional[Customer]:
        """Fetch a single customer by ID."""
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT customer_id, industry, plan_tier, signup_date, mrr, churn_date
                FROM raw.customers
                WHERE customer_id = ?
                """,
                [customer_id],
            ).fetchone()

        if row is None:
            return None
        return self._row_to_entity(row)

    def get_all_active(self) -> Sequence[Customer]:
        """Return all customers without a churn_date."""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT customer_id, industry, plan_tier, signup_date, mrr, churn_date
                FROM raw.customers
                WHERE churn_date IS NULL
                ORDER BY mrr DESC
                """
            ).fetchall()
        return [self._row_to_entity(row) for row in rows]

    def save(self, customer: Customer) -> None:
        """Upsert a customer record."""
        with get_connection(read_only=False) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO raw.customers
                    (customer_id, industry, plan_tier, signup_date, mrr, churn_date)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    customer.customer_id,
                    customer.industry.value,
                    customer.plan_tier.value,
                    customer.signup_date,
                    float(customer.mrr.amount),
                    customer.churn_date,
                ],
            )

    @staticmethod
    def _row_to_entity(row: tuple) -> Customer:  # type: ignore[type-arg]
        customer_id, industry, plan_tier, signup_date, mrr, churn_date = row
        return Customer(
            customer_id=str(customer_id),
            industry=Industry(industry),
            plan_tier=PlanTier(plan_tier),
            signup_date=date.fromisoformat(str(signup_date)),
            mrr=MRR(amount=Decimal(str(mrr))),
            churn_date=date.fromisoformat(str(churn_date)) if churn_date else None,
        )
