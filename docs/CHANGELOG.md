# Changelog

All notable changes to SaaSGuard are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [Unreleased]

---

## [1.2.0] – 2026-03-21 – Expansion Narrative Service (Signal-to-Action Engine)

### Added

- **`POST /summaries/expansion`** — new FastAPI endpoint that generates a personalised AE tactical brief + optional email draft from the expansion propensity model output; propensity gates at 0.15 (HTTP 422) and 0.35 (no-LLM "not ready" message)
- **`ExpansionGuardrailsService`** — three-gate validation for expansion LLM output: Gate 1 hallucination detection (snake_case whitelist → REJECTED at 2+ flags), Gate 2 tone calibration (strip urgency if propensity < 0.50), Gate 3 PII/jargon scrub on email drafts only; confidence = 1.0 − (0.25 × n_flags)
- **`ExpansionSummaryResult`** entity with `correlation_id` UUID for V2 lift-measurement data flywheel (join brief quality → close rates in `expansion_outreach_log`)
- **`GenerateExpansionSummaryUseCase`** — full orchestration: customer guard → expansion predict → propensity gates → CSM audience override → LLM call → guardrails → result
- **`SummaryPort.generate_from_prompt()`** — new abstract method for pre-assembled prompt strings; implemented on both `GroqSummaryService` and `OllamaSummaryService` (max_tokens=600, temperature=0.2)
- **`PromptBuilder.build_expansion_prompt()`** — expansion-specific prompt builder injecting only SHAP-verified facts; AE audience adds optional email draft section labelled `[EMAIL_DRAFT]`
- **32 new unit tests** (13 domain guardrails + 10 application use case + 9 API router); full suite: 197 passed, 85.5% coverage
- **Pre-req fix**: `build_warehouse.py` now loads `expansion_outreach_log.csv` into `raw` schema — unblocks dbt tests for `stg_expansion_outreach` and `mart_propensity_quadrant`

### Changed

- `SummaryPort` (abstract) — added `generate_from_prompt` abstract method (backwards-compatible: existing implementations `GroqSummaryService` and `OllamaSummaryService` now implement both methods)
- `app/dependencies.py` — added `get_expansion_summary_use_case()` factory with `@lru_cache(maxsize=1)`
- `app/main.py` — registered `expansion_summary.router` under `/summaries` prefix

---

## [0.9.1] – 2026-03-19 – Pipeline Activation + Business Narrative

### Added

- **Data pipeline fully activated**: synthetic data regenerated (5K customers, 3.57M events), DuckDB warehouse rebuilt with `upgrade_date` + `opportunity_type` columns, all mart tables populated
- **Expansion model trained**: AUC=0.928, Brier=0.190, precision@decile1=21.7%; artifacts at `models/expansion_model.pkl`
- **Notebook** `notebooks/expansion_propensity_modeling.ipynb` — 7 sections: data validation, EDA, correlation heatmap, calibration, SHAP beeswarm + leakage guard, decile ROI, Propensity Quadrant
- **`docs/economic-model.md`** — NRR bridge document: formula, churn baseline + expansion addendum, combined scenario table ($1.5M–$5.5M), payback ≤17 days, conversion-rate sensitivity
- **Business document updates**:
  - `docs/prd.md` — Expansion Propensity Addendum (problem extension, new personas, new success metrics)
  - `docs/roi-calculator.md` — Section 4 (expansion revenue model) + Section 5 (combined NRR calculator, 20× ROI)
  - `docs/growth-framework.md` — Stage 4 expanded with Propensity Quadrant diagram, conflict matrix, tier ladder with multipliers
  - `docs/tickets.md` — EPIC-09 (stories SGD-037 through SGD-042)
  - `docs/model-design.md` — Section 2: Expansion Propensity Model (20 features, training design, leakage guard, thresholds)
  - `docs/data_dictionary.md` — `upgrade_date`, `premium_feature_trial`, `opportunity_type`, `mart_customer_expansion_features` (5 columns)
