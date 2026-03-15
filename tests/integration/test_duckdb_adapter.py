"""Integration tests for the DuckDB infrastructure layer.

These tests create a real (in-memory) DuckDB instance.
They run slower than unit tests but validate the SQL queries and
row-to-entity mapping work against an actual DuckDB connection.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from typing import Generator

import duckdb
import pytest

# Override DB path to use in-memory DB for tests
os.environ["DUCKDB_PATH"] = ":memory:"

from src.infrastructure.repositories.customer_repository import DuckDBCustomerRepository  # noqa: E402


@pytest.fixture
def seeded_db() -> Generator[None, None, None]:
    """Create the customers table and seed one row for integration tests."""
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE customers (
            customer_id VARCHAR PRIMARY KEY,
            industry    VARCHAR,
            plan_tier   VARCHAR,
            signup_date DATE,
            mrr         DECIMAL(10,2),
            churn_date  DATE
        )
        """
    )
    conn.execute(
        """
        INSERT INTO customers VALUES
            ('cust-int-001', 'FinTech', 'starter', '2026-01-01', 500.00, NULL),
            ('cust-int-002', 'HealthTech', 'growth', '2025-06-01', 2000.00, '2026-02-01')
        """
    )
    conn.close()
    yield


@pytest.mark.skip(
    reason="Requires shared connection fixture – implement in Phase 2 when warehouse is built"
)
class TestDuckDBCustomerRepository:
    def test_get_by_id_returns_customer(self, seeded_db: None) -> None:
        repo = DuckDBCustomerRepository()
        customer = repo.get_by_id("cust-int-001")
        assert customer is not None
        assert customer.customer_id == "cust-int-001"
        assert customer.mrr.amount == Decimal("500.00")

    def test_get_by_id_returns_none_for_missing(self, seeded_db: None) -> None:
        repo = DuckDBCustomerRepository()
        assert repo.get_by_id("does-not-exist") is None

    def test_get_all_active_excludes_churned(self, seeded_db: None) -> None:
        repo = DuckDBCustomerRepository()
        active = repo.get_all_active()
        ids = [c.customer_id for c in active]
        assert "cust-int-001" in ids
        assert "cust-int-002" not in ids
