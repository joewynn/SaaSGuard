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

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-editable

# ── Stage 3: development (includes dev extras, hot-reload) ─────────────────────
FROM base AS dev

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --all-extras

COPY . .

EXPOSE 8000 8888

# ── Stage 4: production ────────────────────────────────────────────────────────
FROM deps AS prod

COPY src/ ./src/
COPY app/ ./app/

# Non-root user for security
RUN addgroup --system saasguard && adduser --system --ingroup saasguard saasguard
USER saasguard

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["gunicorn", "app.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
