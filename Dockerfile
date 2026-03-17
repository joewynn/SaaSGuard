# ── Stage 1: base ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# ── Stage 2: dependencies ──────────────────────────────────────────────────────
FROM base AS deps

COPY pyproject.toml uv.lock* README.md ./
RUN uv sync --frozen --no-dev --no-editable

# ── Stage 3: data-gen (generates demo data + trains model at build time) ──────
FROM deps AS data-gen

# Install dbt-duckdb into the same environment uv manages.
# uv pip install resolves the active project environment automatically.
RUN uv pip install --no-cache-dir dbt-duckdb==1.8.4

COPY src/ ./src/
COPY dbt_project/ ./dbt_project/

# DuckDB path for build stage; profiles.yml hardcodes /data/saasguard.duckdb
ENV DUCKDB_PATH=/app/data/saasguard.duckdb
RUN mkdir -p /app/data /app/models /data

# Use `uv run` for every command — it resolves the project environment
# (venv or system Python) automatically, no PATH guessing required.

# 1. Generate synthetic data → data/raw/*.csv
RUN uv run python -m src.infrastructure.data_generation.generate_synthetic_data

# 2. Build DuckDB warehouse (raw schema) → /app/data/saasguard.duckdb
RUN uv run python -m src.infrastructure.db.build_warehouse

# 3. Symlink so dbt finds /data/saasguard.duckdb (profiles.yml hardcoded path)
RUN ln -sf ${DUCKDB_PATH} /data/saasguard.duckdb

# 4. dbt build handles seeds + run + tests in one pass
RUN uv run dbt build --project-dir dbt_project --profiles-dir dbt_project --target prod

# 5. Train XGBoost churn model → models/churn_model.pkl + metadata JSON
RUN uv run python -m src.infrastructure.ml.train_churn_model

# 6. Export drift baseline → models/churn_training_baseline.json
RUN uv run python -m src.infrastructure.monitoring.drift_detector --export-baseline

# ── Stage 4: development (includes dev extras, hot-reload) ─────────────────────
FROM base AS dev

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --all-extras

COPY . .

EXPOSE 8000 8888

# ── Stage 5: production ────────────────────────────────────────────────────────
FROM deps AS prod

COPY src/ ./src/
COPY app/ ./app/
COPY gunicorn.conf.py ./

# Bake demo data and model artifacts from data-gen stage
COPY --from=data-gen /app/data/saasguard.duckdb ./data/saasguard.duckdb
COPY --from=data-gen /app/models/ ./models/

# Env vars so /ready probe passes immediately on startup
ENV DUCKDB_PATH=/app/data/saasguard.duckdb
ENV MODELS_DIR=/app/models

# Non-root user for security
RUN addgroup --system saasguard && adduser --system --ingroup saasguard saasguard
USER saasguard

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["gunicorn", "app.main:app", "-c", "gunicorn.conf.py"]
