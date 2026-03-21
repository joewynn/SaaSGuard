# Runbook – SaaSGuard On-Call Operations

## Overview

This runbook covers alert response procedures, deployment steps, rollback instructions,
data refresh operations, and model retraining for the SaaSGuard platform.

**On-call contact:** Data Engineering team
**Escalation:** VP Engineering → VP Customer Success (for customer-facing impact)

---

## 1. Alert Response

### `/health` returns 503 (API liveness failure)

**Symptom:** `curl http://localhost:8000/health` returns non-200, or Prometheus alert fires.

**Diagnosis:**
```bash
docker compose ps                        # check container state
docker compose logs api --tail=50        # check for startup errors or OOM
```

**Resolution:**
```bash
docker compose restart api
# Wait 15s for HEALTHCHECK start-period, then verify:
curl http://localhost:8000/health        # expect {"status": "ok"}
```

**Escalate if:** Container crashes in a restart loop — check for missing env vars or volume mount failures.

---

### `/ready` returns 503 (Model not loaded)

**Symptom:** `curl http://localhost:8000/ready` returns 503 with `"detail": "Model not loaded"`.

**Cause:** Model `.pkl` files are missing from the `MODELS_DIR` volume (typically after a fresh deploy without DVC pull).

**Resolution:**
```bash
dvc pull                                  # restore model artifacts from DVC remote
# If DVC remote is unavailable, retrain locally:
dvc repro
# Then restart API to reload:
docker compose restart api
curl http://localhost:8000/ready          # expect {"status": "ready"}
```

---

### Superset unreachable (Dashboard 503/timeout)

**Symptom:** Superset UI at `:8088` is unresponsive.

**Diagnosis:**
```bash
docker compose ps superset               # check state
docker compose logs superset --tail=50   # check for DB connection errors
docker volume ls | grep superset_db      # verify volume exists
```

**Resolution:**
```bash
docker compose restart superset
# If DB volume is corrupted:
docker compose down superset
docker volume rm saasguard_superset_db   # WARNING: loses saved dashboards
docker compose up -d superset
# Re-import dashboards from docs/superset-exports/
```

---

### High API latency (p95 > 500ms)

**Symptom:** Prometheus alert on `http_request_duration_seconds` p95 or Gunicorn worker queue backing up.

**Resolution:**
```bash
# Check worker count in gunicorn.conf.py — may need tuning for the deployment host
docker compose exec api ps aux | grep gunicorn   # count worker processes
# Scale out:
docker compose -f docker-compose.prod.yml up -d --scale api=2
```

---

### Model drift alert (PSI > 0.20 on any monitored feature)

**Symptom:** GitHub Issue auto-opened by `drift-monitor.yml` with title
`[Drift Alert] PSI > 0.20 — <feature_name>`. Prometheus gauge
`saasguard_drift_psi{feature="<name>"}` exceeds 0.20.

**Severity thresholds:**

| PSI | Action |
|---|---|
| 0.10 – 0.20 | Moderate drift — log, monitor next weekly run before acting |
| > 0.20 | Significant drift — investigate root cause, schedule retrain |
| > 0.20 on `events_last_30d` or `avg_adoption_score` | Immediate escalation — these are primary churn signal features |

**Diagnosis:**
```bash
# Review which features are drifting and by how much
curl http://localhost:8000/metrics | grep saasguard_drift

# Check the drift monitor workflow logs
gh run list --workflow=drift-monitor.yml --limit=5
gh run view <run-id> --log
```

**Root cause checklist:**
1. **Data pipeline failure** — check if `data-pipeline.yml` ran successfully this week.
   A skipped dbt run leaves stale mart data; the drift detector compares against a
   stale distribution, producing false-positive drift signals.
2. **Real behavioural shift** — if the dbt run was healthy, the distribution change
   reflects genuine customer behaviour (e.g., a product change reduced `events_last_30d`
   across the board). This requires model retraining.
3. **New customer segment** — free-tier customers were added in v0.9.0. If their volume
   changes significantly, `mrr` and `mrr_tier_ceiling_pct` distributions will shift.
   Check segment proportions before retraining.

**Resolution — false positive (data pipeline failure):**
```bash
# Re-run the data pipeline manually
docker compose exec dbt dbt run
docker compose exec dbt dbt test
# Re-run drift detection against refreshed data
uv run python -m src.infrastructure.monitoring.drift_detector --check
```

**Resolution — confirmed drift (retrain required):**
```bash
# 1. Export a fresh baseline from current data
uv run python -m src.infrastructure.monitoring.drift_detector --export-baseline

# 2. Retrain — see Section 5 (Model Retraining)
dvc repro

# 3. After retrain, run accuracy gates
pytest tests/model_accuracy/ -v --no-cov

# 4. If accuracy gates pass, close the GitHub Issue with the retrain commit SHA
```

**Escalate if:** PSI > 0.20 on three or more features simultaneously — this signals a
systemic data change (schema migration, ingestion failure, or a major product change)
rather than organic model staleness.

---

### Prediction 500 errors (model inference failure)

**Symptom:** `POST /predictions/churn` or `POST /predictions/upgrade` returns 503 with
`"Prediction service error"`.

**Diagnosis:**
```bash
docker compose logs api --tail=100 | grep "ERROR"
# Look for: "model_not_loaded", "feature_extraction_failed", "mart_unavailable"
```

**Triage by log message:**

| Log key | Cause | Resolution |
|---|---|---|
| `model_not_loaded` | `.pkl` file missing from `MODELS_DIR` | `dvc pull && docker compose restart api` |
| `mart_unavailable` | dbt mart not built | `docker compose exec dbt dbt run --select mart_customer_churn_features` |
| `feature_extraction_failed` | Customer not found in raw tables | Verify `customer_id` exists: `SELECT COUNT(*) FROM raw.customers WHERE customer_id = '<id>'` |
| `expansion_feature_extractor.mart_unavailable` | Expansion mart stale | `docker compose exec dbt dbt run --select mart_customer_expansion_features` |

