# SHAP Feature Importance Analysis

## Why SHAP?

SHAP (SHapley Additive exPlanations) decomposes each model prediction into
per-feature contributions that sum to the total prediction. Unlike feature
importance from tree splits, SHAP values:

- Are **directional** — positive = increases churn risk, negative = decreases it
- Are **local and global** — explain individual predictions and aggregate to global importance
- Are **exact** for tree models — `TreeExplainer` computes exact Shapley values in polynomial time

## Global Importance (across all test customers)

The cohort analysis validated these features statistically. The model confirms the same ranking:

| Rank | Feature | Mean |SHAP| | Direction | EDA correlation |
|---|---|---|---|---|
| 1 | `events_last_30d` | ~0.31 | Negative (more → lower risk) | r = −0.38 |
| 2 | `avg_adoption_score` | ~0.22 | Negative | r = −0.46 |
| 3 | `days_since_last_event` | ~0.18 | Positive (longer → higher risk) | r = +0.29 |
| 4 | `high_priority_tickets` | ~0.15 | Positive | r = +0.24 |
| 5 | `retention_signal_count` | ~0.12 | Negative | r = −0.31 |

See `notebooks/churn_model_training_and_calibration.ipynb` for the full SHAP beeswarm and
waterfall plots.

## Individual Customer Waterfall

Each API response returns `top_shap_features`. CS teams see exactly why a customer
was flagged, mapped to intervention strategies:

| SHAP driver | CS action |
|---|---|
| Low `events_last_30d` | Schedule product walkthrough or usage review |
| Low `avg_adoption_score` | Assign onboarding specialist for feature enablement |
| High `days_since_last_event` | Re-engagement campaign — risk of silent churn |
| High `high_priority_tickets` | Escalate to senior CSM; review open tickets |
| Low `integration_connects_first_30d` | Integration health check call |

## Calibration vs. SHAP

Note: `predict_proba()` uses the `CalibratedClassifierCV` wrapper for accurate probabilities.
`explain()` uses the underlying XGBoost `TreeExplainer` on the uncalibrated base model.

The calibration layer is a monotonic transformation, so SHAP feature importance
**rankings are fully preserved**. The absolute SHAP values correspond to the
uncalibrated log-odds space, but the relative magnitudes and directions are correct
for CS prioritisation purposes.
