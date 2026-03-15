# Getting Started

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Docker | 24+ | Container runtime |
| Docker Compose | v2 | Multi-service orchestration |
| Git | any | Clone repo |
| uv *(optional)* | 0.4+ | Local Python dev without Docker |

---

## One-Command Start (Docker)

```bash
# 1. Clone
git clone https://github.com/josephwam/saasguard
cd saasguard

# 2. Copy env file
cp .env.example .env

# 3. Start everything (dev profile includes JupyterLab + MkDocs)
docker compose --profile dev up -d
```

Wait ~30 seconds for services to pass healthchecks, then open:

| Service | URL | Default credentials |
|---|---|---|
| FastAPI Swagger | http://localhost:8000/docs | — |
| Superset | http://localhost:8088 | admin / admin |
| JupyterLab | http://localhost:8888 | no token (dev only) |
| MkDocs (docs) | http://localhost:8001 | — |

---

## Data Pipeline

Before running predictions, you need the DuckDB warehouse populated:

```bash
# 1. Generate synthetic data (runs inside container)
docker compose exec api python -m src.infrastructure.data_generation.generate_synthetic_data

# 2. Run dbt transformations
docker compose exec dbt dbt run --profiles-dir .

# 3. Train models (Phase 4)
docker compose exec api dvc repro
```

Or with DVC (after `dvc pull` if artifacts are remote):

```bash
dvc pull      # fetch pre-built data + models
dvc repro     # re-run pipeline if sources changed
```

---

## Local Development (without Docker)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies including dev + notebook extras
uv sync --all-extras

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Lint + format
ruff check . && ruff format .

# Type check
mypy src/ app/

# MkDocs live server
mkdocs serve
```

---

## Running Tests

```bash
# Full suite with coverage
pytest

# Unit tests only (fast, no DB)
pytest tests/unit/ -v

# Integration tests (requires DuckDB file)
pytest tests/integration/ -v

# Single test
pytest tests/unit/domain/test_customer_entities.py::TestMRR::test_annual_revenue_at_risk_is_mrr_times_12 -v
```

---

## Building the Docs Site

```bash
# Live reload (dev)
docker compose --profile dev up mkdocs

# One-off static build
docker compose run --rm mkdocs mkdocs build
# → outputs to ./site/

# Deploy to GitHub Pages
docker compose run --rm mkdocs mkdocs gh-deploy
```

---

## Environment Variables

See [`.env.example`](../.env.example) for all variables. Key ones:

| Variable | Default | Description |
|---|---|---|
| `DUCKDB_PATH` | `/app/data/saasguard.duckdb` | Warehouse file path (mounted volume) |
| `GROQ_API_KEY` | — | Required for LLM executive summaries (Phase 5) |
| `SUPERSET_SECRET_KEY` | change_me | Must be changed in production |
| `APP_ENV` | `development` | Controls logging verbosity and gunicorn vs uvicorn |
