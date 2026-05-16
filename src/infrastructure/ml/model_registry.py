"""Model registry — loads model artifacts from the ZenML Model Control Plane."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_MODELS_DIR = Path(os.getenv("MODELS_DIR", "models"))


@lru_cache(maxsize=4)
def load_model(name: str) -> Any:  # noqa: ANN401 — generic model loader, return type depends on artifact
    """Load the production model artifact from the ZenML Model Control Plane.

    Args:
        name: Model name, e.g. "churn_model". Must match the Model(name=...) in
              the training pipeline.

    Returns:
        The deserialized model object.

    Raises:
        Exception: If the ZenML server is unreachable or no production artifact exists.
    """
    from zenml.client import Client
    from zenml.enums import ModelStages

    client = Client()
    model_version = client.get_model_version(
        model_name_or_id=name,
        model_version_name_or_number_or_id=ModelStages.PRODUCTION,
    )
    artifact = model_version.get_artifact("calibrated_model")
    model = artifact.load()
    logger.info(
        "model.loaded_from_zenml_mcp",
        name=name,
        version=str(model_version.version),
    )
    return model


def get_model_metadata(name: str) -> dict[str, Any]:
    """Return metadata (version, training date, metrics) for a model artifact."""
    meta_path = _MODELS_DIR / f"{name}_metadata.json"
    if not meta_path.exists():
        return {"version": "unknown"}
    with open(meta_path) as f:
        return json.load(f)  # type: ignore[no-any-return]
