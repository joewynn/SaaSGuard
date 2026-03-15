#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# create_issues.sh
# Creates all 16 SaaSGuard GitHub Issues from docs/tickets.md spec.
# Each issue uses the user_story template format.
#
# Prerequisites:
#   bash scripts/github_setup.sh   (labels + milestones must exist first)
#   gh auth login
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
export GH_PAGER=

BODY=/tmp/sg_issue_body.md

# ── Guard: abort if issues already exist ─────────────────────────────────────
existing=$(gh issue list --repo joewynn/SaaSGuard --search "SGD-001" --json number --jq 'length')
if [[ "$existing" -gt 0 ]]; then
  echo "⚠️  Issues already exist (found SGD-001). Aborting to prevent duplicates."
  echo "   To re-run, first close or delete all existing SGD issues, then retry."
  exit 1
fi

echo "▶ Creating SaaSGuard GitHub Issues..."
echo "  (docs/tickets.md is the canonical spec — these issues are generated from it)"
echo ""

# ── EPIC 01 – Scoping & Requirements ─────────────────────────────────────────

echo "Creating Phase 1 issues..."

cat > "$BODY" <<'EOF'
## User Story
As a stakeholder, I want to see real customer evidence backing the problem statement so that the project has credibility in an interview or board context.

## Context
SaaSGuard's entire business case rests on documented customer pain. Per `docs/stakeholder-notes.md`, real G2/Capterra/Reddit evidence from Vanta, Drata, and Secureframe users maps directly to churn-predictive signals in the schema (e.g., integration friction → `integration_connect` events, support complaints → `high_priority_tickets` feature).

## Acceptance Criteria
- [ ] ≥5 direct customer quotes sourced from G2, Capterra, Reddit, or equivalent — no simulated quotes
- [ ] Each quote mapped to a product signal in the schema
- [ ] Churn statistics cited from ≥2 independent industry sources (Vitally, Recurly, Churnfree, etc.)
- [ ] `docs/stakeholder-notes.md` merged to `main`

## Definition of Done
- [ ] Merged to `develop` via PR
- [ ] `mkdocs build --strict` passes
- [ ] CHANGELOG.md updated

## References
- Spec: `docs/tickets.md` (SGD-001)
- Output: `docs/stakeholder-notes.md`
EOF
gh issue create \
  --title "SGD-001 · Conduct VoC research and document pain points" \
  --milestone "Phase 1 – Scoping & Requirements" \
  --label "phase-1,p0-critical,type:research" \
  --body-file "$BODY"

cat > "$BODY" <<'EOF'
## User Story
As a hiring manager or stakeholder, I want a concise PRD so that I can understand the problem, solution, and success metrics in under 5 minutes.

## Context
The PRD anchors all downstream work. Every phase deliverable should be traceable to a success metric defined here. References real VoC from `docs/stakeholder-notes.md`.

## Acceptance Criteria
- [ ] Problem statement cites ≥2 real VoC quotes with sources
- [ ] Success metrics are quantified and measurable (AUC threshold, churn % reduction target)
- [ ] In-scope / out-of-scope explicitly stated
- [ ] Risks section with likelihood + mitigation
- [ ] `docs/prd.md` merged and visible in MkDocs nav

## Definition of Done
- [ ] Merged to `develop` via PR
- [ ] `mkdocs build --strict` passes
- [ ] CHANGELOG.md updated

## References
- Spec: `docs/tickets.md` (SGD-002)
- Output: `docs/prd.md`
- Depends on: #1 (VoC research)
EOF
gh issue create \
  --title "SGD-002 · Write 1-page PRD" \
  --milestone "Phase 1 – Scoping & Requirements" \
  --label "phase-1,p0-critical,type:docs" \
  --body-file "$BODY"

cat > "$BODY" <<'EOF'
## User Story
As a VP of Customer Success, I want to see a quantified ROI model so that I can justify the SaaSGuard investment to the CFO.

