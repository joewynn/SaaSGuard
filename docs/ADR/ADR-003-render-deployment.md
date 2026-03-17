# ADR-003: Cloud Deployment Platform — Railway

**Status:** Accepted
**Date:** 2026-03-16
**Deciders:** Joseph Wam
**Context:** Phase 7 — Production Deployment

---

## Context

SaaSGuard needed a publicly accessible live URL to demonstrate that the platform is
production-deployable, not just locally runnable. Without a live URL, a portfolio
reviewer cannot verify P99 latency claims, test the OpenAPI docs, or confirm the
Docker image actually runs end-to-end.

The deployment target needed to:
- Accept a Docker image from GitHub Container Registry (`ghcr.io`) without credentials
- Provide automatic HTTPS with no certificate management overhead
- Deploy on `git push` to `main` via a webhook (no separate deploy step)
- Require no cloud credits or AWS/GCP accounts

---

## Decision

**Railway** with a Docker-based web service on the free tier.

---

## Alternatives Considered

| Platform | Pros | Cons | Decision |
|---|---|---|---|
| **Railway** | Docker-native, GitHub auto-deploy, free HTTPS, no cold-start on Starter plan, generous free tier | Slightly less portfolio name-recognition than legacy platforms | ✅ **Selected** |
| Render.com | Similar Docker-native setup, free HTTPS | Free tier cold-start ~30s, 512MB RAM limit, less generous free tier | ❌ Rejected — cold-start degrades live demo experience |
| AWS ECS + ECR | Full enterprise stack, autoscaling, no cold-start | Requires AWS account, free-tier expires, complex IAM setup | ❌ Rejected — overkill for portfolio demo |
| Fly.io | Good free tier, global regions | Requires `flyctl` CLI, less familiar to reviewers | ❌ Rejected |
| Heroku | Industry recognition | Paid-only since Nov 2022, no Docker-native web dyno | ❌ Rejected |

---

## Consequences

### Positive

- **Single live URL** for CV/LinkedIn: `https://saasguard.up.railway.app/docs`
- **Zero additional infrastructure** — Railway reads from `ghcr.io` directly
- **CI closes the loop**: `push → lint → test → build → push image → deploy` is a single
  pipeline — the `deploy` job in `ci.yml` fires the Railway deploy hook after smoke tests pass
- **`railway.toml`** as infrastructure-as-code documents the service config in git

### Negative / Trade-offs

- **Free tier resource limits** — sufficient for demo traffic but limits concurrent users
  to ~50 before resource pressure. Documented in `docs/benchmarks.md`
- **512MB RAM** on free tier — sufficient for the DuckDB + XGBoost model but limits
  concurrent users to ~50 before OOM risk. Documented in ADR

### Data strategy

Demo data (DuckDB + model artifacts) is baked into the Docker image at build time via
the `data-gen` multi-stage build stage. This eliminates cold-start generation time on
Railway and makes the image self-contained. See ADR implications:

- Image size target: ~350–450 MB (Python runtime + data + model artifacts)
- No external storage dependency for the free tier deployment
- On retrain, a new image push triggers a fresh Railway deploy via the deploy hook

### Secret management

`GROQ_API_KEY` is set directly in the Railway dashboard (never committed). All other
env vars are in `railway.toml` and safe to commit.

### Upgrade path

Railway Starter ($5/month) removes resource restrictions and increases RAM to 2GB,
which is sufficient for production CS team usage (~200 DAU).

---

## References

- Railway documentation: https://docs.railway.app/deploy/dockerfiles
- `.github/workflows/ci.yml` — `deploy` job
- `railway.toml` — service definition
