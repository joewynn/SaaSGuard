# SaaSGuard — 15-Minute Loom Video Script

> **Format:** `[MM:SS]` timestamp · `[SCREEN: ...]` tells you what to show · `[PAUSE]` = breath.
> Record at 1080p. Zoom browser to 125%. Use a clean browser profile (no bookmarks bar).
> Recommended tool: Loom or QuickTime + separate audio.

---

## Pre-Recording Setup

```bash
# Start the full stack
docker compose --profile dev up -d

# Verify all services healthy
docker compose ps
# Expected: api, superset, jupyterlab, mkdocs — all "healthy"

# Open these tabs in order before recording:
# Tab 1: GitHub README      → https://github.com/josephwam/saasguard
# Tab 2: FastAPI Swagger    → http://localhost:8000/docs
# Tab 3: JupyterLab         → http://localhost:8888
# Tab 4: Apache Superset    → http://localhost:8088
# Tab 5: MkDocs             → http://localhost:8001
```

Have the DuckDB loaded with data: `docker compose exec api python -c "import duckdb; conn = duckdb.connect('data/saasguard.duckdb'); print(conn.execute('SELECT COUNT(*) FROM raw.customers').fetchone())"`

---

## Segment 1 — Hook (0:00–0:45)

`[SCREEN: GitHub README — full page visible]`

**[0:00]**
> "I'm going to show you SaaSGuard — a production-grade B2B SaaS churn prediction platform
> I built to demonstrate what a full product analytics practice looks like from raw data to
> executive dashboard."

`[PAUSE]`

> "The core problem: 20 to 25 percent of voluntary B2B SaaS churn happens in the first 90 days.
> The customer's decision to leave is made 60 days before they ever click cancel. By the time
> a CSM notices — usage drop, missed meeting, support escalation — it's already too late."

`[SCROLL down slowly to show the phase table and JD mapping table]`

**[0:25]**
> "SaaSGuard gives CS teams a 60-day early warning signal, with an explanation of why,
> an AI-generated brief, and a dashboard ready for Monday morning."

> "Everything runs with one command."

`[HIGHLIGHT the docker compose command block]`

> "Clone, copy the env file, run docker compose — and in under 5 minutes you have a full stack:
> FastAPI, Superset dashboards, JupyterLab, and a live documentation site."

**[0:45]** `[TRANSITION to Segment 2]`

---

## Segment 2 — Data Layer (0:45–2:30)

`[SCREEN: Switch to Tab 3 — JupyterLab]`

**[0:45]**
> "Let's start at the bottom of the stack: the data layer."

`[Open notebooks/ folder, click phase3_01_eda_cohort_analysis.ipynb]`

> "The warehouse holds 5,000 synthetic customers and 3.5 million product usage events —
> modelled with realistic correlations: usage decay predicts churn, compliance gaps
> predict support ticket volume, enterprise customers have longer survival windows."

`[Scroll to the cohort retention curve cell — show the chart]`

**[1:10]**
> "This is the cohort retention curve by plan tier. Enterprise customers retain at 85% at 12
> months. Starter tier falls to 62%. That gap — 23 percentage points — is the addressable
> opportunity."

`[PAUSE]`

`[Scroll or switch to the survival analysis notebook — show a Kaplan-Meier curve]`

**[1:30]**
> "We built Kaplan-Meier survival curves to validate the churn timeline. The log-rank test
> confirms the tiers are statistically distinct — which means we can segment the model's
> intervention targets by tier."

`[SCREEN: Switch to MkDocs at :8001 → Phase 2 → Data Dictionary]`

**[1:55]**
> "The data layer is driven by a full dbt project — staging, intermediate, and mart models —
> with schema tests on every table. Column-level not_null, uniqueness, and accepted_values
> tests run in CI on every push."

**[2:30]** `[TRANSITION to Segment 3]`

---

## Segment 3 — Model Layer (2:30–5:00)

`[SCREEN: Switch to Tab 2 — FastAPI at localhost:8000/docs]`

**[2:30]**
> "Now the model layer. FastAPI exposes all the intelligence as a RESTful API."

`[Scroll to POST /predictions/churn, click to expand]`

> "Let's make a live prediction."

`[Click 'Try it out' → enter a real customer UUID from the database → Execute]`

**[2:55]**
`[Show the JSON response — highlight churn_probability, risk_tier, top_shap_features]`

> "The response gives us: churn probability — 0.72, so 72% chance of churning in the next
> 90 days. Risk tier: HIGH. And the top SHAP feature drivers."

`[PAUSE — let the response sit on screen for 2 seconds]`

