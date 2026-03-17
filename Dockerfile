# ── Stage 1: base ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

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

# Install build-time-only tools: dbt-duckdb for transforms, faker for synthetic data.
# These are dev/build deps not present in the prod image.
RUN uv pip install --no-cache-dir dbt-duckdb==1.8.4 faker

COPY src/ ./src/
COPY dbt_project/ ./dbt_project/

# Activate the venv so bare `python` and `dbt` use the venv's packages directly,
# bypassing uv run's lockfile enforcement which would evict manually installed deps.
ENV PATH="/app/.venv/bin:$PATH"
ENV DUCKDB_PATH=/app/data/saasguard.duckdb

RUN mkdir -p /app/data /app/models /data

# 1. Generate synthetic data → data/raw/*.csv
RUN python -m src.infrastructure.data_generation.generate_synthetic_data

# 2. Build DuckDB warehouse (raw schema) → /app/data/saasguard.duckdb
RUN python -m src.infrastructure.db.build_warehouse

# 3. Symlink so dbt finds /data/saasguard.duckdb (profiles.yml hardcoded path)
RUN ln -sf ${DUCKDB_PATH} /data/saasguard.duckdb

# 4. dbt build handles seeds + run + tests in one pass
RUN dbt build --project-dir dbt_project --profiles-dir dbt_project --target prod

# 5. Train XGBoost churn model → models/churn_model.pkl + metadata JSON
RUN python -m src.infrastructure.ml.train_churn_model

# 6. Export drift baseline → models/churn_training_baseline.json
RUN python -m src.infrastructure.monitoring.drift_detector --export-baseline

# ── Stage 4: development (includes dev extras, hot-reload) ─────────────────────
FROM base AS dev

COPY pyproject.toml uv.lock* README.md ./
RUN uv sync --frozen --all-extras

COPY . .

EXPOSE 8000 8888

# ── Stage 5: production ────────────────────────────────────────────────────────
FROM deps AS prod

# Create non-root user FIRST so --chown can reference it below
RUN addgroup --system saasguard && adduser --system --ingroup saasguard saasguard
RUN chown saasguard:saasguard /app

# Copy application code with ownership
COPY --chown=saasguard:saasguard src/ ./src/
COPY --chown=saasguard:saasguard app/ ./app/
COPY --chown=saasguard:saasguard gunicorn.conf.py ./

# Copy ENTIRE data/ and models/ directories (not just files) so saasguard
# owns the folders — DuckDB must write .wal/.tmp files next to the database
COPY --chown=saasguard:saasguard --from=data-gen /app/data/ ./data/
COPY --chown=saasguard:saasguard --from=data-gen /app/models/ ./models/

# Activate the venv so gunicorn, python etc. resolve from it at runtime
ENV PATH="/app/.venv/bin:$PATH"
ENV DUCKDB_PATH=/app/data/saasguard.duckdb
ENV MODELS_DIR=/app/models

USER saasguard

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use $PORT from Railway (falls back to 8000 locally)
CMD ["sh", "-c", "gunicorn -c gunicorn.conf.py app.main:app --bind 0.0.0.0:${PORT:-8000}"]
