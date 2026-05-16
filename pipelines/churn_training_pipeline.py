# pipelines/churn_training_pipeline.py
"""
Churn model training pipeline.

This pipeline replaces the monolithic train_churn_model.py script.
Run it with:
    OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES python -m pipelines.churn_training_pipeline

Every run is logged to the ZenML server at https://zenml-server-77.up.railway.app/.
Metrics are attached via log_metadata() and visible in the dashboard.
The CHURN_MODEL entity links every artifact from this run to a named, versioned
model in the ZenML Model Control Plane.
"""

from zenml import pipeline
from zenml.logger import get_logger
from zenml.model.model import Model

from steps.churn_training_steps import (
    calibrate_model,
    compute_global_shap,
    evaluate_model,
    load_training_data,
    register_model_artifact,
    train_base_pipeline,
)
from steps.model_promotion_step import promote_model_if_passing

logger = get_logger(__name__)

CHURN_MODEL = Model(
    name="churn_model",
    tags=["xgboost", "calibrated", "churn"],
)


@pipeline(name="churn_training", enable_cache=True, model=CHURN_MODEL)
def churn_training_pipeline() -> None:
    """
    End-to-end churn model training DAG.

    Steps run in dependency order. ZenML automatically infers the DAG from
    the function signatures — a step that takes `base_pipeline` as input
    runs after the step that outputs `base_pipeline`.

    Caching is enabled: if you re-run and the DuckDB file hasn't changed,
    `load_training_data` returns its cached result instantly.

    The CHURN_MODEL entity links all artifacts from this run to a named model
    version in ZenML's Model Control Plane. promote_model_if_passing then
    transitions that version from staging → production if AUC >= 0.80.
    """
    X_train, X_test, y_train, y_test = load_training_data()

    base_pipeline = train_base_pipeline(X_train=X_train, y_train=y_train)

    calibrated_model = calibrate_model(
        base_pipeline=base_pipeline,
        X_train=X_train,
        y_train=y_train,
    )

    evaluation_metrics = evaluate_model(
        calibrated_model=calibrated_model,
        X_test=X_test,
        y_test=y_test,
    )

    shap_importances = compute_global_shap(
        base_pipeline=base_pipeline,
        X_train=X_train,
    )

    model_version = register_model_artifact(
        calibrated_model=calibrated_model,
        evaluation_metrics=evaluation_metrics,
        shap_importances=shap_importances,
    )

    promote_model_if_passing(
        evaluation_metrics=evaluation_metrics,
        model_version=model_version,
    )


if __name__ == "__main__":
    churn_training_pipeline()
