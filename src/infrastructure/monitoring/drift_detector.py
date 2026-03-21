"""Feature drift detector — PSI + KS test against training baseline.

Business Context:
    Model performance degrades silently when the distribution of incoming customer
    features diverges from the training distribution. This module detects that drift
    by computing Population Stability Index (PSI) and Kolmogorov-Smirnov (KS) tests
    against a JSON baseline exported at training time.

    Alert thresholds (documented in ADR-004):
        PSI > 0.10  — moderate drift, investigate
        PSI > 0.20  — significant drift, retrain candidate
        KS p-value < 0.05 — statistically significant distribution shift

Prometheus Gauges (module-level singletons, registered in default registry):
    saasguard_drift_psi_max             — Max PSI across all monitored features
    saasguard_drift_psi_by_feature      — Per-feature PSI (label: feature)
    saasguard_drift_ks_max_statistic    — Max KS statistic across features
    saasguard_drift_ks_pvalue_min       — Min KS p-value across features

CLI modes:
    python -m src.infrastructure.monitoring.drift_detector --export-baseline
        Reads marts.mart_customer_churn_features from DuckDB, computes per-feature
        histogram + sample, writes to MODELS_DIR/churn_training_baseline.json.

    python -m src.infrastructure.monitoring.drift_detector --check
        Loads baseline, reads current production features, computes drift report,
        writes to drift_report.json, exits non-zero if drift thresholds exceeded.

Usage:
    from src.infrastructure.monitoring.drift_detector import DriftDetector
    detector = DriftDetector()
    report = detector.run(production_df)
    detector.expose_prometheus(report)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import structlog
from prometheus_client import Gauge
from scipy.stats import ks_2samp

from src.infrastructure.db.duckdb_adapter import get_connection

logger = structlog.get_logger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

MODELS_DIR = Path(os.getenv("MODELS_DIR", "models"))
BASELINE_FILENAME = "churn_training_baseline.json"

PSI_MODERATE_THRESHOLD = 0.10
PSI_ALERT_THRESHOLD = 0.20
KS_PVALUE_THRESHOLD = 0.05

# 12 numerical features monitored for drift (is_early_stage is binary/derived, excluded)
MONITORED_FEATURES: list[str] = [
    "mrr",
    "tenure_days",
    "total_events",
    "events_last_30d",
    "events_last_7d",
    "avg_adoption_score",
    "days_since_last_event",
    "retention_signal_count",
    "integration_connects_first_30d",
    "tickets_last_30d",
    "high_priority_tickets",
    "avg_resolution_hours",
]

# ── Prometheus Gauges (module-level singletons for API process) ────────────────
# Registered in the default prometheus_client registry so /metrics exposes them.
# Tests should use a fresh CollectorRegistry per test to avoid duplicate errors.
try:
    GAUGE_PSI_MAX = Gauge(
        "saasguard_drift_psi_max",
        "Maximum Population Stability Index across all monitored features",
    )
    GAUGE_PSI_FEATURE = Gauge(
        "saasguard_drift_psi_by_feature",
        "Population Stability Index per monitored feature",
        ["feature"],
    )
    GAUGE_KS_MAX_STAT = Gauge(
        "saasguard_drift_ks_max_statistic",
        "Maximum KS test statistic across monitored features",
    )
    GAUGE_KS_MIN_PVALUE = Gauge(
        "saasguard_drift_ks_pvalue_min",
        "Minimum KS test p-value across monitored features",
    )
    _GAUGES_AVAILABLE = True
except ValueError:
    # Already registered in this process (e.g., test re-imports)
    _GAUGES_AVAILABLE = False
    logger.debug("drift_detector.gauges_already_registered")


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class FeatureBaseline:
    """Statistical baseline for a single feature, computed from training data.

    Attributes:
        name: Feature column name.
        min_val: Minimum training value.
        max_val: Maximum training value.
        mean: Training mean.
        std: Training standard deviation.
        bins: 11 bin edges defining 10 histogram buckets.
        hist: 10 normalized histogram values (sum to 1.0).
        sample: Up to 500 random training values for KS test.
    """

    name: str
    min_val: float
    max_val: float
    mean: float
    std: float
    bins: list[float]
    hist: list[float]
    sample: list[float]


@dataclass
class FeatureDriftResult:
    """Drift metrics for a single feature.

    Attributes:
        feature: Feature column name.
        psi: Population Stability Index (0 = no drift, >0.20 = alert).
        ks_stat: KS test statistic (0–1, higher = more diverged).
        ks_pvalue: KS test p-value (<0.05 = statistically significant shift).
        drift_detected: True if PSI > ALERT_THRESHOLD or p-value < KS threshold.
    """

    feature: str
    psi: float
    ks_stat: float
    ks_pvalue: float
    drift_detected: bool = field(init=False)

    def __post_init__(self) -> None:
        self.drift_detected = self.psi > PSI_ALERT_THRESHOLD or self.ks_pvalue < KS_PVALUE_THRESHOLD


@dataclass
class DriftReport:
    """Aggregated drift report across all monitored features.

    Attributes:
        feature_results: Per-feature drift metrics.
        max_psi: Worst-case PSI across all features.
        min_ks_pvalue: Most significant KS p-value across all features.
        has_drift: True if any feature exceeds alert thresholds.
        checked_at: ISO timestamp of when the check was performed.
        drifted_features: Names of features with drift_detected=True.
    """

    feature_results: list[FeatureDriftResult]
    max_psi: float
    min_ks_pvalue: float
    has_drift: bool
    checked_at: str
    drifted_features: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Serialize report to a JSON-serialisable dict."""
        return {
            "checked_at": self.checked_at,
            "has_drift": self.has_drift,
            "max_psi": round(self.max_psi, 6),
            "min_ks_pvalue": round(self.min_ks_pvalue, 6),
            "drifted_features": self.drifted_features,
            "psi_alert_threshold": PSI_ALERT_THRESHOLD,
            "ks_pvalue_threshold": KS_PVALUE_THRESHOLD,
            "features": [
                {
                    "feature": r.feature,
                    "psi": round(r.psi, 6),
                    "psi_level": _psi_level(r.psi),
                    "ks_stat": round(r.ks_stat, 6),
                    "ks_pvalue": round(r.ks_pvalue, 6),
                    "drift_detected": r.drift_detected,
                }
                for r in self.feature_results
            ],
        }


