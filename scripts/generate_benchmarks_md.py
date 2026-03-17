#!/usr/bin/env python3
"""Convert Locust CSV stats output to a Markdown benchmarks table.

Reads benchmarks_stats.csv (written by `locust --csv=benchmarks`) and outputs
a Markdown table to stdout, which CI redirects to docs/benchmarks.md.

Usage:
    python scripts/generate_benchmarks_md.py benchmarks_stats.csv > docs/benchmarks.md
"""

from __future__ import annotations

import csv
import sys
from datetime import UTC, datetime
from pathlib import Path


def _ms(value: str) -> str:
    """Format a millisecond string, rounding to nearest integer."""
    try:
        return f"{float(value):.0f}ms"
    except (ValueError, TypeError):
        return "N/A"


def _rps(value: str) -> str:
    """Format requests-per-second value."""
    try:
        return f"{float(value):.0f}"
    except (ValueError, TypeError):
        return "N/A"


def generate(csv_path: Path) -> str:
    """Read Locust CSV and return a Markdown table string.

    Args:
        csv_path: Path to the Locust stats CSV file.

    Returns:
        Markdown string with header, table, and timestamp.
    """
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Keep only named endpoints (skip the Aggregated row for the detail table)
    endpoint_rows = [r for r in rows if r.get("Name") and r["Name"] != "Aggregated"]
    aggregate_rows = [r for r in rows if r.get("Name") == "Aggregated"]

    lines: list[str] = [
        "# Performance Benchmarks",
        "",
        "*Auto-updated by CI after every deploy to Render (Oregon, free tier). "
        "Measured under 50 concurrent users, 5 users/s spawn rate, 60s duration.*",
        "",
        "## Endpoint Latency",
        "",
        "| Endpoint | Method | P50 | P95 | P99 | Req/s | Failures |",
        "|---|---|---|---|---|---|---|",
    ]

    for row in endpoint_rows:
        method = row.get("Request Type", "GET").upper()
        name = row.get("Name", "unknown")
        p50 = _ms(row.get("50%", "0"))
        p95 = _ms(row.get("95%", "0"))
        p99 = _ms(row.get("99%", "0"))
        rps = _rps(row.get("Requests/s", "0"))
        failures = row.get("Failure Count", "0")
        lines.append(f"| `{name}` | {method} | {p50} | {p95} | {p99} | {rps} | {failures} |")

    # Aggregate row
    if aggregate_rows:
        agg = aggregate_rows[0]
        p50 = _ms(agg.get("50%", "0"))
        p95 = _ms(agg.get("95%", "0"))
        p99 = _ms(agg.get("99%", "0"))
        rps = _rps(agg.get("Requests/s", "0"))
        total_req = agg.get("Request Count", "N/A")
        fail_count = agg.get("Failure Count", "0")
        lines += [
            "",
            "## Aggregate Summary",
            "",
            "| Metric | Value |",
            "|---|---|",
            f"| P50 latency (all endpoints) | {p50} |",
            f"| P95 latency (all endpoints) | {p95} |",
            f"| P99 latency (all endpoints) | {p99} |",
            f"| Max throughput | {rps} req/s |",
            f"| Total requests | {total_req} |",
            f"| Total failures | {fail_count} |",
            "| Cold start (free tier) | ~30s |",
        ]

    lines += [
        "",
        "---",
        "",
        f"*Last updated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} by CI*",
        "",
        "> **Note:** Cold-start latency (~30s) applies only on first request after "
        "Render free-tier sleep. All numbers above are steady-state after warm-up.",
    ]

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: generate_benchmarks_md.py <benchmarks_stats.csv>", file=sys.stderr)
        sys.exit(1)

    csv_file = Path(sys.argv[1])
    if not csv_file.exists():
        print(f"Error: {csv_file} not found", file=sys.stderr)
        sys.exit(1)

    print(generate(csv_file), end="")
