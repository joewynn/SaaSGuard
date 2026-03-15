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

**Correlations baked in:** `enterprise` tier churns less; `starter` tier with low `feature_adoption_score` churns within 90 days at elevated rate.

---

## usage_events

One row per product interaction. High cardinality (~10M rows for 5k customers over 2 years).

| Column | Type | Description |
|---|---|---|
| `event_id` | VARCHAR | UUID |
| `customer_id` | VARCHAR | FK → customers |
| `timestamp` | TIMESTAMP | UTC |
| `event_type` | VARCHAR | evidence_upload \| monitoring_run \| report_view \| user_invite \| integration_connect \| api_call |
| `feature_adoption_score` | FLOAT | 0–1 composite score at time of event |

**Correlations baked in:** Declining event frequency in the 30 days before churn; `integration_connect` events are strong retention signals.

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

## risk_signals

Computed/external risk flags per customer. Updated periodically.

| Column | Type | Description |
|---|---|---|
| `customer_id` | VARCHAR | FK → customers |
| `compliance_gap_score` | FLOAT | 0–1; higher = more compliance gaps detected |
| `vendor_risk_flags` | INTEGER | Count of third-party vendor risk alerts |
