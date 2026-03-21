"""ExpansionResult entity — output of the Expansion domain services.

Symmetric mirror of PredictionResult in the prediction domain.
Immutable (frozen=True) because results are computed once at inference time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.customer.value_objects import PlanTier
from src.domain.expansion.value_objects import TargetTier, UpgradePropensity
from src.domain.prediction.entities import ShapFeature
from src.domain.prediction.value_objects import RiskTier


@dataclass(frozen=True)
class ExpansionResult:
    """The complete output of an expansion propensity prediction for one customer.

    Business Context: Pairs with PredictionResult to form the full NRR lifecycle
    view — Retain (churn) + Expand (upgrade). The expected_arr_uplift property
    produces a probability-weighted dollar figure for VP/Sales prioritisation.

    Args:
        customer_id: The customer this prediction belongs to.
        current_mrr: Customer's current MRR at prediction time (USD).
        propensity: Calibrated P(upgrade to next tier within 90 days).
        target: TargetTier encapsulating next step and uplift multiplier.
        top_features: Top SHAP drivers sorted by |shap_impact| descending.
        model_version: Semantic version of the expansion model artifact.
        predicted_at: UTC timestamp of when the prediction was generated.
    """

    customer_id: str
    current_mrr: float
    propensity: UpgradePropensity
    target: TargetTier
    top_features: list[ShapFeature] = field(default_factory=list)
    model_version: str = "1.0.0"
    predicted_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def expected_arr_uplift(self) -> float:
        """Probability-weighted net annual revenue opportunity from this upgrade.

        Business Context: Delegates to TargetTier.calculate_expected_uplift()
        to avoid duplicating the (MRR × 12 × (multiplier - 1) × propensity)
        formula. This property is the primary input for Sales prioritisation:
        sort the expansion list by expected_arr_uplift DESC to find accounts
        with the highest ROI on an upgrade conversation.

        Returns:
            Expected net ARR uplift in USD.
        """
        return self.target.calculate_expected_uplift(
            current_mrr=self.current_mrr,
            propensity=self.propensity.value,
        )

    @property
    def is_high_value_target(self) -> bool:
        """True if this account warrants Senior AE (or CSM) attention.

        Business Context: A $50 ARR uplift at 85% propensity is not worth a
        Senior AE's time. This property separates 'interesting signal' from
        'actionable Sales motion' — resource allocation logic baked into the
        domain, not the dashboard filters. Threshold: > $10k expected uplift
        AND propensity tier is High or Critical.

        FREE-tier override: free-to-paid max uplift is $6k (below the $10k
        threshold), so free-tier customers at CRITICAL propensity (≥0.75)
        always return True — the conversion event is high-priority regardless.

        Returns:
            True if the account should be escalated for active outreach.
        """
        if (
            self.target.current_tier == PlanTier.FREE
            and self.propensity.tier == RiskTier.CRITICAL
        ):
            return True
        return (
            self.expected_arr_uplift > 10_000
            and self.propensity.tier in (RiskTier.HIGH, RiskTier.CRITICAL)
        )

    def recommended_action(self, churn_probability: float | None = None) -> str:
        """Deterministic GTM playbook routing based on propensity tier.

        Business Context: When both churn probability and expansion propensity
        are available, the conflict matrix resolves the correct CS motion.
        High Churn + High Expansion = 'Flight Risk' — upselling a churning
        customer accelerates churn rather than preventing it.

        Args:
            churn_probability: Optional churn probability from PredictionResult.
                               When provided, enables conflict-matrix resolution.

        Returns:
            Human-readable action string for CS/Sales tooling.
        """
        next_plan = self.target.next_tier.value.upper() if self.target.next_tier else "UPSELL"

        # Conflict matrix: when both scores are available, churn risk takes precedence
        if churn_probability is not None:
            high_churn = churn_probability >= 0.50
            high_expansion = self.propensity.value >= 0.50
            if not high_churn and high_expansion:
                return (
                    f"Growth Engine — schedule {next_plan} upgrade conversation. "
                    f"Expected ARR uplift: ${self.expected_arr_uplift:,.0f}."
                )
            if high_churn and high_expansion:
                return (
                    f"Flight Risk — Senior Exec intervention required before any "
                    f"upsell motion. Restore health first, then revisit {next_plan} migration."
                )
            if high_churn and not high_expansion:
                return "Retention priority — defer expansion until account health is restored."
            return "Stable base — nurture via product-led expansion signals."

        # Single-score routing (no churn context)
        if self.propensity.tier == RiskTier.CRITICAL:
            return (
                f"EXPANSION PRIORITY: High intent detected. "
                f"Immediate outreach for {next_plan} migration."
            )
        if self.propensity.tier == RiskTier.HIGH:
            return (
                f"NURTURE: Strong usage signals. "
                f"Highlight {next_plan} features in next QBR."
            )
        if self.propensity.tier == RiskTier.MEDIUM:
            return "MONITOR: Early signals detected. Increase feature-adoption marketing."
        return "STABLE: Maintain current service levels."

    def to_summary_context(self) -> dict[str, object]:
        """Produces a verified, grounded-facts dict for the LLM PromptBuilder.

        Business Context: Only surfaces confirmed model outputs to the LLM.
        This is the 'clean hands' hallucination guardrail — the model can only
        fabricate facts we explicitly passed to it, not invent new signals.

        Returns:
            Dict of scalar values safe to inject into a prompt [CONTEXT] block.
        """
        return {
            "customer_id": self.customer_id,
            "propensity_score": f"{self.propensity.value:.2%}",
            "propensity_tier": self.propensity.tier.value,
            "expected_uplift": f"${self.expected_arr_uplift:,.2f}",
            "target_tier": self.target.next_tier.value if self.target.next_tier else "N/A",
            "top_signals": [f.feature_name for f in self.top_features[:3]],
        }
