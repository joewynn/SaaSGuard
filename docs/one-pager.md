# SaaSGuard — One-Page Executive Summary

---

## The Problem

20–25% of voluntary B2B SaaS churn happens in the first 90 days. The customer's decision to
leave is made 60+ days before they cancel — during a **silent decay period** that is invisible
to today's CS tools. By the time a CSM acts, the window has closed.

Reducing churn by 1% on $200M ARR saves **$2M+ annually**.

---

## The Platform

SaaSGuard is a production-grade churn and risk prediction platform that gives CS teams a
**60-day early warning signal** — with an explanation of why, an AI-generated brief, and
a dashboard ready for action.

| Layer | What it delivers |
|---|---|
| **Data** | DuckDB + dbt; 5K customers × 3.5M events; nightly refresh |
| **Model** | XGBoost + survival analysis; SHAP explainability; 4 risk tiers |
| **AI** | Llama-3 executive summaries; RAG "Ask about Customer X"; 3-layer guardrails |
| **Action** | 4 Superset dashboards; Customer 360 API; CS outreach triggers |

**One-command deploy:** `docker compose --profile dev up -d`

---

## The Proof

| Metric | Target | Status |
|---|---|---|
| Churn model AUC-ROC | ≥ 0.80 | ✅ Achieved |
| Calibration vs. Kaplan-Meier | ±15pp | ✅ Achieved |
| Precision @ top churn decile | ≥ 0.60 | ✅ Achieved |
| **Expansion model AUC-ROC** | **≥ 0.75** | **✅ 0.928 achieved** |
| **Expansion precision @ top-10%** | **≥ 20%** | **✅ 21.7% achieved** |
| Churn protection (base case) | $2.0M ARR | ✅ Modelled |
| **Expansion capture (base case)** | **$1.2M ARR** | **✅ Modelled** |
| **Combined NRR impact (base case)** | **$3.2M net** | **✅ Modelled** |
| Payback period | < 30 days | ✅ 17 days |

**Top churn signal:** `events_last_30d` — a 50% drop in 30-day activity doubles churn risk.
**Top expansion signal:** `premium_feature_trials_30d` — trialling above-tier features is the #1 upgrade predictor.

**Built-in experiment:** Bayesian A/B, 60 accounts/arm, 88% confidence in 1–2 quarters.

---

## The Ask

Run a **90-day pilot** with 60 at-risk accounts.

- Resources: 2 senior CSMs · data access · $0 marginal cloud cost
- Platform: Already built, tested (137 tests), and deployed
- Change management plan: Written (12-week rollout, success metrics, runbook)
- Decision gate: P(impact) ≥ 0.90 → expand to full CS team

---

> **Repo:** [github.com/joewynn/saasguard](https://github.com/joewynn/saasguard)
> **Docs:** `docker compose --profile dev up -d` → [localhost:8001](http://localhost:8001)
> **Full deck:** [docs/presentation/deck.md](presentation/deck.md)
