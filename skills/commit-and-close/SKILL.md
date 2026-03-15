---
name: commit-and-close
description: Verify green tests, stage files, write a conventional commit, update CHANGELOG, sync docs, push to origin, and close linked GitHub issues. Run at the end of every feature or phase.
triggers: ["commit and close", "commit progress", "close issue", "wrap up", "finalize phase", "ship it", "close the feature"]
version: 1.0.0
---

# Commit and Close Skill

**Prime directive:** Never commit broken code. Every invocation must verify a green test suite before touching git. Close issues only after the commit is on origin.

---

## When to Invoke

- At the end of a phase (chained automatically from `/phase-advance`)
- After a feature or bugfix is complete and tests are passing
- When the user says "commit", "close issue", "ship it", or "wrap up"

Invoke with optional arguments:
```
/commit-and-close                          # auto-detect issue from branch name
/commit-and-close --issue 42               # close a specific GitHub issue
/commit-and-close --issue 42,43 --no-push  # close multiple issues, skip push
```

---

## Step-by-Step Workflow

### Step 1 — Verify green status

Run the test suite. If any test fails, **stop and surface the failure** — do not proceed.

```bash
pytest --no-cov -q
```

Also run linters:
```bash
ruff check .
mypy . --ignore-missing-imports
```

If any check fails: report the error, suggest a fix, and ask the user whether to proceed anyway or fix first. Do **not** silently skip.

---

### Step 2 — Verify documentation is in sync

Check that every new public function/class added in this session has a Google-style docstring. Check that `mkdocs.yml` nav includes any new `docs/` pages.

If out of sync → chain to `/mkdocs-autoupdate` first.

---

### Step 3 — Update CHANGELOG.md

Add or verify an entry in `docs/CHANGELOG.md` using Keep-a-Changelog format:

```markdown
## [X.Y.Z] – YYYY-MM-DD
### Added
- Short, user-facing description of each new capability

### Changed
- Any modified behaviour or interface

### Fixed
- Bug fixes, if any
```

Rules:
- Use today's date (from `currentDate` in context, or `date +%Y-%m-%d`)
- Bump semantic version: `feat` → minor, `fix` → patch, breaking → major
- Keep entries concise — one line per deliverable

---

### Step 4 — Stage files and draft commit message

Show the user a `git status` summary. Stage all relevant files:

```bash
git add <specific files — never git add -A blindly>
```

Draft a commit message following Conventional Commits:

```
<type>(<scope>): <short summary, ≤72 chars>

- <bullet: what changed and why>
- <bullet: any breaking changes or notable decisions>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

**Type vocabulary:**
| Type | When |
|---|---|
| `feat` | New feature or phase deliverable |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code restructure, no behaviour change |
| `test` | Tests added or updated |
| `chore` | Build, deps, config changes |
| `ci` | CI/CD changes |

**Scope** = domain or layer (e.g., `prediction`, `ml`, `api`, `dbt`, `docs`)

Show the drafted message to the user for approval before committing.

---

### Step 5 — Commit

```bash
git commit -m "$(cat <<'EOF'
<type>(<scope>): <summary>

- <bullet 1>
- <bullet 2>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

If a pre-commit hook fails: fix the issue, re-stage, and create a **new** commit. Never use `--no-verify`.

---

### Step 6 — Push to origin

```bash
git push origin <current-branch>
```

If the branch has no upstream yet:
```bash
git push -u origin <current-branch>
```

Skip this step only if the user explicitly passed `--no-push`.

---

### Step 7 — Close GitHub issues

For each issue number provided (or detected from branch name pattern `feature/<n>-*`):

```bash
gh issue close <n> --comment "Resolved in commit $(git rev-parse --short HEAD) — <one-line summary>"
```

If `gh` is not authenticated or no issue number is known, print a ready-to-paste comment and remind the user to close manually.

---

### Step 8 — Print completion summary

Output a structured status block:

```
## Commit & Close — Complete

**Commit:**   <hash> <summary>
**Branch:**   <branch> → origin/<branch>
**Issues:**   Closed #<n>, #<m>
**Tests:**    <N> passed, <M> skipped, 0 failed
**Docs:**     CHANGELOG updated to v<X.Y.Z>

Next: <suggested next step — e.g., "Ready for Phase 5 – AI/LLM Layer">
```

---

## Rules

- **Never commit without green tests.** If tests can't run (missing env, Docker not up), say so explicitly and ask the user to confirm.
- **Never use `git add -A` or `git add .`** — stage files by name to avoid accidentally committing `.env`, `*.pkl`, or large binaries.
- **Never amend a published commit.** If the previous commit needs updating, create a new one.
- **Never skip pre-commit hooks** (`--no-verify`). Fix the underlying issue instead.
- **DVC-tracked files** (`data/`, `models/`) must not be committed to git. If they appear in `git status`, remind the user to run `dvc add` + commit the `.dvc` pointer file instead.
- **One commit per logical unit.** If the session touched multiple unrelated concerns, split into separate commits (e.g., `feat(ml): ...` and `docs: ...`).
- Close issues **after** push so the linked commit SHA is valid on GitHub.

---

## Chain Behaviour

This skill is automatically chained from:
- `/phase-advance` → runs `/self-critique` → runs `/mkdocs-autoupdate` → runs `/commit-and-close`

Can be invoked standalone at any time without running the full chain.
