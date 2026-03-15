---
name: ddd-entity
description: Create or extend any bounded context in SaaSGuard following strict DDD. Produces value objects, entity, repository interface, and domain service in the correct folder. Always chains to /tdd-cycle after creation.
triggers: ["ddd", "entity", "bounded context", "domain model", "repository", "value object", "domain service", "new domain"]
version: 1.0.0
---

# DDD Entity Skill

**Prime directive:** The domain layer must contain zero infrastructure imports. All external dependencies are injected through abstract repository ports or service protocols.

---

## Workflow

### Step 1 — Identify Bounded Context
Determine which context this belongs to:

| Context | Folder | Owns |
|---|---|---|
| `customer_domain` | `src/domain/customer/` | Customer lifecycle, plan tiers, churn events |
| `usage_domain` | `src/domain/usage/` | Product events, feature adoption |
| `prediction_domain` | `src/domain/prediction/` | Churn model, risk score, SHAP explanations |
| `gtm_domain` | `src/domain/gtm/` | Sales opportunities, pipeline risk |

If the concept doesn't fit any existing context, propose a new bounded context and explain the rationale for the ADR.

### Step 2 — Output in Strict Order

**Always produce files in this sequence — never combine into one file:**

#### 2a. Value Objects (`value_objects.py`)
Rules:
- `@dataclass(frozen=True)` — immutable by definition
- `__post_init__` validates all invariants and raises `ValueError` with clear messages
- Named after domain concepts, not technical types (`MRR`, not `Decimal`)
- Include computed properties that express business rules (e.g. `is_low`, `revenue_at_risk`)
- Enums use `StrEnum` for JSON serializability

```python
@dataclass(frozen=True)
class ChurnProbability:
    """P(churn in next 90 days).

    Business Context:
        Calibrated probability output from XGBoost model.
        The 0.5 CS-trigger threshold should be validated quarterly
        against actual churn outcomes using a confusion matrix.
    """
    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"ChurnProbability must be in [0, 1], got {self.value}")
```

#### 2b. Entity (`entities.py`)
Rules:
- Identity via a `{name}_id` string field (UUID)
- Mutable state expressed through explicit business methods, not setters
- Business methods raise `ValueError` for invalid state transitions
- `@property` for derived attributes that involve business logic
- **No** `from src.infrastructure import ...` anywhere

```python
@dataclass
class Customer:
    """Core customer entity.

    Business Context:
        Central anchor for all churn and risk analysis.
        tenure_days is the time axis in survival analysis models.
    """
    customer_id: str
    ...

    def mark_churned(self, churn_date: date) -> None:
        """Record churn event. Raises ValueError if already churned."""
```

#### 2c. Repository Interface (`repository.py`)
Rules:
- `ABC` with `@abstractmethod` only — no implementation
- Method names express intent in domain language (`get_all_active`, not `select_where_churn_is_null`)
- Returns domain entities, never raw dicts or tuples
- Infrastructure implementation goes in `src/infrastructure/repositories/`

#### 2d. Domain Service (only if needed)
Create a domain service when an operation:
- Involves multiple entities from the same or different bounded contexts
- Doesn't naturally belong to a single entity
- Has no infrastructure dependency

If the logic belongs in an entity method instead, put it there and skip the service.

### Step 3 — Update Architecture Diagram
Add the new entity/service to `docs/architecture.md` Mermaid diagram. Keep the diagram current — it is the canonical reference for the bounded-context topology.

### Step 4 — Chain to /tdd-cycle
After producing all domain files, immediately say:

> "Domain files created. Chaining to /tdd-cycle — writing tests next."

Then follow the full TDD-Cycle skill for the new code.

### Step 5 — Update `__init__.py`
Export the new entity and repository interface from the context's `__init__.py`:
```python
from src.domain.customer.entities import Customer
from src.domain.customer.repository import CustomerRepository
__all__ = ["Customer", "CustomerRepository"]
```

---

## Anti-Patterns to Reject

| Anti-pattern | Correct approach |
|---|---|
| `import duckdb` in domain layer | Use repository interface |
| `import pickle` in domain layer | Use `ChurnModelPort` abstract class |
| `from fastapi import ...` in domain | FastAPI is delivery layer only |
| Mutable value objects | Use `@dataclass(frozen=True)` |
| Setters on entities | Use explicit business methods |
| Anemic models (data bags) | Business logic lives in entity/service methods |
