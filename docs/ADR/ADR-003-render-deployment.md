# ADR-003: Cloud Deployment Platform — Render.com

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

**Render.com** with a Docker-based web service on the free tier.

---

## Alternatives Considered

| Platform | Pros | Cons | Decision |
|---|---|---|---|
| **Render.com** | Docker-native, GitHub auto-deploy, free HTTPS, no cloud credits | Free tier cold-start ~30s, 512MB RAM limit | ✅ **Selected** |
| Railway | Similar to Render, generous free tier | Less portfolio recognition, fewer docs | ❌ Rejected |
| AWS ECS + ECR | Full enterprise stack, autoscaling, no cold-start | Requires AWS account, free-tier expires, complex IAM setup | ❌ Rejected — overkill for portfolio demo |
| Fly.io | Good free tier, global regions | Requires `flyctl` CLI, less familiar to reviewers | ❌ Rejected |
| Heroku | Industry recognition | Paid-only since Nov 2022, no Docker-native web dyno | ❌ Rejected |

---

## Consequences

### Positive

- **Single live URL** for CV/LinkedIn: `https://saasguard.onrender.com/docs`
- **Zero additional infrastructure** — Render reads from `ghcr.io` directly
- **CI closes the loop**: `push → lint → test → build → push image → deploy` is a single
  pipeline — the `deploy` job in `ci.yml` fires the Render deploy hook after smoke tests pass
- **render.yaml** as infrastructure-as-code documents the service config in git

### Negative / Trade-offs

- **Free tier cold-start ~30s** after 15 minutes of inactivity. Documented in
  `docs/benchmarks.md`. Upgrade path: Render Starter plan ($7/month) for always-on
- **512MB RAM** on free tier — sufficient for the DuckDB + XGBoost model but limits
  concurrent users to ~50 before OOM risk. Documented in ADR

### Data strategy

Demo data (DuckDB + model artifacts) is baked into the Docker image at build time via
the `data-gen` multi-stage build stage. This eliminates cold-start generation time on
Render and makes the image self-contained. See ADR implications:

- Image size target: ~350–450 MB (Python runtime + data + model artifacts)
- No external storage dependency for the free tier deployment
- On retrain, a new image push triggers a fresh Render deploy via the deploy hook

### Secret management

`GROQ_API_KEY` is set directly in the Render dashboard (never committed). All other
env vars are in `render.yaml` and safe to commit.

### Upgrade path

Render Starter ($7/month) removes the cold-start restriction and increases RAM to 2GB,
which is sufficient for production CS team usage (~200 DAU).

---

## References

- Render documentation: https://render.com/docs/deploy-a-docker-image
- `.github/workflows/ci.yml` — `deploy` job
- `render.yaml` — service definition
