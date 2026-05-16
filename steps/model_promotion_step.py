# steps/model_promotion_step.py
"""
ZenML step that promotes a trained churn model to production if it passes
the AUC quality gate.

Business context: Without a promotion gate, any model — even a degraded one
retrained on drifted data — would silently overwrite the production artifact.
This step makes promotion explicit and auditable: every version in the ZenML
Model Control Plane has a stage (staging | production) and the metrics that
determined that stage are attached to the same model version record.
"""

from typing import Annotated

from zenml import get_step_context, log_metadata, step
from zenml.enums import ModelStages
from zenml.logger import get_logger

logger = get_logger(__name__)

MIN_ACCEPTABLE_AUC = 0.80


@step
def promote_model_if_passing(
    evaluation_metrics: dict,
    model_version: str,
) -> Annotated[bool, "promoted"]:
    """
    Promote the current model version to 'production' if AUC >= 0.80.

    Takes model_version as an explicit input to declare the dependency on
    register_model_artifact — ZenML will not run this step until registration
    is complete.

    The model handle comes from the step context rather than a Client lookup,
    so this step always acts on the model version produced by *this* pipeline run,
    not whatever is currently in the registry.

    Args:
        evaluation_metrics: Dict containing at least {"auc_roc": float}.
        model_version: Version string from register_model_artifact (creates DAG edge).

    Returns:
        True if the model was promoted to production, False if kept in staging.
    """
    auc = evaluation_metrics["auc_roc"]
    model = get_step_context().model

    if auc >= MIN_ACCEPTABLE_AUC:
        model.set_stage(stage=ModelStages.PRODUCTION, force=True)
        log_metadata({"stage": "production", "promoted": True, "auc_roc": auc})
        logger.info(
            "Model version %s promoted to PRODUCTION (AUC: %.4f >= %.2f threshold)",
            model_version,
            auc,
            MIN_ACCEPTABLE_AUC,
        )
        return True
    else:
        model.set_stage(stage=ModelStages.STAGING)
        log_metadata({"stage": "staging", "promoted": False, "auc_roc": auc})
        logger.warning(
            "Model version %s NOT promoted — AUC %.4f < %.2f threshold. Kept in staging.",
            model_version,
            auc,
            MIN_ACCEPTABLE_AUC,
        )
        return False
