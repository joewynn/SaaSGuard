"""FastAPI application entrypoint.

This is a thin delivery layer. Business logic lives in src/application/ and src/domain/.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

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

# ── Drift detector singleton (initialised at startup) ─────────────────────────
_drift_detector = None


def model_registry_loaded() -> bool:
    """Check whether model artifacts are present on disk.

    Returns:
        True if at least one .pkl file exists in the models/ directory.
    """
    models_dir = Path(os.getenv("MODELS_DIR", "models"))
    return models_dir.is_dir() and any(models_dir.glob("*.pkl"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup initialisation and graceful shutdown.

    Startup:
        Initialises the drift detector if a baseline exists. A missing baseline
        is a warning (not fatal) so the API can still serve predictions while
        the baseline is being generated.

    Shutdown:
        No teardown required — all connections are managed via context managers.
    """
    global _drift_detector

    # Initialise drift detector (non-fatal if baseline not yet generated)
    try:
        from src.infrastructure.monitoring.drift_detector import DriftDetector

        _drift_detector = DriftDetector()
        logger.info(
            "drift_detector.initialised",
            baseline_features=len(_drift_detector.baselines),
        )
    except FileNotFoundError:
        logger.warning(
            "drift_detector.baseline_missing",
            hint="Run: python -m src.infrastructure.monitoring.drift_detector --export-baseline",
        )
    except Exception as exc:
        logger.warning("drift_detector.init_failed", error=str(exc))

    yield
    # Shutdown: stateless — no teardown needed


app = FastAPI(
    title="SaaSGuard API",
    description="B2B SaaS Churn & Risk Prediction Platform",
    version="0.7.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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


@app.get("/health/model", tags=["Health"])
async def model_health() -> dict[str, object]:
    """Returns the latest drift PSI and KS statistics from the startup check.

    Business Context:
        Consumers can poll this endpoint to determine if the deployed model's
        input distribution has shifted significantly from the training data,
        which is an early warning signal for model performance degradation.

    Returns:
        Dict with drift status, max_psi, min_ks_pvalue, and drifted_features.
        Returns {"status": "baseline_unavailable"} if baseline was not loaded.
    """
    if _drift_detector is None:
        return {
            "status": "baseline_unavailable",
            "hint": "Drift baseline not generated — run --export-baseline after training",
        }

    # Run a lightweight drift check against active customers
    try:
        from src.infrastructure.db.duckdb_adapter import get_connection

        with get_connection(read_only=True) as conn:
            prod_df = conn.execute(
                "SELECT * FROM marts.mart_customer_churn_features LIMIT 1000"
            ).df()

        report = _drift_detector.run(prod_df)
        _drift_detector.expose_prometheus(report)

        return {
            "status": "drift_detected" if report.has_drift else "healthy",
            "max_psi": round(report.max_psi, 4),
            "min_ks_pvalue": round(report.min_ks_pvalue, 4),
            "drifted_features": report.drifted_features,
            "psi_alert_threshold": 0.20,
            "ks_pvalue_threshold": 0.05,
            "checked_at": report.checked_at,
        }
    except Exception as exc:
        logger.warning("model_health.check_failed", error=str(exc))
        return {"status": "check_failed", "error": str(exc)}
