"""Model registry – loads and caches DVC-tracked model artifacts.

Model files (.pkl) are versioned via DVC and stored in models/.
This module is the only place in the codebase that touches pickle files.
"""

from __future__ import annotations

import json
import os
import pickle
from functools import lru_cache
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_MODELS_DIR = Path(os.getenv("MODELS_DIR", "models"))


@lru_cache(maxsize=4)
def load_model(name: str) -> Any:  # noqa: ANN401 — generic model loader, return type depends on artifact
    """Load a pickled model artifact by name (cached after first load).

    Args:
        name: Model name without extension, e.g. "churn_model" or "risk_model".

    Returns:
        The deserialized model object.

    Raises:
        FileNotFoundError: If the artifact does not exist. Run `dvc pull` first.
    """
    path = _MODELS_DIR / f"{name}.pkl"
    if not path.exists():
        raise FileNotFoundError(
            f"Model artifact not found at {path}. "
            "Run `dvc pull` to fetch versioned artifacts."
        )
    logger.info("model.loaded", name=name, path=str(path))
    with open(path, "rb") as f:
        return pickle.load(f)  # noqa: S301


def get_model_metadata(name: str) -> dict[str, Any]:
    """Return metadata (version, training date, metrics) for a model artifact."""
    meta_path = _MODELS_DIR / f"{name}_metadata.json"
    if not meta_path.exists():
        return {"version": "unknown"}
    with open(meta_path) as f:
        return json.load(f)  # type: ignore[no-any-return]
