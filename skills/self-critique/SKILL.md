---
name: self-critique
description: Force a structured review of the last output before handing it to the user. Checks for correctness, completeness, DDD/TDD compliance, docs quality, security issues, and business storytelling gaps. Run after any significant output.
triggers: ["self critique", "review output", "check your work", "critique this", "review last response", "quality check", "before we commit"]
version: 1.1.0
---

# Self-Critique Skill

**Prime directive:** Output nothing to the user until this review is complete. If issues are found, fix them first.

---

## Critique Dimensions

Run through every dimension. Score each: ✅ Pass | ⚠️ Needs improvement | ❌ Fail.

---

### Dimension 1: Correctness

| Check | Pass criteria |
|---|---|
| Python syntax | Code runs without SyntaxError |
| Type annotations | All public functions have return type + parameter types |
| Import paths | All `from src.domain.xxx import` paths exist in the repo structure |
| No hallucinated modules | Every imported package is in `pyproject.toml` |
| Business logic | Domain rules match the Project Brain (schema, thresholds, weights) |
| DuckDB SQL | SQL is valid DuckDB dialect (not Postgres-specific syntax) |

**Red flags:** Any `import` that doesn't map to a real file. Any column name not in the data dictionary. Any threshold or weight not matching the Brain.

---

### Dimension 2: DDD Compliance

| Check | Pass criteria |
|---|---|
| Domain purity | No `import duckdb`, `import fastapi`, `import pickle` in `src/domain/` |
| Value object immutability | All VOs use `@dataclass(frozen=True)` |
| Entity identity | Entities have an `{name}_id` field as the identity |
| Repository is abstract | Repository classes use `ABC` + `@abstractmethod` only |
| Business logic location | Logic is in entities/services, not in FastAPI routers or infrastructure |
| Ubiquitous language | Variable/method names match domain terminology, not DB column names |

---

### Dimension 3: TDD Compliance

| Check | Pass criteria |
|---|---|
| Tests exist | Every new public function/class has a corresponding test |
| Tests written before implementation | (Verify from conversation history or ask user) |
| Edge cases covered | Boundary values, invalid inputs, state transitions tested |
| Property-based tests | At least one `@given` for any value object with numeric constraints |
| Coverage estimate | New code achieves ≥85% estimated line coverage |
| No implementation in test files | Tests use fakes/stubs, not real infrastructure |

---

### Dimension 4: Documentation Quality

| Check | Pass criteria |
|---|---|
| Google-style docstring | Every public function/class has one |
| Business Context section | Present in all domain service methods |
| Args / Returns / Raises | All populated correctly |
| mkdocs nav updated | New page added to `mkdocs.yml` nav |
| CHANGELOG.md updated | Entry written for this change |
| ADR updated | If an architectural decision was made, ADR exists or was updated |

---

### Dimension 5: Security

| Check | Pass criteria |
|---|---|
| No hardcoded secrets | No API keys, passwords, or tokens in code |
| No SQL injection risk | All DuckDB queries use parameterised `?` placeholders |
| No `pickle.loads` on untrusted input | Model loading only from trusted local paths |
| No `eval()` or `exec()` | Not present |
| `.env` not in output | Never include `.env` content in generated code |
| Non-root Docker user | `prod` Dockerfile stage runs as `saasguard` user |

---

### Dimension 6: Business Storytelling (for Phase outputs and exec content)

| Check | Pass criteria |
|---|---|
| Leads with business impact | Revenue, risk, or competitive advantage stated first |
| ROI quantified | Tied to $2M / 1% churn reduction frame |
| No raw metrics to executives | AUC/F1 translated to plain-English business outcomes |
| Call-to-action specific | Who does what by when |
| LLM guardrail present | Any AI-generated customer text has `⚠️ AI-generated. Requires human review.` |

---

### Dimension 7: Completeness

| Check | Pass criteria |
|---|---|
| No TODOs in output | No `# TODO`, `# placeholder`, or `pass` in deliverable code |
| No skeleton files | Every file has real, functional content |
| Phase deliverable list | All items from `phase-advance` checklist are present |
| Dependencies declared | Any new package added to `pyproject.toml` |

---

### Dimension 8: ML Model Safety

**Required whenever any of these files were touched:** `xgboost_*.py`, `train_*.py`, `_FEATURE_ORDER` constants, dbt mart models that feed ML training.

| Check | Pass criteria |
|---|---|
| `_FEATURE_ORDER` sync | `_FEATURE_ORDER` in each model class exactly matches `ALL_FEATURES` in its training script — count AND order |
| No-mock inference test exists | `tests/integration/test_model_inference.py` has a test for every modified model that calls real `predict_proba()` with a complete feature dict |
| `explain()` SHAP length test exists | Integration test asserts `len(shap_features) == len(_FEATURE_ORDER)` — catches stale pkl files |
| Models retrained after constant change | If `_FEATURE_ORDER` was modified, `uv run python -m src.infrastructure.ml.train_*` was run and new `.pkl` files exist |
| Smoke test covers prediction endpoints | CI smoke test (or manual check) hits `GET /customers/:id` and `POST /summaries/expansion` — not just `/health` and `/ready` |

**Red flag:** Any unit test that mocks the model and feature extractor for an inference path. Mocked tests **cannot** catch `"columns are missing"` errors. Integration tests with real pkl files are required.

**The production failure pattern:** Training script adds column X → dbt mart includes X → pkl is trained with X → `_FEATURE_ORDER` NOT updated → inference DataFrame missing X → XGBoost raises `"columns are missing: {'X'}"`. This bug is invisible to all unit tests and only surfaces at inference time in production.

---

## Output Format

```
## Self-Critique Report

### Dimension 1: Correctness    [✅/⚠️/❌]
[Issue found / nothing to report]

### Dimension 2: DDD Compliance [✅/⚠️/❌]
[Issue found / nothing to report]

### Dimension 3: TDD Compliance [✅/⚠️/❌]
[Issue found / nothing to report]

### Dimension 4: Documentation  [✅/⚠️/❌]
[Issue found / nothing to report]

### Dimension 5: Security       [✅/⚠️/❌]
[Issue found / nothing to report]

### Dimension 6: Business Story [✅/⚠️/❌]  (N/A for pure code)
[Issue found / nothing to report]

### Dimension 7: Completeness   [✅/⚠️/❌]
[Issue found / nothing to report]

### Dimension 8: ML Model Safety [✅/⚠️/❌]  (N/A if no ML files touched)
[Issue found / nothing to report]

---
Overall: [PASS – ready to hand off] | [FIX REQUIRED – see issues above]
```

If any dimension is ❌, fix the issue **before** showing the corrected output to the user. Do not show the failed version and the fix separately — show only the corrected final output with the critique report prepended.
