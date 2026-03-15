# Demo Guide

Step-by-step walkthrough for running the full SaaSGuard demo — designed for stakeholders, new team members, or anyone evaluating the platform.

---

## Setup (2 minutes)

```bash
git clone https://github.com/josephwam/saasguard
cd saasguard && cp .env.example .env
docker compose --profile dev up -d
```

Wait for all healthchecks to pass:

```bash
docker compose ps
# All services should show "healthy" or "running"
```

---

## Demo Flow

### Step 1 – Prediction API

Open **http://localhost:8000/docs** → try the `/predictions/churn` endpoint:

```json
POST /predictions/churn
{ "customer_id": "cust-001" }
```

Response shows:

- `churn_probability`: 0–1 calibrated score
- `risk_tier`: low / medium / high / critical
- `top_shap_features`: the top 5 reasons driving the prediction
- `recommended_action`: plain-English CS instruction

**Talking point:** *"The SHAP features tell the CS team exactly why a customer is at risk — not just that they are."*

---

### Step 2 – BI Dashboard (Superset)

Open **http://localhost:8088** → login: `admin / admin`

Key dashboards to show:

- **Customer 360**: single-customer churn score + usage trend + support history
- **Churn Heatmap**: all customers plotted by churn probability × MRR (revenue at risk)
- **Risk Drill-down**: compliance gap vs. usage decay scatter
- **Uplift Simulator**: "what if CS intervenes on these 50 customers?"

**Talking point:** *"Reducing churn on the top-right quadrant — high probability, high MRR — is where we generate the most ROI."*

---

### Step 3 – EDA & Model Notebooks (JupyterLab)

Open **http://localhost:8888**

Key notebooks to show:

- `phase3_01_eda_cohort_analysis.ipynb`: Monthly retention cohorts, churn rate by tier × industry, correlation heatmap
- `phase3_02_survival_analysis.ipynb`: Kaplan-Meier survival curves, Cox PH model, integration activation gate
- `phase3_03_ab_test_simulation.ipynb`: Bayesian A/B test with power analysis — why frequentist tests fail in B2B SaaS
- `phase4_01_model_training.ipynb`: XGBoost training, AUC/Brier evaluation, SHAP global importance + individual waterfall

**Talking point (Phase 3):** *"We ran a Bayesian test instead of a classical one because our customer segments are small — this is typical in B2B SaaS."*

**Talking point (Phase 4):** *"The SHAP waterfall shows exactly which features pushed this customer's churn probability from the baseline to 0.78. CS teams see this on every API call."*

---

### Step 4 – Documentation (MkDocs)

Open **http://localhost:8001**

Show:

- Architecture diagram (Mermaid DDD diagram)
- Auto-generated API reference (from docstrings — no manual maintenance)
- ADRs explaining key decisions (why DuckDB, why DDD)
- Data dictionary

**Talking point:** *"The docs auto-generate from code docstrings. Any new function with a Google-style docstring is instantly reflected here."*

---

### Step 5 – CI/CD Pipeline

Show the GitHub Actions tab: lint → TDD tests → dbt build → Docker push.

**Talking point:** *"Tests are written before implementation. The CI gate blocks any merge that drops coverage below 80%."*

---

## Quick Metrics to Cite

| Metric | Value |
|---|---|
| Customers in dataset | 5,000 |
| Usage events | ~10M |
| Churn model AUC (target) | >0.80 |
| Test coverage | >80% |
| Time from `git clone` to live demo | <5 minutes |
| Revenue impact of 1% churn reduction | $2M+ on $200M ARR |

---

## Teardown

```bash
docker compose --profile dev down
# Data is preserved in ./data/saasguard.duckdb (DVC-tracked)
```