def _psi_level(psi: float) -> str:
    """Classify PSI into human-readable risk level."""
    if psi < PSI_MODERATE_THRESHOLD:
        return "no_drift"
    if psi < PSI_ALERT_THRESHOLD:
        return "moderate"
    return "alert"


# ── DriftDetector ─────────────────────────────────────────────────────────────


class DriftDetector:
    """Detects feature drift between training baseline and production data.

    Business Context:
        Called at API startup to initialise the drift state, and optionally
        scheduled weekly via the drift-monitor GitHub Actions workflow.
        Exposes PSI and KS metrics to Prometheus for Grafana alerting.

    Attributes:
        baselines: Dict mapping feature name → FeatureBaseline.
        baseline_path: Path to the JSON baseline file.
    """

    def __init__(self, baseline_path: Path | None = None) -> None:
        """Initialise detector and load baseline.

        Args:
            baseline_path: Override for the baseline JSON path.
                           Defaults to MODELS_DIR/churn_training_baseline.json.

        Raises:
            FileNotFoundError: If the baseline file does not exist.
        """
        self.baseline_path = baseline_path or (MODELS_DIR / BASELINE_FILENAME)
        self.baselines: dict[str, FeatureBaseline] = self.load_baseline(self.baseline_path)
        logger.info(
            "drift_detector.loaded",
            baseline_path=str(self.baseline_path),
            n_features=len(self.baselines),
        )

    def load_baseline(self, path: Path) -> dict[str, FeatureBaseline]:
        """Load per-feature baselines from the JSON sidecar file.

        Args:
            path: Path to churn_training_baseline.json.

        Returns:
            Dict mapping feature name → FeatureBaseline dataclass.

        Raises:
            FileNotFoundError: If the file does not exist at the given path.
        """
        if not path.exists():
            raise FileNotFoundError(
                f"Drift baseline not found at {path}. "
                "Run: python -m src.infrastructure.monitoring.drift_detector --export-baseline"
            )
        with open(path) as f:
            raw: dict[str, dict[str, object]] = json.load(f)

        return {
            name: FeatureBaseline(
                name=name,
                min_val=float(data["min"]),  # type: ignore[arg-type]
                max_val=float(data["max"]),  # type: ignore[arg-type]
                mean=float(data["mean"]),  # type: ignore[arg-type]
                std=float(data["std"]),  # type: ignore[arg-type]
                bins=[float(b) for b in data["bins"]],  # type: ignore[union-attr]
                hist=[float(h) for h in data["hist"]],  # type: ignore[union-attr]
                sample=[float(s) for s in data["sample"]],  # type: ignore[union-attr]
            )
            for name, data in raw.items()
        }

    def run(self, production_df: pd.DataFrame) -> DriftReport:
        """Compute PSI and KS drift metrics against the training baseline.

        Business Context:
            A PSI > 0.20 on 'mrr' or 'tenure_days' often indicates segment mix
            shift (e.g., a new enterprise sales campaign). A KS p-value < 0.05
            on 'days_since_last_event' signals product engagement change that
            the model hasn't seen.

        Args:
            production_df: DataFrame containing the monitored feature columns.
                           Rows with NaN are dropped per-feature before scoring.

        Returns:
            DriftReport with per-feature PSI/KS results and aggregate summary.
        """
        results: list[FeatureDriftResult] = []

        for feature in MONITORED_FEATURES:
            if feature not in self.baselines:
                logger.warning("drift_detector.feature_missing_baseline", feature=feature)
                continue
            if feature not in production_df.columns:
                logger.warning("drift_detector.feature_missing_prod", feature=feature)
                continue

            baseline = self.baselines[feature]
            prod_series = production_df[feature].dropna().astype(float)

            if len(prod_series) < 10:
                logger.warning(
                    "drift_detector.insufficient_prod_data",
                    feature=feature,
                    n=len(prod_series),
                )
                continue

            psi = self._compute_psi(baseline, prod_series)
            ks_stat, ks_pvalue = self._compute_ks(baseline, prod_series)

            result = FeatureDriftResult(
                feature=feature,
                psi=psi,
                ks_stat=ks_stat,
                ks_pvalue=ks_pvalue,
            )
            results.append(result)

            logger.debug(
                "drift_detector.feature_result",
                feature=feature,
                psi=round(psi, 4),
                psi_level=_psi_level(psi),
                ks_stat=round(ks_stat, 4),
                ks_pvalue=round(ks_pvalue, 4),
                drift_detected=result.drift_detected,
            )

        max_psi = max((r.psi for r in results), default=0.0)
        min_ks_pvalue = min((r.ks_pvalue for r in results), default=1.0)
        has_drift = any(r.drift_detected for r in results)
        drifted = [r.feature for r in results if r.drift_detected]

        report = DriftReport(
            feature_results=results,
            max_psi=max_psi,
            min_ks_pvalue=min_ks_pvalue,
            has_drift=has_drift,
            checked_at=datetime.now(UTC).isoformat(),
            drifted_features=drifted,
        )

        logger.info(
            "drift_detector.run_complete",
            has_drift=has_drift,
            max_psi=round(max_psi, 4),
            min_ks_pvalue=round(min_ks_pvalue, 4),
            drifted_features=drifted,
        )
        return report

    def expose_prometheus(self, report: DriftReport) -> None:
        """Update module-level Prometheus gauges with the latest drift report.

        Args:
            report: DriftReport from the most recent run() call.
        """
        if not _GAUGES_AVAILABLE:
            return
        GAUGE_PSI_MAX.set(report.max_psi)
        GAUGE_KS_MAX_STAT.set(max((r.ks_stat for r in report.feature_results), default=0.0))
        GAUGE_KS_MIN_PVALUE.set(report.min_ks_pvalue)
        for result in report.feature_results:
            GAUGE_PSI_FEATURE.labels(feature=result.feature).set(result.psi)

    @staticmethod
    def _compute_psi(baseline: FeatureBaseline, prod_series: pd.Series) -> float:
        """Population Stability Index between baseline histogram and production.

        PSI = Σ (actual_pct - expected_pct) × ln(actual_pct / expected_pct)
        Uses the same bin edges as the training histogram.

        Args:
            baseline: FeatureBaseline with bins and hist.
            prod_series: Production values (NaN already dropped).

        Returns:
            PSI value ≥ 0. Higher = more diverged from training distribution.
        """
        bins = np.array(baseline.bins)
        # Extend edges slightly to capture out-of-range prod values in end bins
        bins[0] = min(bins[0], prod_series.min()) - 1e-6
        bins[-1] = max(bins[-1], prod_series.max()) + 1e-6

        hist_prod, _ = np.histogram(prod_series.values, bins=bins)
        total_prod = hist_prod.sum()
        if total_prod == 0:
            return 0.0
        hist_prod_norm = hist_prod / total_prod

        hist_base = np.array(baseline.hist)

        eps = 1e-10
        psi_terms = (hist_prod_norm - hist_base) * np.log((hist_prod_norm + eps) / (hist_base + eps))
        return float(max(psi_terms.sum(), 0.0))

    @staticmethod
    def _compute_ks(baseline: FeatureBaseline, prod_series: pd.Series) -> tuple[float, float]:
        """Two-sample KS test between stored training sample and production data.

        Uses the stored random subsample from the baseline for the training
        distribution (up to 500 values, sufficient for KS power at n≥30).

        Args:
            baseline: FeatureBaseline with sample field.
            prod_series: Production values (NaN already dropped).

        Returns:
            Tuple of (ks_statistic, p_value). p < 0.05 = significant shift.
        """
        baseline_sample = np.array(baseline.sample)
        prod_sample = prod_series.values
        stat, pvalue = ks_2samp(baseline_sample, prod_sample)
        return float(stat), float(pvalue)


