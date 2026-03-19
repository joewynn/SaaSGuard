"""DuckDB warehouse builder — loads raw CSVs into the saasguard.duckdb file.

Creates the `raw` schema and all 5 source tables with correct column types
matching data_dictionary.md. Idempotent: safe to re-run after regenerating
synthetic data.

Usage: python -m src.infrastructure.db.build_warehouse
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import structlog

logger = structlog.get_logger(__name__)

DATA_DIR = Path("data/raw")
DB_PATH = Path("data/saasguard.duckdb")

DDL: dict[str, str] = {
    "customers": """
        CREATE OR REPLACE TABLE raw.customers (
            customer_id   VARCHAR        NOT NULL,
            industry      VARCHAR        NOT NULL,
            plan_tier     VARCHAR        NOT NULL,
            signup_date   DATE           NOT NULL,
            mrr           DECIMAL(10, 2) NOT NULL,
            churn_date    DATE,
            upgrade_date  DATE
        )
    """,
    "usage_events": """
        CREATE OR REPLACE TABLE raw.usage_events (
            event_id              VARCHAR   NOT NULL,
            customer_id           VARCHAR   NOT NULL,
            timestamp             TIMESTAMP NOT NULL,
            event_type            VARCHAR   NOT NULL,
            feature_adoption_score FLOAT   NOT NULL
        )
    """,
    "support_tickets": """
        CREATE OR REPLACE TABLE raw.support_tickets (
            ticket_id       VARCHAR NOT NULL,
            customer_id     VARCHAR NOT NULL,
            created_date    DATE    NOT NULL,
            priority        VARCHAR NOT NULL,
            resolution_time INTEGER NOT NULL,
            topic           VARCHAR NOT NULL
        )
    """,
    "gtm_opportunities": """
        CREATE OR REPLACE TABLE raw.gtm_opportunities (
            opp_id            VARCHAR        NOT NULL,
            customer_id       VARCHAR        NOT NULL,
            stage             VARCHAR        NOT NULL,
            close_date        DATE           NOT NULL,
            amount            DECIMAL(12, 2) NOT NULL,
            sales_owner       VARCHAR        NOT NULL,
            opportunity_type  VARCHAR        NOT NULL
        )
    """,
    "risk_signals": """
        CREATE OR REPLACE TABLE raw.risk_signals (
            customer_id          VARCHAR NOT NULL,
            compliance_gap_score FLOAT   NOT NULL,
            vendor_risk_flags    INTEGER NOT NULL
        )
    """,
}


def build(db_path: Path = DB_PATH, data_dir: Path = DATA_DIR) -> None:
    """Load all raw CSVs into DuckDB.

    Business Context:
        This is the ingestion step of the SaaSGuard pipeline. dbt reads
        from this DuckDB file via the `raw` schema. The warehouse must be
        rebuilt whenever synthetic data is regenerated.

    Args:
        db_path: Path to the DuckDB file to create/overwrite.
        data_dir: Directory containing the 5 raw CSV files.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("warehouse.build.start", db_path=str(db_path))
    conn = duckdb.connect(str(db_path))

    try:
        conn.execute("CREATE SCHEMA IF NOT EXISTS raw")

        for table, ddl in DDL.items():
            csv_path = data_dir / f"{table}.csv"
            if not csv_path.exists():
                raise FileNotFoundError(
                    f"Missing: {csv_path}. Run generate_synthetic_data first."
                )

            conn.execute(ddl)
            conn.execute(f"COPY raw.{table} FROM '{csv_path}' (HEADER TRUE, NULLSTR '')")
            row = conn.execute(f"SELECT COUNT(*) FROM raw.{table}").fetchone()
            count = row[0] if row else 0
            logger.info("warehouse.table.loaded", table=table, rows=count)
            print(f"  ✓ raw.{table:<22} {count:>10,} rows")

        conn.close()
        logger.info("warehouse.build.complete", db_path=str(db_path))
        print(f"\n✅ Warehouse written to {db_path}")

    except Exception:
        conn.close()
        raise


if __name__ == "__main__":
    print("Building DuckDB warehouse...")
    build()
