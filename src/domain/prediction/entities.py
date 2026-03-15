"""PredictionResult entity – output of the Prediction domain services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.prediction.value_objects import ChurnProbability, RiskScore


@dataclass
class ShapFeature:
    """A single SHAP feature contribution to a prediction.

    Provides model explainability for CS teams to understand why a
    customer was flagged, enabling targeted interventions.
    """

    feature_name: str
    feature_value: float
    shap_impact: float  # Positive = increases churn risk


@dataclass
class PredictionResult:
    """The complete output of a churn + risk prediction for one customer.

    Args:
        customer_id: The customer this prediction belongs to.
        churn_probability: Calibrated P(churn in 90 days).
        risk_score: Composite compliance/usage risk score.
        top_shap_features: Top-N SHAP drivers (sorted by |shap_impact|).
        model_version: Semantic version of the model artifact used.
        predicted_at: UTC timestamp of when the prediction was generated.
    """

    customer_id: str
    churn_probability: ChurnProbability
    risk_score: RiskScore
    top_shap_features: list[ShapFeature] = field(default_factory=list)
    model_version: str = "0.0.0"
    predicted_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def recommended_action(self) -> str:
        """Natural-language CS recommendation based on prediction outputs.

        This is a deterministic rule — LLM summaries build on top of this
        in the AI/LLM layer (Phase 5).
        """
        if self.churn_probability.value >= 0.75:
            return "CRITICAL – Escalate to senior CSM immediately. Schedule EBR within 7 days."
        if self.churn_probability.value >= 0.5:
            return "HIGH RISK – Trigger CS outreach within 48 hours. Review top SHAP drivers."
        if self.churn_probability.value >= 0.25:
            return "MEDIUM RISK – Add to CSM watch list. Schedule check-in call."
        return "LOW RISK – No immediate action required. Monitor monthly."