- **Deck** `docs/presentation/deck.md` — Slide 11: "Retain + Expand" with Propensity Quadrant and $3.2M combined NRR
- **One-pager** `docs/one-pager.md` — expansion ROI row ($1.2M) added to proof table
- **`scripts/run_dbt_models.py`** — Docker-free dbt runner executing all staging views and mart tables directly against DuckDB
- **`DVC/dvc.yaml`** — `train_expansion_model` stage added for full pipeline reproducibility
- **`mkdocs.yml`** — `economic-model.md` added to Product & Planning nav section

### Fixed

- `src/infrastructure/db/build_warehouse.py` — DDL updated to include `upgrade_date` (customers) and `opportunity_type` (gtm_opportunities)
- `Dockerfile` — `train_expansion_model` step added to `data-gen` stage so `expansion_model.pkl` is present in prod image
- `docker-compose.yml` — jupyterlab healthcheck added

### Metrics

- 53/53 expansion tests pass (unit + integration + property-based)
- Mann-Whitney U: expanded customers have statistically more `premium_feature_trials_30d` (p < 0.05)
- Combined NRR impact base case: **$3.2M** ($2.0M churn protection + $1.2M expansion capture)
- Payback period: **17 days** (vs. 30 days for churn-only)

---

## [0.9.0] – 2026-03-19 – Expansion Propensity Module

### Added

- **Expansion domain** (`src/domain/expansion/`) — bounded context mirroring the prediction domain:
  - `UpgradePropensity` value object: P(upgrade in 90d), tier mapping via `RiskTier`
  - `TargetTier` value object: tier-ladder logic, ARR uplift multipliers, `calculate_expected_uplift()`
  - `ExpansionResult` entity: `expected_arr_uplift`, `is_high_value_target`, `recommended_action()` with conflict matrix
  - `ExpansionModelService` domain service with `ExpansionModelPort` ABC and `ExpansionFeatureVector` Protocol
- **Infrastructure** (`src/infrastructure/ml/`):
  - `ExpansionFeatureExtractor` — 20-feature dual-path extractor (mart + raw SQL fallback)
  - `XGBoostExpansionModel` — CalibratedClassifierCV + TreeExplainer adapter
  - `train_expansion_model.py` — full training pipeline with point-in-time correctness, leakage guard, AUC/Brier thresholds
- **Application layer** (`src/application/use_cases/predict_expansion.py`) — `PredictExpansionUseCase`
- **API layer**:
  - `POST /predictions/upgrade` — upgrade propensity endpoint
  - `GET /predictions/customers/{id}/360` — full NRR lifecycle view with conflict-matrix routing
  - `UpgradePredictionRequest/Response`, `Customer360Response` Pydantic schemas
- **dbt**:
  - `mart_customer_expansion_features.sql` — 20-feature expansion mart (reuses churn mart via JOIN)
  - Schema tests block for all 20 columns in `schema.yml`
- **Synthetic data** (`generate_synthetic_data.py`):
  - `upgrade_date` column on customers (expanded destiny)
  - `premium_feature_trial` event type (7th event type, destiny-weighted)
  - `opportunity_type` column on GTM opportunities (`expansion` vs `new_business`)
  - Feature-request ticket topic boost for expanded customers
- **dbt staging updates**: `upgrade_date`/`is_upgraded` in `stg_customers`, `is_premium_trial` in `stg_usage_events`, `opportunity_type`/`is_open_expansion_opp` in `stg_gtm_opportunities`
- **Tests** (TDD-first):
  - `tests/unit/domain/test_expansion_value_objects.py` — hypothesis property tests + tier mapping
  - `tests/unit/domain/test_expansion_service.py` — fake model isolation tests
  - `tests/unit/application/test_predict_expansion_use_case.py` — use case layer tests
  - `tests/integration/test_expansion_data_contracts.py` — Mann-Whitney U causal coherence check
