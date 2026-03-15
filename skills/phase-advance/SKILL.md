---
name: phase-advance
description: Advance SaaSGuard to the next project phase. Generates complete phase deliverables, updates all docs, writes changelog entry, and outputs a ready-to-copy git commit. Never skips a deliverable.
triggers: ["phase advance", "next phase", "move to phase", "start phase", "phase complete"]
version: 1.0.0
---

# Phase Advance Skill

**Prime directive:** Each phase must be complete, not partial. Deliver everything listed under the phase — nothing implied or deferred without explicit user agreement.

---

## Pre-Advance Checklist
Before generating phase deliverables, verify:
- [ ] All tests from the previous phase are passing (`pytest` green)
- [ ] `mypy` is clean
- [ ] `CHANGELOG.md` has an entry for the completed phase
- [ ] `mkdocs.yml` nav includes all new docs pages
- [ ] Git working tree is clean (or user has acknowledged outstanding changes)

If any check fails, surface it and ask the user how to proceed. Do not advance silently over broken state.

---

## Phase Deliverables Reference

### Phase 1 – Scoping & Requirements
- `docs/prd.md` — 1-page PRD: problem statement, success metrics, out-of-scope
- `docs/tickets.md` — Jira-style epics + stories (user-story format, acceptance criteria)
- `docs/roi-calculator.md` — ROI model: churn rate × ARR × intervention success rate
- `docs/growth-framework.md` — Activation → Engagement → Retention → Expansion diagram (Mermaid)
- Update `mkdocs.yml` nav under a new "Phase 1" section

### Phase 2 – Data Architecture
- Complete dbt project: `dbt_project/models/staging/`, `intermediate/`, `marts/`
- `dbt_project/models/sources.yml` — source definitions with freshness checks
- `dbt_project/models/schema.yml` — column-level tests (not_null, unique, accepted_values, relationships)
- `src/infrastructure/data_generation/generate_synthetic_data.py` — Faker script
- `DVC/dvc.yaml` — full pipeline stages
- `docs/data-architecture.md` — lineage diagram (Mermaid)

### Phase 3 – EDA & Experiment Design
- `notebooks/phase3_cohort_analysis.ipynb` — cohort retention curves by plan_tier + industry
- `notebooks/phase3_survival_analysis.ipynb` — Kaplan-Meier curves, log-rank tests
- `notebooks/phase3_ab_test_simulation.ipynb` — power analysis + Bayesian A/B test simulation
- `docs/experiment-design.md` — hypothesis, test design, sample size rationale

### Phase 4 – Predictive Models
- `src/domain/prediction/churn_model_service.py` — full XGBoost + survival ensemble
- `src/infrastructure/ml/xgboost_churn_model.py` — `ChurnModelPort` implementation
- `src/infrastructure/ml/churn_feature_extractor.py` — feature engineering
- `notebooks/phase4_model_development.ipynb` — training, calibration plots, ROC/PR curves
- `notebooks/phase4_shap_analysis.ipynb` — SHAP waterfall + beeswarm plots
- `docs/model-card.md` — model card: intended use, bias checks, performance metrics, guardrails
- Updated `models/churn_model_metadata.json`

### Phase 5 – AI/LLM Layer
- `src/infrastructure/llm/executive_summary_service.py` — Groq/Llama-3 summary generator
- `src/infrastructure/llm/rag_chatbot.py` — RAG "ask about customer X"
- `docs/ethical-guardrails.md` — hallucination mitigation, human-in-loop, bias audit
- `docs/llm-time-saved.md` — time-saved metric methodology

### Phase 6 – Dashboard
- `superset/` — dashboard JSON exports (Customer 360, churn heatmap, risk drill-down, uplift simulator)
- `docs/dashboard-guide.md` — how to interpret each chart + business narrative

### Phase 7 – Deployment & Change Management
- `app/` — all FastAPI routers fully implemented with e2e tests passing
- `docker-compose.prod.yml` — production-hardened overrides
- `docs/change-management.md` — 5-section change management plan (stakeholders, training, rollout, governance, success metrics)
- `docs/runbook.md` — operations runbook for on-call

### Phase 8 – Executive Presentation
- `docs/presentation/` — 10-slide deck outline (Markdown → can export to Slides)
- `docs/presentation/speaker-notes.md`
- `docs/one-pager.md` — 1-page LLM-generated executive summary of the whole project

---

## Output Format (always follow this structure)

```
## Phase X Deliverables

### 1. [First deliverable name]
[Complete file content]

### 2. [Second deliverable name]
[Complete file content]

...

## CHANGELOG.md Entry (ready to paste)
## [X.Y.Z] – Phase X Complete
### Added
- ...

## Git Commit Message (ready to copy)
feat(phaseX): complete [phase name] deliverables

- [bullet 1]
- [bullet 2]

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

---
Phase X complete. Ready for Phase X+1: [Phase Name]?
```

---

## Rules
- Output **complete files**, not skeletons or `# TODO` placeholders
- All new Python files get full TDD treatment (chain to `/tdd-cycle`)
- All new docs pages get added to `mkdocs.yml` nav
- Bump `CHANGELOG.md` with a semantic version entry
- End every phase with the status line and readiness question