## Context
Base case: 1% churn reduction on $200M ARR = $2M+ saved. Model must show three scenarios with explicit, cited assumptions. This is the financial anchor for the exec presentation in Phase 8.

## Acceptance Criteria
- [ ] Three scenarios: conservative / base / optimistic with different CS conversion rates and signal coverage
- [ ] Step-by-step base case calculation shown
- [ ] Sensitivity analysis table (vary CS conversion rate, signal coverage, ARR)
- [ ] All input assumptions cited to industry sources
- [ ] `docs/roi-calculator.md` merged and visible in MkDocs nav

## Definition of Done
- [ ] Merged to `develop` via PR
- [ ] Numbers cross-checked against `docs/stakeholder-notes.md` statistics
- [ ] CHANGELOG.md updated

## References
- Spec: `docs/tickets.md` (SGD-003)
- Output: `docs/roi-calculator.md`
- Skill: `/exec-story`
EOF
gh issue create \
  --title "SGD-003 · Build ROI calculator model" \
  --milestone "Phase 1 – Scoping & Requirements" \
  --label "phase-1,p1-high,type:research" \
  --body-file "$BODY"

cat > "$BODY" <<'EOF'
## User Story
As a product analytics interviewer, I want to see how the team maps the customer lifecycle to measurable signals so that I can assess product analytics thinking.

## Context
The Activation → Engagement → Retention → Expansion framework maps directly to SaaSGuard's 4 DDD bounded contexts. Each stage is backed by VoC evidence and a measurable leading metric.

## Acceptance Criteria
- [ ] Mermaid flowchart with all 4 stages rendered in MkDocs
- [ ] Each stage mapped to its bounded context (`customer_domain`, `usage_domain`, etc.)
- [ ] Each stage has ≥1 VoC quote and ≥1 leading metric
- [ ] Feedback loops shown (churn signal → activation/engagement remediation)
- [ ] `docs/growth-framework.md` merged

## Definition of Done
- [ ] Mermaid diagram renders without error in `mkdocs serve`
- [ ] Merged to `develop` via PR
- [ ] CHANGELOG.md updated

## References
- Spec: `docs/tickets.md` (SGD-004)
- Output: `docs/growth-framework.md`
- Depends on: #1 (VoC), #2 (PRD)
EOF
gh issue create \
  --title "SGD-004 · Define growth analytics framework diagram" \
  --milestone "Phase 1 – Scoping & Requirements" \
  --label "phase-1,p1-high,type:docs" \
  --body-file "$BODY"

# ── EPIC 02 – Data Architecture ───────────────────────────────────────────────

echo "Creating Phase 2 issues..."

cat > "$BODY" <<'EOF'
## User Story
As a data scientist, I want a realistic synthetic dataset with known churn correlations so that the model has meaningful signal to learn from and the demo is self-contained.

## Context
5 tables, 5,000 customers, ~10M usage events. Correlations must be baked in: usage decay precedes churn, ticket spikes occur 60 days before churn, `integration_connect` events predict retention. All files DVC-tracked.

## Acceptance Criteria
- [ ] `src/infrastructure/data_generation/generate_synthetic_data.py` produces all 5 CSVs
- [ ] Seeded random state — output is reproducible across runs
- [ ] Correlation checks pass: churned customers have measurably lower `events_last_30d` than active
- [ ] All 5 CSVs tracked with `dvc add data/raw/`
- [ ] `pytest tests/integration/test_data_contracts.py` passes (not_null, uniqueness, range checks)

## Definition of Done
- [ ] Tests written before implementation (`/tdd-cycle`)
- [ ] `dvc repro` runs end-to-end without errors
- [ ] Merged to `develop` via PR
- [ ] CHANGELOG.md updated

## References
- Spec: `docs/tickets.md` (SGD-005)
- Data dictionary: `docs/data_dictionary.md`
- Skills: `/tdd-cycle`, `/dvc-version`, `/data-contract`
EOF
gh issue create \
  --title "SGD-005 · Generate synthetic dataset (Faker, 5k customers)" \
  --milestone "Phase 2 – Data Architecture" \
  --label "phase-2,p0-critical,type:engineering" \
  --body-file "$BODY"

