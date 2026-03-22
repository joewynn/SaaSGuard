# SaaSGuard Claude Skills

Reusable SOPs for consistent, production-grade delivery. Each skill enforces a specific standard — DDD, TDD, documentation, Docker hardening, data contracts, executive storytelling.

## Available Skills

| Skill | Invoke | Purpose |
|---|---|---|
| **tdd-cycle** | `/tdd-cycle` | Red-Green-Refactor for any new entity, service, or model |
| **ddd-entity** | `/ddd-entity` | Create bounded-context entities, value objects, repositories |
| **phase-advance** | `/phase-advance` | Complete a full project phase with all deliverables |
| **mkdocs-autoupdate** | `/mkdocs-autoupdate` | Keep docs site in sync after every code change |
| **docker-harden** | `/docker-harden` | Audit and harden Docker/Compose configuration |
| **dvc-version** | `/dvc-version` | Version data files and model artifacts with DVC |
| **exec-story** | `/exec-story` | Turn findings into C-level slides and ROI narratives |
| **self-critique** | `/self-critique` | Structured quality review before handing off any output |
| **data-contract** | `/data-contract` | Define schema tests, Pydantic validation, freshness SLAs |
| **commit-and-close** | `/commit-and-close` | Verify tests, commit with conventional message, push, close GitHub issues |

## How to Use

### In Claude Code (this repo)
Skills are detected automatically when trigger words appear in your message, or invoke explicitly:

```
/tdd-cycle for ChurnProbability value object
/ddd-entity for a new ComplianceEvent in usage_domain
/phase-advance to Phase 2 - Data Architecture
/exec-story for Phase 4 model results (AUC 0.87, $2M ARR impact)
/self-critique
/data-contract for the usage_events table
```

### In Claude.ai Chat
Upload this `/skills/` folder or paste the relevant `SKILL.md` content at the start of a conversation.

### Chaining Skills
Skills chain naturally:
```
/ddd-entity → auto-chains to → /tdd-cycle → auto-chains to → /mkdocs-autoupdate
/phase-advance → runs → /self-critique → then → /mkdocs-autoupdate
```

## Skill File Structure

```
skills/
├── {skill-name}/
│   └── SKILL.md        ← YAML frontmatter + full instructions
└── README.md           ← this file
```

## Extending Skills

To create a new skill:
1. Create `skills/{new-skill}/SKILL.md`
2. Add YAML frontmatter: `name`, `description`, `triggers`, `version`
3. Write a step-by-step workflow with explicit output format
4. Add to the table above
5. Update `CLAUDE.md` Section 9

## Version History

| Version | Change |
|---|---|
| 1.0.0 | Initial 9 skills: tdd-cycle, ddd-entity, phase-advance, mkdocs-autoupdate, docker-harden, dvc-version, exec-story, self-critique, data-contract |
| 1.1.0 | Added commit-and-close skill — git commit + push + GitHub issue closing SOP |
| 1.2.0 | Post-mortem: codified ML model safety rules across tdd-cycle, self-critique, commit-and-close — mandatory no-mock integration tests for inference paths, `_FEATURE_ORDER` sync check, retrain-before-push gate |
