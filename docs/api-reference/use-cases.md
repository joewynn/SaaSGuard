# Application Use Cases

The application layer orchestrates domain objects to fulfil business use cases. It has no knowledge of FastAPI, DuckDB, or pickle files — those are injected via the repository and model ports.

## Predict Churn

::: src.application.use_cases.predict_churn

## Compute Risk Score

::: src.application.use_cases.compute_risk_score

## Get Customer 360

::: src.application.use_cases.get_customer_360
