---
name: mkdocs-autoupdate
description: Keep MkDocs documentation perfectly in sync after every code change. Updates API reference pages, architecture diagrams, nav structure, and changelog. Run after every phase or significant code addition.
triggers: ["update docs", "sync docs", "mkdocs update", "docs out of date", "update api reference", "regenerate docs"]
version: 1.0.0
---

# MkDocs Auto-Update Skill

**Prime directive:** Docs are never an afterthought. This skill ensures the MkDocs site at `:8001` accurately reflects the current codebase at all times.

---

## Workflow

### Step 1 — Scan for New/Changed Code
Identify all files changed since the last docs update:
- New modules in `src/domain/`, `src/application/`, `src/infrastructure/`
- New or modified docstrings (check for Google-style compliance)
- New dbt models in `dbt_project/models/`
- New notebooks in `notebooks/`

### Step 2 — Audit Docstring Quality
For every new public function/class, verify the docstring has all required sections:

```python
def method(self, arg: Type) -> ReturnType:
    """One-line summary.

    Business Context:
        Why this exists and what business problem it solves.
        Link to relevant phase or ADR if applicable.

    Args:
        arg: Description including valid range or expected values.

    Returns:
        Description of return value and its meaning.

    Raises:
        ValueError: When and why this is raised.

    Example:
        >>> result = method(valid_arg)
        >>> assert result.value > 0
    """
```

Flag any docstring missing the **Business Context** section — this is required for SaaSGuard to keep domain intent visible across all layers.

### Step 3 — Update API Reference Pages

For each new module, ensure a corresponding page exists in `docs/api-reference/`:

**For domain entities/services:**
```markdown
# [Context] Domain

::: src.domain.{context}.entities
::: src.domain.{context}.value_objects
::: src.domain.{context}.repository
```

**For new domain services:**
```markdown
::: src.domain.{context}.{service_name}
```

**For infrastructure implementations:**
```markdown
::: src.infrastructure.{layer}.{module}
```

### Step 4 — Update `mkdocs.yml` Nav
Any new page must appear in the nav. Follow this hierarchy:

```yaml
nav:
  - API Reference:
    - Overview: api-reference/index.md
    - Customer Domain: api-reference/customer.md
    - [New Domain]: api-reference/{new-domain}.md   ← add here
```

Never leave an orphaned page (file exists but not in nav).

### Step 5 — Update Architecture Diagram
If a new entity, service, or relationship was added, update the Mermaid diagram in `docs/architecture.md`:

- Add new entities to the correct bounded context subgraph
- Add new arrows for data flow
- Keep the diagram readable — use subgraphs to manage complexity

### Step 6 — Verify Docs Build
Output the exact command to test the build:

```bash
# Test that MkDocs can build without errors
docker compose run --rm mkdocs mkdocs build --strict

# Or locally
mkdocs build --strict
```

`--strict` treats warnings as errors. All `::: src.xxx` directives must resolve.

### Step 7 — Output Summary
```
## Docs Update Summary

New pages added: [list]
Nav entries added: [list]
Docstrings flagged for improvement: [list]
Architecture diagram updated: yes/no
Build status: ready / [issue to fix]

Run: docker compose --profile dev up mkdocs
Browse: http://localhost:8001
```

---

## Docstring Quality Checklist

| Element | Required | Example |
|---|---|---|
| One-line summary | Yes | `Compute composite risk score.` |
| Business Context | **Yes** | `Usage decay (weight 0.50) is the strongest churn predictor.` |
| Args | Yes (if any) | `signals: The three risk signal components.` |
| Returns | Yes (if non-void) | `RiskScore value object in [0, 1].` |
| Raises | Yes (if any) | `ValueError: If compliance_gap_score is outside [0, 1].` |
| Example | Encouraged | Inline `>>>` doctest |

---

## CI Integration
The `mkdocs build --strict` command runs in CI (see `.github/workflows/ci.yml`).
A docs build failure blocks merge to `main` — treat it as seriously as a failing test.
