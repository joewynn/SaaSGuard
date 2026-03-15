---
name: tdd-cycle
description: Enforce strict Red-Green-Refactor TDD for any new domain entity, service, use case, or model in SaaSGuard. Always writes tests before implementation. Enforces 85%+ coverage, pytest + hypothesis, Google-style docstrings.
triggers: ["tdd", "test first", "write tests", "unit test", "add tests", "new entity test", "new service test"]
version: 1.0.0
---

# TDD Cycle Skill

**Prime directive:** No implementation code is written before failing tests exist. Every output from this skill follows Red → Green → Refactor.

---

## Workflow (never skip a step)

### Step 1 — Explore
Before writing anything, read:
- The existing test structure in `tests/unit/` or `tests/integration/` for the relevant domain
- The target module in `src/domain/` or `src/application/` if it already exists
- `tests/conftest.py` for existing shared fixtures

Output a one-line summary: *"Existing tests: X. New tests to write: Y. Coverage gap: Z."*

### Step 2 — Design Tests First
Output **only** the complete test file. Do not write any implementation yet.

Test file conventions:
- Location: `tests/unit/domain/test_{entity_name}.py` or `tests/unit/application/test_{use_case}.py`
- Class per logical group: `class TestMRR`, `class TestCustomerEntity`, etc.
- Name every test: `test_{what}_{condition}_{expected_outcome}`
- Include at least:
  - Happy path tests
  - Boundary / edge case tests
  - Invariant violation tests (should raise `ValueError`)
  - At least one `@given` property-based test using `hypothesis` where applicable
- Use fixtures from `conftest.py`; add new fixtures to `conftest.py` if reusable

```python
# Example test structure
class TestChurnProbability:
    def test_valid_probability_is_stored(self) -> None: ...
    def test_above_one_raises_value_error(self) -> None: ...
    def test_below_zero_raises_value_error(self) -> None: ...
    def test_risk_tier_critical_above_075(self) -> None: ...

    @given(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    def test_any_valid_float_always_accepted(self, value: float) -> None: ...
```

Announce: **"Tests written. Run `pytest tests/unit/... -v` and share the output."**

### Step 3 — Confirm Red (tests fail)
Wait for the user to run pytest and share output.
Confirm all new tests fail with `ModuleNotFoundError` or `AttributeError` (not implementation errors).
If any test passes unexpectedly, investigate before continuing.

### Step 4 — Implement (minimal passing code)
Write the minimal implementation to make all tests pass. Do not over-engineer.

Implementation conventions:
- Location mirrors the bounded context: `src/domain/{context}/{module}.py`
- All classes/functions must have Google-style docstrings including a **Business Context** note:
  ```python
  def compute(self, signals: RiskSignals) -> RiskScore:
      """Compute a composite risk score from raw signals.

      Business Context:
          Usage decay (weight 0.50) is the strongest churn predictor.
          Recalibrate weights quarterly using SHAP analysis.

      Args:
          signals: The three risk signal components.

      Returns:
          RiskScore value object in [0, 1].
      """
  ```
- Full type hints — mypy must pass with `--strict`
- No direct infrastructure imports in domain layer

Announce: **"Implementation written. Run `pytest tests/unit/... -v --cov=src --cov-report=term-missing`."**

### Step 5 — Confirm Green (all pass)
Wait for test output. If any test fails, fix the implementation — do not modify tests to make them pass.

### Step 6 — Refactor
With green tests as a safety net:
- Remove duplication
- Improve naming to match domain language (ubiquitous language)
- Ensure no infrastructure leaks into domain layer
- Re-run tests to confirm still green

### Step 7 — Finalise
Output the following in order:
1. Coverage summary: `X% coverage. Lines missing: [list]`
2. Mypy check: `mypy src/domain/... --strict` — must be clean
3. CHANGELOG.md entry to add (ready to paste)
4. Any `docs/api-reference/` page that needs updating (usually auto-generated, but confirm `::: src.domain.xxx` directive is present)

---

## Quality Gates (CI will enforce these — fix before handing off)

| Gate | Requirement |
|---|---|
| Coverage | ≥85% on new code |
| Mypy | Zero errors with `--strict` |
| Ruff | Zero lint errors |
| Tests | All pass, including property-based |
| Docstrings | All public functions/classes |
| Business context note | Present in all domain service methods |