- **LLM**: expansion audience in `PromptBuilder`, 5 new features in `KNOWN_FEATURES` whitelist
- **Documentation**: `docs/expansion-model-card.md`, `docs/expansion-propensity-methodology.md`, `docs/api-reference/expansion.md`
- `PlanTier.CUSTOM` added to customer domain for seat/add-on expansion tier

### Changed

- `mkdocs.yml` — Expansion Model Card and Methodology in Models nav; Expansion Domain in API Reference nav
- `app/dependencies.py` — `get_predict_expansion_use_case()` singleton
- `src/domain/customer/value_objects.py` — `PlanTier.CUSTOM` added

---

## [0.8.0] – 2026-03-15 – Phase 8: Executive Presentation

### Added

- `docs/presentation/deck.md` — 10-slide executive deck in Markdown; renders in MkDocs, pasteable to Google Slides
- `docs/presentation/speaker-notes.md` — full per-slide speaker notes with Vanta-specific language, timing guide, and lightning (5-min) variant
- `docs/presentation/video-script.md` — 15-min Loom walkthrough script with `[MM:SS]` timestamps, `[SCREEN: ...]` cues, `[PAUSE]` markers, and post-production notes
- `docs/one-pager.md` — 4-section 30-second-skim executive summary: problem, platform, proof, ask
- `README.md` — Live Demo section, phase status `🔲→✅` for all 8 completed phases, `commit-and-close` skill added to table, star CTA at bottom

### Changed

- `mkdocs.yml` — Phase 8 nav section (deck, speaker notes, video script, one-pager)

### Metrics Targets (v0.8)

- Deck: 10 slides, ≤15 min to present, ≤5 min lightning version
- Video: 15 min, 7 segments, timestamped chapters for Loom
- One-pager: ≤30 seconds to skim, 4 sections only

---

## [0.7.0] – 2026-03-14 – Phase 7: Deployment & Change Management

### Added

- `app/routers/customers.py` — `GET /customers/{customer_id}` Customer 360 endpoint (replaced placeholder)
- `app/schemas/customer.py` — `Customer360Response` and `ShapFeatureSummary` Pydantic schemas
- `src/application/use_cases/get_customer_360.py` — `GetCustomer360UseCase` orchestrates customer data, churn prediction, usage velocity, support health, and GTM stage
- `app/main.py` — `/ready` readiness probe (returns 503 when model artifacts missing); `model_registry_loaded()` helper
- `gunicorn.conf.py` — extracted Gunicorn tuning from Dockerfile; auto-scales workers to `2 * cpu_count + 1`
- `.github/workflows/ci.yml` — `security-scan` job (Trivy, SARIF upload to GitHub Security tab) and `smoke-test` job (pulls image, hits `/health` and `/ready`)
- `docs/change-management.md` — 5-section stakeholder plan: stakeholder map, training plan, phased rollout, governance, success metrics
- `docs/runbook.md` — on-call operations: alert response, deployment procedure, rollback, data refresh, model retraining
- `tests/unit/api/test_customers_router.py` — 4 TDD tests for Customer 360 endpoint
- `tests/unit/api/test_health_endpoints.py` — 3 TDD tests for `/health` and `/ready`
- `tests/e2e/test_production_scenarios.py` — CORS lockdown and full flow E2E tests

### Changed

- `app/main.py` — CORS now restricted to `ALLOWED_ORIGINS` env var (default: `localhost:3000,localhost:8088`); bumped version to `0.7.0`
- `Dockerfile` — production CMD uses `gunicorn.conf.py` instead of hardcoded flags; copies `gunicorn.conf.py` in prod stage
- `docker-compose.prod.yml` — added `ALLOWED_ORIGINS` env var; updated CMD to use `gunicorn.conf.py`
- `.env.example` — added `ALLOWED_ORIGINS` configuration variable
- `mkdocs.yml` — added Phase 7 nav entries (Change Management + Runbook)

### Security

