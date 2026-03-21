"""ExpansionGuardrailsService — three-gate LLM output validation for expansion briefs.

Three-layer defence:
  1. Feature name whitelist (Gate 1) — flag hallucinated snake_case signals;
     2+ flags → REJECTED
  2. Tone calibration (Gate 2) — strip urgency language when propensity < 0.50
  3. PII/jargon scrub (Gate 3) — remove UUIDs and ML terms from email_draft only;
     append watermark to ae_tactical_brief

Business Context: An AE acting on a hallucinated signal (fabricated feature name,
wrong propensity tier) in an outreach email destroys trust and may misrepresent
product capabilities. The three gates ensure every expansion brief delivered to
Sales is factually grounded and appropriately calibrated to actual propensity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from src.domain.ai_summary.guardrails_service import WATERMARK

# Domain-level whitelist of legitimate feature names the expansion model uses.
# Mirrors the keys of _FEATURE_LABELS in prompt_builder.py; defined here to
# keep the domain layer free of infrastructure imports.
# Update whenever the expansion feature set changes.
_EXPANSION_KNOWN_FEATURES: frozenset[str] = frozenset(
    [
        # Churn model features (may appear in joint briefs)
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
        "plan_tier",
        "industry",
        "is_early_stage",
        # Expansion-specific features
        "premium_feature_trials_30d",
        "feature_request_tickets_90d",
        "has_open_expansion_opp",
        "expansion_opp_amount",
        "mrr_tier_ceiling_pct",
    ]
)

# ML/model terms to scrub from email_draft (not from ae_tactical_brief).
EXPANSION_TECHNICAL_TERMS: frozenset[str] = frozenset(
    [
        "xgboost",
        "shap",
        "shap_impact",
        "lightgbm",
        "sklearn",
        "propensity_score",
        "model_version",
    ]
)

# Urgency phrases stripped from ae_tactical_brief when propensity < 0.50.
_URGENCY_PHRASES: list[str] = ["immediately", "urgent", "critical"]

# UUID pattern (case-insensitive, standard 8-4-4-4-12 format).
_UUID_PATTERN: re.Pattern[str] = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)

# Snake_case feature-name pattern (at least one underscore, all lowercase + digits).
_FEATURE_PATTERN: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+){1,}$")

# Confidence degrades 0.25 per Gate 1 flag.
_CONFIDENCE_PENALTY_PER_FLAG: float = 0.25

# Common safe compound words that match the snake_case pattern but are not ML features.
_SAFE_TOKENS: frozenset[str] = frozenset(
    [
        "plan_tier",
        "customer_id",
        "risk_tier",
        "churn_date",
        "sign_up",
        "follow_up",
        "well_known",
        "opt_in",
        "check_in",
        "log_in",
        "next_tier",
        "upgrade_date",
    ]
)


@dataclass(frozen=True)
class ExpansionGuardrailResult:
    """Result of ExpansionGuardrailsService.validate().

    Args:
        ae_tactical_brief: Brief with watermark appended (urgency stripped if applicable).
        email_draft: Scrubbed email draft, or None.
        guardrail_status: 'PASSED' / 'FLAGGED' / 'REJECTED' based on Gate 1 flags.
        fact_confidence: 1.0 − (0.25 × n_flags), floored at 0.0.
        flags: List of Gate 1 flag strings for audit logging.
    """

    ae_tactical_brief: str
    email_draft: str | None
    guardrail_status: Literal["PASSED", "FLAGGED", "REJECTED"]
    fact_confidence: float
    flags: list[str]


class ExpansionGuardrailsService:
    """Validates and transforms LLM output for expansion briefs.

    Business Context: Mirrors GuardrailsService for the churn domain but
    scoped to expansion signals. Gate 1 uses the expansion_result's actual
    top_features as the fact whitelist, preventing the LLM from referencing
    signals outside the model's output.

    Gate thresholds:
      - 0 flags → PASSED, confidence 1.0
      - 1 flag  → FLAGGED, confidence 0.75
      - 2+ flags → REJECTED, confidence ≤ 0.50
    """

    def validate(
        self,
        ae_tactical_brief: str,
        email_draft: str | None,
        expansion_result: object,
        propensity: float,
    ) -> ExpansionGuardrailResult:
        """Run all three gates and return the validated/transformed result.

        Business Context: Called by GenerateExpansionSummaryUseCase after every
        LLM call. Returns the final texts (with watermark and scrubbing) plus
        a result entity for audit logging and confidence scoring.

        Args:
            ae_tactical_brief: Raw LLM-generated AE brief.
            email_draft: Optional raw LLM-generated email draft (None for CSM).
            expansion_result: ExpansionResult entity (provides top_features whitelist).
            propensity: Calibrated upgrade propensity in [0, 1].

        Returns:
            ExpansionGuardrailResult with all transformations applied.
        """
        # Build the fact whitelist from the expansion result's actual features.
        top_feature_names: frozenset[str] = frozenset(
            f.feature_name for f in expansion_result.top_features  # type: ignore[attr-defined]
        )
        allowed_tokens: frozenset[str] = (
            top_feature_names | _EXPANSION_KNOWN_FEATURES | _SAFE_TOKENS
        )

        # ── Gate 1: hallucination detection ───────────────────────────────────
        flags: list[str] = []
        seen: set[str] = set()
        for token in ae_tactical_brief.split():
            clean = token.strip(".,;:!?()'\"")
            if (
                len(clean) >= 8
                and _FEATURE_PATTERN.match(clean)
                and clean not in allowed_tokens
                and clean not in seen
                and clean not in EXPANSION_TECHNICAL_TERMS
            ):
                flags.append(f"hallucinated_feature:{clean}")
                seen.add(clean)

        # Determine status from Gate 1 flags.
        if len(flags) >= 2:
            status: Literal["PASSED", "FLAGGED", "REJECTED"] = "REJECTED"
        elif len(flags) == 1:
            status = "FLAGGED"
        else:
            status = "PASSED"

        # ── Gate 2: tone calibration ───────────────────────────────────────────
        brief_body = ae_tactical_brief
        if propensity < 0.50:
            for phrase in _URGENCY_PHRASES:
                # Case-insensitive replacement — preserves surrounding text.
                brief_body = re.sub(
                    re.escape(phrase),
                    "",
                    brief_body,
                    flags=re.IGNORECASE,
                )
            # Collapse extra whitespace left by removals.
            brief_body = re.sub(r"  +", " ", brief_body).strip()

        # ── Gate 3: PII + jargon scrub (email_draft only) ────────────────────
        scrubbed_draft: str | None = None
        if email_draft is not None:
            scrubbed = _UUID_PATTERN.sub("[REDACTED]", email_draft)
            for term in EXPANSION_TECHNICAL_TERMS:
                scrubbed = re.sub(
                    r"\b" + re.escape(term) + r"\b",
                    "[REDACTED]",
                    scrubbed,
                    flags=re.IGNORECASE,
                )
            scrubbed_draft = scrubbed

        # Append watermark to ae_tactical_brief.
        final_brief = f"{brief_body}\n\n{WATERMARK}"

        # Confidence: 1.0 − (0.25 × n_flags), floored at 0.0.
        confidence = max(0.0, 1.0 - _CONFIDENCE_PENALTY_PER_FLAG * len(flags))

        return ExpansionGuardrailResult(
            ae_tactical_brief=final_brief,
            email_draft=scrubbed_draft,
            guardrail_status=status,
            fact_confidence=confidence,
            flags=flags,
        )
