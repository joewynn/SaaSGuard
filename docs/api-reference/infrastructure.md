# Infrastructure Layer

The infrastructure layer implements the repository interfaces defined in the domain layer. It is the only layer that touches DuckDB, pickle files, or external HTTP calls.

## DuckDB Adapter

::: src.infrastructure.db.duckdb_adapter

## Customer Repository (DuckDB)

::: src.infrastructure.repositories.customer_repository

## Usage Repository (DuckDB)

::: src.infrastructure.repositories.usage_repository

## Model Registry

::: src.infrastructure.ml.model_registry
