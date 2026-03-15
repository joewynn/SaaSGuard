"""FastAPI application entrypoint.

This is a thin delivery layer. Business logic lives in src/application/ and src/domain/.
"""

from __future__ import annotations

import os
from pathlib import Path

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.routers import customers, predictions, summaries

logger = structlog.get_logger(__name__)

# ── CORS: restrict origins for production ─────────────────────────────────────
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8088",
).split(",")

app = FastAPI(
    title="SaaSGuard API",
    description="B2B SaaS Churn & Risk Prediction Platform",
    version="0.7.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# Prometheus metrics at /metrics
Instrumentator().instrument(app).expose(app)

app.include_router(predictions.router, prefix="/predictions", tags=["Predictions"])
app.include_router(customers.router, prefix="/customers", tags=["Customers"])
app.include_router(summaries.router, prefix="/summaries", tags=["AI Summaries"])


def model_registry_loaded() -> bool:
    """Check whether model artifacts are present on disk.

    Returns:
        True if at least one .pkl file exists in the models/ directory.
    """
    models_dir = Path(os.getenv("MODELS_DIR", "models"))
    return models_dir.is_dir() and any(models_dir.glob("*.pkl"))


@app.get("/health", tags=["Health"])
async def health() -> dict[str, str]:
    """Liveness probe – returns 200 if the service is running."""
    return {"status": "ok", "version": "0.7.0"}


@app.get("/ready", tags=["Health"])
async def readiness() -> dict[str, str]:
    """Readiness probe – fails if model artifacts are not loaded.

    Returns:
        200 {"status": "ready"} when models are available.

    Raises:
        503: If model artifacts are missing from MODELS_DIR.
    """
    if not model_registry_loaded():
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ready", "version": "0.7.0"}