- CORS wildcard `allow_origins=["*"]` replaced with explicit origin allowlist
- Container vulnerability scanning (Trivy) added to CI/CD; fails on CRITICAL/HIGH CVEs
- Production smoke tests validate `/health` and `/ready` on every main/develop push

### Metrics Targets (v0.7)

- Customer 360 API response time: < 200ms p95
- `/ready` probe correctly reflects model artifact state
- CORS allows only configured origins
- CI passes with Trivy scan and smoke test

---

## [0.6.0] – 2026-03-14 – Phase 6: Dashboard

### Added

- `dbt_project/models/marts/mart_customer_risk_scores.sql` — new dbt mart:
  rule-based churn scores, risk tier, ARR at risk, intervention value,
  top risk drivers; 9 risk flag signals derived from Phase 4 feature set
- `dbt_project/models/marts/schema.yml` — added `mart_customer_risk_scores`
  model with column-level tests (not_null, unique, accepted_values)
- `superset/dashboards/sql/customer_360.sql` — 5 chart definitions:
  Risk KPI header, flag breakdown, usage trend (90d), open tickets, GTM opportunity
- `superset/dashboards/sql/churn_heatmap.sql` — 6 chart definitions:
  plan_tier × industry heatmap, risk tier donut, ARR by tier, churn by industry,
  KPI row, score distribution histogram
- `superset/dashboards/sql/risk_drilldown.sql` — 5 chart definitions:
  at-risk customer table (conditional formatting), usage-decay scatter,
  engagement funnel, support correlation, onboarding activation gate
- `superset/dashboards/sql/uplift_simulator.sql` — 5 chart definitions:
  cumulative ARR recovery curve, ROI table (top-10/25/50/100),
  segment uplift, KPI summary, early-stage intervention value
- `superset/init_dashboards.py` — Flask CLI script: creates DuckDB connection,
  registers 5 datasets, creates 4 dashboard stubs; run inside Superset container
- `superset/dashboards/README.md` — quick-start setup guide
- `docs/dashboard-guide.md` — comprehensive guide: chart interpretations,
  business narratives, how-to-use for each of the 4 dashboards,
  data freshness schedule, known limitations

### Dashboard Business Narratives

- **Customer 360**: CSM pre-call prep 15min → 30sec
- **Churn Heatmap**: VP CS portfolio risk posture in 30s; data-driven resource allocation
- **Risk Drill-Down**: Daily CS intervention queue; validates Phase 3/4 analytical findings
- **Uplift Simulator**: $10M at-risk ARR → $580K recoverable from top-50 accounts at 4:1 ROI

---

## [0.5.0] – 2026-03-14 – Phase 5: AI/LLM Layer

### Added

- `src/domain/ai_summary/` — new bounded context: `ExecutiveSummary`, `SummaryContext`,
  `GuardrailResult` entities; `SummaryPort` ABC; `GuardrailsService` with three-layer
  hallucination defence (feature whitelist, probability accuracy ±2pp, watermark)
- `src/infrastructure/llm/groq_summary_service.py` — `GroqSummaryService` implementing
  `SummaryPort` via Groq Cloud API (`llama-3.1-8b-instant`, temperature=0.2)
- `src/infrastructure/llm/ollama_summary_service.py` — `OllamaSummaryService` local fallback
  via Ollama Docker sidecar (`llama3.1:8b`)
- `src/infrastructure/llm/prompt_builder.py` — `PromptBuilder`: assembles structured
  `[CONTEXT]` + `[INSTRUCTION]` + `[CONSTRAINT]` prompts from `SummaryContext` data
- `src/application/use_cases/generate_executive_summary.py` — `GenerateExecutiveSummaryUseCase`:
  full pipeline (fetch customer → predict churn → build context → LLM call → guardrails)
- `src/application/use_cases/ask_customer_question.py` — `AskCustomerQuestionUseCase`:
  RAG chatbot using context-stuffing strategy; `scope_exceeded` flag for out-of-context questions
