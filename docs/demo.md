# Demo Guide

Step-by-step walkthrough for running the full SaaSGuard demo — designed for showing to interviewers or stakeholders.

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

### Step 3 – EDA Notebooks (JupyterLab)

Open **http://localhost:8888**

Key notebooks to show:
- `phase3_cohort_analysis.ipynb`: Kaplan-Meier survival curves by plan tier
- `phase3_ab_test_simulation.ipynb`: Bayesian A/B test with power analysis

**Talking point:** *"We ran a Bayesian test instead of a classical one because our customer segments are small — this is typical in B2B SaaS."*

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
| Churn model AUC (target) | >0.85 |
| Test coverage | >80% |
| Time from `git clone` to live demo | <5 minutes |
| Revenue impact of 1% churn reduction | $2M+ on $200M ARR |

---

## Teardown

```bash
docker compose --profile dev down
# Data is preserved in ./data/saasguard.duckdb (DVC-tracked)
```