The feature extractor has an automatic raw-table fallback — a mart miss does not
immediately surface as a 503. A 503 from the prediction endpoint indicates a deeper
failure (missing model artifact or missing customer).

---

## 2. Deployment Procedure

### Standard Release

```bash
# 1. Tag the release on main branch
git tag v0.7.0
git push origin v0.7.0

# 2. CI/CD pipeline runs automatically:
#    lint → test → dbt build/test → docker build/push → Trivy scan → smoke test

# 3. On the production host, pull and redeploy
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 4. Verify health
curl http://localhost:8000/health
curl http://localhost:8000/ready
docker compose ps                        # all services "healthy"
```

### Environment Variables Checklist (Before Deploy)

| Variable | Required | Default |
|---|---|---|
| `ALLOWED_ORIGINS` | Yes | `http://localhost:8088` |
| `DUCKDB_PATH` | Yes | `/app/data/saasguard.duckdb` |
| `MODELS_DIR` | Yes | `/app/models` |
| `GROQ_API_KEY` | If using Groq LLM | — |
| `LLM_PROVIDER` | No | `groq` |
| `SUPERSET_SECRET_KEY` | Yes | Must be changed from default |
| `APP_ENV` | Yes | `production` |

---

## 3. Rollback

### Immediate Rollback (Previous Image)

```bash
# Find the previous image tag from CI/CD history
export PREV_TAG=sha-<previous-commit-sha>

# Stop current api, deploy previous
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  up -d api --no-deps \
  --image ghcr.io/<org>/saasguard:${PREV_TAG}

# Verify
curl http://localhost:8000/health
```

### Emergency Stop

```bash
# Scale API to zero — keeps DuckDB and Superset running
docker compose stop api
# Restore service:
docker compose start api
```

---

## 4. Data Refresh

### Nightly dbt Run (Standard)

```bash
docker compose exec dbt dbt run
docker compose exec dbt dbt test
```

**Expected output:** All models pass, no test failures. If dbt tests fail:

```bash
docker compose exec dbt dbt test --store-failures   # write failures to DB
docker compose exec dbt dbt docs serve              # inspect data lineage
```

### DuckDB File Permissions Issue

**Symptom:** `dbt run` or API queries fail with `Permission denied` on DuckDB file.

```bash
ls -la data/saasguard.duckdb
# Should be readable by saasguard user (uid matches container non-root user)
chmod 644 data/saasguard.duckdb
chown 1000:1000 data/saasguard.duckdb  # adjust UID to match container user
```

---

## 5. Model Retraining

```bash
# 1. Reproduce the full ML pipeline from dvc.yaml
dvc repro

# 2. Review accuracy metrics in tests/model_accuracy/
pytest tests/model_accuracy/ -v

# 3. Manual review: open notebooks/churn_model_training_and_calibration.ipynb
#    Verify calibration curve + AUC-ROC >= previous version

# 4. If metrics pass, push new artifacts to DVC remote
dvc push

# 5. Restart API to load the new model
docker compose restart api
curl http://localhost:8000/ready        # expect {"status": "ready"}

# 6. Tag the model version in git
git tag model-v<N+1>
git push origin model-v<N+1>
```

**Rollback a bad model:**
```bash
git checkout model-v<N>  -- models/   # restore previous model artifacts
dvc checkout             -- models/
docker compose restart api
```

---

## 6. Docker Build Validation (Manual — Run When Docker Is Available)

The `Dockerfile` `data-gen` stage runs a full pipeline at build time:
`generate_synthetic_data → build_warehouse → dbt build → train_churn_model → train_expansion_model → export-baseline`

Because Docker Desktop is not always available locally, validate with these commands when it is:

```bash
# Build and verify model artifacts exist in the data-gen stage
docker build --target data-gen -t saasguard-data-gen . && \
docker run --rm saasguard-data-gen ls -lh /app/models/
# Expected: churn_model.pkl, expansion_model.pkl, churn_training_baseline.json

# Build the production image and verify the non-root user
docker build --target prod -t saasguard-prod .
docker run --rm saasguard-prod id
# Expected: uid=<non-zero>(saasguard) gid=<non-zero>(saasguard)

# Full smoke test after build
docker compose up -d --build
sleep 20
curl http://localhost:8000/health   # {"status": "ok"}
curl http://localhost:8000/ready    # {"status": "ready"}
docker compose ps                   # all services "healthy"
```

### Drift Baseline (`models/churn_training_baseline.json`)

This file is **gitignored** (`models/*.json`) because it is generated from training data.
It must exist at API startup or a drift warning is logged.

- **In Docker:** regenerated automatically in the `data-gen` stage (step 7).
- **Locally (no Docker):**
  ```bash
  uv run python -m src.infrastructure.monitoring.drift_detector --export-baseline
  ```
- **In CI:** the `data-gen` build stage handles it; the prod image inherits from `data-gen`.

---

## 7. Useful Diagnostic Commands

```bash
# Service status
docker compose ps

# Live API logs (structured JSON)
docker compose logs api -f | python -m json.tool

# DuckDB quick query
docker compose exec api python -c "
import duckdb
conn = duckdb.connect('data/saasguard.duckdb', read_only=True)
print(conn.execute('SELECT COUNT(*) FROM raw.customers').fetchone())
"

# Prometheus metrics snapshot
curl http://localhost:8000/metrics | grep http_requests

# CORS header check (replace origin with target)
curl -H "Origin: http://localhost:8088" -I http://localhost:8000/health
```