cat > "$BODY" <<'EOF'
## User Story
As a data engineer, I want a tested dbt staging layer so that all downstream models and ML features are built on validated, typed data.

## Context
Staging models cast types, apply naming conventions, and expose business-logic flags (`is_early_stage`, `is_retention_signal`). Schema tests are the data contract — a failing test blocks the dbt run.

## Acceptance Criteria
- [ ] `stg_customers`, `stg_usage_events`, `stg_support_tickets`, `stg_gtm_opportunities`, `stg_risk_signals` exist
- [ ] `schema.yml` has `not_null`, `unique`, `accepted_values`, and freshness checks on all 5 tables
- [ ] `dbt test` passes with zero failures in CI
- [ ] `dbt docs generate` produces browsable lineage site

## Definition of Done
- [ ] `dbt build` passes in GitHub Actions CI step
- [ ] Merged to `develop` via PR
- [ ] CHANGELOG.md updated

## References
- Spec: `docs/tickets.md` (SGD-006)
- Skill: `/data-contract`
- Depends on: #5 (synthetic data)
EOF
gh issue create \
  --title "SGD-006 · Build dbt staging layer with schema tests" \
  --milestone "Phase 2 – Data Architecture" \
  --label "phase-2,p0-critical,type:engineering" \
  --body-file "$BODY"

cat > "$BODY" <<'EOF'
## User Story
As a ML engineer, I want a single feature mart so that model training and batch scoring read from one consistent, tested source of truth.

## Context
`mart_customer_churn_features` is the ML feature store — one row per active customer with all engineered features. Column names must match what `ChurnFeatureExtractor` in `src/` expects.

## Acceptance Criteria
- [ ] Materialised as a `table` in DuckDB
- [ ] Includes all required features: `events_last_30d`, `days_since_last_event`, `avg_adoption_score`, `retention_signal_count`, `tickets_last_30d`, `high_priority_tickets`, `avg_resolution_hours`
- [ ] Column-level dbt tests pass (not_null on all feature columns, range checks)
- [ ] Feature names match `ChurnFeatureExtractor` interface

## Definition of Done
- [ ] `dbt build` passes end-to-end
- [ ] Merged to `develop` via PR

## References
- Spec: `docs/tickets.md` (SGD-007)
- Depends on: #6 (staging layer)
EOF
gh issue create \
  --title "SGD-007 · Build mart_customer_churn_features (ML feature store)" \
  --milestone "Phase 2 – Data Architecture" \
  --label "phase-2,p0-critical,type:engineering" \
  --body-file "$BODY"

# ── EPIC 03 – EDA & Experiments ───────────────────────────────────────────────

echo "Creating Phase 3 issues..."

cat > "$BODY" <<'EOF'
## User Story
As a data scientist, I want Kaplan-Meier survival curves by plan tier so that I can show interviewers I understand censored data and time-to-event analysis.

## Context
Survival analysis is the technically correct framing for churn (not binary classification alone). Showing log-rank tests and discussing the first-90-day dropout window demonstrates senior DS competency.

## Acceptance Criteria
- [ ] Kaplan-Meier curves by `plan_tier` and `industry` rendered in notebook
- [ ] Log-rank test p-values reported and interpreted
- [ ] First-90-day dropout rate quantified per cohort
- [ ] Key finding translated into plain English for Phase 8 exec deck
- [ ] Notebook runs end-to-end from `dvc repro` without errors

## Definition of Done
- [ ] `notebooks/phase3_survival_analysis.ipynb` merged
- [ ] CHANGELOG.md updated

## References
- Spec: `docs/tickets.md` (SGD-008)
- Skill: `/exec-story` for plain-English translation
EOF
gh issue create \
  --title "SGD-008 · Cohort survival analysis notebook" \
  --milestone "Phase 3 – EDA & Experiments" \
  --label "phase-3,p0-critical,type:research" \
  --body-file "$BODY"

