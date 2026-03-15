# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SaaSGuard** is a production-grade, portfolio-ready B2B SaaS churn and risk prediction platform. It ingests product usage, GTM, and support data to predict P(churn in 90 days) and compliance/usage risk scores, delivered via BI dashboards and AI-augmented executive summaries.

**Business context:** Reducing B2B SaaS churn by 1% on $200M ARR saves $2M+. Early CS intervention yields 10–15% churn reduction. The platform attacks specific pain points: poor onboarding (20–25% first-90-day churn), reactive support, and integration friction.

## Tech Stack & Engineering Standards

### Infrastructure

| Layer | Tool |
|---|---|
| Containerization | Docker + Docker Compose v2 (healthchecks, restart policies, multi-stage builds, `depends_on`, volumes) |
| Warehouse | DuckDB (file-based, versioned via DVC) |
| Orchestration | dbt-core + dbt-duckdb adapter (`ghcr.io/dbt-labs/dbt-duckdb`) |
| Analysis/Modeling | JupyterLab container — pandas, scipy, statsmodels, lifelines, shap, xgboost, lightgbm |
| AI/LLM | Llama-3 via Groq/Ollama — executive summaries + RAG |
| Serving | FastAPI (gunicorn workers for scale, OpenAPI docs auto-generated) |
| Dashboard | Apache Superset (Docker image, connects via `duckdb-engine`) |
| Documentation | MkDocs + Material theme (`squidfunk/mkdocs-material`) — auto-generated from docstrings |
| Dependencies | uv (or poetry) — lockfile enforced, reproducible builds |

**Everything runs with a single command (dev profile includes MkDocs + JupyterLab):**

```bash
docker compose --profile dev up -d
```

Demo flow: `git clone` → `docker compose --profile dev up` → open Superset (:8088), FastAPI `/docs` (:8000), JupyterLab (:8888), **MkDocs (:8001)**.

### Architecture: Domain-Driven Design (DDD)

Bounded contexts — all code lives under one of these domains:

- `customer_domain` — customer entities, plan tiers, churn lifecycle
- `usage_domain` — event ingestion, feature adoption scoring
- `prediction_domain` — churn model, risk scores, SHAP explanations
- `gtm_domain` — opportunities, sales signals, CS outreach triggers

Each domain contains: **Entities**, **Value Objects**, **Repositories**, **Domain Services**, **Application Services**. No anemic models.

### Testing: TDD Enforced

- Tests written **first**, then implementation, then passing tests — every code output follows this order
- pytest: unit, integration, model accuracy, API contract tests
- dbt tests: schema + data quality
- Property-based testing: `hypothesis` for edge cases
- Before any phase begins, output the corresponding test suite first

### Versioning

- **Code:** Conventional commits + git flow (`main` / `develop` / `feature/*`)
- **Releases:** Semantic versioning (git tags + GitHub Releases)
- **Data & models:** DVC — tracks DuckDB file, model artifacts, synthetic data

### Documentation Standards

- **Engine:** MkDocs + Material theme — `Dockerfile.mkdocs` extends `squidfunk/mkdocs-material`; runs at `:8001` in dev
- **Auto-generated API docs:** `mkdocstrings[python]` reads Google-style docstrings from `src/`; every new public function appears automatically
- **Plugins:** `mkdocstrings[python]`, `mkdocs-git-revision-date-localized-plugin`, `mkdocs-gen-files`
- **Structure:** `docs/index.md`, `getting-started.md`, `demo.md`, `architecture.md`, `api-reference/` (per domain), `ADR/`, `data_dictionary.md`, `CHANGELOG.md`, `API.md`
- **Build:** `mkdocs build` → `site/` (gitignored); `mkdocs gh-deploy` for GitHub Pages
- **Rule:** Every new function/class needs a Google-style docstring with business context. It will appear in docs automatically.
- **Rule:** Every phase must update relevant `docs/` files and `mkdocs.yml` nav section.
- Always update `CHANGELOG.md` and relevant ADR when architectural decisions change.

### CI/CD

- GitHub Actions pipeline: ruff/black lint → mypy → pytest → dbt build/test → Docker build/push to `ghcr.io`
- Pre-commit hooks (`pre-commit` config)
- Branch protection + conventional commit enforcement

### Observability & Scalability

- Structured logging: `structlog` (JSON output)
- Prometheus metrics endpoint on FastAPI
- Healthchecks + readiness probes in all Docker services
- Stateless services; env-based config via `.env` + `pydantic-settings`
- Kubernetes-ready labels on containers for future scale-out

## Commands

```bash
# --- Full stack (dev profile adds MkDocs + JupyterLab) ---
docker compose --profile dev up -d        # start all services including docs
docker compose up -d                      # production services only (api + dbt + superset)
docker compose up -d --build              # rebuild after config changes
docker compose down                       # tear down

# --- MkDocs ---
docker compose --profile dev up mkdocs    # live docs at http://localhost:8001
docker compose run --rm mkdocs mkdocs build       # build static site → ./site/
docker compose run --rm mkdocs mkdocs gh-deploy   # deploy to GitHub Pages

# --- dbt (inside container) ---
docker compose exec dbt dbt run
docker compose exec dbt dbt test
docker compose exec dbt dbt docs generate && dbt docs serve

# --- Testing (TDD) ---
pytest                                               # full suite
pytest tests/unit/                                   # unit only
pytest tests/integration/                            # integration only
pytest tests/path/to/test_file.py::test_name -v      # single test

# --- Lint / format ---
ruff check .
ruff format .

# --- Type check ---
mypy .

# --- DVC (data & model versioning) ---
dvc add data/saasguard.duckdb
dvc push                        # push to remote storage
dvc pull                        # restore versioned data/models
dvc repro                       # replay pipeline from dvc.yaml

# --- Pre-commit ---
pre-commit install              # set up hooks (run once)
pre-commit run --all-files      # run all hooks manually

# --- Dependency management ---
uv sync                         # install from lockfile
uv add <package>                # add dependency
```

