---
name: User Story
about: Standard ticket format for SaaSGuard feature work, research, and docs
title: "SGD-XXX · [Short description]"
labels: ""
assignees: ""
---

## User Story
As a [CSM / VP CS / data scientist / platform engineer / hiring manager], I want [capability] so that [business outcome].

## Context
[1–2 sentences linking to VoC evidence, project brain, or a previous issue. Explain *why* this matters now, not just *what* it is. Reference `docs/stakeholder-notes.md`, `docs/prd.md`, or a specific pain point if relevant.]

## Acceptance Criteria
- [ ] Specific, testable condition 1
- [ ] Specific, testable condition 2
- [ ] Named pytest / dbt test passes (e.g., `pytest tests/unit/domain/test_customer_entities.py`)
- [ ] `mkdocs build --strict` passes if docs were changed

## Definition of Done
- [ ] Tests written before implementation (`/tdd-cycle` if code; `/data-contract` if data)
- [ ] `mypy` clean on changed files
- [ ] Merged to `develop` via PR (or `main` for Phase 7+)
- [ ] CHANGELOG.md entry added
- [ ] MkDocs nav updated if a new doc page was created
- [ ] `/self-critique` run and all dimensions green

## Skill to Use
<!-- Delete all but one -->
- `/tdd-cycle` — new entity, service, or model
- `/ddd-entity` — new bounded context artifact
- `/phase-advance` — completing a full phase
- `/mkdocs-autoupdate` — docs sync after code change
- `/docker-harden` — Docker/Compose audit
- `/dvc-version` — data or model artifact versioning
- `/exec-story` — business narrative / slides
- `/data-contract` — schema tests, Pydantic validation, freshness SLA
- `/self-critique` — quality review before PR

## References
- Spec: `docs/tickets.md` (SGD-XXX)
- Depends on: #N (issue number)
- Related ADR: `docs/ADR/ADR-00X-...`