- `app/routers/summaries.py` — `POST /summaries/customer` + `POST /summaries/customer/ask`
- `app/schemas/summary.py` — `GenerateSummaryRequest/Response`, `AskCustomerRequest/Response`
- `app/dependencies.py` — `get_summary_use_case()`, `get_ask_use_case()` with `LLM_PROVIDER`
  env-var switching (groq | ollama)
- `docker-compose.yml` — `ollama` service under dev profile; `ollama_data` named volume
- `.env.example` — `GROQ_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`, `OLLAMA_HOST`
- `pyproject.toml` — `groq>=0.9.0`, `ollama>=0.3.0` dependencies
- `docs/ethical-guardrails.md` — three-layer guardrail documentation, bias considerations,
  human-in-loop annotation plan, escalation path by confidence score
- `docs/llm-time-saved.md` — CS productivity ROI: 15 min → 30 sec, $129K annual savings,
  compounding churn-reduction ROI, Phase 7 feedback loop design
- `tests/unit/domain/test_guardrails_service.py` — 8 tests: clean pass, watermark, hallucinated
  feature detection, probability mismatch, confidence score degradation
- `tests/unit/application/test_generate_executive_summary.py` — 7 tests: entity returned,
  watermark present, unknown customer 404, guardrail failure graceful, clean pass
- `tests/e2e/test_summary_endpoints.py` — 6 endpoint tests with mocked use cases
- `tests/integration/test_groq_summary_service.py` — 3 integration tests (skip if no GROQ_API_KEY)

### Changed

- `app/main.py` — includes `summaries.router` at `/summaries`
- `app/dependencies.py` — extended with LLM dependency wiring
- `src/domain/ai_summary/entities.py` — `ExecutiveSummary` stores `prediction` for router access

### Metrics Targets

| Metric | Target |
|---|---|
| Guardrail pass rate | > 90% |
| Probability accuracy | ±2pp |
| Latency (Groq) | < 3s p95 |
| Latency (Ollama) | < 15s p95 |

---

## [0.4.0] – 2026-03-14 – Phase 4: Predictive Models

### Added

- `tests/model_accuracy/test_churn_model.py` — TDD accuracy gate: AUC > 0.80, Brier < 0.15,
  calibration within 15pp of KM estimate per tier, top-2 SHAP features are known signals,
  POST /predictions/churn endpoint returns 200 + correct schema (all tests skip until model is trained)
- `src/infrastructure/ml/train_churn_model.py` — Point-in-time–correct training script:
  builds feature matrix for all 5,000 customers (churned + active), time-based split
  (train: signup < 2025-06-01, test: ≥ 2025-06-01), XGBoost pipeline + CalibratedClassifierCV,
  global SHAP importance, model artifacts → models/
- `src/infrastructure/ml/xgboost_churn_model.py` — ChurnModelPort implementation: loads
  calibrated sklearn Pipeline, serves predict_proba() via CalibratedClassifierCV,
  SHAP explanations via TreeExplainer on the base XGBoost step
- `src/infrastructure/ml/churn_feature_extractor.py` — ChurnFeatureVector implementation:
  queries marts.mart_customer_churn_features for all 15 features in one DuckDB read (~1ms)
- `src/domain/prediction/risk_signals_repository.py` — RiskSignalsRepository ABC (domain port)
- `src/infrastructure/repositories/risk_signals_repository.py` — DuckDBRiskSignalsRepository:
  fetches compliance_gap_score + vendor_risk_flags from raw.risk_signals, computes
  usage_decay_score as recent vs. prior 30-day event ratio
- `notebooks/phase4_01_model_training.ipynb` — End-to-end training narrative: dataset
  construction, class balance, feature correlation recap, model training + hyperparameter
  choices, AUC/Brier/calibration evaluation, SHAP global importance + customer waterfall,
  CS ROI at top decile

### Changed

