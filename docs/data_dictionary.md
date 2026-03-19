# Data Dictionary

All tables are generated synthetically via Faker with realistic inter-variable correlations. Source: `data/raw/*.csv` → loaded into DuckDB via `src/infrastructure/db/build_warehouse.py`.

## customers

Primary entity. One row per customer. `churn_date` is NULL for active customers (right-censored for survival analysis).

| Column | Type | Description |
|---|---|---|
| `customer_id` | VARCHAR | UUID primary key |
| `industry` | VARCHAR | e.g. FinTech, HealthTech, LegalTech, HR Tech |
| `plan_tier` | VARCHAR | starter \| growth \| enterprise |
| `signup_date` | DATE | Date of first contract |
| `mrr` | DECIMAL | Monthly Recurring Revenue (USD) |
| `churn_date` | DATE / NULL | NULL = still active (censored) |
| `upgrade_date` | DATE / NULL | Date customer upgraded to next plan tier. NULL = not yet upgraded. Added v0.9.0 for expansion propensity model. |

**Correlations baked in:** `enterprise` tier churns less; `starter` tier with low `feature_adoption_score` churns within 90 days at elevated rate. Customers with `upgrade_date IS NOT NULL` have statistically higher `premium_feature_trials_30d` (Mann-Whitney U p < 0.05).

---

## usage_events

One row per product interaction. High cardinality (~10M rows for 5k customers over 2 years).

| Column | Type | Description |
|---|---|---|
| `event_id` | VARCHAR | UUID |
| `customer_id` | VARCHAR | FK → customers |
| `timestamp` | TIMESTAMP | UTC |
| `event_type` | VARCHAR | evidence_upload \| monitoring_run \| report_view \| user_invite \| integration_connect \| api_call \| **premium_feature_trial** |
| `feature_adoption_score` | FLOAT | 0–1 composite score at time of event |

**`premium_feature_trial`** (added v0.9.0): customer accessed a feature available only in their next plan tier. This is the single strongest expansion signal (`mean_abs_shap=3.94`). Destiny-weighted — customers with `upgrade_date IS NOT NULL` are 4–6× more likely to generate this event type.

**Correlations baked in:** Declining event frequency in the 30 days before churn; `integration_connect` events are strong retention signals; `premium_feature_trial` frequency positively correlates with upgrade propensity.

---

## gtm_opportunities

CRM-style table. One row per sales/expansion opportunity.

| Column | Type | Description |
|---|---|---|
| `opp_id` | VARCHAR | UUID |
| `customer_id` | VARCHAR | FK → customers |
| `stage` | VARCHAR | prospecting \| qualification \| proposal \| closed_won \| closed_lost |
| `close_date` | DATE | Actual or expected close date |
| `amount` | DECIMAL | USD opportunity value |
| `sales_owner` | VARCHAR | Anonymised rep name |
| `opportunity_type` | VARCHAR | **expansion** \| new_business. Added v0.9.0. `expansion` = existing customer upgrade; `new_business` = net-new logo. |

---

## support_tickets

Customer support interactions.

| Column | Type | Description |
|---|---|---|
| `ticket_id` | VARCHAR | UUID |
| `customer_id` | VARCHAR | FK → customers |
| `created_date` | DATE | |
| `priority` | VARCHAR | low \| medium \| high \| critical |
| `resolution_time` | INTEGER | Hours to resolution |
| `topic` | VARCHAR | compliance \| integration \| billing \| onboarding \| feature_request |

**Correlations baked in:** Spike in `high`/`critical` tickets in 60 days before churn; `integration` and `onboarding` topics are leading churn indicators.

---

## Derived Features — EDA Analysis

Computed in EDA notebooks and pre-modelling signal tests. These features
are computed for **all customers** (churned + active) using direct queries against the
`raw` schema. They extend `mart_customer_churn_features` (which covers active customers
only) to support survival analysis and EDA.

| Column | Type | Description |
|---|---|---|
| `duration_days` | INTEGER | Survival time: `DATEDIFF('day', signup_date, churn_date)` for churned; `DATEDIFF('day', signup_date, DATE '2026-03-14')` for active (right-censored) |
| `event` | INTEGER | Survival event indicator: 1 = customer churned, 0 = right-censored (still active at reference date) |
| `integration_connects_first_30d` | INTEGER | Count of `integration_connect` usage events in the first 30 days of the customer's tenure (`timestamp <= signup_date + 30 days`). Activation gate feature. |
| `retention_signal_count` | INTEGER | Count of `evidence_upload`, `monitoring_run`, and `report_view` events across the customer's full tenure. Proxy for deep product adoption. |
| `events_last_30d` | INTEGER | Usage events in the 30-day window before churn_date (churned) or reference date (active). Captures the decay signal. |
| `integration_bucket` | VARCHAR | Derived category: `"0"` / `"1–2"` / `"3–5"` / `"6+"` based on `integration_connects_first_30d`. Used in integration gate visualisations. |

