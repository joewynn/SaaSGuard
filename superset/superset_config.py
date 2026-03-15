"""Apache Superset configuration for SaaSGuard.

Mounted into the Superset container at /app/pythonpath/superset_config.py
"""

import os

# Security
SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "change_me_in_production")

# DuckDB connection string (mounted volume path)
DUCKDB_PATH = os.environ.get("DUCKDB_PATH", "/app/data/saasguard.duckdb")

# Enable feature flags for dashboard embedding (Phase 6)
FEATURE_FLAGS = {
    "EMBEDDED_SUPERSET": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
}

# Allow iframe embedding for the portfolio demo page
HTTP_HEADERS = {"X-Frame-Options": "ALLOWALL"}

# Default row limit for SQL Lab
SQL_MAX_ROW = 100_000