- `dbt_project/models/marts/mart_customer_churn_features.sql` — Added `integration_connects_first_30d`
  CTE and column (Phase 3 finding #2: ≥3 integrations in 30d → 2.7× lower churn rate)
- `dbt_project/models/marts/schema.yml` — Added `not_null` test for `integration_connects_first_30d`
- `src/domain/prediction/churn_model_service.py` — Updated `ChurnFeatureVector` Protocol:
  `extract()` now takes only `customer: Customer` (events no longer needed; all feature
  engineering lives in dbt mart). Removed `recent_events` from `ChurnModelService.predict()`.
- `src/application/use_cases/predict_churn.py` — Fixed hardcoded zero risk signals (lines 74–78):
  now resolves real risk data via optional `RiskSignalsRepository`; falls back to zeros when
  not provided (backward-compatible for unit tests)
- `app/dependencies.py` — Wired `DuckDBRiskSignalsRepository` into `get_predict_churn_use_case()`
- `DVC/dvc.yaml` — Updated `train_churn_model` stage: now points to correct training module,
  added params.yaml dependency for reproducible seeding

### Model metrics (RANDOM_SEED=42, out-of-time test set)

- AUC-ROC: > 0.80 (target met)
- Brier score: < 0.15 (target met)
- Precision @ top decile: > 0.60 (target met)
- Top SHAP features: events_last_30d, avg_adoption_score, days_since_last_event

---

## [0.3.0] – 2026-03-14 – Phase 3: EDA & Experiments

### Added

- `notebooks/phase3_01_eda_cohort_analysis.ipynb` — Monthly cohort retention heatmap,
  plan tier × industry churn rates, feature distributions (churned vs. active violin
  plots), Spearman correlation heatmap, integration activation gate analysis (SGD-008)
- `notebooks/phase3_02_survival_analysis.ipynb` — Kaplan-Meier curves by plan tier and
  industry, log-rank tests, first-90-day dropout heatmap, integration threshold KM split,
  Cox proportional hazards model (HR + 95% CI + forest plot), intervention window
  identification via smoothed hazard rate (SGD-008)
- `notebooks/phase3_03_ab_test_simulation.ipynb` — Frequentist power analysis proving
  inadequacy for small-n B2B cohorts, Bayesian Beta-Bernoulli simulation, P(treatment >
  control) vs. n sample size curves, experiment governance model (SGD-009)
- `tests/model_accuracy/test_feature_signal.py` — Pre-modelling signal validation:
  log-rank p < 0.01 for KM tier separation, events_last_30d |r| > 0.30, retention_signal_count
  in top 3 features, starter 90-day dropout > 25% (all tests passing)
- `docs/experiment-design.md` — Formal experiment spec: H₀/H₁, randomisation unit,
  primary/secondary metrics, MDE, Bayesian prior justification, sample size table,
  decision criteria, governance model with human-in-the-loop gate (SGD-009)
- `docs/eda-findings.md` — 5-finding executive summary with statistical evidence, business
  insights, exec deck bullets, and ROI model validation/challenge for each finding

### Data (Phase 3 derived features — see data_dictionary.md)

- `events_last_30d` — Usage events in 30-day window before reference/churn date (all customers)
- `integration_connects_first_30d` — integration_connect events in first 30 days of tenure
- `retention_signal_count` — Count of evidence_upload, monitoring_run, report_view events
- `duration_days` — Survival time: days from signup to churn or reference date
- `event` — Survival event indicator (1 = churned, 0 = right-censored)

### Key analytical findings

- Starter 90-day dropout: ~33% (higher than PRD estimate; strengthens intervention ROI case)
- Integration gate: ≥3 integrations in 30d → 2.7× lower churn rate (log-rank p < 0.001)
- Cox PH: enterprise HR = 0.18 vs. starter (82% lower hazard after controlling for usage)
- Bayesian design: n = 60/arm achieves 88% confidence for 5pp MDE — achievable in 1 quarter
- Top feature: events_last_30d, avg_adoption_score, retention_signal_count (all |r| > 0.30)

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
