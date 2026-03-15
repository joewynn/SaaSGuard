# Architecture

SaaSGuard follows Domain-Driven Design (DDD) with a hexagonal (ports & adapters) structure. The domain layer has zero infrastructure dependencies.

## Domain Contexts

```mermaid
graph TB
    subgraph customer_domain["Customer Domain"]
        CE[Customer Entity]
        CV[PlanTier, MRR Value Objects]
        CR[CustomerRepository Interface]
    end

    subgraph usage_domain["Usage Domain"]
        UE[UsageEvent Entity]
        UV[FeatureAdoptionScore Value Object]
        UR[UsageRepository Interface]
    end

    subgraph prediction_domain["Prediction Domain"]
        CM[ChurnModelService]
        RM[RiskModelService]
        PE[PredictionResult Entity]
        PV[ChurnProbability, RiskScore Value Objects]
    end

    subgraph gtm_domain["GTM Domain"]
        OE[Opportunity Entity]
        GV[SalesStage Value Object]
        GR[OpportunityRepository Interface]
    end

    subgraph application["Application Layer"]
        PCS[PredictChurnUseCase]
        CRS[ComputeRiskScoreUseCase]
        CS[CustomerService]
    end

    subgraph infrastructure["Infrastructure Layer"]
        DB[(DuckDB)]
        DBT[dbt Models]
        API[FastAPI]
        ML[Model Registry .pkl]
        SUP[Apache Superset]
    end

    PCS --> CM
    PCS --> CE
    CRS --> RM
    CS --> CE
    CS --> UE

    CM --> PE
    RM --> PE

    CR --> DB
    UR --> DB
    GR --> DB
    DB --> DBT
    DBT --> SUP
    API --> PCS
    API --> CRS
    ML --> CM
    ML --> RM
```

## Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI as FastAPI (app/)
    participant UseCase as PredictChurnUseCase
    participant Domain as ChurnModelService
    participant Repo as CustomerRepository
    participant DB as DuckDB

    Client->>FastAPI: POST /predictions/churn {customer_id}
    FastAPI->>UseCase: execute(customer_id)
    UseCase->>Repo: get_by_id(customer_id)
    Repo->>DB: SELECT * FROM customers WHERE ...
    DB-->>Repo: CustomerRecord
    Repo-->>UseCase: Customer entity
    UseCase->>Domain: predict(customer)
    Domain-->>UseCase: PredictionResult
    UseCase-->>FastAPI: PredictionResult
    FastAPI-->>Client: 200 {churn_probability, risk_score, shap_values}
```

## Folder → Layer Mapping

| Folder | DDD Layer | Rule |
|---|---|---|
| `src/domain/` | Domain | No imports from infra or app. Pure Python. |
| `src/application/` | Application | Orchestrates domain objects. No DB calls. |
| `src/infrastructure/` | Infrastructure | Implements repository interfaces. DB/ML/HTTP. |
| `app/` | Delivery (API) | Thin layer. Calls application services only. |
| `dbt_project/` | Infrastructure | SQL transformations over DuckDB. |
