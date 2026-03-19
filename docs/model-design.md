# Predictive Model Design & Accuracy

## Overview

The model layer delivers: a calibrated XGBoost churn model that
takes each active customer's 15-feature vector and returns `P(churn in 90 days)`, SHAP
feature explanations, and a recommended CS action.

## Model Architecture

```
ChurnFeatureExtractor
    └── Queries marts.mart_customer_churn_features (1 DuckDB read, ~1ms)

sklearn Pipeline
    ├── ColumnTransformer
    │   ├── StandardScaler        → 13 numerical features
    │   └── OrdinalEncoder        → plan_tier, industry
    └── XGBClassifier
        ├── n_estimators=300, max_depth=5, learning_rate=0.05
        ├── scale_pos_weight = n_negative / n_positive
        └── eval_metric='logloss'

CalibratedClassifierCV(method='isotonic', cv=5)
    └── Wraps the pipeline for probability calibration
```

## Feature Set (15 total)

| Feature | Type | Source | EDA Signal |
|---|---|---|---|
| `mrr` | Numerical | customers table | Revenue-at-risk weighting |
| `tenure_days` | Numerical | Derived from signup_date | Time-in-product |
| `total_events` | Numerical | usage_events | Lifetime engagement |
| `events_last_30d` | Numerical | usage_events | **Primary decay signal** (|r|>0.30) |
| `events_last_7d` | Numerical | usage_events | Leading disengagement indicator |
| `avg_adoption_score` | Numerical | usage_events | Feature depth (|r|>0.20) |
| `days_since_last_event` | Numerical | usage_events | Recency decay |
| `retention_signal_count` | Numerical | usage_events | High-value event depth |
| `integration_connects_first_30d` | Numerical | usage_events | Activation gate — 2.7× lower churn |
| `tickets_last_30d` | Numerical | support_tickets | Pre-churn frustration signal |
| `high_priority_tickets` | Numerical | support_tickets | Positively correlated with churn |
| `avg_resolution_hours` | Numerical | support_tickets | CS experience quality |
| `is_early_stage` | Binary | Derived (tenure ≤ 90d) | First-90-day cohort flag |
| `plan_tier` | Categorical | customers table | Tier-differentiated churn rates |
| `industry` | Categorical | customers table | Vertical segment |

## Accuracy Targets

| Metric | Target | Business Rationale |
|---|---|---|
| AUC-ROC | > 0.80 | Model must reliably rank at-risk customers above safe ones |
| Brier score | < 0.15 | Calibrated probabilities → trustworthy risk tiers |
| Precision @ decile 1 | > 0.60 | CS team acts on top 10% — this is the actionable bucket |
| Tier calibration | ±15pp of KM | Model tier rates should match survival analysis baseline |

## Training Strategy

**Point-in-time correctness**: churned customers' features are computed as of their
`churn_date`, not the reference date. This prevents data leakage where post-churn
behaviour contaminates the feature vector.

**Out-of-time validation**: train on `signup_date < 2025-06-01`, test on `signup_date ≥ 2025-06-01`.
This simulates genuine temporal holdout — the most realistic validation for churn models.

**Class imbalance**: handled via `scale_pos_weight = n_negative / n_positive` in XGBoost.
The calibration layer further corrects probability estimates.

## Risk Signal Integration

`POST /predictions/churn` now returns real risk scores (not hardcoded zeros):

- `compliance_gap_score` and `vendor_risk_flags` — from `raw.risk_signals` table
- `usage_decay_score` — computed as `max(0, 1 - events_last_30d / events_prev_30d)`

The composite `RiskScore` is computed by `RiskModelService` with weights:
usage (0.50) + compliance (0.35) + vendor (0.15).

## SHAP Explanations

Every prediction returns `top_shap_features` — the top 5 features by |SHAP impact|.
CS teams see a plain-English reason for the risk tier:

```json
{
  "churn_probability": 0.78,
  "risk_tier": "critical",
  "recommended_action": "CRITICAL – Escalate to senior CSM immediately. Schedule EBR within 7 days.",
  "top_shap_features": [
    {"feature": "events_last_30d",       "value": 2.0,  "shap_impact":  0.31},
    {"feature": "high_priority_tickets", "value": 3.0,  "shap_impact":  0.22},
    {"feature": "avg_adoption_score",    "value": 0.12, "shap_impact":  0.18}
  ]
}
```

## Reproducing the Model

```bash
# 1. Generate data (if not already done)
dvc repro generate_data build_duckdb

# 2. Run dbt to build the feature mart
docker compose exec dbt dbt run

# 3. Train the model
uv run python -m src.infrastructure.ml.train_churn_model

# 4. Run accuracy tests
pytest tests/model_accuracy/test_churn_model.py -v --no-cov

# 5. Verify the API endpoint
uv run uvicorn app.main:app --reload &
curl -X POST http://localhost:8000/predictions/churn \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "<uuid-from-duckdb>"}'
```

---

## Section 2 — Expansion Propensity Model (v0.9.0)

### Overview

