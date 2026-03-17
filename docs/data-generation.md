# Synthetic Data Generation — Methodology & Guardrails

**Source:** `src/infrastructure/data_generation/generate_synthetic_data.py`
**Seed:** `RANDOM_SEED = 42` — output is fully reproducible across runs.

---

## Why Synthetic Data Needs to Be Designed, Not Randomised

Purely random Faker data produces no churn signal. A model trained on it would learn nothing
real — every feature would be statistically independent of the churn label, producing an
AUC near 0.50. The fundamental challenge is generating data that mirrors the **causal
structure** of real B2B SaaS churn: disengagement precedes cancellation, support spikes
follow friction, compliance gaps correlate with inattention.

The solution is **profile-based generation**: rather than generating each column independently,
every customer is first assigned a hidden *churn destiny* that then drives all downstream
behaviour in a coherent, causal chain.

---

## The Churn Destiny Model

Each customer receives one of four profiles at generation time, sampled from plan-tier-specific
probability distributions that mirror real B2B SaaS churn benchmarks (Vitally, Recurly, Churnfree).

```
customer → plan_tier → destiny (probability-weighted)
                          ↓
                 destiny → churn_date
                         → usage event rate + decay shape
                         → integration_connect count
                         → support ticket rate + priority mix
                         → compliance_gap_score (Beta distribution)
```

### Destiny Probabilities by Plan Tier

| Destiny | starter | growth | enterprise | Rationale |
|---|---|---|---|---|
| `early_churner` | 25% | 8% | 3% | First-90-day dropout; matches ~20–25% early churn (Recurly 2025) |
| `mid_churner` | 20% | 12% | 5% | Stalls after partial activation; churn at 91–365 days |
| `retained` | 45% | 65% | 75% | Stable recurring usage; no churn date |
| `expanded` | 10% | 15% | 17% | Retained + open GTM opportunity; top 30% MRR |

This produces realistic observed churn rates: **starter ~43%, growth ~20%, enterprise ~7%**
— consistent with the Vitally 2025 B2B SaaS benchmark range.

---

## Behavioural Profiles per Destiny

### early_churner
- **Activation:** 0–1 `integration_connect` events in first 30 days — failed onboarding
- **Adoption score:** starts 0.3–0.5, decays to 0.05–0.15 by day 60
- **Usage:** 0–2 events/week, drops to zero at `churn_date`
- **Support:** 1–3 high/critical tickets in the 14–30 days before churn; topics: `onboarding` | `integration`
- **Risk:** `compliance_gap_score` ~ Beta(6, 2), mean ≈ 0.75

### mid_churner
- **Activation:** 2–3 `integration_connect` events — partial onboarding, then stalls
- **Adoption score:** peaks at 0.55–0.65 around day 60, then decays linearly
- **Usage:** stable for 2–4 months, then –40% per month for the final 60 days
- **Support:** spike in 30–60 days before churn; topics: `billing` | `integration`
- **Risk:** `compliance_gap_score` ~ Beta(3.5, 3), mean ≈ 0.54

### retained
- **Activation:** 3–6 `integration_connect` events in first 30 days — strong embedding
- **Adoption score:** climbs from 0.50 to 0.70–0.90 over first 90 days, then stabilises
- **Usage:** consistent 5–15 events/week, low variance
- **Support:** 0–1 tickets/month, mostly `feature_request` | `compliance`
- **Risk:** `compliance_gap_score` ~ Beta(1.5, 6), mean ≈ 0.20

### expanded
- Same behavioural profile as `retained`
- MRR at top 30% of their plan-tier range
- Guaranteed open GTM opportunity (`proposal` or `closed_won` stage)
- `compliance_gap_score` ~ Beta(1.2, 7), mean ≈ 0.15

---

## The Decay Function

For churning customers, event frequency is not cut off abruptly. Instead, a **sigmoid decay
multiplier** reduces the Poisson rate as the customer approaches their churn date:

```
multiplier(t) = 1 / (1 + exp(k × (t − churn_days_away + decay_window)))
```

Where:
- `t` = current day offset from signup
- `k = 0.1` — controls steepness (gradual, realistic slope)
- `decay_window = 45` days — decay begins ~45 days before churn

