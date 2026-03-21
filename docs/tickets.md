# Tickets — SaaSGuard v1.0

> **Single source of truth: [GitHub Issues](https://github.com/joewynn/saasguard/issues)**
>
> This file is the **canonical spec** used to generate GitHub Issues via `scripts/create_issues.sh`.
> Live progress, open/closed state, PR links, and assignees are tracked in GitHub Issues — not here.
> To create all issues from scratch: `bash scripts/github_setup.sh && bash scripts/create_issues.sh`

Epics map to the 8 project phases. Each story has acceptance criteria written from the perspective of the end-user or the CI pipeline.

---

## EPIC-01 — Scoping & Requirements

### SGD-001 · Conduct VoC research and document pain points
**Type:** Research | **Priority:** P0 | **Phase:** 1

**User story:** As a stakeholder, I want to see real customer evidence backing the problem statement so that the project has credibility with executives and the wider team.

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

---

## EPIC-09 — Expansion Propensity Module

### SGD-037 · Design expansion domain model (entities, VOs, service)
**Type:** Architecture | **Priority:** P1 | **Phase:** Expansion (v0.9.0)

**User story:** As a data scientist, I want a clean DDD expansion domain so that business logic
(tier ladders, ARR uplift, conflict matrix) lives in domain code, not the ML pipeline.

**Acceptance criteria:**
- [ ] `UpgradePropensity` frozen VO validates [0, 1] range; raises on violation
- [ ] `TargetTier` VO encodes tier ladder and `calculate_expected_uplift()` formula
- [ ] `ExpansionResult` entity holds propensity, target tier, SHAP features, ARR uplift, recommended action
- [ ] `ExpansionModelService` returns `ExpansionResult` from feature dict + model output
- [ ] All VOs are immutable (frozen dataclasses)
- [ ] Unit tests pass: 29/29 for VOs + service

---

### SGD-038 · Build expansion feature mart (dbt)
**Type:** Data | **Priority:** P1 | **Phase:** Expansion (v0.9.0)

**User story:** As a ML engineer, I want a single DuckDB mart table with all 20 expansion
features so that the model and API can read features in ~1ms.

**Acceptance criteria:**
- [ ] `mart_customer_expansion_features` contains 20 columns (15 churn + 5 expansion)
- [ ] Scope: active customers who have NOT yet upgraded (expansion candidates only)
- [ ] 5 expansion-specific features: `premium_feature_trials_30d`, `feature_request_tickets_90d`,
  `has_open_expansion_opp`, `expansion_opp_amount`, `mrr_tier_ceiling_pct`
- [ ] dbt schema tests pass (not_null, accepted_values)
- [ ] Mart populates ~3K rows from 5K synthetic customers

---

### SGD-039 · Train expansion propensity model
**Type:** ML | **Priority:** P1 | **Phase:** Expansion (v0.9.0)

**User story:** As a data scientist, I want a calibrated XGBoost model that predicts
P(upgrade in 90d) with AUC ≥ 0.75 so that the top-10% decile captures ≥ $1M ARR.

**Acceptance criteria:**
- [ ] AUC-ROC ≥ 0.75 on held-out test set (20% split, stratified)
- [ ] CalibratedClassifierCV wraps XGBClassifier (isotonic, cv=5)
- [ ] Point-in-time correctness: feature window is [signup_date, REFERENCE_DATE)
- [ ] Leakage guard: `has_open_expansion_opp` must NOT be rank #1 SHAP feature
- [ ] Artifacts written: `models/expansion_model.pkl` + `models/expansion_model_metadata.json`
- [ ] Training script exits non-zero if AUC < 0.70

---

### SGD-040 · Implement `POST /predictions/upgrade` API endpoint
**Type:** API | **Priority:** P1 | **Phase:** Expansion (v0.9.0)

**User story:** As a Sales AE, I want to call `/predictions/upgrade` with a customer_id and
receive the upgrade propensity, target tier, expected ARR uplift, and top SHAP drivers.

**Acceptance criteria:**
- [ ] `POST /predictions/upgrade` returns `UpgradePredictionResponse` (Pydantic v2)
- [ ] Response includes: `upgrade_propensity`, `propensity_tier`, `target_tier`,
  `expected_arr_uplift_annual`, `top_shap_features`, `recommended_action`, `model_version`
- [ ] 422 on unknown customer_id; 409 on already-churned customer
- [ ] OpenAPI docs auto-generated with Business Context in docstring
- [ ] API contract tests pass

---

### SGD-041 · Regenerate synthetic data with expansion signals
**Type:** Data | **Priority:** P1 | **Phase:** Expansion (v0.9.0)

**User story:** As a data engineer, I want the synthetic dataset to include `upgrade_date`,
`premium_feature_trial` events, and `opportunity_type` so that the expansion model has
realistic training signal.

**Acceptance criteria:**
- [ ] `customers.upgrade_date` populated for 10–20% of customers
- [ ] `usage_events.event_type` includes `premium_feature_trial` (7th event type)
- [ ] `gtm_opportunities.opportunity_type` includes `expansion` vs `new_business`
- [ ] Expanded customers have statistically higher `premium_feature_trials_30d`
  (Mann-Whitney U p < 0.05)
- [ ] Integration test `test_expansion_data_contracts.py` passes: 5/5

---

### SGD-042 · Create expansion propensity notebook (Section 10)
**Type:** Notebook | **Priority:** P2 | **Phase:** Expansion (v0.9.0)

**User story:** As an engineering lead reviewing the expansion module, I want a notebook that walks through the complete
expansion analysis — data validation, EDA, calibration, SHAP, ROI, and Propensity Quadrant.

**Acceptance criteria:**
- [ ] `notebooks/expansion_propensity_modeling.ipynb` with 7 sections
- [ ] Section 5 includes leakage guard assertion
- [ ] Section 6 computes top-10% decile ARR uplift ≥ $1M at 25% conversion
- [ ] Section 7 produces `data/propensity_quadrant.png` (primary Superset viz)
- [ ] All cells run without error on a clean kernel
