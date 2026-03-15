# Changelog

All notable changes to SaaSGuard are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [Unreleased]

---

## [0.2.0] – 2026-03-14 – Phase 2: Data Architecture

### Added
- Profile-based synthetic data generator (`src/infrastructure/data_generation/generate_synthetic_data.py`) — 5,000 customers, 3.5M usage events, 34K support tickets with causal churn correlations baked in via destiny profiles (early_churner / mid_churner / retained / expanded)
- Sigmoid decay function for usage event frequency approaching churn_date — produces realistic pre-churn disengagement signal
- DuckDB warehouse loader (`src/infrastructure/db/build_warehouse.py`) — idempotent CSV → DuckDB ingestion with typed schema
- Three new dbt staging models: `stg_support_tickets`, `stg_gtm_opportunities`, `stg_risk_signals`
- dbt `schema.yml` for staging layer — source definitions, freshness config, `not_null`/`unique`/`accepted_values` tests on all 5 raw tables and all 5 staging models
- dbt `schema.yml` for marts layer — column descriptions and `not_null` tests on all 13 `mart_customer_churn_features` columns
- 45 integration tests: 13 statistical correlation checks + 32 schema contract checks (all passing)
- `numba>=0.60.0` constraint to fix Python 3.13 compatibility with shap

### Changed
- `mart_customer_churn_features.sql` — support ticket CTE now references `ref('stg_support_tickets')` instead of raw source for proper dbt lineage
- `pyproject.toml` — pinned `numba>=0.60.0`, updated `shap>=0.46.0`

### Data summary (RANDOM_SEED=42)
- Starter tier churn: 43.3% | Growth: 19.7% | Enterprise: 6.7%
- Mann-Whitney U: churned customers have significantly lower events_last_30d (p < 0.001)
- Point-biserial r(avg_adoption_score, is_active) = 0.46 — strong adoption signal

---

## [0.1.0] – Phase 1: Scoping & Requirements

### Added
- Initial project scaffold: DDD folder structure, Docker Compose stack, CI/CD pipeline
- `pyproject.toml` with uv dependency management
- Multi-stage `Dockerfile` (dev / prod targets)
- `docker-compose.yml` with healthchecks for api, dbt, jupyterlab, superset
- `.pre-commit-config.yaml` (ruff, mypy, conventional commits)
- GitHub Actions CI: lint → TDD tests → dbt build → Docker push
- DVC pipeline skeleton (`DVC/dvc.yaml`)
- Architecture docs: Mermaid DDD diagram, ADRs, data dictionary

---

## [0.1.0] - 2026-03-14

_Phase 1 – Scoping & Requirements_

### Added
- `docs/stakeholder-notes.md` — research-backed VoC with 10+ real customer quotes from G2, Capterra, Reddit (r/netsec, r/sysadmin), and 6clicks/Complyjet verified review analyses of Vanta, Drata, Secureframe; churn statistics from Vitally, Recurly, Churnfree (2024–2025)
- `docs/prd.md` — 1-page PRD with cited success metrics, personas, risks, and in/out scope
- `docs/roi-calculator.md` — three-scenario ROI model (conservative/base/optimistic) with sensitivity analysis; base case $1.85M net ROI on $200M ARR
- `docs/growth-framework.md` — Activation → Engagement → Retention → Expansion framework mapped to DDD bounded contexts with Mermaid diagram
- `docs/tickets.md` — 16 Jira-style tickets across 8 epics with acceptance criteria
- Phase 1 section added to `mkdocs.yml` nav