> "That third field is what makes this different from a black box. The model doesn't just
> score — it explains. Events in the last 30 days is the top driver: this customer's usage
> dropped by 60% last month. That's the opening line of the CSM's call."

`[SCREEN: Switch to Tab 3 — JupyterLab, open the SHAP analysis notebook]`

**[3:30]**
> "The SHAP analysis notebook shows this at a population level."

`[Scroll to the SHAP waterfall or beeswarm plot]`

> "Across all 5,000 customers, 30-day product event volume is the single strongest predictor —
> stronger than tenure, plan tier, support tickets, or GTM pipeline stage. Usage decay is the
> leading indicator."

`[SCREEN: Switch to MkDocs → Phase 4 → Model Card]`

**[4:15]**
> "The model card documents everything: AUC-ROC above 0.80, calibration within 15 percentage
> points of the Kaplan-Meier baseline, precision at the top decile above 0.60. All targets met."

> "The model is wrapped in a CalibratedClassifierCV — isotonic regression post-processing —
> so the probability output is a genuine probability, not a raw score. A 70% prediction means
> the customer churns 70% of the time."

**[5:00]** `[TRANSITION to Segment 4]`

---

## Segment 4 — AI Layer (5:00–7:00)

`[SCREEN: Back to FastAPI at :8000/docs]`

**[5:00]**
> "Now the AI layer. This is where we turn a JSON prediction into something a CSM can read
> in 30 seconds."

`[Scroll to POST /summaries/customer, expand]`

`[Click Try it out → enter the same customer UUID, audience: "csm" → Execute]`

**[5:20]**
`[Show the response — highlight the summary text, confidence_score, guardrail_flags]`

> "The response is a 3 to 5 sentence brief, grounded entirely in the customer's DuckDB data:
> churn probability, usage events, support tickets, GTM stage. Confidence score of 1.0 means
> every fact was verified against the warehouse."

`[PAUSE — read one sentence of the summary aloud]`

> "Notice the watermark at the bottom: 'AI-generated. Human review required.' That's not
> optional — it's hardcoded. Every single output has it."

`[Scroll to POST /summaries/customer/ask]`

**[5:55]**
> "We also have a RAG-style question answering endpoint."

`[Try it out → same customer → question: "Why is this customer at risk?" → Execute]`

`[Show the answer]`

> "The model answers in plain English, grounded in the same DuckDB context. If you ask a
> question the data can't answer — 'What did the CEO say in the last board meeting?' —
> it returns scope_exceeded: true and an empty answer. No hallucination."

**[7:00]** `[TRANSITION to Segment 5]`

---

## Segment 5 — Dashboard (7:00–10:30)

`[SCREEN: Switch to Tab 4 — Apache Superset at :8088]`

**[7:00]**
> "The dashboards are where all of this becomes operational for a CS team."

`[Navigate to the Customer 360 dashboard]`

**[7:15]**
> "Customer 360 is the CSM's daily view. Risk KPI row at the top — churn probability, risk
> tier, ARR at risk, open tickets. Then a 90-day usage trend, the top SHAP flag breakdown,
> and the GTM opportunity stage."

`[PAUSE — point at 2–3 specific charts]`

> "This is what a CSM sees at 9am on Monday before their at-risk account calls. No manual
> research. 30 seconds to context."

`[Navigate to Churn Heatmap dashboard]`

**[8:00]**
> "The Churn Heatmap shows risk at the portfolio level. Plan tier on one axis, industry on
> the other — colour intensity is average churn probability. This is the VP CS view:
> where are our highest-concentration risk clusters?"

`[Point at the darkest cell]`

> "Starter tier, fintech — highest risk cohort. 34% average churn probability. That's the
> first cohort to prioritise for the pilot."

`[Navigate to Risk Drill-Down dashboard]`

**[8:45]**
> "Risk Drill-Down is for the CS lead who wants to get into the data. At-risk customer table
> with conditional formatting — red for critical, orange for high. Sortable by ARR at risk,
> so you can triage by revenue impact."

`[Navigate to Uplift Simulator dashboard]`

**[9:30]**
> "The Uplift Simulator is the CFO slide. It answers: if our CS team improves their
> outreach conversion rate from 12% to 15%, what does that mean for ARR?"

`[Show the sliders — adjust one and show the ARR line move]`

> "Slide the conversion rate up 3 points — ARR protected jumps by $570K. This is the model
> that lives in `docs/roi-calculator.md`, made interactive."

`[PAUSE]`

> "These four dashboards don't require any data exports or manual updates. They query DuckDB
> directly, refreshed nightly by the dbt pipeline."

**[10:30]** `[TRANSITION to Segment 6]`

---

## Segment 6 — Engineering Depth (10:30–12:30)

