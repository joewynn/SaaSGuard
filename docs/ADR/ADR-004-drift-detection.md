# ADR-004: Model Drift Detection — Custom PSI + KS Test

**Status:** Accepted
**Date:** 2026-03-16
**Deciders:** Joseph Wam
**Context:** MLOps hardening — closing the "no drift detection" gap

---

## Context

A model trained on historical data degrades silently when incoming customer feature
distributions shift. Common causes in B2B SaaS:
- A sales campaign acquires a new customer segment (MRR distribution shifts)
- Product changes alter usage patterns (events_last_30d decays to near-zero)
- Support workflow changes affect ticket volume and resolution time

Without drift detection, model performance degradation is only discovered after
CS teams report bad recommendations — typically weeks after the issue started.

---

## Decision

**Custom PSI + KS test** with a JSON baseline sidecar co-versioned with the model artifact.

---

## Alternatives Considered

| Library | Pros | Cons | Decision |
|---|---|---|---|
| **Custom PSI + KS** | Zero extra dependencies, native Prometheus export, full control | More code to write | ✅ **Selected** |
| Evidently.ai | Full-featured, HTML reports, data drift + model drift | Adds ~200MB to image, requires a sidecar process, overkill for 12 features | ❌ Rejected |
| WhyLogs | Pandas-native, lightweight | Less interpretable for business stakeholders, no PSI threshold documentation | ❌ Rejected |
| NannyML | Strong statistical guarantees | Active development, API churn risk, not widely known | ❌ Rejected |

---

## Why Custom PSI + KS (Dual Metric Rationale)

### PSI — "Risk Manager" interpretability
Population Stability Index is the standard metric used by credit risk teams for over
two decades. Its thresholds are internationally recognized:

| PSI | Interpretation | Action |
|---|---|---|
| < 0.10 | No significant drift | Monitor as usual |
| 0.10 – 0.20 | Moderate drift — investigate | Check data pipeline, segment analysis |
| > 0.20 | **Significant drift** — retrain candidate | Open GitHub Issue, schedule retrain |

PSI is explainable to a business audience: "The MRR distribution of incoming customers
has shifted 27% from the training population." KS p-values alone are not.

### KS test — Statistical rigour for model rollback decisions
The two-sample KS test provides a p-value that answers: "Is this distribution shift
statistically significant or just sampling noise?" Combined with PSI:

- PSI > 0.20 AND KS p < 0.05 → High confidence: retrain or rollback
- PSI > 0.20 BUT KS p > 0.05 → Likely sampling artefact from small production batch
- PSI < 0.10 BUT KS p < 0.05 → Subtle shift; investigate data quality

---

## Baseline Design

### Storage: `models/churn_training_baseline.json`
```json
{
  "mrr": {
    "min": 500.0, "max": 50000.0, "mean": 4821.3, "std": 8234.1,
    "bins": [500.0, 5450.0, ...],   // 11 edges → 10 buckets
    "hist": [0.32, 0.18, ...],      // normalized probabilities
    "sample": [1200.0, 8400.0, ...]  // 500 random training values for KS test
  },
  ...
}
```

### Versioning
The baseline JSON is regenerated at the end of every `train_churn_model.py` run (step 6
of the `data-gen` Docker stage and step 5 of the weekly `data-pipeline.yml` cron). It
is co-versioned with `churn_model.pkl` in DVC so rollback of model = rollback of baseline.

---

## Prometheus Integration

Four module-level Gauges registered in the default `prometheus_client` registry,
exposed via the existing `/metrics` endpoint:

| Gauge | Description |
|---|---|
| `saasguard_drift_psi_max` | Worst-case PSI across all monitored features |
| `saasguard_drift_psi_by_feature{feature="..."}` | Per-feature PSI |
| `saasguard_drift_ks_max_statistic` | Max KS statistic |
| `saasguard_drift_ks_pvalue_min` | Most significant KS p-value |

No Grafana sidecar required — metrics are already on `/metrics`.

---

## Actionability

### Automated response (drift-monitor.yml, weekly Sunday 00:00 UTC)
1. Generates a fresh data snapshot
2. Runs `python -m src.infrastructure.monitoring.drift_detector --check`
3. Writes `drift_report.json` artifact
4. If exit code 1 → opens a GitHub Issue labelled `model-health, priority-high`

### On-call runbook
1. **Triage:** Inspect `drift_report.json` — which features drifted?
2. **Data check:** `dbt test` to rule out upstream data quality issues
3. **Segment check:** Has a new customer segment been onboarded recently?
4. **Decision:**
   - Temporary shift (promo campaign) → document, set a retrain reminder
   - Structural shift → trigger weekly data pipeline manually, rebuild image
5. **Escalation:** If AUC drops below 0.75 on a holdout validation set, escalate to
   model retrain with the new data distribution included in training

---

## Monitored Features (12 numerical)

`mrr`, `tenure_days`, `total_events`, `events_last_30d`, `events_last_7d`,
`avg_adoption_score`, `days_since_last_event`, `retention_signal_count`,
`integration_connects_first_30d`, `tickets_last_30d`, `high_priority_tickets`,
`avg_resolution_hours`

Binary/derived features (`is_early_stage`, categorical `plan_tier`, `industry`) are
excluded from drift detection — their distributions are structurally bounded and
unlikely to drift in ways that degrade model performance.

---

## References

- `src/infrastructure/monitoring/drift_detector.py` — implementation
- `.github/workflows/drift-monitor.yml` — weekly cron
- `app/main.py` — startup initialization and `/health/model` endpoint
- Siddiqi, N. (2006). *Credit Risk Scorecards* — PSI methodology
