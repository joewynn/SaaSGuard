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

    subgraph ai_summary_domain["AI Summary Domain – Phase 5"]
        SP[SummaryPort ABC]
        GS[GuardrailsService]
        ESE[ExecutiveSummary Entity]
        SC[SummaryContext]
    end

    subgraph application["Application Layer"]
        PCS[PredictChurnUseCase]
        CRS[ComputeRiskScoreUseCase]
        GESC[GenerateExecutiveSummaryUseCase]
        AQU[AskCustomerQuestionUseCase]
    end

    subgraph infrastructure["Infrastructure Layer"]
        DB[(DuckDB)]
        DBT[dbt Models\nmart_churn_features\nmart_risk_scores]
        API[FastAPI\n/predictions\n/summaries]
        ML[Model Registry .pkl]
        LLM[LLM Adapters\nGroq / Ollama]
        SUP[Apache Superset\n4 Dashboards]
    end

    PCS --> CM
    PCS --> CE
    CRS --> RM
    GESC --> PCS
    GESC --> CE
    GESC --> SP
    GESC --> GS
    AQU --> PCS
    AQU --> SP

    CM --> PE
    RM --> PE
    SP --> LLM
    GS --> ESE
    SC --> CE
    SC --> PE

    CR --> DB
    UR --> DB
    GR --> DB
    DB --> DBT
    DBT --> SUP
    API --> PCS
    API --> CRS
    API --> GESC
    API --> AQU
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

## AI Summary Request Flow (Phase 5)

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI as FastAPI (app/)
    participant UC as GenerateExecutiveSummaryUseCase
    participant Predict as PredictChurnUseCase
    participant LLM as SummaryPort (Groq/Ollama)
    participant Guard as GuardrailsService
    participant DB as DuckDB

    Client->>FastAPI: POST /summaries/customer {customer_id, audience}
    FastAPI->>UC: execute(customer_id, audience)
    UC->>DB: get_by_id(customer_id)
    UC->>Predict: execute(customer_id)
    Predict-->>UC: PredictionResult + SHAP features
    UC->>DB: fetch events, tickets, GTM context
    UC->>LLM: generate(SummaryContext, audience)
    LLM-->>UC: raw narrative
    UC->>Guard: validate(raw_text, context)
    Guard-->>UC: (final_text + watermark, GuardrailResult)
    UC-->>FastAPI: ExecutiveSummary entity
    FastAPI-->>Client: 200 {summary, churn_probability, confidence_score, guardrail_flags}
```

## Folder → Layer Mapping

| Folder | DDD Layer | Rule |
|---|---|---|
| `src/domain/` | Domain | No imports from infra or app. Pure Python. |
| `src/application/` | Application | Orchestrates domain objects. No DB calls. |
| `src/infrastructure/` | Infrastructure | Implements repository interfaces. DB/ML/HTTP. |
| `app/` | Delivery (API) | Thin layer. Calls application services only. |
| `dbt_project/` | Infrastructure | SQL transformations over DuckDB. |