This produces a smooth trailing off of engagement rather than a step function. The model
therefore learns a **leading indicator** (gradual decay) rather than a perfect label leak.

```
Event rate
   │
1.0┤━━━━━━━━━━━━━━━━━━┓
   │                   ┃
0.5┤                    ╲
   │                     ╲
0.0┤──────────────────────┸━━━━━━━━━
                         ↑         ↑
                  decay starts   churn_date
                  (t - 45 days)
```

---

## Statistical Guardrails

After generation, a **validation suite** (`tests/integration/test_data_generation.py`) acts
as the acceptance gate. If any guardrail fails, the data pipeline aborts — the generator
produced invalid signal.

| Guardrail | Test method | Pass threshold |
|---|---|---|
| Usage decay before churn | Mann-Whitney U: `events_last_30d` (churned vs active) | p < 0.001 |
| Adoption score separation | Point-biserial r: `avg_adoption_score` vs `is_active` | r > 0.35 |
| Integration retention signal | Welch t-test: `retention_signal_count` (retained vs churned) | p < 0.01 |
| Support ticket churn spike | Welch t-test: `high_priority_tickets` (churned vs active) | p < 0.05 |
| Churn rate realism (starter) | Observed churn rate | 35%–55% |
| Churn rate realism (growth) | Observed churn rate | 12%–28% |
| Churn rate realism (enterprise) | Observed churn rate | 4%–15% |
| Enterprise churns less than starter | Directional comparison | enterprise rate < starter rate |

### Achieved results (RANDOM_SEED=42)

| Guardrail | Observed value | Status |
|---|---|---|
| Usage decay (Mann-Whitney p) | p < 0.0001 | ✅ |
| Adoption score correlation | r = 0.46 | ✅ |
| Integration signal (t-test p) | p < 0.0001 | ✅ |
| Support ticket spike (t-test p) | p < 0.001 | ✅ |
| Starter churn rate | 43.3% | ✅ |
| Growth churn rate | 19.7% | ✅ |
| Enterprise churn rate | 6.7% | ✅ |

---

## Schema Contract Guardrails

A second test file (`tests/integration/test_data_contracts.py`) enforces structural integrity
across all 5 tables — 32 checks covering:

- **Uniqueness:** all primary keys (`customer_id`, `event_id`, `ticket_id`, etc.)
- **FK integrity:** every `customer_id` in child tables exists in `customers`
- **Date range sanity:** no events before `signup_date`, no events after `churn_date`
- **Value constraints:** `feature_adoption_score` ∈ [0, 1], `compliance_gap_score` ∈ [0, 1]
- **Accepted values:** `plan_tier`, `event_type`, `priority`, `topic`, `stage`

---

## How to Regenerate

```bash
# 1. Generate all 5 CSVs (RANDOM_SEED=42, ~2 minutes)
uv run python -m src.infrastructure.data_generation.generate_synthetic_data

# 2. Load into DuckDB
uv run python -m src.infrastructure.db.build_warehouse

# 3. Validate statistical guardrails (must all pass before proceeding)
uv run pytest tests/integration/ --no-cov -v

# 4. Track with DVC
dvc add data/raw/
dvc add data/saasguard.duckdb
dvc push
```

Changing `RANDOM_SEED` will produce a different but equally valid dataset —
all statistical guardrails will still pass (by design of the profile system).

---

## Limitations & Known Simplifications

| Simplification | Real-world difference | Impact on model |
|---|---|---|
| Binary destiny at birth | Real churn is a continuous process influenced by external events (competitor launch, price change, key contact leaving) | Model will be slightly overconfident — calibrate with Platt scaling |
| No seasonality | Real SaaS usage dips in Q4 holidays and spikes in Q1 planning | Feature engineering can add month-of-year features |
| No customer-to-customer effects | Real churn can propagate within an enterprise (one power user leaving reduces other seats) | Not modelled — acceptable for v1 |
| MRR is static | Real MRR changes with seat counts and tier upgrades | Survival analysis handles time-varying risk better than snapshot MRR |

These limitations are documented here so readers understand the deliberate design
tradeoffs — not unexamined assumptions.
