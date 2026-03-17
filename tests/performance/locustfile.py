"""Locust load test suite for SaaSGuard API.

Targets the three production endpoints with realistic traffic ratios:
  - POST /predictions/churn  (weight 3) — primary inference endpoint
  - GET  /health             (weight 1) — liveness probe
  - GET  /customers/{id}     (weight 1) — Customer 360 profile

Customer IDs are loaded from tests/performance/customer_ids.json (written by
benchmarks.yml from the baked DuckDB). If the fixture file is absent the test
falls back to CUSTOMER_IDS_JSON env var.

Usage (headless, as run by CI):
    locust -f tests/performance/locustfile.py \\
        --host http://localhost:8000 \\
        --headless -u 50 -r 5 -t 60s \\
        --csv=benchmarks --only-summary

Usage (interactive UI):
    locust -f tests/performance/locustfile.py --host http://localhost:8000
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

from locust import HttpUser, between, events, task

# ── Customer ID fixture ────────────────────────────────────────────────────────

_FIXTURE_PATH = Path(__file__).parent / "customer_ids.json"


def _load_customer_ids() -> list[str]:
    """Load customer IDs from fixture file or environment variable.

    Precedence:
      1. tests/performance/customer_ids.json  (written by benchmarks.yml)
      2. CUSTOMER_IDS_JSON env var            (JSON array string)

    Returns:
        List of customer_id strings.

    Raises:
        RuntimeError: If no customer IDs can be loaded.
    """
    if _FIXTURE_PATH.exists():
        with open(_FIXTURE_PATH) as f:
            ids: list[str] = json.load(f)
        print(f"[locust] Loaded {len(ids)} customer IDs from {_FIXTURE_PATH}")
        return ids

    env_ids = os.getenv("CUSTOMER_IDS_JSON")
    if env_ids:
        ids = json.loads(env_ids)
        print(f"[locust] Loaded {len(ids)} customer IDs from CUSTOMER_IDS_JSON env")
        return ids

    raise RuntimeError(
        "No customer IDs available. Run benchmarks.yml to generate "
        "tests/performance/customer_ids.json, or set CUSTOMER_IDS_JSON env var."
    )


# Load once at module import (shared across all users)
_CUSTOMER_IDS: list[str] = _load_customer_ids()


# ── Locust user ────────────────────────────────────────────────────────────────


class SaaSGuardUser(HttpUser):
    """Simulates a CS platform querying SaaSGuard for customer risk signals.

    Task weights reflect a realistic read pattern:
      - Prediction requests dominate (batch scoring runs)
      - Customer 360 lookups are on-demand (CS agent workflow)
      - Health checks are low-frequency (load balancer probes)
    """

    wait_time = between(0.1, 0.5)  # 100–500ms think time between requests

    def on_start(self) -> None:
        """Pick a random customer ID for this virtual user's session."""
        self._customer_id = random.choice(_CUSTOMER_IDS)

    @task(3)
    def predict_churn(self) -> None:
        """POST /predictions/churn — primary inference endpoint (weight 3)."""
        self.client.post(
            "/predictions/churn",
            json={"customer_id": self._customer_id},
            name="/predictions/churn",
        )
        # Rotate customer every ~5 requests to spread load
        if random.random() < 0.2:
            self._customer_id = random.choice(_CUSTOMER_IDS)

    @task(1)
    def health_check(self) -> None:
        """GET /health — liveness probe (weight 1)."""
        self.client.get("/health", name="/health")

    @task(1)
    def customer_360(self) -> None:
        """GET /customers/{id} — Customer 360 profile (weight 1)."""
        self.client.get(
            f"/customers/{self._customer_id}",
            name="/customers/{customer_id}",
        )


# ── P95 / P99 summary on test stop ────────────────────────────────────────────


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):  # type: ignore[no-untyped-def]
    """Print P50/P95/P99 latency summary when Locust finishes."""
    stats = environment.runner.stats
    print("\n" + "=" * 60)
    print("SaaSGuard Performance Benchmark Results")
    print("=" * 60)
    for name, entry in stats.entries.items():
        print(
            f"  {name[1]:<40} "
            f"P50={entry.get_response_time_percentile(0.50):>6.0f}ms  "
            f"P95={entry.get_response_time_percentile(0.95):>6.0f}ms  "
            f"P99={entry.get_response_time_percentile(0.99):>6.0f}ms  "
            f"RPS={entry.current_rps:>6.1f}"
        )
    print("=" * 60)