**Correlation with churn label (point-biserial r, all p < 0.001):**

| Feature | r | Direction |
|---|---|---|
| `events_last_30d` | −0.38 | Negative (usage decay → churn) |
| `avg_adoption_score` | −0.34 | Negative (low adoption → churn) |
| `retention_signal_count` | −0.32 | Negative (deep adoption → retention) |
| `high_priority_tickets` | +0.27 | Positive (ticket spike → churn risk) |
| `integration_connects_first_30d` | −0.24 | Negative (integration → activation) |

---

## mart_customer_churn_features (dbt mart)

Pre-aggregated feature mart built by dbt. One row per **active** customer (WHERE `is_active = TRUE`). Queried at inference time by `ChurnFeatureExtractor` (~1ms per request). All 15 model features sourced here.

| Column | Type | Description |
|---|---|---|
| `customer_id` | VARCHAR | FK → customers |
| `mrr` | DECIMAL | Monthly Recurring Revenue (USD) |
| `tenure_days` | INTEGER | Days from `signup_date` to reference date |
| `plan_tier` | VARCHAR | starter \| growth \| enterprise |
| `industry` | VARCHAR | fintech \| healthtech \| legaltech \| proptech \| saas |
| `total_events` | INTEGER | Lifetime usage event count |
| `events_last_30d` | INTEGER | Events in 30-day window before reference date |
| `events_last_7d` | INTEGER | Events in 7-day window before reference date |
| `avg_adoption_score` | FLOAT | Mean `feature_adoption_score` across all events |
| `days_since_last_event` | INTEGER | Days since most recent usage event |
| `retention_signal_count` | INTEGER | Count of high-value events: `evidence_upload`, `monitoring_run`, `report_view` |
| `integration_connects_first_30d` | INTEGER | `integration_connect` events in first 30 days (activation gate) |
| `tickets_last_30d` | INTEGER | Support tickets created in 30-day window |
| `high_priority_tickets` | INTEGER | Count of `high` or `critical` priority tickets |
| `avg_resolution_hours` | FLOAT | Mean hours to ticket resolution |
| `is_early_stage` | BOOLEAN | TRUE if `tenure_days ≤ 90` |

**Derived at runtime (not in mart):**

| Computed value | Where | Description |
|---|---|---|
| `usage_decay_score` | `DuckDBRiskSignalsRepository` | `max(0, 1 - events_last_30d / events_prev_30d)` — 0 = no decay, 1 = complete drop-off |

---

## risk_signals

Computed/external risk flags per customer. Updated periodically.

| Column | Type | Description |
|---|---|---|
| `customer_id` | VARCHAR | FK → customers |
| `compliance_gap_score` | FLOAT | 0–1; higher = more compliance gaps detected |
| `vendor_risk_flags` | INTEGER | Count of third-party vendor risk alerts |

---

## mart_customer_expansion_features (dbt mart — v0.9.0)

Pre-aggregated expansion feature mart. One row per **active non-upgraded** customer
(WHERE `is_active = TRUE AND is_upgraded = FALSE`). This is the inference population
for the expansion propensity model. Queried by `ExpansionFeatureExtractor` (~1ms).

**Scope note:** Upgraded customers are excluded from this mart because they are no
longer expansion candidates. Training uses a wider query that includes upgraded customers
as positive labels.

| Column | Type | Description |
|---|---|---|
| `customer_id` | VARCHAR | FK → customers |
| **15 churn features** | (see above) | Reused from `mart_customer_churn_features` via JOIN — no duplication |
| `premium_feature_trials_30d` | INTEGER | Count of `premium_feature_trial` events in last 30 days. Strongest expansion signal (mean |SHAP|=3.94). |
| `feature_request_tickets_90d` | INTEGER | Count of support tickets with `topic = 'feature_request'` in last 90 days. Customer explicitly asking for above-tier capabilities. |
| `has_open_expansion_opp` | BOOLEAN | TRUE if an open GTM opportunity with `opportunity_type = 'expansion'` exists for this customer. Sales intent signal — use with caution (leakage guard applied). |
| `expansion_opp_amount` | DECIMAL | USD value of the open expansion opportunity (0 if none). |
| `mrr_tier_ceiling_pct` | FLOAT | `(mrr − tier_floor) / (tier_ceiling − tier_floor)`, clamped [0, 1]. Measures how close the customer's MRR is to the top of their tier. High value (~1.0) = outgrown tier → ripe for upgrade conversation. |
