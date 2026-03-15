# Tickets — SaaSGuard v1.0

> **Single source of truth: [GitHub Issues](https://github.com/josephwam/saasguard/issues)**
>
> This file is the **canonical spec** used to generate GitHub Issues via `scripts/create_issues.sh`.
> Live progress, open/closed state, PR links, and assignees are tracked in GitHub Issues — not here.
> To create all issues from scratch: `bash scripts/github_setup.sh && bash scripts/create_issues.sh`

Epics map to the 8 project phases. Each story has acceptance criteria written from the perspective of the end-user or the CI pipeline.

---

## EPIC-01 — Scoping & Requirements

### SGD-001 · Conduct VoC research and document pain points
**Type:** Research | **Priority:** P0 | **Phase:** 1

**User story:** As a stakeholder, I want to see real customer evidence backing the problem statement so that the project has credibility in an interview or board context.

**Acceptance criteria:**
- [ ] ≥5 direct customer quotes sourced from G2, Capterra, Reddit, or equivalent (no simulated quotes)
- [ ] Each quote mapped to a product signal in the schema (see `stakeholder-notes.md`)
- [ ] Churn statistics cited from ≥2 independent industry sources
- [ ] `docs/stakeholder-notes.md` merged to `main`

---

### SGD-002 · Write 1-page PRD
**Type:** Docs | **Priority:** P0 | **Phase:** 1

**Acceptance criteria:**
- [ ] Problem statement cites real VoC evidence
- [ ] Success metrics defined and measurable
- [ ] In-scope / out-of-scope explicitly stated
- [ ] `docs/prd.md` merged and linked in `mkdocs.yml`

---

### SGD-003 · Build ROI calculator model
**Type:** Analysis | **Priority:** P1 | **Phase:** 1

**Acceptance criteria:**
- [ ] Three scenarios (conservative / base / optimistic) with explicit assumptions
- [ ] Revenue figures derivable from ARR input
- [ ] `docs/roi-calculator.md` includes formula + table

---

### SGD-004 · Define growth analytics framework
**Type:** Docs | **Priority:** P1 | **Phase:** 1

**Acceptance criteria:**
- [ ] Four-stage diagram: Activation → Engagement → Retention → Expansion
- [ ] Each stage mapped to a bounded context in the DDD architecture
- [ ] Mermaid diagram renders in MkDocs
- [ ] `docs/growth-framework.md` merged

---

## EPIC-02 — Data Architecture

### SGD-005 · Generate synthetic dataset
**Type:** Engineering | **Priority:** P0 | **Phase:** 2

**User story:** As a data scientist, I want realistic synthetic data with known correlations so that the churn model has something meaningful to learn from.

**Acceptance criteria:**
- [ ] 5,000 customers, ~10M usage events, proportional GTM/support/risk rows
- [ ] Faker-generated with seeded random state (reproducible)
- [ ] Correlation baked in: usage decay → churn, ticket spike → pre-churn signal
- [ ] All 5 CSVs DVC-tracked (`dvc add data/raw/`)
- [ ] `pytest tests/integration/test_data_contracts.py` passes for all tables

---

### SGD-006 · Build dbt staging layer
**Type:** Engineering | **Priority:** P0 | **Phase:** 2

**Acceptance criteria:**
- [ ] `stg_customers`, `stg_usage_events`, `stg_support_tickets`, `stg_gtm_opportunities`, `stg_risk_signals` exist
- [ ] `schema.yml` has `not_null`, `unique`, `accepted_values`, freshness checks on all tables
- [ ] `dbt test` passes with zero failures
- [ ] `dbt docs generate` produces a browsable lineage site

---

### SGD-007 · Build churn feature mart
**Type:** Engineering | **Priority:** P0 | **Phase:** 2

**Acceptance criteria:**
- [ ] `mart_customer_churn_features` materialised as a table
- [ ] Includes: `events_last_30d`, `days_since_last_event`, `avg_adoption_score`, `retention_signal_count`, `tickets_last_30d`, `high_priority_tickets`, `avg_resolution_hours`
- [ ] Column-level dbt tests pass
- [ ] Features match column names expected by `ChurnFeatureExtractor` in `src/`

---

## EPIC-03 — EDA & Experiment Design

### SGD-008 · Cohort survival analysis
**Type:** Analysis | **Priority:** P0 | **Phase:** 3

**Acceptance criteria:**
- [ ] Kaplan-Meier curves by `plan_tier` and `industry`
- [ ] Log-rank test p-values reported
- [ ] Notebook renders end-to-end from `dvc repro` without errors
- [ ] Key finding translated into plain English for exec-story

---

### SGD-009 · A/B test simulation (power analysis + Bayesian)
**Type:** Analysis | **Priority:** P1 | **Phase:** 3

**Acceptance criteria:**
- [ ] Power analysis: minimum detectable effect, required sample size, significance level stated
- [ ] Bayesian test: posterior distribution plotted, probability of treatment > control reported
- [ ] Rationale for Bayesian approach over frequentist documented (small-n B2B context)

---

## EPIC-04 — Predictive Models

### SGD-010 · Train churn classification model
**Type:** ML | **Priority:** P0 | **Phase:** 4

**Acceptance criteria:**
- [ ] XGBoost model trained on `mart_customer_churn_features`
- [ ] AUC-ROC ≥ 0.85 on held-out test set
- [ ] Calibration plot shows probabilities are calibrated (Brier score < 0.15)
- [ ] SHAP waterfall + beeswarm plots generated
- [ ] `models/churn_model.pkl` DVC-tracked
- [ ] `models/churn_model_metadata.json` contains version, metrics, features, bias check result

---

### SGD-011 · Fairness audit by cohort
**Type:** ML / Ethics | **Priority:** P1 | **Phase:** 4

**Acceptance criteria:**
- [ ] AUC reported separately by `plan_tier` and `industry`
- [ ] No single cohort has AUC < 0.75 (flag for investigation if so)
- [ ] Result documented in `docs/model-card.md`

---

## EPIC-05 — AI/LLM Layer

### SGD-012 · Executive summary generator
**Type:** AI | **Priority:** P0 | **Phase:** 5

**Acceptance criteria:**
- [ ] Llama-3 via Groq API generates ≤150-word account brief from `PredictionResult`
- [ ] Output always includes `⚠️ AI-generated. Requires human review before customer-facing use.`
- [ ] Latency < 3 seconds p95
- [ ] `docs/ethical-guardrails.md` documents hallucination mitigation approach

---

## EPIC-06 — Dashboard

### SGD-013 · Customer 360 Superset dashboard
**Type:** BI | **Priority:** P0 | **Phase:** 6

**Acceptance criteria:**
- [ ] Single customer view: churn score, risk tier, MRR, tenure, last event, top SHAP drivers
- [ ] Churn heatmap: all customers plotted by churn probability × MRR
- [ ] Accessible from `docker compose up` at `localhost:8088`
- [ ] Dashboard JSON exported to `superset/` and version-controlled

---

## EPIC-07 — Deployment

### SGD-014 · FastAPI production deployment
**Type:** Engineering | **Priority:** P0 | **Phase:** 7

**Acceptance criteria:**
- [ ] `docker compose -f docker-compose.yml -f docker-compose.prod.yml up` starts gunicorn workers
- [ ] `/health` returns 200 within 15 seconds of container start
- [ ] All e2e tests in `tests/e2e/` pass against the running container
- [ ] Non-root user confirmed: `docker exec <container> id` does not return `uid=0`

---

### SGD-015 · Change management documentation
**Type:** Docs | **Priority:** P1 | **Phase:** 7

**Acceptance criteria:**
- [ ] `docs/change-management.md` covers: stakeholders, training plan, rollout phases (pilot → full), governance model, success metrics
- [ ] `docs/runbook.md` covers: restart procedures, model staleness response, data pipeline failure response

---

## EPIC-08 — Executive Presentation

### SGD-016 · 10-slide exec deck
**Type:** Presentation | **Priority:** P0 | **Phase:** 8

**Acceptance criteria:**
- [ ] Follows `/exec-story` skill slide template (problem → solution → data → ROI → risk → rollout → ask)
- [ ] ROI figures cite real benchmark sources from `stakeholder-notes.md`
- [ ] No raw ML metrics shown without business translation
- [ ] `docs/presentation/` contains deck outline + speaker notes
