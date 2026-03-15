# Model Card — SaaSGuard Churn Prediction Model v0.4

> Intended for CS operations teams, product analytics, and technical stakeholders.
> Updated: 2026-03-14. Artifact: `models/churn_model.pkl` (DVC-tracked).

---

## Model Summary

| Property | Value |
|---|---|
| **Task** | Binary classification — P(customer churns within next 90 days) |
| **Algorithm** | XGBoost inside sklearn `Pipeline`, wrapped in `CalibratedClassifierCV` (isotonic, cv=5) |
| **Feature count** | 15 (13 numerical + 2 categorical encoded as ordinal) |
| **Training data** | 5,000 customers (1,471 churned / 3,529 active); RANDOM_SEED=42 |
| **Validation strategy** | Out-of-time split — train: `signup_date < 2025-06-01`, test: `≥ 2025-06-01` |
| **Output** | Calibrated probability ∈ [0, 1] + top-5 SHAP drivers + risk tier + recommended CS action |

---

## Intended Use

**Primary use case:** Customer Success teams prioritising outreach for at-risk accounts.

**Input:** A `customer_id` for any active customer in `marts.mart_customer_churn_features`.

**Output consumed by:**
- `POST /predictions/churn` — individual prediction with SHAP explanation
- Superset Churn Heatmap dashboard — portfolio view ranked by `churn_probability × MRR`
- CS intervention queue — `GET /customers?tier=critical&limit=20`

**Not intended for:**
- Predicting churn for customers with < 7 days tenure (insufficient usage signal)
- Automated contract termination decisions (human-in-the-loop required)
- Any use outside CS prioritisation without bias audit (see below)

---

## Features

| Feature | Type | Source | Phase 3 Signal |
|---|---|---|---|
| `mrr` | Numerical | `raw.customers` | Revenue-at-risk weighting |
| `tenure_days` | Numerical | Derived: `signup_date → reference_date` | Time-in-product proxy |
| `total_events` | Numerical | `raw.usage_events` | Lifetime engagement volume |
| `events_last_30d` | Numerical | `raw.usage_events` | **Primary decay signal** — r = −0.38 |
| `events_last_7d` | Numerical | `raw.usage_events` | Leading disengagement indicator |
| `avg_adoption_score` | Numerical | `raw.usage_events` | Feature depth — r = −0.34 |
| `days_since_last_event` | Numerical | `raw.usage_events` | Recency decay |
| `retention_signal_count` | Numerical | `raw.usage_events` | Deep product adoption — r = −0.32 |
| `integration_connects_first_30d` | Numerical | `raw.usage_events` | Activation gate: ≥3 → 2.7× lower churn |
| `tickets_last_30d` | Numerical | `raw.support_tickets` | Pre-churn frustration signal |
| `high_priority_tickets` | Numerical | `raw.support_tickets` | r = +0.27 |
| `avg_resolution_hours` | Numerical | `raw.support_tickets` | CS experience quality |
| `is_early_stage` | Binary (int) | Derived: `tenure_days ≤ 90` | First-90-day cohort flag |
| `plan_tier` | Categorical → ordinal | `raw.customers` | starter=0, growth=1, enterprise=2 |
| `industry` | Categorical → ordinal | `raw.customers` | fintech=0, healthtech=1, legaltech=2, proptech=3, saas=4 |

All features are pre-aggregated by dbt in `mart_customer_churn_features`. Feature engineering lives entirely in dbt — not duplicated in Python.

---

## Performance Metrics (RANDOM_SEED=42, out-of-time test set)

| Metric | Target | Status |
|---|---|---|
| AUC-ROC | > 0.80 | ✅ Met |
| Brier score | < 0.15 | ✅ Met |
| Precision @ top decile | > 0.60 | ✅ Met |
| Calibration per tier | ±15pp of KM baseline | ✅ Met |

Calibration note: `predict_proba()` uses `CalibratedClassifierCV`. SHAP values are computed on the underlying XGBoost base model — relative rankings and directions are preserved (calibration is monotonic). See `docs/shap-analysis.md` for details.

---

## Training Strategy

**Point-in-time correctness:** churned customers' features are computed as of their `churn_date`. Active customers use `REFERENCE_DATE = 2026-03-14`. This prevents leakage where post-churn behaviour contaminates the feature vector.

**Label:** `is_churned` — a churned-vs-active discriminator. The model learns the pre-churn signal pattern (usage decay, ticket spikes) from all 1,471 labelled churn examples. The "90-day horizon" is the CS intervention window communicated to business stakeholders, not the label definition.

**Class imbalance:** handled with `scale_pos_weight = n_negative / n_positive` in XGBoost. The calibration layer further corrects probability estimates per tier.

**Reproducibility:** `dvc repro` retrains from scratch deterministically. All hyperparameters are logged in `models/churn_model_metadata.json`.

---

## SHAP Explainability

Every prediction returns `top_shap_features` — the 5 features with largest |SHAP impact|:

| Top driver | Direction | CS action |
|---|---|---|
| Low `events_last_30d` | ↓ risk when high | Schedule product walkthrough |
| Low `avg_adoption_score` | ↓ risk when high | Assign onboarding specialist |
| High `days_since_last_event` | ↑ risk | Re-engagement campaign — silent churn risk |
| High `high_priority_tickets` | ↑ risk | Escalate to senior CSM |
| Low `integration_connects_first_30d` | ↓ risk when high | Integration health check call |

Full global importance rankings and individual waterfall charts: `notebooks/phase4_01_model_training.ipynb` § SHAP Analysis.

---

## Risk Tiers

| Tier | Probability range | Recommended action |
|---|---|---|
| `low` | < 0.30 | Monitor quarterly; standard CS cadence |
| `medium` | 0.30 – 0.60 | Proactive check-in within 30 days |
| `high` | 0.60 – 0.80 | Escalate to CSM; schedule EBR within 14 days |
| `critical` | > 0.80 | Escalate to senior CSM immediately; schedule EBR within 7 days |

---

## Known Limitations & Bias Considerations

- **Synthetic data:** The model is trained on Faker-generated data with baked-in correlations. Real-world performance should be validated on production data before acting on predictions for live customers.
- **Industry imbalance:** FinTech and HealthTech customers dominate the training set. Industries with fewer examples (PropTech, LegalTech) have wider prediction uncertainty.
- **No temporal drift detection:** Model training cutoff is 2025-06-01. After 90 days from any deployment date, a data drift check should be triggered. Phase 7 scope.
- **Label definition:** The model distinguishes churned from active customers — it does not predict future churn probability for customers who have never churned. Calibration per tier addresses this but does not eliminate uncertainty.
- **Human-in-the-loop required:** Model output must be reviewed by a CS manager before automated outreach or contract actions. `recommended_action` is advisory only.

---

## Reproducing the Model

```bash
# 1. Generate data (if not already done)
dvc repro generate_data build_duckdb

# 2. Build the dbt feature mart
docker compose exec dbt dbt run --select mart_customer_churn_features

# 3. Train (deterministic — RANDOM_SEED=42 fixed in params.yaml)
uv run python -m src.infrastructure.ml.train_churn_model

# 4. Run accuracy gates
pytest tests/model_accuracy/test_churn_model.py -v --no-cov

# 5. Check metadata
cat models/churn_model_metadata.json
```

---

## Versioning

Model artifacts are DVC-tracked and not committed to git:
- `models/churn_model.pkl` — serialised `CalibratedClassifierCV` wrapping the sklearn Pipeline
- `models/churn_model_metadata.json` — version, training date, AUC, Brier, feature list, data cutoff

To pull a specific model version: `dvc pull models/churn_model.pkl`.
