# ADR-003: Cloud Deployment Platform — Railway

**Status:** Accepted
**Date:** 2026-03-16
**Deciders:** Engineering

---

## Context

SaaSGuard requires a shared live endpoint accessible to business stakeholders (CS managers,
VP Sales, Compliance reviewers) without local environment setup. The operational constraints
at current traffic levels are:

- **Time-to-value:** Stakeholder access must require zero local tooling — a URL, not a
  `docker compose up` instruction.
- **TCO target:** Pre-PMF infrastructure cost ceiling is $0–$50/month. At this stage,
  operational simplicity has a higher priority than raw scalability.
- **CI/CD closure:** The deployment pipeline must complete end-to-end on `git push` to
  `main` — lint → test → dbt build → Docker build → image push → live deploy. No
  manual deploy steps.
- **HTTPS without certificate management:** TLS termination must be platform-provided.
- **No cold-start on the critical path:** CS teams querying the prediction API during
  an account review cannot absorb 30-second cold-start latencies.

---

## Decision

**Railway** with a Docker-based web service (Starter plan, $5/month).

---

## Alternatives Considered

| Platform | TCO (pre-PMF) | Time-to-Value | Cold-start | Decision |
|---|---|---|---|---|
| **Railway** | $0 free / $5 Starter | Immediate — Docker-native, GitHub auto-deploy | None on Starter | ✅ Selected |
| Render.com | $0 free / $7 Starter | Immediate | ~30s on free tier | ❌ Cold-start violates latency SLA |
| AWS ECS + ECR | >$20/month + IAM overhead | High — requires VPC, IAM, ECR, ECS task config | None | ❌ Operational overhead disproportionate to current traffic envelope |
| Fly.io | $0 free tier | Medium — requires `flyctl` CLI setup | Minimal | ❌ Additional toolchain dependency without meaningful benefit over Railway |
| Heroku | $7+/month | Immediate | None (paid) | ❌ No Docker-native web dyno on current plans |

**TCO rationale:** AWS ECS would provide autoscaling and enterprise SLAs at a cost of
$20–$80/month plus non-trivial IAM and networking configuration time. At <200 DAU and
~50 concurrent users at peak, that operational overhead is not justified. The documented
upgrade path (Railway → AWS ECS) is a `railway.toml` → ECS task definition conversion —
no application code changes required.

---

## Consequences

### Positive

- **Zero infrastructure state outside the repo:** `railway.toml` is the complete
  infrastructure-as-code definition. Reprovisioning the environment requires no
  out-of-band configuration.
- **CI/CD closes the loop:** `push → lint → test → build → push image → deploy` is a
  single pipeline. The `deploy` job in `ci.yml` fires the Railway webhook after smoke
  tests pass. No manual deploy steps exist.
- **Benchmarked capacity:** P99 latency ~140ms at 50 concurrent users on Railway US-West.
  Documented in `docs/benchmarks.md`. Sufficient for current CS team usage.

### Negative / Trade-offs

- **Resource ceiling at free tier:** 512MB RAM limits concurrent users to ~50 before
  OOM risk. The Starter plan ($5/month) removes this constraint and increases RAM to 2GB.
  All published benchmarks are measured on Starter.
- **Single-region:** Railway US-West. Latency from EMEA is ~180ms P99. A multi-region
  deployment requires moving to a managed Kubernetes platform.

### Data Strategy

Demo and staging data (DuckDB + model artifacts) is baked into the Docker image at build
time via the `data-gen` multi-stage build stage. This eliminates cold-start generation
time and makes the image self-contained for the current traffic profile. On retrain, a
new image push triggers a fresh deploy via the Railway webhook.

- Image size target: ~350–450 MB (Python runtime + data + model artifacts)
- No external storage dependency at current scale
- Production migration path: mount DuckDB from a persistent volume (Railway Volumes or S3)
  and decouple data from the image lifecycle

### Secret Management

`GROQ_API_KEY` is injected via the Railway dashboard environment variables (never
committed). All other configuration is in `railway.toml` and safe to commit.

### Upgrade Path

| Traffic level | Platform | Monthly TCO |
|---|---|---|
| <200 DAU (current) | Railway Starter | $5 |
| 200–2,000 DAU | Railway Pro or Fly.io | $20–$50 |
| >2,000 DAU | AWS ECS + RDS or Snowflake | $80–$200 |

---

## References

- `railway.toml` — service definition
- `.github/workflows/ci.yml` — `deploy` job
- `docs/benchmarks.md` — P50/P95/P99 latency table
