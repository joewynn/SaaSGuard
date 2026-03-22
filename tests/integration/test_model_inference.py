"""Integration tests: real feature dict → real _to_dataframe() → real XGBoost predict_proba().

These tests exercise the full inference path with no mocks. They would have caught the
production "columns are missing" errors immediately — the bug was that _FEATURE_ORDER
constants were stale and did not include activated_at_30d / feature_limit_hit_30d.
"""

from __future__ import annotations

import pytest

from src.infrastructure.ml.xgboost_churn_model import XGBoostChurnModel
from src.infrastructure.ml.xgboost_expansion_model import XGBoostExpansionModel

# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

_BASE_FEATURES: dict[str, float | str] = {
    "mrr": 1200.0,
    "tenure_days": 180.0,
    "total_events": 450.0,
    "events_last_30d": 40.0,
    "events_last_7d": 10.0,
    "avg_adoption_score": 0.65,
    "days_since_last_event": 3.0,
    "retention_signal_count": 5.0,
    "integration_connects_first_30d": 2.0,
    "activated_at_30d": 1.0,
    "tickets_last_30d": 1.0,
    "high_priority_tickets": 0.0,
    "avg_resolution_hours": 8.0,
    "is_early_stage": 0.0,
    "plan_tier": "professional",
    "industry": "technology",
}

_EXPANSION_EXTRA_FEATURES: dict[str, float | str] = {
    "premium_feature_trials_30d": 3.0,
    "feature_request_tickets_90d": 2.0,
    "has_open_expansion_opp": 0.0,
    "expansion_opp_amount": 0.0,
    "mrr_tier_ceiling_pct": 0.72,
    "feature_limit_hit_30d": 1.0,
}


# ---------------------------------------------------------------------------
# Churn model inference
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_churn_model_accepts_full_feature_dict() -> None:
    """Real XGBoostChurnModel.predict_proba() must accept all 16 features including activated_at_30d.

    Business Context: This test exercises the full inference path — no mocks.
    It would have caught the production bug where activated_at_30d was missing
    from _FEATURE_ORDER, causing XGBoost to raise "columns are missing".
    """
    model = XGBoostChurnModel()
    prob = model.predict_proba(_BASE_FEATURES)
    assert 0.0 <= prob <= 1.0, f"Expected probability in [0, 1], got {prob}"


@pytest.mark.integration
def test_churn_model_explain_returns_all_features() -> None:
    """SHAP explain() must return one ShapFeature per entry in _FEATURE_ORDER."""
    from src.infrastructure.ml.xgboost_churn_model import _FEATURE_ORDER

    model = XGBoostChurnModel()
    shap_features = model.explain(_BASE_FEATURES)
    assert len(shap_features) == len(_FEATURE_ORDER)
    names = [sf.feature_name for sf in shap_features]
    assert "activated_at_30d" in names


# ---------------------------------------------------------------------------
# Expansion model inference
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_expansion_model_accepts_full_feature_dict() -> None:
    """Real XGBoostExpansionModel.predict_proba() must accept all 21 features.

    Business Context: This test exercises the full inference path — no mocks.
    It would have caught the production bug where activated_at_30d and
    feature_limit_hit_30d were missing from _EXPANSION_FEATURE_ORDER.
    """
    model = XGBoostExpansionModel()
    features = {**_BASE_FEATURES, **_EXPANSION_EXTRA_FEATURES}
    prob = model.predict_proba(features)
    assert 0.0 <= prob <= 1.0, f"Expected probability in [0, 1], got {prob}"


@pytest.mark.integration
def test_expansion_model_explain_returns_all_features() -> None:
    """SHAP explain() must return one ShapFeature per entry in _EXPANSION_FEATURE_ORDER (22 total)."""
    from src.infrastructure.ml.xgboost_expansion_model import _EXPANSION_FEATURE_ORDER

    model = XGBoostExpansionModel()
    features = {**_BASE_FEATURES, **_EXPANSION_EXTRA_FEATURES}
    shap_features = model.explain(features)
    assert len(shap_features) == len(_EXPANSION_FEATURE_ORDER)
    names = [sf.feature_name for sf in shap_features]
    assert "activated_at_30d" in names
    assert "feature_limit_hit_30d" in names