The expansion model complements the churn model by predicting `P(upgrade in 90 days)`
for active non-upgraded customers. Both models feed the **Propensity Quadrant** — the
primary Superset dashboard visualization.

### Architecture

```
ExpansionFeatureExtractor
    └── Queries marts.mart_customer_expansion_features (1 DuckDB read, ~1ms)
        Primary path: mart table (pre-computed 20 features)
        Fallback path: inline SQL (if mart not available at inference time)

sklearn Pipeline
    ├── ColumnTransformer
    │   ├── StandardScaler        → 18 numerical features
    │   └── OrdinalEncoder        → plan_tier, industry
    └── XGBClassifier
        ├── n_estimators=300, max_depth=5, learning_rate=0.05
        ├── scale_pos_weight = n_not_upgraded / n_upgraded
        └── eval_metric='logloss'

CalibratedClassifierCV(method='isotonic', cv=5)
    └── Wraps the pipeline for probability calibration
```

### Feature Set (20 total — 15 churn features + 5 expansion-specific)

**Base features (reused from churn model via mart JOIN):**

| Feature | Type | Source |
|---|---|---|
| `mrr` | Numerical | customers |
| `tenure_days` | Numerical | Derived |
| `total_events` | Numerical | usage_events |
| `events_last_30d` | Numerical | usage_events |
| `events_last_7d` | Numerical | usage_events |
| `avg_adoption_score` | Numerical | usage_events |
| `days_since_last_event` | Numerical | usage_events |
| `retention_signal_count` | Numerical | usage_events |
| `integration_connects_first_30d` | Numerical | usage_events |
| `tickets_last_30d` | Numerical | support_tickets |
| `high_priority_tickets` | Numerical | support_tickets |
| `avg_resolution_hours` | Numerical | support_tickets |
| `is_early_stage` | Binary | Derived |
| `plan_tier` | Categorical | customers |
| `industry` | Categorical | customers |

**Expansion-specific features (5 new):**

| Feature | Type | Source | Signal |
|---|---|---|---|
| `premium_feature_trials_30d` | Numerical | usage_events | Customer trialling above-tier features |
| `feature_request_tickets_90d` | Numerical | support_tickets | Requesting unowned capabilities |
| `has_open_expansion_opp` | Boolean | gtm_opportunities | Sales aware of expansion intent |
| `expansion_opp_amount` | Numerical | gtm_opportunities | Size of identified opportunity |
| `mrr_tier_ceiling_pct` | Numerical | Derived | `(mrr - floor) / (ceiling - floor)` |

### Leakage Guard

`has_open_expansion_opp` encodes a *sales decision* (did Sales open an opp?), not a
*customer signal*. If this feature dominates the SHAP ranking, the model is predicting
Sales' behaviour, not the customer's readiness.

**Guard:** Training script asserts `has_open_expansion_opp` is not rank #1 SHAP feature.
Notebook Section 5 re-asserts this on the hold-out set.

### Training Design

**Label:** `is_upgraded = 1` if `upgrade_date IS NOT NULL` and `upgrade_date ≤ REFERENCE_DATE`.
Customers with no upgrade and no churn at REFERENCE_DATE are `is_upgraded = 0`.

**Point-in-time correctness:** Features computed as of the REFERENCE_DATE observation window,
not as of today. Prevents lookahead bias.

**Scope:** Training data includes all non-churned customers (both upgraded and not).
The mart (`mart_customer_expansion_features`) scopes to non-upgraded only (inference candidates).

### Accuracy Targets & Achieved Metrics

| Metric | Target | Achieved | Status |
|---|---|---|---|
| AUC-ROC | ≥ 0.75 | **0.928** | ✅ |
| Brier score | < 0.25 | 0.190 | ✅ |
| Precision @ decile 1 | ≥ 20% | 21.7% | ✅ |

### Top SHAP Features (from training run)

1. `premium_feature_trials_30d` — mean |SHAP| 3.94 (strongest expansion signal)
2. `tenure_days` — 2.88 (longer-tenured customers more likely to upgrade)
3. `mrr_tier_ceiling_pct` — 1.90 (tier pressure: close to ceiling = ripe for upgrade)
4. `retention_signal_count` — 0.84 (engaged customers upgrade)
5. `total_events` — 0.59 (lifetime engagement depth)

### Reproducing the Expansion Model

```bash
# 1. Regenerate synthetic data (adds upgrade_date, premium_feature_trial, opportunity_type)
uv run python -m src.infrastructure.data_generation.generate_synthetic_data

# 2. Rebuild DuckDB warehouse
uv run python -m src.infrastructure.db.build_warehouse

# 3. Run dbt models (or the Docker-free runner)
docker compose exec dbt dbt run
# OR (without Docker):
uv run python scripts/run_dbt_models.py

# 4. Train the model
uv run python -m src.infrastructure.ml.train_expansion_model

# 5. Run tests
uv run pytest tests/unit/domain/test_expansion_value_objects.py \
              tests/unit/domain/test_expansion_service.py \
              tests/unit/application/test_predict_expansion_use_case.py \
              tests/integration/test_expansion_data_contracts.py -v --no-cov
```
