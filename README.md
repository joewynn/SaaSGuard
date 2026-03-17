# SaaSGuard

> **Production-ready** B2B SaaS Churn & Risk Prediction Platform

[![Live API](https://img.shields.io/badge/API-Live-brightgreen)](https://saasguard.up.railway.app/docs)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://josephwam.github.io/saasguard/)
[![CI](https://github.com/josephwam/saasguard/actions/workflows/ci.yml/badge.svg)](https://github.com/josephwam/saasguard/actions)
[![codecov](https://codecov.io/gh/josephwam/saasguard/branch/main/graph/badge.svg)](https://codecov.io/gh/josephwam/saasguard)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Live System Links

This project is deployed live as a fully automated MLOps architecture:

- **[System Documentation & ADRs](https://joewynn.github.io/saasguard/)** — Runbooks, Architecture Decision Records, and Data Dictionaries hosted via MkDocs on GitHub Pages
- **[Live Inference API](https://saasguard.up.railway.app/docs)** — FastAPI Swagger UI; test the churn prediction model in real-time
- **[CI/CD Pipelines](https://github.com/joewynn/saasguard/actions)** — Live view of automated data ingestion, performance benchmarking, and drift monitoring workflows

---

## The Business Case

> **1% churn reduction on $200M ARR = $2M+ revenue saved.**
> SaaSGuard predicts which B2B accounts will churn in 90 days — with SHAP explanations
> and AI-generated CS briefs — so teams intervene before the cancellation email.

| Signal | Impact |
|---|---|
| Early onboarding risk (first 90 days) | 20–25% of B2B churn starts here |
| CS proactive outreach (ML-triggered) | 10–15% churn reduction |
| Revenue at risk per enterprise account | MRR × 12 = annual exposure |

---

## One-command demo

```bash
git clone https://github.com/josephwam/saasguard
cd saasguard
cp .env.example .env
docker compose --profile dev up -d   # dev profile adds MkDocs + JupyterLab
```

| Service | URL | Purpose |
|---|---|---|
| FastAPI (Swagger) | http://localhost:8000/docs | Prediction & customer API |
| Apache Superset | http://localhost:8088 | BI dashboard (Customer 360) |
| JupyterLab | http://localhost:8888 | EDA notebooks |
| **MkDocs (docs)** | **http://localhost:8001** | **Full documentation site** |
| Prometheus Metrics | http://localhost:8000/metrics | Observability |

## Live Demo

| Resource | Link |
|---|---|
| **Live API (Swagger UI)** | **https://saasguard.up.railway.app/docs** |
| **Live API (health)** | **https://saasguard.up.railway.app/health** |
| MkDocs Documentation | Deploy: `docker compose run --rm mkdocs mkdocs gh-deploy` |
| 15-min Loom Walkthrough | Record using the stack above — FastAPI, Superset, JupyterLab, MkDocs |

> Steady-state latency (P99) is ~140ms — see [Performance Benchmarks](docs/benchmarks.md).

---

## What this is

SaaSGuard predicts which B2B SaaS customers will churn in the next 90 days and why. It combines:

- **Survival analysis** (time-to-churn, censored data)
- **XGBoost classification** with SHAP explainability
- **Compliance + usage risk scoring**
- **AI executive summaries** (Llama-3 via Groq)
- **Interactive BI dashboard** (Apache Superset)

**Business impact:** Reducing churn by 1% on $200M ARR = **$2M+ revenue saved**.

---

## Architecture

```mermaid
graph LR
    subgraph Docker Compose
        A[FastAPI :8000] --> B[Application Layer]
        B --> C[Domain Layer]
        C --> D[(DuckDB)]
        D --> E[dbt Models]
        E --> F[Apache Superset :8088]
        G[JupyterLab :8888] --> D
    end
```

Full DDD diagram: [docs/architecture.md](docs/architecture.md)

### Domain-Driven Design

| Bounded Context | Responsibility |
|---|---|
| `customer_domain` | Customer lifecycle, plan tiers, churn events |
| `usage_domain` | Product event ingestion, feature adoption scoring |
| `prediction_domain` | Churn model, risk scoring, SHAP explanations |
| `gtm_domain` | Sales opportunities, pipeline risk signals |

### Architecture Decision Records

| ADR | Decision | Trade-off |
|---|---|---|
| [ADR-001](docs/ADR/ADR-001-duckdb-over-postgres.md) | DuckDB over Postgres | Zero-ops file warehouse; versionable with DVC; eliminates managed DB cost for demo |
| [ADR-002](docs/ADR/ADR-002-ddd-architecture.md) | Domain-Driven Design | Bounded contexts enable independent testing; more upfront structure for long-term maintainability |
| [ADR-003](docs/ADR/ADR-003-render-deployment.md) | Railway over AWS/ECS | No cloud credits required; GitHub-native auto-deploy; upgrade path to paid tier is $5/month |
| [ADR-004](docs/ADR/ADR-004-drift-detection.md) | Custom PSI + KS over Evidently.ai | Zero added dependencies; Prometheus-native; PSI is standard credit-risk vocabulary for business stakeholders |

---

## Why I built SaaSGuard

Most churn tools stop at a dashboard. They give you a probability and leave the team to figure out what to do next.

SaaSGuard closes the full loop: raw product + GTM events → calibrated 90-day churn probability → SHAP explanations → AI-generated executive brief → ready-to-act CS recommendations.

I wanted a codebase that enforces the same discipline a real product analytics team would demand: strict DDD bounded contexts, TDD from day one, dbt for reliable data assets, and an LLM layer with actual guardrails instead of prompt engineering vibes.

The result is a system that runs end-to-end with one command and scales from a solo builder to a full team without breaking.

| Stack Choice | What it demonstrates |
|---|---|
| DuckDB + dbt | Full dbt project with staging → intermediate → mart models |
| XGBoost + lifelines | Churn model + survival analysis + SHAP (src/domain/prediction/) |
| Bayesian A/B | Experiment design with small-n power analysis (notebooks/phase3_experiments.ipynb) |
| Llama-3 + guardrails | AI-generated summaries with 3-layer hallucination prevention |
| Apache Superset | BI dashboards with DuckDB — Customer 360, heatmaps, uplift simulator |
| DDD + TDD + CI/CD | Bounded contexts, 153 tests, Docker, semantic versioning, DVC |

---

## Performance Benchmarks

*Auto-updated by `benchmarks.yml` after every merge to `main`. Measured on Railway (US-West, steady-state, 50 concurrent users).*

| Metric | Value |
|---|---|
| P50 latency | ~42ms |
| P95 latency | ~89ms |
| P99 latency | ~140ms |
| Max throughput | ~180 req/s |
| Cold start (free tier) | ~30s |

Full latency table: [docs/benchmarks.md](docs/benchmarks.md)

---

## MLOps Automation

Three GitHub Actions workflows run on schedule — no human trigger required:

| Workflow | Schedule | What it does |
|---|---|---|
| [`data-pipeline.yml`](.github/workflows/data-pipeline.yml) | Every Monday 02:00 UTC | Re-generates synthetic data → dbt build → retrain churn model → export drift baseline |
| [`drift-monitor.yml`](.github/workflows/drift-monitor.yml) | Every Sunday 00:00 UTC | PSI + KS test against training baseline → opens GitHub Issue automatically on PSI > 0.20 |
| [`benchmarks.yml`](.github/workflows/benchmarks.yml) | After every CI deploy | Locust load test (50 users, 60s) → auto-commits updated `docs/benchmarks.md` |

**Drift detection:** Custom PSI + KS implementation (`src/infrastructure/monitoring/drift_detector.py`),
12 features monitored, Prometheus gauges on `/metrics`, runbook in [ADR-004](docs/ADR/ADR-004-drift-detection.md).

---

## Project phases

| Phase | Status | Deliverable |
|---|---|---|
| 1 – Scoping | ✅ | PRD, tickets, ROI calculator |
| 2 – Data Architecture | ✅ | dbt project + DuckDB warehouse |
| 3 – EDA & Experiments | ✅ | Cohort analysis, survival curves, A/B test |
| 4 – Predictive Models | ✅ | XGBoost + survival + SHAP |
| 5 – AI/LLM Layer | ✅ | Executive summaries + RAG chatbot |
| 6 – Dashboard | ✅ | Superset Customer 360 + heatmaps |
| 7 – Deployment | ✅ | FastAPI + Docker + change-management deck |
| 8 – Presentation | ✅ | Executive deck + ROI close + change-management narrative |

---

<details>
<summary>Claude Code Skills (delivery SOPs)</summary>

Reusable delivery SOPs live in `skills/`. See [`skills/README.md`](skills/README.md).
</details>

---

## Documentation

The full documentation site auto-generates from source code docstrings using **MkDocs + Material theme**.

```bash
# Live docs (auto-reloads on code + markdown changes)
docker compose --profile dev up mkdocs
# → http://localhost:8001

# Build static site (for GitHub Pages / Netlify)
docker compose run --rm mkdocs mkdocs build
# → outputs to ./site/

# Deploy to GitHub Pages
docker compose run --rm mkdocs mkdocs gh-deploy
```

Docs are auto-generated from Google-style docstrings in `src/`. Adding a new function with a docstring immediately makes it appear in the [API Reference](http://localhost:8001/api-reference/).

---

## Development

```bash
# Install dependencies
uv sync --all-extras

# Install pre-commit hooks
pre-commit install

# Run tests (TDD – always write tests first)
pytest

# Lint
ruff check . && ruff format .

# dbt
docker compose exec dbt dbt run && dbt test
```

See [docs/API.md](docs/API.md) for HTTP endpoint reference.
See [docs/data_dictionary.md](docs/data_dictionary.md) for schema details.
See [docs/getting-started.md](docs/getting-started.md) for full setup guide.

---

⭐ **Star this repo** if it helped you think about how to build production-grade analytics systems.