cat > "$BODY" <<'EOF'
## User Story
As a product analyst, I want a rigorous experiment design so that I can demonstrate I know how to measure the impact of CS interventions in a small-n B2B context.

## Context
B2B SaaS has small customer counts per segment — classical frequentist tests are often underpowered. Bayesian testing with posterior distributions is the correct approach and demonstrates senior-level thinking.

## Acceptance Criteria
- [ ] Power analysis: MDE, sample size, significance level explicitly stated
- [ ] Bayesian test: posterior plotted, P(treatment > control) reported
- [ ] Written rationale for Bayesian over frequentist in this context
- [ ] `docs/experiment-design.md` documents the design decisions

## Definition of Done
- [ ] `notebooks/phase3_ab_test_simulation.ipynb` merged
- [ ] Experiment design doc merged

## References
- Spec: `docs/tickets.md` (SGD-009)
EOF
gh issue create \
  --title "SGD-009 · A/B test simulation (power analysis + Bayesian)" \
  --milestone "Phase 3 – EDA & Experiments" \
  --label "phase-3,p1-high,type:research" \
  --body-file "$BODY"

# ── EPIC 04 – Predictive Models ───────────────────────────────────────────────

echo "Creating Phase 4 issues..."

cat > "$BODY" <<'EOF'
## User Story
As a CS team lead, I want a calibrated churn probability per customer so that my team can prioritise outreach by predicted revenue at risk.

## Context
XGBoost on `mart_customer_churn_features`. Must be calibrated (not just discriminative) so that a 0.7 score actually means ~70% churn probability. SHAP explanations turn the model into a CS talking-points generator.

## Acceptance Criteria
- [ ] AUC-ROC >= 0.85 on held-out test set
- [ ] Calibration plot shows Brier score < 0.15
- [ ] SHAP waterfall + beeswarm plots generated and saved to `models/`
- [ ] `models/churn_model.pkl` DVC-tracked
- [ ] `models/churn_model_metadata.json` contains version, metrics, feature list, bias check result
- [ ] `XGBoostChurnModel` implements `ChurnModelPort` interface

## Definition of Done
- [ ] Tests written first (`/tdd-cycle` for model accuracy tests)
- [ ] `dvc repro` trains model end-to-end
- [ ] `/self-critique` run before PR

## References
- Spec: `docs/tickets.md` (SGD-010)
- Skills: `/tdd-cycle`, `/dvc-version`
- Depends on: #7 (feature mart)
EOF
gh issue create \
  --title "SGD-010 · Train XGBoost churn classification model" \
  --milestone "Phase 4 – Predictive Models" \
  --label "phase-4,p0-critical,type:ml" \
  --body-file "$BODY"

cat > "$BODY" <<'EOF'
## User Story
As a responsible AI practitioner, I want to verify the model performs equitably across customer segments so that we don't systematically disadvantage any cohort with false high-risk flags.

## Context
Alert fatigue is already a known problem in this space (per `docs/stakeholder-notes.md` — Vanta users reported ignoring alerts). A biased model that over-flags specific industries makes this worse.

## Acceptance Criteria
- [ ] AUC-ROC reported separately by `plan_tier` (starter / growth / enterprise)
- [ ] AUC-ROC reported separately by `industry`
- [ ] No single cohort has AUC < 0.75 (flag for investigation if so)
- [ ] False positive rate compared across cohorts
- [ ] Results documented in `docs/model-card.md`

## Definition of Done
- [ ] Model card merged and visible in MkDocs
- [ ] CHANGELOG.md updated

## References
- Spec: `docs/tickets.md` (SGD-011)
- Ethical guardrails: `docs/ethical-guardrails.md`
- Depends on: #10 (trained model)
EOF
gh issue create \
  --title "SGD-011 · Fairness audit by plan tier and industry cohort" \
  --milestone "Phase 4 – Predictive Models" \
  --label "phase-4,p1-high,type:ml" \
  --body-file "$BODY"

# ── EPIC 05 – AI/LLM Layer ────────────────────────────────────────────────────