## Data Schema (Synthetic — generated with Faker, never hallucinate columns)

- **customers** (5,000 rows): `customer_id`, `industry`, `plan_tier`, `signup_date`, `mrr`, `churn_date` (censored)
- **usage_events**: `event_id`, `customer_id`, `timestamp`, `event_type` (evidence_upload | monitoring_run | report_view | ...), `feature_adoption_score`
- **gtm_opportunities**: `opp_id`, `customer_id`, `stage`, `close_date`, `amount`, `sales_owner`
- **support_tickets**: `ticket_id`, `customer_id`, `created_date`, `priority`, `resolution_time`, `topic` (compliance | integration | ...)
- **risk_signals**: `customer_id`, `compliance_gap_score`, `vendor_risk_flags`

Data must be generated with realistic correlations: usage decay → churn, ticket volume → risk.

## Project Phases

| Phase | Deliverable |
|---|---|
| 1 – Scoping | PRD, Jira-style tickets, growth analytics framework diagram, ROI calculator |
| 2 – Data Architecture | Full dbt project (models/, macros/, tests/, dbt_project.yml), incremental models, docs site |
| 3 – EDA & Experiments | Cohort analysis, survival curves, small-n A/B test simulation (power analysis + Bayesian) |
| 4 – Predictive Models | XGBoost + survival churn model, risk score model, SHAP explanations, calibration, ROI eval |
| 5 – AI/LLM Layer | Executive summary generator, RAG chatbot ("Ask about customer X"), ethical guardrails doc |
| 6 – Dashboard | Customer 360, churn heatmaps, risk drill-down, uplift simulator |
| 7 – Deployment | FastAPI endpoint, Docker, 5-page change-management deck |
| 8 – Presentation | 10-slide exec deck, speaker notes, 15-min recorded walkthrough |

When asked to work on a phase, output **only** that phase's deliverables + next steps.

## Conventions

### Folder Structure

```
saasguard/
├── src/
│   ├── customer_domain/       # Entities, VOs, Repos, Domain/App Services
│   ├── usage_domain/
│   ├── prediction_domain/
│   └── gtm_domain/
├── dbt/                       # models/, macros/, tests/, dbt_project.yml
├── notebooks/                 # JupyterLab analysis per phase
├── api/                       # FastAPI app (main.py, routers/, schemas/)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── model_accuracy/
├── data/                      # DVC-tracked DuckDB file + synthetic data
├── models/                    # DVC-tracked model artifacts
├── docs/
│   ├── adr/                   # Architecture Decision Records
│   ├── API.md
│   └── data_dictionary.md
├── .github/workflows/         # CI/CD pipelines
├── docker-compose.yml
├── .pre-commit-config.yaml
├── CHANGELOG.md
└── README.md
```

### Code Rules

- **TDD always:** tests first → implementation → green tests. Never deliver code without passing tests.
- **DDD always:** use domain language in naming; no anemic models; logic lives in domain services.
- **Docstrings:** Google-style on all public functions/classes; include a **Business Context** note in all domain service methods.
- **Type hints:** full coverage; mypy must pass with `--strict`.
- All model outputs: SHAP explanations + calibration plots + business ROI framing.
- All LLM outputs: hallucination guardrails + human-in-the-loop annotation.
- Consistent naming across schema → dbt models → API response fields → dashboard labels.
- Prioritize business storytelling alongside technical rigor in all presentation artifacts.

## Loaded Claude Skills

Reusable delivery SOPs live in `skills/`. Invoke with `/skill-name` or trigger automatically with keyword phrases.

| Skill | Invoke | When to use |
|---|---|---|
| `tdd-cycle` | `/tdd-cycle` | Any new entity, service, or model — writes tests first |
| `ddd-entity` | `/ddd-entity` | Creating bounded-context entities, VOs, repositories |
| `phase-advance` | `/phase-advance` | Moving to the next project phase |
| `mkdocs-autoupdate` | `/mkdocs-autoupdate` | After any code change — keeps docs in sync |
| `docker-harden` | `/docker-harden` | Auditing Docker/Compose for production readiness |
| `dvc-version` | `/dvc-version` | Versioning data files or model artifacts |
| `exec-story` | `/exec-story` | Turning findings into C-level narratives + ROI slides |
| `self-critique` | `/self-critique` | Quality review before handing off any output |
| `data-contract` | `/data-contract` | Defining schema tests, Pydantic validation, freshness SLAs |
| `commit-and-close` | `/commit-and-close` | Verify tests, commit with conventional message, push, close GitHub issues |

**Skill chaining:** `/ddd-entity` → auto-chains to `/tdd-cycle` → auto-chains to `/mkdocs-autoupdate`.
**Phase chaining:** `/phase-advance` → runs `/self-critique` → then `/mkdocs-autoupdate` → then `/commit-and-close`.

Full skill documentation: `skills/README.md`
