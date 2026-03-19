"""GuardrailsService – validates LLM output before returning to callers.

Three-layer defence:
  1. Feature name whitelist — reject summaries that mention made-up model features
  2. Probability accuracy — flag if stated probability deviates > 2pp from model output
  3. Watermark — always append human-in-loop annotation to every output

Business Context: In a CS context, a hallucinated summary (wrong probability,
invented feature name) could trigger the wrong intervention or erode trust with
CS teams. The guardrail layer ensures all LLM outputs are fact-grounded before
reaching customers-facing workflows.
"""

from __future__ import annotations

import re

from src.domain.ai_summary.entities import GuardrailResult, SummaryContext

# All legitimate feature names that can appear in model explanations.
# Any feature-like token in LLM output that is NOT in this set is flagged
# as a potential hallucination. Update when new features are added to the mart.
KNOWN_FEATURES: frozenset[str] = frozenset(
    [
        "events_last_30d",
        "avg_adoption_score",
        "days_since_last_event",
        "high_priority_tickets",
        "retention_signal_count",
        "integration_connects_first_30d",
        "mrr",
        "tenure_days",
        "total_events",
        "tickets_last_30d",
        "avg_resolution_hours",
        "events_last_7d",
        "is_early_stage",
        "plan_tier",
        "industry",
        "events_last_30d_by_type",
        "churn_probability",
        "risk_score",
        "risk_tier",
        "cohort_churn_rate",
        "compliance_gap_score",
        "vendor_risk_flags",
        "usage_decay_score",
        # Expansion-specific features
        "premium_feature_trials_30d",
        "feature_request_tickets_90d",
        "has_open_expansion_opp",
        "expansion_opp_amount",
        "mrr_tier_ceiling_pct",
    ]
)

WATERMARK = "⚠️ AI-generated. Requires human review."

# Confidence degrades 0.2 per flag
_CONFIDENCE_PENALTY_PER_FLAG = 0.2

# Probability tolerance: ±2 percentage points
_PROBABILITY_TOLERANCE_PP = 2.0


def _extract_percentage(text: str) -> float | None:
    """Extract the first percentage value from text, or None if not found.

    Handles patterns like "72%", "72.5%", "72 percent".
    """
    # Match patterns like "72%", "72.5%", "72 %"
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if match:
        return float(match.group(1))
    # Match "N percent"
    match = re.search(r"(\d+(?:\.\d+)?)\s+percent\b", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


class GuardrailsService:
    """Validates LLM output and appends the human-in-loop watermark.

    Business Context: The three validation layers (feature whitelist,
    probability accuracy, watermark) implement the ethical guardrails
    described in docs/ethical-guardrails.md. A confidence_score < 0.5
    should trigger human review before the summary is used.
    """

    def validate(
        self, raw_text: str, context: SummaryContext
    ) -> tuple[str, GuardrailResult]:
        """Validate raw LLM output and append the required watermark.

        Business Context: Called by GenerateExecutiveSummaryUseCase after
        every LLM call. Returns the final text (with watermark) and a
        GuardrailResult for audit logging and confidence scoring.

        Args:
            raw_text: The raw string returned by the LLM backend.
            context: The SummaryContext used to generate the text (for fact-checking).

        Returns:
            Tuple of (final_text_with_watermark, GuardrailResult).
        """
        flags: list[str] = []

        # 1. Check for hallucinated feature names
        # Scan for tokens that look like ML/feature engineering names:
        # snake_case compound words (≥2 parts, all lowercase + digits) that are
        # NOT in the KNOWN_FEATURES whitelist.
        # This catches both explicit suffix patterns (e.g. _score, _days) and
        # general feature-name patterns like "days_until_renewal".
        _FEATURE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+){1,}$")  # noqa: N806
        # Tokens that look like feature names but are safe (common English compounds)
        _SAFE_TOKENS: frozenset[str] = frozenset(  # noqa: N806
            ["plan_tier", "customer_id", "risk_tier", "churn_date", "sign_up",
             "follow_up", "well_known", "opt_in", "check_in", "log_in"]
        )
        seen_hallucinations: set[str] = set()
        tokens = raw_text.split()
        for token in tokens:
            clean_token = token.strip(".,;:!?()'\"")
            if (
                _FEATURE_PATTERN.match(clean_token)
                and clean_token not in KNOWN_FEATURES
                and clean_token not in _SAFE_TOKENS
                and clean_token not in seen_hallucinations
                and len(clean_token) >= 8  # avoid short words like "re_run"
            ):
                flags.append(f"hallucinated_feature:{clean_token}")
                seen_hallucinations.add(clean_token)

        # 2. Check probability accuracy
        stated_pct = _extract_percentage(raw_text)
        if stated_pct is not None:
            model_pct = context.prediction.churn_probability.value * 100
            if abs(stated_pct - model_pct) > _PROBABILITY_TOLERANCE_PP:
                flags.append("probability_mismatch")

        # 3. Append watermark
        final_text = f"{raw_text.strip()}\n\n{WATERMARK}"

        # Compute confidence: 1.0 degraded by 0.2 per flag, floored at 0.0
        confidence = max(0.0, 1.0 - _CONFIDENCE_PENALTY_PER_FLAG * len(flags))

        return final_text, GuardrailResult(
            passed=len(flags) == 0,
            flags=flags,
            confidence_score=confidence,
        )
