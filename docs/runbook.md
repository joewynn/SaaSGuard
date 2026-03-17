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

## 6. Useful Diagnostic Commands

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
