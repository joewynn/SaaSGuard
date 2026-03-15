# Prediction Domain

The `prediction_domain` bounded context contains the churn model, risk scoring, and SHAP explanation logic. It consumes entities from `customer_domain` and `usage_domain` but has no knowledge of infrastructure.

## Entities

::: src.domain.prediction.entities

## Value Objects

::: src.domain.prediction.value_objects

## Churn Model Service

::: src.domain.prediction.churn_model_service

## Risk Model Service

::: src.domain.prediction.risk_model_service
