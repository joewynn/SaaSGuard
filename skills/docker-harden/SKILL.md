---
name: docker-harden
description: Audit and harden any Docker or Docker Compose configuration in SaaSGuard. Enforces healthchecks, restart policies, multi-stage builds, non-root users, resource limits, and K8s-ready labels on every service.
triggers: ["docker harden", "harden docker", "docker review", "production docker", "dockerize", "add healthcheck", "docker best practices"]
version: 1.0.0
---

# Docker Harden Skill

**Prime directive:** Every container that ships to production must be independently healthy, restartable, non-root, resource-bounded, and observable. No exceptions.

---

## Audit Checklist

Run through this for every service in `docker-compose.yml` and `docker-compose.prod.yml`:

### 1. Multi-Stage Dockerfile
- [ ] Separate `base`, `deps`, `dev`, `prod` stages
- [ ] `prod` stage copies only `src/` and `app/` — no test files, no notebooks, no dev tools
- [ ] `prod` stage runs as a non-root user:
  ```dockerfile
  RUN addgroup --system saasguard && adduser --system --ingroup saasguard saasguard
  USER saasguard
  ```
- [ ] `HEALTHCHECK` instruction in `prod` stage
- [ ] `.dockerignore` excludes: `.git`, `.venv`, `__pycache__`, `*.pyc`, `tests/`, `notebooks/`, `*.duckdb`, `models/`, `.env`

### 2. Healthchecks (every service)
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:{port}/health"]
  interval: 30s
  timeout: 10s
  start_period: 20s   # give service time to initialise
  retries: 3
```
- FastAPI: `GET /health`
- Superset: `GET /health`
- JupyterLab: `GET /api` or curl port 8888
- MkDocs: `GET /` on port 8000

### 3. Restart Policies
| Service type | Policy |
|---|---|
| Long-running (api, superset) | `restart: unless-stopped` |
| Dev-only (jupyterlab, mkdocs) | `restart: unless-stopped` (profile: dev) |
| One-shot (dbt) | `restart: "no"` |
| Production | `restart: always` in `docker-compose.prod.yml` |

### 4. `depends_on` with Conditions
Use `condition: service_healthy` (not just `service_started`) for hard dependencies:
```yaml
api:
  depends_on:
    dbt:
      condition: service_completed_successfully
    superset:
      condition: service_healthy   # if api calls superset APIs
```

### 5. Volume Strategy
- DuckDB file: named volume **or** bind mount to `./data/` (bind preferred for DVC)
- Superset home: named volume (persists dashboard configs)
- Source code (dev only): bind mount `./src:/app/src` for hot-reload
- Models: bind mount `./models:/app/models` (DVC-managed)
- **Never** mount `.env` as a volume — use `env_file`

### 6. Resource Limits (prod only — `docker-compose.prod.yml`)
```yaml
deploy:
  resources:
    limits:
      cpus: "2"
      memory: 2G
    reservations:
      cpus: "0.5"
      memory: 512M
```

### 7. Kubernetes-Ready Labels
Every service in `docker-compose.prod.yml`:
```yaml
labels:
  app.kubernetes.io/name: saasguard-{service}
  app.kubernetes.io/component: {serving|analytics|docs|database}
  app.kubernetes.io/part-of: saasguard
  app.kubernetes.io/version: "${APP_VERSION}"
```

### 8. Secrets Management
- No secrets in `docker-compose.yml` — all via `env_file: .env`
- `.env` is gitignored; `.env.example` documents all required variables
- For production: consider Docker Secrets or a secrets manager

### 9. `.dockerignore`
Verify this file exists and includes:
```
.git
.github
.venv
__pycache__
*.pyc
*.pyo
*.egg-info
.pytest_cache
.mypy_cache
.ruff_cache
tests/
notebooks/
data/*.duckdb
models/*.pkl
.env
site/
DVC/
docs/
```

---

## Output Format
```
## Docker Hardening Report

### Issues Found
- [ ] Missing healthcheck on: {service}
- [ ] Running as root in: {service}
- [ ] No resource limits in prod for: {service}

### Files to Update
1. Dockerfile — [what to change]
2. docker-compose.yml — [what to change]
3. docker-compose.prod.yml — [what to change]
4. .dockerignore — [what to add]

### Complete Updated Sections
[output only the changed stanzas, not the full file unless everything changed]

## Verify with
docker compose config   # validates compose syntax
docker build --target prod -t saasguard:test .
docker run --rm saasguard:test id   # should NOT print root
```
