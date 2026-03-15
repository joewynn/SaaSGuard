# ADR-002: Adopt Domain-Driven Design (DDD)

**Date:** 2026-03-14
**Status:** Accepted
**Deciders:** Joseph M

## Context

SaaSGuard spans four business contexts (customers, usage, predictions, GTM). Without explicit boundaries, ML pipelines, API handlers, and DB queries tend to intermingle, making the codebase brittle and hard to test.

## Decision

Adopt **DDD with hexagonal architecture**:

- Four bounded contexts: `customer_domain`, `usage_domain`, `prediction_domain`, `gtm_domain`
- Domain layer is pure Python — zero infrastructure imports
- Application layer orchestrates use cases
- Infrastructure layer implements repository interfaces (DuckDB, model registry)
- FastAPI is a thin delivery layer only

## Rationale

- TDD is only viable when domain logic is decoupled from I/O
- Bounded contexts match the four data sources in the schema (customers, usage_events, gtm_opportunities, risk_signals)
- Enables swapping infrastructure (DuckDB → Snowflake, pickle → MLflow) without touching domain logic
- Demonstrates software engineering maturity for senior DS / product analytics roles

## Consequences

- **Positive:** Domain logic is 100% unit-testable with no DB or ML dependencies.
- **Positive:** Repository pattern makes integration tests straightforward with in-memory fakes.
- **Negative:** More files and boilerplate than a notebook-first approach.
- **Accepted trade-off:** Portfolio goal requires demonstrating production-grade engineering, not just analytical skill.
