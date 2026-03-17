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