`[SCREEN: Switch to file explorer or terminal — show tests/ directory]`

**[10:30]**
> "Let me show you what's underneath."

`[Run in terminal: pytest --no-cov -q 2>&1 | tail -5]`

> "137 tests. Unit, integration, end-to-end, and model accuracy tests. Layered: domain logic
> tested in pure Python, infrastructure tested against a real DuckDB fixture, API tested with
> FastAPI TestClient. TDD — tests were written before every implementation."

`[SCREEN: Switch to Tab 5 — MkDocs at :8001 → CLAUDE.md or Skills page]`

**[11:00]**
> "I built this using Claude Code with a custom skills system. The skills folder contains
> 10 reusable SOPs — TDD cycle, DDD entity factory, self-critique, phase advance, and more."

`[Show the skills table in MkDocs or README]`

> "Every phase was implemented by invoking a skill: write tests first, implement, run
> self-critique, update docs, commit. The same discipline a senior engineering team would
> enforce with a style guide and code review — codified as AI skills."

`[SCREEN: Show docker-compose.yml or Dockerfile briefly]`

**[11:40]**
> "The infrastructure layer: multi-stage Docker build with a non-root production user,
> gunicorn with auto-scaled workers, healthchecks on every service, Prometheus metrics
> endpoint, Trivy vulnerability scanning in CI."

`[SCREEN: Show .github/workflows/ci.yml]`

**[12:00]**
> "Every push to main runs: ruff lint, mypy type check, pytest, dbt build and test, Docker
> build and push to GHCR, Trivy security scan, and a production smoke test that starts the
> container and hits /health and /ready. The pipeline is the safety net."

**[12:30]** `[TRANSITION to Segment 7]`

---

## Segment 7 — ROI Close (12:30–15:00)

`[SCREEN: Switch to MkDocs at :8001 → ROI Calculator]`

**[12:30]**
> "Let me close with the business case."

`[Scroll through the ROI calculator page slowly]`

> "Three scenarios. Conservative: 0.5% churn reduction on $200M ARR — $850K net ROI on
> $150K platform cost. Base case: 1% reduction — $1.85M net. Payback period under one month."

> "The primary lever isn't the model accuracy — it's the CS conversion rate. Every 5
> percentage point improvement in how often a CS outreach retains a customer adds $925K
> to the ROI. That's the human-in-the-loop multiplier."

`[SCREEN: Switch to MkDocs → Change Management]`

**[13:15]**
> "The change management plan is written. 12-week rollout: pilot in Week 1 with 2 CSMs and
> 10 accounts, full CS team in Week 2, executive dashboards in Week 4, CRM API integration
> in Week 8. Every milestone has a success gate."

`[SCREEN: Navigate to GitHub README — scroll to the bottom]`

**[13:45]**
> "Everything I've shown you — the data pipeline, the model, the AI layer, the dashboards,
> the API, the tests, the docs, the change management plan — is in this repository."

`[PAUSE — 2 seconds of silence]`

> "One command. Five minutes. Full stack."

`[HIGHLIGHT: docker compose --profile dev up -d]`

**[14:10]**
> "The platform is built. The experiment is designed. The runbook is written."

`[PAUSE]`

> "The only thing missing is the pilot."

**[14:25]**
> "If you're evaluating this for a product analytics or senior DS role — the answer to
> 'What would you build in your first 90 days?' is: I already built it."

> "The repo link is in the description. Clone it, spin it up, and tell me what you'd add."

**[14:50]**
> "Thanks for watching."

`[END RECORDING at 15:00]`

---

## Post-Production Notes

- **Thumbnail:** Screenshot of the Superset Churn Heatmap — most visually striking frame
- **Title:** "SaaSGuard – Full B2B SaaS Churn Prediction Platform (15-min walkthrough)"
- **Description:**
  ```
  SaaSGuard is a production-grade churn and risk prediction platform:
  DuckDB + dbt data pipeline, XGBoost + survival analysis, Llama-3 AI summaries,
  Apache Superset dashboards, FastAPI, Docker, CI/CD.

  One-command demo: docker compose --profile dev up -d
  Repo: https://github.com/josephwam/saasguard
  Docs: http://localhost:8001 (after running the stack)
  ```
- **Chapters** (add to Loom description):
  - 0:00 — Hook & problem statement
  - 0:45 — Data layer (DuckDB + dbt + EDA)
  - 2:30 — Model layer (FastAPI + SHAP)
  - 5:00 — AI layer (executive summaries + guardrails)
  - 7:00 — Dashboard (Superset tour)
  - 10:30 — Engineering depth (tests, skills, CI/CD)
  - 12:30 — ROI close & the ask
