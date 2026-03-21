"""TDD tests for feature engineering contracts.

Verifies two production-hardening changes:

P1-1  Day-Zero Imputation — days_since_last_event must never be 999 for a
      customer who has simply not used the product yet.  When total_events == 0
      the correct sentinel is tenure_days (account age), not an arbitrary 999
      that aliases new customers with heavily-lapsed ones.

P1-4  Activation Gate — integration_connects_first_30d ≥ 3 is a threshold
      effect, not a linear relationship (log-rank p < 0.001, 2.7× churn
      reduction).  activated_at_30d surfaces this as a first-class binary
      feature so SHAP attribution is unambiguous and CS playbooks can reference
      a yes/no milestone rather than a raw count.
"""

from __future__ import annotations

# ── Helpers that mirror the production computation rules ──────────────────────
# These functions capture the rule once; both the dbt SQL and the Python
# extractors must implement exactly this logic.


def compute_days_since_last_event(
    total_events: int, days_since_last_event_from_db: int | None, tenure_days: int
) -> int:
    """Smart imputation rule for days_since_last_event.

    If a customer has zero events the DB aggregation returns NULL (no MAX to
    DATEDIFF against).  The correct imputation is tenure_days — the customer
    has been inactive for exactly as long as they have existed.  Using 999 is
    wrong because:
      - It aliases new accounts (tenure_days ≤ 7) with severely lapsed ones.
      - XGBoost will assign the same tree-split path to both, inflating the
        churn score of every new customer on their first day.
    """
    if total_events == 0 or days_since_last_event_from_db is None:
        return tenure_days
    return days_since_last_event_from_db


def compute_activated_at_30d(integration_connects_first_30d: int) -> int:
    """Activation gate: True (1) if customer connected ≥ 3 integrations in first 30d.

    Threshold is derived from Phase 3 survival analysis: ≥ 3 integrations in
    the onboarding window produces a 2.7× churn rate reduction (log-rank
    p < 0.001).  Exposing this as a binary feature forces the model to weight
    the milestone independently of the raw count, and produces SHAP outputs
    that CS teams can act on directly ("Not Activated" vs. a count).
    """
    return 1 if integration_connects_first_30d >= 3 else 0


# ── P1-1: Day-Zero Imputation ─────────────────────────────────────────────────


class TestDayZeroImputation:
    """days_since_last_event must never be 999 for a new customer with zero events."""

    def test_new_customer_no_events_uses_tenure_days(self) -> None:
        """Brand-new customer on day 2 — recency = 2, not 999."""
        result = compute_days_since_last_event(total_events=0, days_since_last_event_from_db=None, tenure_days=2)
        assert result == 2

    def test_new_customer_one_week_no_events_uses_tenure_days(self) -> None:
        """One-week-old customer with no product activity — recency = 7."""
        result = compute_days_since_last_event(total_events=0, days_since_last_event_from_db=None, tenure_days=7)
        assert result == 7

    def test_lapsed_customer_no_events_uses_tenure_days(self) -> None:
        """180-day customer who never used the product — recency = 180 (correct)."""
        result = compute_days_since_last_event(total_events=0, days_since_last_event_from_db=None, tenure_days=180)
        assert result == 180

    def test_active_customer_uses_actual_recency(self) -> None:
        """Customer with recent activity uses the real days_since value."""
        result = compute_days_since_last_event(total_events=42, days_since_last_event_from_db=3, tenure_days=90)
        assert result == 3

    def test_active_customer_lapsed_uses_actual_recency(self) -> None:
        """Lapsed customer who previously had events uses the real lapse duration."""
        result = compute_days_since_last_event(total_events=15, days_since_last_event_from_db=45, tenure_days=120)
        assert result == 45

    def test_result_is_never_999_for_zero_event_customer(self) -> None:
        """No zero-event customer should ever receive the 999 sentinel."""
        for tenure_days in [1, 7, 30, 90, 365, 730]:
            result = compute_days_since_last_event(
                total_events=0, days_since_last_event_from_db=None, tenure_days=tenure_days
            )
            assert result != 999, f"days_since_last_event must not be 999 for tenure_days={tenure_days}"

    def test_zero_total_events_with_db_value_ignores_db_value(self) -> None:
        """Edge case: if total_events is 0, always use tenure_days regardless."""
        result = compute_days_since_last_event(total_events=0, days_since_last_event_from_db=999, tenure_days=5)
        assert result == 5


# ── P1-4: Activation Gate ─────────────────────────────────────────────────────


class TestActivationGate:
    """activated_at_30d binary flag — the ≥3 integration onboarding milestone."""

    def test_exactly_3_integrations_is_activated(self) -> None:
        """≥ 3 is the threshold — exactly 3 must produce activated = 1."""
        assert compute_activated_at_30d(3) == 1

    def test_4_integrations_is_activated(self) -> None:
        assert compute_activated_at_30d(4) == 1

    def test_10_integrations_is_activated(self) -> None:
        """High-integration customers are definitively activated."""
        assert compute_activated_at_30d(10) == 1

    def test_2_integrations_is_not_activated(self) -> None:
        """One below the threshold — not activated."""
        assert compute_activated_at_30d(2) == 0

    def test_1_integration_is_not_activated(self) -> None:
        assert compute_activated_at_30d(1) == 0

    def test_zero_integrations_is_not_activated(self) -> None:
        """No integrations — not activated."""
        assert compute_activated_at_30d(0) == 0

    def test_return_type_is_int(self) -> None:
        """activated_at_30d must be int (0 or 1) for sklearn OrdinalEncoder compatibility."""
        assert isinstance(compute_activated_at_30d(5), int)
        assert isinstance(compute_activated_at_30d(0), int)

    def test_only_binary_values_produced(self) -> None:
        """Exhaustive check — only 0 or 1 are valid outputs."""
        for n in range(0, 20):
            result = compute_activated_at_30d(n)
            assert result in (0, 1), f"Expected 0 or 1, got {result} for n={n}"
