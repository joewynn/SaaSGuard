"""Superset dashboard initialization script for SaaSGuard.

Runs inside the Superset container after first startup to:
  1. Create the DuckDB database connection
  2. Register chart datasets (virtual datasets backed by SQL views)
  3. (Optional) Bootstrap dashboard stubs – add charts manually via UI

Usage:
    docker compose exec superset python /app/pythonpath/init_dashboards.py

Prerequisites:
    - Superset admin user created (via superset fab create-admin)
    - Superset DB initialized (via superset db upgrade && superset init)
    - DuckDB file mounted at /app/data/saasguard.duckdb

Business Context:
    This script automates the Superset setup that would otherwise require 30+
    manual clicks through the UI. It creates the 4 core dashboards defined in
    superset/dashboards/sql/ and wires them to the DuckDB warehouse.
"""

from __future__ import annotations

import os
import sys

# Superset's Flask app context is available when running inside the container
try:
    from superset.connectors.sqla.models import SqlaTable, TableColumn  # type: ignore[import]
    from superset.extensions import db  # type: ignore[import]
    from superset.models.core import Database  # type: ignore[import]
    from superset.models.dashboard import Dashboard  # type: ignore[import]
    from superset.models.slice import Slice  # type: ignore[import]

    from superset import app as superset_app  # type: ignore[import]
    HAS_SUPERSET = True
except ImportError:
    HAS_SUPERSET = False

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "/app/data/saasguard.duckdb")
DUCKDB_URI = f"duckdb:///{DUCKDB_PATH}"

# ── Dashboard metadata ────────────────────────────────────────────────────────

DASHBOARDS = [
    {
        "title": "SaaSGuard – Customer 360",
        "slug": "customer-360",
        "description": (
            "Single-customer risk snapshot: churn probability, ARR at risk, "
            "usage trend, open support tickets, and GTM opportunity status."
        ),
    },
    {
        "title": "SaaSGuard – Churn Heatmap",
        "slug": "churn-heatmap",
        "description": (
            "Portfolio-level churn distribution across plan_tier × industry segments. "
            "Surfaces which cohorts carry the most ARR risk."
        ),
    },
    {
        "title": "SaaSGuard – Risk Drill-Down",
        "slug": "risk-drilldown",
        "description": (
            "Actionable CS intervention list: at-risk customers ranked by ARR impact, "
            "with recommended action, usage decay funnel, and support correlation."
        ),
    },
    {
        "title": "SaaSGuard – Uplift Simulator",
        "slug": "uplift-simulator",
        "description": (
            "What-if analysis: estimated ARR recovery from targeting top-N at-risk customers "
            "with CS interventions at 10/15/20% churn reduction effectiveness."
        ),
    },
]

# Virtual datasets — SQL queries that Superset treats as tables
DATASETS = [
    {
        "schema": "marts",
        "table_name": "mart_customer_risk_scores",
        "sql": None,  # use the dbt-materialized table directly
        "description": "Customer risk scores with churn_score, risk_tier, ARR at risk. Materialized by dbt.",
    },
    {
        "schema": "raw",
        "table_name": "customers",
        "sql": None,
        "description": "Raw customer profiles from synthetic data generation.",
    },
    {
        "schema": "raw",
        "table_name": "usage_events",
        "sql": None,
        "description": "Raw product usage events (evidence_upload, monitoring_run, etc.).",
    },
    {
        "schema": "raw",
        "table_name": "support_tickets",
        "sql": None,
        "description": "Raw support tickets with priority, topic, resolution_time.",
    },
    {
        "schema": "raw",
        "table_name": "gtm_opportunities",
        "sql": None,
        "description": "Raw GTM opportunities: stage, amount, close_date.",
    },
]