# ── Baseline export ───────────────────────────────────────────────────────────


def export_baseline(output_path: Path | None = None) -> Path:
    """Read training features from DuckDB mart and write baseline JSON.

    Business Context:
        Called once after every model retrain to update the drift reference
        distribution. Co-versioned with churn_model.pkl in DVC.

    Args:
        output_path: Override for the output path.
                     Defaults to MODELS_DIR/churn_training_baseline.json.

    Returns:
        Path where the baseline was written.
    """
    out = output_path or (MODELS_DIR / BASELINE_FILENAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    logger.info("drift_baseline.export_start", output_path=str(out))

    with get_connection(read_only=True) as conn:
        df = conn.execute("SELECT * FROM marts.mart_customer_churn_features").df()

    logger.info("drift_baseline.data_loaded", n_rows=len(df))

    baseline: dict[str, dict[str, object]] = {}
    for feature in MONITORED_FEATURES:
        if feature not in df.columns:
            logger.warning("drift_baseline.feature_missing", feature=feature)
            continue
        series = df[feature].dropna().astype(float)
        if len(series) == 0:
            continue

        hist, bin_edges = np.histogram(series.values, bins=10)
        hist_norm = (hist / hist.sum()).tolist()

        # Store a reproducible subsample for KS testing
        rng = np.random.default_rng(42)
        idx = rng.choice(len(series), size=min(500, len(series)), replace=False)
        sample = series.iloc[idx].tolist()

        baseline[feature] = {
            "min": float(series.min()),
            "max": float(series.max()),
            "mean": float(series.mean()),
            "std": float(series.std()),
            "bins": bin_edges.tolist(),
            "hist": hist_norm,
            "sample": sample,
        }

    with open(out, "w") as f:
        json.dump(baseline, f, indent=2)

    logger.info("drift_baseline.export_complete", path=str(out), n_features=len(baseline))
    print(f"Drift baseline written to {out} ({len(baseline)} features)")
    return out


# ── CLI entry point ───────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SaaSGuard drift detector — PSI + KS test against training baseline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--export-baseline",
        action="store_true",
        help="Read DuckDB mart and export histogram baseline JSON",
    )
    group.add_argument(
        "--check",
        action="store_true",
        help="Run drift check and exit non-zero if thresholds exceeded",
    )
    parser.add_argument(
        "--threshold-psi",
        type=float,
        default=PSI_ALERT_THRESHOLD,
        help=f"PSI alert threshold (default {PSI_ALERT_THRESHOLD})",
    )
    parser.add_argument(
        "--threshold-ks-pvalue",
        type=float,
        default=KS_PVALUE_THRESHOLD,
        help=f"KS p-value threshold (default {KS_PVALUE_THRESHOLD})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("drift_report.json"),
        help="Output path for drift report JSON (--check mode only)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.export_baseline:
        export_baseline()
        sys.exit(0)

    if args.check:
        # Override module-level thresholds with CLI args
        psi_threshold = args.threshold_psi
        ks_threshold = args.threshold_ks_pvalue

        detector = DriftDetector()

        with get_connection(read_only=True) as conn:
            prod_df = conn.execute("SELECT * FROM marts.mart_customer_churn_features").df()

        report = detector.run(prod_df)

        # Write report JSON
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as fh:
            json.dump(report.to_dict(), fh, indent=2)

        print(json.dumps(report.to_dict(), indent=2))

        if report.max_psi > psi_threshold or report.min_ks_pvalue < ks_threshold:
            logger.critical(
                "drift_detector.alert",
                max_psi=round(report.max_psi, 4),
                min_ks_pvalue=round(report.min_ks_pvalue, 4),
                drifted_features=report.drifted_features,
            )
            sys.exit(1)

        logger.info("drift_detector.no_alert", max_psi=round(report.max_psi, 4))
        sys.exit(0)
