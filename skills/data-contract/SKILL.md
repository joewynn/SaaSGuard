---
name: data-contract
description: Define, validate, and enforce data contracts between producers and consumers in SaaSGuard. Generates dbt schema tests, Pydantic input validation, data quality checks, and documents SLA/freshness expectations. Critical for production-grade data pipelines.
triggers: ["data contract", "schema test", "data quality", "validate data", "data sla", "dbt test", "data expectations", "data validation", "null check", "data freshness"]
version: 1.0.0
---

# Data Contract Skill

**Prime directive:** The churn model is only as good as the data feeding it. A silent data quality failure is worse than a loud one. Every table has a contract; every contract has tests; every test runs in CI.

---

## What Is a Data Contract Here?
A data contract specifies:
1. **Schema** — column names, types, nullable/required
2. **Quality rules** — uniqueness, accepted values, referential integrity
3. **Freshness SLA** — how stale data is allowed to be before alerting
4. **Business rules** — domain-specific constraints (e.g., MRR ≥ 0, churn_date > signup_date)

---

## Workflow

### Step 1 — Identify the Consumer and Producer
For each contract being created, name:
- **Producer:** script that writes the data (e.g., `generate_synthetic_data.py`, upstream CRM)
- **Consumer:** dbt model or ML feature extractor that reads it
- **Failure impact:** what breaks if the contract is violated (e.g., "feature extractor produces NaN features → model returns garbage predictions")

### Step 2 — Generate `dbt_project/models/schema.yml`

For every source table and mart model, define:

```yaml
version: 2

sources:
  - name: raw
    description: "Synthetic raw data loaded from data/raw/ CSVs"
    freshness:
      warn_after: {count: 24, period: hour}
      error_after: {count: 48, period: hour}
    loaded_at_field: _loaded_at
    tables:
      - name: customers
        description: "One row per B2B SaaS customer account"
        columns:
          - name: customer_id
            description: "UUID primary key"
            tests:
              - unique
              - not_null
          - name: plan_tier
            tests:
              - not_null
              - accepted_values:
                  values: ["starter", "growth", "enterprise"]
          - name: mrr
            tests:
              - not_null
              - dbt_utils.expression_is_true:
                  expression: "mrr >= 0"
          - name: churn_date
            tests:
              - dbt_utils.expression_is_true:
                  expression: "churn_date > signup_date OR churn_date IS NULL"
                  name: churn_date_after_signup_date
```

### Step 3 — Generate Pydantic Validation Models
For every API input and ML pipeline input, define a Pydantic model:

```python
from pydantic import BaseModel, Field, field_validator
from datetime import date
from decimal import Decimal

class CustomerRecord(BaseModel):
    """Input validation contract for raw customer data.

    Business Context:
        Validates data at the boundary between raw CSVs and the DuckDB warehouse.
        Fails loud — any violation raises a ValidationError before loading.
    """
    customer_id: str = Field(..., pattern=r"^[0-9a-f-]{36}$", description="UUID")
    plan_tier: Literal["starter", "growth", "enterprise"]
    mrr: Decimal = Field(..., ge=Decimal("0"), description="Monthly Recurring Revenue ≥ 0")
    signup_date: date
    churn_date: date | None = None

    @field_validator("churn_date")
    @classmethod
    def churn_after_signup(cls, v: date | None, info: ValidationInfo) -> date | None:
        if v is not None and "signup_date" in info.data:
            if v <= info.data["signup_date"]:
                raise ValueError("churn_date must be after signup_date")
        return v
```

### Step 4 — Write pytest Data Quality Tests
```python
# tests/integration/test_data_contracts.py

class TestCustomerDataContract:
    def test_customer_ids_are_unique(self, duckdb_conn) -> None:
        result = duckdb_conn.execute(
            "SELECT COUNT(*) != COUNT(DISTINCT customer_id) FROM customers"
        ).fetchone()[0]
        assert not result, "Duplicate customer_ids found"

    def test_mrr_is_non_negative(self, duckdb_conn) -> None:
        count = duckdb_conn.execute(
            "SELECT COUNT(*) FROM customers WHERE mrr < 0"
        ).fetchone()[0]
        assert count == 0, f"{count} customers have negative MRR"

    def test_churn_date_after_signup_date(self, duckdb_conn) -> None:
        count = duckdb_conn.execute(
            "SELECT COUNT(*) FROM customers WHERE churn_date <= signup_date"
        ).fetchone()[0]
        assert count == 0, "churn_date must be after signup_date"

    def test_feature_adoption_score_in_valid_range(self, duckdb_conn) -> None:
        count = duckdb_conn.execute(
            "SELECT COUNT(*) FROM usage_events WHERE feature_adoption_score NOT BETWEEN 0 AND 1"
        ).fetchone()[0]
        assert count == 0
```

### Step 5 — Define Freshness SLA
Document in `docs/data-dictionary.md` under each table:

| Table | Max acceptable staleness | Alert channel |
|---|---|---|
| `customers` | 24 hours | dbt freshness check |
| `usage_events` | 1 hour | dbt freshness check |
| `risk_signals` | 48 hours | dbt freshness check |
| Model predictions | 24 hours | Prometheus alert |

### Step 6 — Update CHANGELOG and Docs
```markdown
# CHANGELOG entry
### Added
- Data contract for `customers` table: uniqueness + MRR ≥ 0 + churn_date invariant
- Pydantic `CustomerRecord` validation model at data ingestion boundary
- dbt freshness checks: 24h warn, 48h error for all raw tables
```

---

## Contract Violation Response Protocol

| Severity | Example | Response |
|---|---|---|
| Schema mismatch | Column renamed upstream | Block pipeline, alert data engineer |
| Null constraint | `customer_id` = NULL | Quarantine row, log + alert |
| Business rule | MRR < 0 | Reject row, increment `data_quality_errors` Prometheus counter |
| Freshness breach | Data > 48h stale | Pause model scoring, alert on-call |

---

## Output Format
```
## Data Contract: {table_name}

### Schema Tests (add to schema.yml)
[yaml block]

### Pydantic Validation Model
[python code]

### pytest Data Quality Tests
[python code]

### Freshness SLA
[table]

### CHANGELOG entry
[markdown]
```
