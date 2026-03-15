---
name: dvc-version
description: Version any new data file, model artifact, or pipeline stage using DVC. Enforces reproducible pipelines, correct .gitignore entries, and DVC remote configuration. Run whenever synthetic data is generated or a model is trained.
triggers: ["dvc version", "version data", "version model", "dvc track", "add to dvc", "dvc pipeline", "model artifact", "track dataset"]
version: 1.0.0
---

# DVC Version Skill

**Prime directive:** Any file larger than a few KB that is not code belongs in DVC, not Git. The DuckDB warehouse and all model artifacts must be DVC-tracked so the demo is reproducible from any clean clone.

---

## When to Apply This Skill
- After `generate_synthetic_data.py` produces CSVs in `data/raw/`
- After DuckDB warehouse is built (`data/saasguard.duckdb`)
- After any model is trained (`.pkl` files in `models/`)
- When a new pipeline stage is added (new script that transforms data or trains a model)
- When DVC remote storage changes (e.g., switching from local to S3/GCS)

---

## Workflow

### Step 1 — Check DVC Initialisation
```bash
# If .dvc/ doesn't exist at repo root
dvc init
git add .dvc/ .dvcignore
git commit -m "chore: initialise DVC"
```

Verify `DVC/dvc.yaml` exists and `DVC/.dvc/` has a `config` file.

### Step 2 — Track New Files

#### Synthetic data (CSVs):
```bash
dvc add data/raw/customers.csv
dvc add data/raw/usage_events.csv
dvc add data/raw/gtm_opportunities.csv
dvc add data/raw/support_tickets.csv
dvc add data/raw/risk_signals.csv
```

#### DuckDB warehouse:
```bash
dvc add data/saasguard.duckdb
```

#### Model artifacts:
```bash
dvc add models/churn_model.pkl
dvc add models/churn_model_metadata.json
dvc add models/risk_model.pkl
dvc add models/risk_model_metadata.json
```

After `dvc add`, verify:
- A `.dvc` pointer file is created (e.g., `data/saasguard.duckdb.dvc`)
- The actual file is added to `.gitignore` automatically
- Commit the `.dvc` pointer file to Git

### Step 3 — Update `DVC/dvc.yaml` Pipeline

Every data transformation or model training step must have a corresponding stage:

```yaml
stages:
  {stage_name}:
    cmd: python -m src.infrastructure.{module}
    deps:
      - src/infrastructure/{module}.py
      - data/raw/{input_file}       # list ALL inputs
    params:                          # optional — hyperparams from params.yaml
      - model.n_estimators
    outs:
      - data/{output_file}           # DVC-tracked outputs
    metrics:
      - models/{name}_metadata.json  # auto-tracked metrics
        cache: false
    plots:
      - models/{name}_calibration.png
        cache: false
```

### Step 4 — Add `params.yaml` for Model Hyperparameters
```yaml
# params.yaml — tracked by DVC, versioned with Git
model:
  n_estimators: 300
  max_depth: 6
  learning_rate: 0.05
  scale_pos_weight: 3    # handles class imbalance

survival:
  duration_col: tenure_days
  event_col: churned

features:
  lookback_days: 30
  min_events_threshold: 3
```

### Step 5 — Configure DVC Remote (for team sharing)
```bash
# Option A: DagsHub (free, works well for open-source projects)
dvc remote add -d origin https://dagshub.com/{username}/saasguard.dvc
dvc remote modify origin --local auth basic
dvc remote modify origin --local user {username}
dvc remote modify origin --local password {token}

# Option B: Local remote (for local dev/CI)
dvc remote add -d local /tmp/dvc-remote
```

### Step 6 — Reproduce Pipeline
```bash
dvc repro          # run all stages where deps have changed
dvc push           # push tracked files to remote
```

### Step 7 — `.gitignore` Verification
After DVC tracking, verify the actual data files are gitignored:
```
data/saasguard.duckdb
data/raw/*.csv
models/*.pkl
models/*.png
```
The `.dvc` pointer files (e.g., `data/saasguard.duckdb.dvc`) should be committed to Git.

---

## Model Metadata Standard
Every trained model must produce a `models/{name}_metadata.json`:
```json
{
  "version": "1.0.0",
  "trained_at": "2026-03-14T10:00:00Z",
  "training_samples": 4200,
  "test_samples": 800,
  "metrics": {
    "auc_roc": 0.87,
    "average_precision": 0.72,
    "brier_score": 0.14,
    "calibration_slope": 0.98
  },
  "features": ["tenure_days", "events_last_30d", "avg_adoption_score", "..."],
  "hyperparameters": { "n_estimators": 300, "max_depth": 6 },
  "dvc_md5": "auto-populated-by-dvc",
  "bias_checks_passed": true
}
```

This file is tracked by DVC as a metric (`cache: false`) so `dvc metrics show` displays it.

---

## Output Format
```
## DVC Versioning Applied

Files tracked:
- data/saasguard.duckdb → data/saasguard.duckdb.dvc
- models/churn_model.pkl → models/churn_model.pkl.dvc

Pipeline stages added/updated in DVC/dvc.yaml:
- {stage_name}: {cmd}

Run to reproduce:
  dvc repro && dvc push

Git files to commit:
  git add data/saasguard.duckdb.dvc models/*.dvc DVC/dvc.yaml params.yaml
  git commit -m "chore(dvc): track warehouse and model artifacts v{version}"
```
