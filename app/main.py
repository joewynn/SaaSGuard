"""FastAPI application entrypoint.

This is a thin delivery layer. Business logic lives in src/application/ and src/domain/.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.routers import customers, predictions

logger = structlog.get_logger(__name__)

app = FastAPI(
    title="SaaSGuard API",
    description="B2B SaaS Churn & Risk Prediction Platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Prometheus metrics at /metrics
Instrumentator().instrument(app).expose(app)

app.include_router(predictions.router, prefix="/predictions", tags=["Predictions"])
app.include_router(customers.router, prefix="/customers", tags=["Customers"])


@app.get("/health", tags=["Health"])
async def health() -> dict[str, str]:
    """Liveness probe – returns 200 if the service is running."""
    return {"status": "ok", "version": "0.1.0"}
