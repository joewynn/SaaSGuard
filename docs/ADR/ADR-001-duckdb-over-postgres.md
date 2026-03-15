# ADR-001: Use DuckDB as the Analytical Warehouse

**Date:** 2026-03-14
**Status:** Accepted
**Deciders:** Joseph M

## Context

SaaSGuard needs an analytical warehouse to store synthetic data (~5,000 customers, millions of usage events) and serve dbt transformations and ML feature queries. Options considered: PostgreSQL, SQLite, Snowflake, DuckDB.

## Decision

Use **DuckDB** (file-based, `.duckdb` file mounted as a Docker volume).

## Rationale

| Criterion | DuckDB | PostgreSQL | Snowflake |
|---|---|---|---|
| Zero-ops setup | ✅ file-based | ❌ server process | ❌ cloud account |
| OLAP performance | ✅ columnar | ⚠️ row-store | ✅ columnar |
| dbt-core adapter | ✅ dbt-duckdb | ✅ dbt-postgres | ✅ dbt-snowflake |
| Superset support | ✅ duckdb-engine | ✅ | ✅ |
| Cost | ✅ free | ✅ free | ⚠️ trial only |
| DVC versionability | ✅ single file | ❌ dump required | ❌ |
| Portfolio demo (offline) | ✅ | ⚠️ | ❌ |

DuckDB's columnar engine handles analytical queries efficiently without a running server, making `git clone → docker compose up` a true single-command demo.

## Consequences

- **Positive:** Entire warehouse is a single versioned file tracked by DVC. No cloud credentials needed for demo.
- **Negative:** Not suitable for high-concurrency writes (acceptable — this is an analytical, not transactional, system).
- **Migration path:** dbt-duckdb → dbt-snowflake swap is a profiles.yml change if scale requires it.
