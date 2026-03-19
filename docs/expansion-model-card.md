# Expansion Propensity Model Card

**Model name:** `expansion_model`
**Version:** 1.0.0
**Type:** XGBoostClassifier + CalibratedClassifierCV (isotonic, cv=5)
**Task:** Binary classification — P(upgrade to next plan tier within 90 days)
**Artifact:** `models/expansion_model.pkl` + `models/expansion_model_metadata.json`

---

## Purpose

The expansion propensity model is the **offensive** complement to the defensive churn model. Together they cover the full NRR lifecycle: Retain + Expand. The model targets Customer Success and Sales teams who need to identify accounts with genuine upgrade intent, distinguish them from accounts that look active but are actually churning, and prioritise outreach by expected ARR uplift.

---

## Features (20 total)

### Base churn features (15) — reused from `mart_customer_churn_features`

| Feature | Type | Description |
|---------|------|-------------|
| `mrr` | numeric | Monthly Recurring Revenue (USD) |
| `tenure_days` | numeric | Days since signup |
| `total_events` | numeric | Lifetime product event count |
| `events_last_30d` | numeric | Product activity last 30 days |
| `events_last_7d` | numeric | Product activity last 7 days |
| `avg_adoption_score` | numeric | Average feature adoption score |
| `days_since_last_event` | numeric | Recency of last product interaction |
| `retention_signal_count` | numeric | High-value events (API, integrations, monitoring) |
| `integration_connects_first_30d` | numeric | Integrations in onboarding window |
| `tickets_last_30d` | numeric | Support tickets last 30 days |
| `high_priority_tickets` | numeric | Lifetime high/critical ticket count |
| `avg_resolution_hours` | numeric | Average ticket resolution time |
| `is_early_stage` | binary | In first 90 days of tenure |
| `plan_tier` | categorical | starter / growth / enterprise / custom |
| `industry` | categorical | Industry vertical |

### Expansion-specific signals (5) — from `mart_customer_expansion_features`

| Feature | Type | Description | Business meaning |
|---------|------|-------------|-----------------|
| `premium_feature_trials_30d` | numeric | `premium_feature_trial` events last 30d | Customers trialing capabilities above their tier |
| `feature_request_tickets_90d` | numeric | Feature request tickets last 90d | Asking for capabilities they don't have yet |
| `has_open_expansion_opp` | binary | Active expansion GTM opportunity | Sales team already sees upgrade signal |
| `expansion_opp_amount` | numeric | USD value of open expansion opp | Dollar size of Sales-identified opportunity |
| `mrr_tier_ceiling_pct` | numeric [0,1] | (MRR − floor) / (ceiling − floor) | How close MRR is to the top of current tier |

---

## Leakage Guard

**`has_open_expansion_opp` must NOT be the #1 SHAP feature.**

If it is, the Sales team may be creating expansion opportunities *in response to* usage signals that the model should be discovering independently. This creates a circular dependency — the feature is a consequence of upgrade intent, not a cause. The training script logs a warning if this occurs. In that case:

1. Retrain without `has_open_expansion_opp`
2. Compare AUC delta — if < 0.03, remove the feature permanently
3. See `notebooks/expansion_propensity_modeling.ipynb` Section 5 for the SHAP beeswarm leakage check

---

## Training Data

| Split | Criteria | Notes |
|-------|----------|-------|
| Train | signup_date < 2025-06-01 | ~18 months of cohorts |
| Test | signup_date ≥ 2025-06-01 | ~9 months of cohorts, out-of-time |
| Scope | Active + never-churned customers only | Churned customers excluded |
| Label | `upgrade_date IS NOT NULL` | Upgraded = 1, never upgraded = 0 |

**Point-in-time correctness:** For upgraded customers, all features are computed AS OF `upgrade_date`. For active customers, AS OF `REFERENCE_DATE`. No future data leaks.

---

## Performance Metrics

| Metric | Threshold | Notes |
|--------|-----------|-------|
| AUC-ROC | > 0.75 | Acceptance gate in training script |
| Brier score | < 0.10 | Calibration quality |
| Precision @decile 1 | Reported | Fraction of upgraders in top 10% by score |

---

## Known Limitations

1. **Synthetic data only** — the model is trained on generated data with causal correlations, not real customer histories. AUC will change when deployed against real data.
2. **Enterprise → Custom tier** — the 1.2× uplift multiplier for seat/add-on expansion is a conservative estimate. Actual enterprise expansion deals vary widely.
3. **No seasonality** — monthly MRR cycles and annual contract renewals are not captured.
4. **Static tier ceilings** — `mrr_tier_ceiling_pct` uses hardcoded tier boundaries (Starter: 500–2000, Growth: 2000–8000, Enterprise: 8000–50000). Update in `train_expansion_model.py` if pricing changes.

---

## Retraining Cadence

| Trigger | Action |
|---------|--------|
| Monthly | Evaluate AUC on new cohort; flag if < 0.72 |
| Quarterly | Full retrain on rolling 24-month window |
| Pricing change | Immediate retrain + update `mrr_tier_ceiling_pct` tier boundaries |
| SHAP leakage alert | Investigate `has_open_expansion_opp` dominance; retrain if needed |