def _get_or_create_database(session: object) -> object:
    """Get existing DuckDB connection or create it."""
    from superset.models.core import Database  # type: ignore[import]

    existing = session.query(Database).filter_by(database_name="SaaSGuard DuckDB").first()  # type: ignore[attr-defined]
    if existing:
        print(f"  ✓ Database connection exists: {existing.id}")
        return existing

    db_conn = Database(  # type: ignore[misc]
        database_name="SaaSGuard DuckDB",
        sqlalchemy_uri=DUCKDB_URI,
        expose_in_sqllab=True,
        allow_run_async=True,
        allow_csv_upload=False,
        extra='{"engine_params": {"connect_args": {"read_only": true}}}',
    )
    session.add(db_conn)  # type: ignore[attr-defined]
    session.commit()  # type: ignore[attr-defined]
    print(f"  + Created database connection: {db_conn.id}")
    return db_conn


def _register_dataset(session: object, database: object, dataset_config: dict[str, object]) -> object:
    """Register a virtual dataset (SQL or table) in Superset."""
    from superset.connectors.sqla.models import SqlaTable  # type: ignore[import]

    existing = (
        session.query(SqlaTable)  # type: ignore[attr-defined]
        .filter_by(
            table_name=dataset_config["table_name"],
            schema=dataset_config["schema"],
        )
        .first()
    )
    if existing:
        print(f"  ✓ Dataset exists: {dataset_config['schema']}.{dataset_config['table_name']}")
        return existing

    table = SqlaTable(  # type: ignore[misc]
        table_name=dataset_config["table_name"],
        schema=dataset_config["schema"],
        sql=dataset_config["sql"],
        description=dataset_config["description"],
        database=database,
        is_featured=True,
    )
    session.add(table)  # type: ignore[attr-defined]
    session.commit()  # type: ignore[attr-defined]
    print(f"  + Registered dataset: {dataset_config['schema']}.{dataset_config['table_name']}")
    return table


def _create_dashboard_stub(session: object, config: dict[str, object]) -> None:
    """Create an empty dashboard stub for each SaaSGuard dashboard."""
    from superset.models.dashboard import Dashboard  # type: ignore[import]

    existing = session.query(Dashboard).filter_by(slug=config["slug"]).first()  # type: ignore[attr-defined]
    if existing:
        print(f"  ✓ Dashboard exists: {config['title']}")
        return

    dash = Dashboard(  # type: ignore[misc]
        dashboard_title=config["title"],
        slug=config["slug"],
        description=config["description"],
        published=False,  # publish manually after adding charts
        position_json="{}",
        css="",
    )
    session.add(dash)  # type: ignore[attr-defined]
    session.commit()  # type: ignore[attr-defined]
    print(f"  + Created dashboard: {config['title']} (slug={config['slug']})")


def main() -> None:
    if not HAS_SUPERSET:
        print("ERROR: Superset not importable. Run this inside the Superset container.")
        print("  docker compose exec superset python /app/pythonpath/init_dashboards.py")
        sys.exit(1)

    with superset_app.app_context():
        from superset.extensions import db as superset_db
        session = superset_db.session

        print("\n=== SaaSGuard Superset Initialization ===\n")

        print("1. Creating DuckDB database connection...")
        database = _get_or_create_database(session)

        print("\n2. Registering datasets...")
        for ds_config in DATASETS:
            _register_dataset(session, database, ds_config)

        print("\n3. Creating dashboard stubs...")
        for dash_config in DASHBOARDS:
            _create_dashboard_stub(session, dash_config)

        print("\n✅ Initialization complete.")
        print("""
Next steps (manual in Superset UI at http://localhost:8088):
  1. Go to Data > Datasets and verify all 5 datasets are listed.
  2. Open each dashboard and use Charts > + to add the charts
     defined in superset/dashboards/sql/*.sql.
  3. Configure native filters (customer_id for Customer 360,
     plan_tier + industry for Churn Heatmap).
  4. Set dashboard to 'Published' when ready for demo.

Superset credentials: admin / admin (change in production)
""")


if __name__ == "__main__":
    main()
