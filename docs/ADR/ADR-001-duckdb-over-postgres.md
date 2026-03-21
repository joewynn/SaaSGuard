# ADR-001: Use DuckDB as the Analytical Warehouse

**Date:** 2026-03-14
**Status:** Accepted
**Deciders:** Engineering

---

## Context

SaaSGuard requires an analytical warehouse to persist ~5,500 customers, millions of
usage events, and the dbt-built feature marts that feed ML training and inference.
The warehouse must satisfy three constraints:

1. **Auditability:** Feature engineering lives in dbt SQL. The warehouse must support
   dbt-core natively so that any risk tier surfaced in a dashboard is reproducible from
   SQL alone, without a Python runtime.
2. **Versionability:** Model artifacts and training data must be co-versioned. Reproducing
   a historical model run requires restoring both the artifact and the data state.
3. **Operational simplicity:** The system must run in a single-command Docker environment
   with no external services, cloud credentials, or connection management overhead.

Options evaluated: PostgreSQL, SQLite, Snowflake, DuckDB.

---

## Decision

**DuckDB** — file-based columnar warehouse, `.duckdb` file mounted as a Docker volume,
tracked by DVC alongside model artifacts.

---

## Rationale

| Criterion | DuckDB | PostgreSQL | Snowflake |
|---|---|---|---|
| Zero-ops setup | ✅ file-based | ❌ server process | ❌ cloud account required |
| OLAP performance | ✅ columnar, vectorised | ⚠️ row-store | ✅ columnar |
| dbt-core adapter | ✅ dbt-duckdb | ✅ dbt-postgres | ✅ dbt-snowflake |
| Superset support | ✅ duckdb-engine | ✅ | ✅ |
| Cost | ✅ no licensing | ✅ no licensing | ⚠️ consumption-based |
| DVC versionability | ✅ single file — `dvc add` | ❌ requires dump + restore | ❌ external state |

DuckDB's columnar execution engine handles the analytical query patterns (feature aggregation
CTEs, window functions, GROUP BY across millions of events) with sub-second latency on the
5,500-customer dataset. The single-file model means `dvc repro` retrains deterministically
from the exact data state that produced any historical model version.

**Migration path:** The `dbt-duckdb` → `dbt-snowflake` swap is a `profiles.yml` change.
No dbt model SQL requires modification. This is the documented upgrade path if write
concurrency or dataset scale requirements change.

---

## Consequences

**Positive:**
- Entire warehouse is a single versioned file. `dvc pull` restores both data and model
  artifacts to a known state without cloud credentials or network access.
- `dbt run` and feature extraction query the same physical file — no sync lag between
  the feature mart and the inference path.
- dbt data contracts (`schema.yml` tests) run against the live warehouse on every CI run.

**Negative:**
- DuckDB does not support high-concurrency writes. This is acceptable because SaaSGuard
  is an analytical system — reads dominate, and the one write path (dbt build) is a
  scheduled batch process, not a transactional workload.
- File-based storage is not appropriate for multi-node deployments. At the point where
  concurrent dbt + API read load requires horizontal scaling, the `profiles.yml` migration
  to Snowflake or Redshift is the planned path.
