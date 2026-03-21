# ADR-002: Adopt Domain-Driven Design with Hexagonal Architecture

**Date:** 2026-03-14
**Status:** Accepted
**Deciders:** Engineering

---

## Context

SaaSGuard spans five business contexts — customers, usage, predictions, expansion, and
GTM signals. Without explicit boundaries, ML pipeline logic, API handlers, and database
queries tend to accumulate in the same modules. This creates two operational risks:

1. **Untestability:** Domain rules embedded inside infrastructure code cannot be
   unit-tested without a live database or trained model. Any refactoring of the
   infrastructure layer (e.g., DuckDB → Snowflake) requires retesting business logic.
2. **Coupling brittleness:** A change to the database schema or model artifact format
   propagates unpredictably across the codebase when there is no explicit boundary
   between what the system *is* (domain) and what it *uses* (infrastructure).

---

## Decision

**Domain-Driven Design with hexagonal (ports and adapters) architecture:**

- Five bounded contexts: `customer_domain`, `usage_domain`, `prediction_domain`,
  `expansion_domain`, `gtm_domain`
- Domain layer is pure Python — zero infrastructure imports (`import duckdb`,
  `import fastapi`, file I/O, and HTTP calls are prohibited in `src/domain/`)
- Application layer orchestrates use cases via dependency injection
- Infrastructure layer implements repository interfaces (DuckDB adapter, model registry,
  LLM adapters)
- FastAPI is a thin delivery layer — request validation and response serialisation only

---

## Rationale

**TDD is only viable when domain logic is decoupled from I/O.** The 165-test suite
completes in under 8 seconds locally because no test in `tests/unit/` touches a database
or model artifact. Infrastructure is replaced with injected fakes.

**Bounded contexts match the data sources.** The four raw tables
(`customers`, `usage_events`, `gtm_opportunities`, `risk_signals`) map directly to domain
contexts. Queries that cross context boundaries go through repository interfaces, not
direct SQL joins in application code.

**Infrastructure is swappable without touching domain logic.** The repository interface
pattern means the DuckDB adapter, the pickle-based model registry, and the Groq/Ollama
LLM adapters can each be replaced by a different implementation (Snowflake, MLflow,
a different LLM provider) without modifying any domain entity, value object, or use case.

---

## Consequences

**Positive:**
- Domain logic is 100% unit-testable. Every prediction path — churn scoring, expansion
  propensity, risk tier classification, conflict matrix resolution — is exercised by
  injected fakes with no I/O dependency.
- The repository pattern enables safe infrastructure evolution. A `profiles.yml` change
  and a new adapter class are the only requirements to migrate to a different warehouse.
- Bounded context boundaries enforce a discipline that prevents the model-serving layer
  from accumulating business rules (a common failure mode in ML codebases).

**Negative:**
- More files and explicit interfaces than a pipeline-oriented or notebook-first approach.
  This overhead is the cost of the decoupling guarantee — it is not incidental complexity.

---

## Enforcement

ADR-002 compliance is verified structurally: `src/domain/` has no entries in
`pyproject.toml`'s infrastructure dependency group, and mypy `--strict` with
`disallow_any_generics = true` catches any infrastructure type leaking into domain
modules at CI time.