echo "Creating Phase 5 issues..."

cat > "$BODY" <<'EOF'
## User Story
As a CSM, I want an AI-generated account brief before a customer call so that I can walk in knowing the top risk signals and what to say — without spending 20 minutes in dashboards.

## Context
Llama-3 via Groq API. Input: `PredictionResult` entity. Output: <=150-word brief with top SHAP-driven talking points. Guardrail: human review required before any customer-facing use. Per `docs/stakeholder-notes.md`, Vanta's AI was criticised for hallucinated responses — this must not happen here.

## Acceptance Criteria
- [ ] Generates <=150-word summary from `PredictionResult`
- [ ] Always appends: `WARNING: AI-generated. Requires human review before customer-facing use.`
- [ ] p95 latency < 3 seconds
- [ ] `docs/ethical-guardrails.md` documents hallucination mitigation strategy
- [ ] Unit tests cover: output contains guardrail disclaimer, latency mock, empty SHAP list edge case

## Definition of Done
- [ ] Tests written first (`/tdd-cycle`)
- [ ] `/self-critique` run before PR
- [ ] CHANGELOG.md updated

## References
- Spec: `docs/tickets.md` (SGD-012)
- Skills: `/tdd-cycle`, `/exec-story`
EOF
gh issue create \
  --title "SGD-012 · Build Llama-3 executive summary generator" \
  --milestone "Phase 5 – AI/LLM Layer" \
  --label "phase-5,p0-critical,type:ai" \
  --body-file "$BODY"

# ── EPIC 06 – Dashboard ───────────────────────────────────────────────────────

echo "Creating Phase 6 issues..."

cat > "$BODY" <<'EOF'
## User Story
As a VP of Customer Success, I want a visual overview of portfolio churn risk so that I can identify which customers need immediate attention and present the risk picture to the board.

## Context
Two views: (1) single-customer Customer 360 — churn score, risk tier, usage trend, top SHAP features; (2) portfolio heatmap — all customers plotted by churn probability x MRR (revenue-at-risk quadrant). This is what interviewers see when you open a browser tab.

## Acceptance Criteria
- [ ] Customer 360 dashboard accessible at `localhost:8088` from `docker compose up`
- [ ] Churn heatmap: x-axis = churn_probability, y-axis = MRR, bubble size = tenure_days
- [ ] Risk drill-down: filter by risk_tier, plan_tier, industry
- [ ] Dashboard JSON exported to `superset/` and version-controlled
- [ ] `docs/dashboard-guide.md` explains each chart with business narrative

## Definition of Done
- [ ] One-command demo verified: `docker compose --profile dev up -d` → open :8088
- [ ] Merged to `develop`

## References
- Spec: `docs/tickets.md` (SGD-013)
- Skill: `/exec-story` for chart narrative copy
- Depends on: #10 (churn model), #11 (fairness audit)
EOF
gh issue create \
  --title "SGD-013 · Build Superset Customer 360 and churn heatmap dashboards" \
  --milestone "Phase 6 – Dashboard" \
  --label "phase-6,p0-critical,type:bi" \
  --body-file "$BODY"

# ── EPIC 07 – Deployment ──────────────────────────────────────────────────────

echo "Creating Phase 7 issues..."

cat > "$BODY" <<'EOF'
## User Story
As a platform engineer, I want the API to run in production mode with multiple workers, a non-root user, and passing healthchecks so that the demo is deployment-ready, not just dev-ready.

## Context
`docker-compose.prod.yml` switches from uvicorn --reload to gunicorn with 4 UvicornWorker processes. Non-root user, resource limits, and K8s-ready labels are required per the Docker Harden skill standards.

## Acceptance Criteria
- [ ] `docker compose -f docker-compose.yml -f docker-compose.prod.yml up` starts gunicorn workers
- [ ] `/health` returns 200 within 15 seconds of container start
- [ ] `docker exec <container> id` does not return `uid=0(root)`
- [ ] All e2e tests in `tests/e2e/` pass against the running container
- [ ] `/docker-harden` skill checklist 100% complete

