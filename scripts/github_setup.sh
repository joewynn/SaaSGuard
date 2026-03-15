#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# github_setup.sh
# Creates all GitHub labels and milestones for SaaSGuard.
# Run ONCE before create_issues.sh.
#
# Prerequisites:
#   gh auth login        (GitHub CLI authenticated)
#   gh repo view         (must be run from inside the repo)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
export GH_PAGER=   # prevent gh from opening a pager for error output

echo "▶ Setting up SaaSGuard GitHub labels and milestones..."
echo ""

# ── Phase Labels ──────────────────────────────────────────────────────────────
echo "Creating phase labels..."

gh label create "phase-1"  --color "#BFD4F2" --description "Phase 1: Scoping & Requirements"        --force
gh label create "phase-2"  --color "#A2C4F5" --description "Phase 2: Data Architecture"             --force
gh label create "phase-3"  --color "#85B4F8" --description "Phase 3: EDA & Experiments"             --force
gh label create "phase-4"  --color "#6AA0F5" --description "Phase 4: Predictive Models"             --force
gh label create "phase-5"  --color "#4F8CF2" --description "Phase 5: AI/LLM Layer"                  --force
gh label create "phase-6"  --color "#3478EF" --description "Phase 6: Dashboard"                     --force
gh label create "phase-7"  --color "#1A64EC" --description "Phase 7: Deployment"                    --force
gh label create "phase-8"  --color "#0050E9" --description "Phase 8: Executive Presentation"        --force

# ── Priority Labels ───────────────────────────────────────────────────────────
echo "Creating priority labels..."

gh label create "p0-critical" --color "#D93F0B" --description "Blocker — must ship in this phase" --force
gh label create "p1-high"     --color "#E4882B" --description "High value — ship in this phase"   --force
gh label create "p2-medium"   --color "#F5C518" --description "Medium — ship if time allows"       --force

# ── Type Labels ───────────────────────────────────────────────────────────────
echo "Creating type labels..."

gh label create "type:engineering" --color "#0E8A16" --description "Backend / infra / data pipeline"  --force
gh label create "type:ml"          --color "#5319E7" --description "Machine learning / modelling"      --force
gh label create "type:docs"        --color "#C5DEF5" --description "Documentation update"              --force
gh label create "type:research"    --color "#FEF2C0" --description "Research / analysis"               --force
gh label create "type:bi"          --color "#1D76DB" --description "BI / dashboard / visualisation"    --force
gh label create "type:ai"          --color "#B60205" --description "LLM / AI feature"                  --force
gh label create "type:devops"      --color "#006B75" --description "Docker / CI / deployment"          --force

# ── Milestones ────────────────────────────────────────────────────────────────
echo ""
echo "Creating milestones..."

gh api repos/:owner/:repo/milestones --method POST \
  --field title="Phase 1 – Scoping & Requirements" \
  --field description="PRD, VoC research, ROI calculator, growth framework, Jira tickets" \
  --field state="open" || echo "  (milestone may already exist)"

gh api repos/:owner/:repo/milestones --method POST \
  --field title="Phase 2 – Data Architecture" \
  --field description="Synthetic data generation, dbt project, DuckDB warehouse, DVC pipeline" \
  --field state="open" || echo "  (milestone may already exist)"

gh api repos/:owner/:repo/milestones --method POST \
  --field title="Phase 3 – EDA & Experiments" \
  --field description="Cohort analysis, survival curves, A/B test simulation" \
  --field state="open" || echo "  (milestone may already exist)"

gh api repos/:owner/:repo/milestones --method POST \
  --field title="Phase 4 – Predictive Models" \
  --field description="XGBoost + survival churn model, risk score, SHAP, model card, fairness audit" \
  --field state="open" || echo "  (milestone may already exist)"

gh api repos/:owner/:repo/milestones --method POST \
  --field title="Phase 5 – AI/LLM Layer" \
  --field description="Executive summary generator, RAG chatbot, ethical guardrails" \
  --field state="open" || echo "  (milestone may already exist)"

gh api repos/:owner/:repo/milestones --method POST \
  --field title="Phase 6 – Dashboard" \
  --field description="Superset Customer 360, churn heatmap, risk drill-down, uplift simulator" \
  --field state="open" || echo "  (milestone may already exist)"

gh api repos/:owner/:repo/milestones --method POST \
  --field title="Phase 7 – Deployment" \
  --field description="FastAPI production, Docker hardening, change management deck, runbook" \
  --field state="open" || echo "  (milestone may already exist)"

gh api repos/:owner/:repo/milestones --method POST \
  --field title="Phase 8 – Executive Presentation" \
  --field description="10-slide deck, speaker notes, 1-pager, recorded walkthrough" \
  --field state="open" || echo "  (milestone may already exist)"

echo ""
echo "✅ Labels and milestones created."
echo "   Run: bash scripts/create_issues.sh"
