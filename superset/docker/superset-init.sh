#!/usr/bin/env bash
# One-time Superset initialisation – run inside the superset container on first boot.
# Registers the DuckDB database connection and creates an admin user.

set -euo pipefail

echo "▶ Initialising Superset database..."
superset db upgrade

echo "▶ Creating admin user..."
superset fab create-admin \
    --username admin \
    --firstname SaaSGuard \
    --lastname Admin \
    --email admin@saasguard.local \
    --password admin

echo "▶ Initialising Superset defaults..."
superset init

echo "▶ Registering DuckDB connection..."
superset set_database_uri \
    --database_name "SaaSGuard DuckDB" \
    --uri "duckdb:////app/data/saasguard.duckdb" || true

echo "✅ Superset initialisation complete."
