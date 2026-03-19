"""Value objects for the Expansion domain.

UpgradePropensity: P(upgrade to next tier in 90 days), analogous to ChurnProbability.
TargetTier: Encapsulates tier-ladder logic and ARR uplift multipliers.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.customer.value_objects import PlanTier
from src.domain.prediction.value_objects import RiskTier


@dataclass(frozen=True)
class UpgradePropensity:
    """Calibrated P(upgrade to next plan tier within 90 days).

    Business Context: Analogous to ChurnProbability in the prediction domain.
    The 0.5 threshold separates accounts to actively pursue vs. nurture.
    Tier boundaries mirror ChurnProbability for consistent CS tooling language.
    """

    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"UpgradePropensity must be in [0, 1], got {self.value}")

    @property
    def tier(self) -> RiskTier:
        """Propensity tier — maps to RiskTier for consistent tooling language.

        Thresholds:
            CRITICAL  ≥ 0.75  — Immediate expansion outreach
            HIGH      ≥ 0.50  — Include in next QBR
            MEDIUM    ≥ 0.25  — Monitor, increase feature-adoption marketing
            LOW       < 0.25  — Maintain current service levels
        """
        if self.value >= 0.75:
            return RiskTier.CRITICAL
        if self.value >= 0.5:
            return RiskTier.HIGH
        if self.value >= 0.25:
            return RiskTier.MEDIUM
        return RiskTier.LOW


@dataclass(frozen=True)
class TargetTier:
    """Encapsulates the tier ladder and ARR uplift multipliers.

    Business Context: Determines what the next upgrade step is and how much
    net-new ARR that upgrade is worth (probability-weighted). Used by
    ExpansionResult.expected_arr_uplift to produce a defensible dollar figure
    for VP/Sales reviews — not a raw ACV, but a probability-weighted delta.

    Tier ladder:
        STARTER → GROWTH → ENTERPRISE → CUSTOM (seat/add-on expansion) → None
    """

    current_tier: PlanTier

    @property
    def next_tier(self) -> PlanTier | None:
        """The next plan tier in the upgrade sequence, or None at the ceiling."""
        mapping: dict[PlanTier, PlanTier | None] = {
            PlanTier.STARTER:    PlanTier.GROWTH,
            PlanTier.GROWTH:     PlanTier.ENTERPRISE,
            PlanTier.ENTERPRISE: PlanTier.CUSTOM,   # seat/add-on expansion, not full tier flip
            PlanTier.CUSTOM:     None,               # ceiling reached
        }
        return mapping.get(self.current_tier)

    @property
    def arr_uplift_multiplier(self) -> float:
        """MRR multiplier representing the target tier's typical ACV vs current ACV.

        Business Context: Multipliers derived from median ACV jumps observed between
        tiers. Enterprise → CUSTOM is 1.2× because growth at that tier comes from
        seat additions and add-on modules (Dash, Sign, AI), not a full tier change.
        """
        multipliers: dict[PlanTier, float] = {
            PlanTier.STARTER:    3.0,   # ~$1k → ~$3k MRR
            PlanTier.GROWTH:     5.0,   # ~$5k → ~$25k MRR
            PlanTier.ENTERPRISE: 1.2,   # seat/add-on upsell, not a tier flip
            PlanTier.CUSTOM:     0.0,   # no automated propensity above this
        }
        return multipliers.get(self.current_tier, 0.0)

    def calculate_expected_uplift(self, current_mrr: float, propensity: float) -> float:
        """Probability-weighted net annual revenue opportunity from this upgrade.

        Formula: (MRR × 12) × (multiplier - 1) × propensity

        Business Context: Uses (multiplier - 1) to capture only the *additional*
        revenue, not the full ACV. A 3× jump is a 200% increase — the net uplift
        is 2× current ARR, not 3×. This makes the dollar figure defensible in a
        VP Sales review where double-counting is closely scrutinised.

        Args:
            current_mrr: Customer's current Monthly Recurring Revenue (USD).
            propensity: UpgradePropensity.value — calibrated probability in [0, 1].

        Returns:
            Expected net ARR uplift in USD, rounded to 2 decimal places.
            Returns 0.0 if there is no higher tier or multiplier is zero.
        """
        if not self.next_tier or self.arr_uplift_multiplier == 0:
            return 0.0
        return round(current_mrr * 12 * max(0.0, self.arr_uplift_multiplier - 1) * propensity, 2)