## Definition of Done
- [ ] `/self-critique` run — all 7 dimensions pass
- [ ] Merged to `main` (not just develop)
- [ ] CHANGELOG.md updated with v1.0.0 tag candidate

## References
- Spec: `docs/tickets.md` (SGD-014)
- Skill: `/docker-harden`
EOF
gh issue create \
  --title "SGD-014 · FastAPI production deployment with gunicorn + Docker hardening" \
  --milestone "Phase 7 – Deployment" \
  --label "phase-7,p0-critical,type:devops" \
  --body-file "$BODY"

cat > "$BODY" <<'EOF'
## User Story
As a VP of Customer Success, I want a change management plan so that I know how to roll out SaaSGuard to my CS team without disrupting existing workflows.

## Context
Interviewers at senior DS / product analytics roles assess change management thinking. The plan must address: who is affected, training requirements, phased rollout, governance, and success metrics. This also demonstrates awareness of the organisational context, not just the technical build.

## Acceptance Criteria
- [ ] `docs/change-management.md` covers: stakeholders, training plan, 3-phase rollout (pilot 30d / full 60d / review 90d), governance model, success metrics
- [ ] `docs/runbook.md` covers: service restart, model staleness response, dbt pipeline failure, data freshness breach
- [ ] Both docs visible in MkDocs nav

## Definition of Done
- [ ] Merged to `develop` via PR
- [ ] CHANGELOG.md updated

## References
- Spec: `docs/tickets.md` (SGD-015)
- Skill: `/exec-story`
EOF
gh issue create \
  --title "SGD-015 · Write change management plan and operations runbook" \
  --milestone "Phase 7 – Deployment" \
  --label "phase-7,p1-high,type:docs" \
  --body-file "$BODY"

# ── EPIC 08 – Executive Presentation ─────────────────────────────────────────

echo "Creating Phase 8 issues..."

cat > "$BODY" <<'EOF'
## User Story
As a job candidate, I want a polished 10-slide executive deck so that I can walk an interviewer through SaaSGuard in 15 minutes and demonstrate senior-level communication, not just technical skill.

## Context
Follows the `/exec-story` skill template: Problem → Current State → Solution → How It Works → Data Credibility → ROI → Pilot Results → Risk & Guardrails → Rollout → Ask. All ROI figures cite `docs/stakeholder-notes.md` and `docs/roi-calculator.md`. No raw ML metrics without business translation.

## Acceptance Criteria
- [ ] 10 slides following `/exec-story` template
- [ ] ROI figures cite real benchmark sources
- [ ] No AUC, F1, or Brier score shown without plain-English business translation
- [ ] Speaker notes for every slide
- [ ] `docs/one-pager.md` — Llama-3 generated 1-page summary of the whole project (with guardrail disclaimer)
- [ ] `docs/presentation/` folder merged and visible in MkDocs nav

## Definition of Done
- [ ] `/self-critique` Dimension 6 (Business Storytelling) passes
- [ ] Merged to `main`
- [ ] GitHub Release v1.0.0 created with deck PDF attached

## References
- Spec: `docs/tickets.md` (SGD-016)
- Skill: `/exec-story`, `/self-critique`
- Inputs: `docs/roi-calculator.md`, `docs/stakeholder-notes.md`, `docs/model-card.md`
EOF
gh issue create \
  --title "SGD-016 · Build 10-slide executive deck with speaker notes" \
  --milestone "Phase 8 – Executive Presentation" \
  --label "phase-8,p0-critical,type:docs" \
  --body-file "$BODY"

rm -f "$BODY"

echo ""
echo "✅ All 16 GitHub Issues created."
echo ""
echo "Next steps:"
echo "  1. Open your repo on GitHub → Issues tab to verify"
echo "  2. Assign issues to yourself"
echo "  3. Move SGD-001 through SGD-004 to 'In Progress' on the Project Board"
echo "  4. Run: /phase-advance Phase 2"
