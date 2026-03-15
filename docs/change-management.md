# Change Management Plan – SaaSGuard Platform Rollout

## Overview

SaaSGuard delivers P(churn in 90 days) scores, compliance risk signals, and AI-augmented
executive summaries to Customer Success and Sales teams. This document covers the stakeholder
map, training approach, phased rollout schedule, governance model, and success metrics for
a production deployment targeting a $200M ARR portfolio.

---

## 1. Stakeholder Map

| Stakeholder | Role | Impact | Engagement Level |
|---|---|---|---|
| **VP of Customer Success** | Executive sponsor; owns churn KPI and CSM headcount | High – defines success metrics and signs off on rollout | Champion |
| **Customer Success Managers (CSMs)** | Primary end users; consume Customer 360 dashboards and AI summaries daily | Critical – adoption determines ROI | Daily users |
| **Sales / Account Executives** | Consume GTM integration signals (renewal risk, upsell triggers) | Medium – use Churn Heatmap for pipeline prioritisation | Weekly users |
| **IT / Security** | Reviews data residency, auth model, container hardening, CORS policy | High – gate for production approval | Approvers |
| **Executive Team (CEO, CFO)** | Consume ROI dashboard and executive summaries in board-prep sessions | Medium – use Uplift Simulator for investment decisions | Monthly users |
| **Data Engineering** | Owns dbt refresh pipeline, DVC model versioning, DuckDB infrastructure | High – responsible for data SLAs | Operators |

---

## 2. Training Plan

### CSM Onboarding Guide (30 min)
Target audience: All Customer Success Managers

- **Module 1 (10 min):** Customer 360 dashboard walkthrough — how to read churn probability, risk tier, and SHAP feature drivers
- **Module 2 (10 min):** AI executive summary generation — how to request a summary, interpret guardrail flags, and apply human judgement before sharing externally
- **Module 3 (10 min):** Hands-on practice with 3 sample at-risk accounts; Q&A

Delivery: Recorded Loom video + live session facilitated by VP CS. Materials in `docs/`.

### Executive Dashboard Walkthrough (15 min)
Target audience: VP CS, CFO, CEO

- Superset Churn Heatmap — cohort-level risk view
- Uplift Simulator — model ROI scenarios (e.g., "if we intervene on 20 high-risk accounts, what is the expected churn reduction?")
- How to interpret confidence ranges and model limitations

Delivery: Slide deck + live session. See `docs/demo.md` for the standard demo script.

### API Integration Guide (Engineering Partners)
Target audience: Sales Ops, CRM integration engineers

- FastAPI endpoint reference: `GET /customers/{id}`, `POST /predictions/churn`, `POST /summaries/customer`
- Authentication headers and CORS configuration
- Webhook patterns for real-time churn alert pipelines

Delivery: `docs/API.md` + OpenAPI interactive docs at `:8000/docs`.

---

## 3. Phased Rollout Schedule

| Week | Milestone | Scope | Success Gate |
|---|---|---|---|
| **Week 1** | Pilot launch | 2 senior CSMs on 10 at-risk accounts | Both CSMs complete onboarding; ≥80% report dashboard "useful" |
| **Week 2** | Full CS team rollout | All CSMs (~15 users) | No P1 support tickets; AI summary guardrail pass rate ≥90% |
| **Week 4** | Executive dashboard access | VP CS, CFO, CEO | VP CS reviews Uplift Simulator in board prep |
| **Week 6** | Sales integration | AEs receive GTM churn signals in CRM | Renewal pipeline enriched for ≥80% of Q2 renewals |
| **Week 8** | API live for integrations | Engineering partners connect CRM webhook | First automated churn alert delivered to Slack |
| **Week 12** | First model retraining | Data Eng runs `dvc repro` on new cohort data | Calibration drift < 5pp; accuracy maintained |

---

## 4. Governance & Data Freshness

### Model Retraining Schedule
- **Frequency:** Quarterly (aligned with new customer cohort data)
- **Trigger:** Calibration drift > 5 percentage points OR accuracy drop > 3pp on holdout set
- **Process:** `dvc repro` → review `tests/model_accuracy/` metrics → `dvc push` → CI/CD deploys new image
- **Approver:** VP CS signs off on model metrics before production promotion

### Data SLA
| Data Source | Refresh Frequency | Owner |
|---|---|---|
| `raw.customers` | Nightly via dbt run | Data Engineering |
| `raw.usage_events` | Nightly | Data Engineering |
| `raw.support_tickets` | Nightly | Data Engineering |
| `raw.gtm_opportunities` | Nightly (Salesforce sync) | Sales Ops |
| Churn predictions | On-demand via API | Prediction service |

### Human-in-the-Loop Policy
All AI-generated executive summaries include the watermark:

> *"[AI-GENERATED SUMMARY — HUMAN REVIEW REQUIRED BEFORE EXTERNAL DISTRIBUTION]"*

CSMs are required to review and edit summaries before sharing with customers or in EBRs.
AI outputs flagged by the guardrails system (hallucination detection, out-of-scope questions)
must be discarded and regenerated with a more specific prompt.

### Data Access Controls
- CORS locked to approved origins (`ALLOWED_ORIGINS` env var — see `docs/runbook.md`)
- DuckDB file mounted read-only to API container workers
- Non-root container user (`saasguard`) — no write access to model artifacts at runtime
- No PII in LLM prompts — customer IDs and aggregate metrics only

---

## 5. Success Metrics

| Metric | Baseline | Target (90 days post-launch) | Measurement |
|---|---|---|---|
| **Churn rate** | Current cohort churn rate | −5% relative reduction | Customer data in DuckDB |
| **CSM time saved per at-risk account** | 15 min manual research | ≤3 min with Customer 360 | CSM survey (n ≥ 10) |
| **AI summary accuracy** | N/A (new capability) | ≥80% rated "accurate" by CSMs | Weekly Loom survey |
| **Platform uptime** | N/A | ≥99.5% (≤3.6h downtime/month) | `/health` endpoint monitoring |
| **Guardrail pass rate** | N/A | ≥90% | Prometheus `guardrail_passed_total` |
| **CSM dashboard adoption** | 0% | ≥80% weekly active CSMs | Superset usage logs |

### ROI Framing
- 1% churn reduction on $200M ARR = **$2M saved annually**
- 10–15% churn reduction achievable through early CS intervention (Forrester)
- CSM time savings: 3.3h/week × 15 CSMs × $85/hr fully-loaded = **$220K/year productivity gain**
