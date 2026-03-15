---
name: exec-story
description: Transform any SaaSGuard analytical finding, model result, or phase output into a C-level narrative — slides, ROI story, executive summary, or 1-pager. Prioritises business impact over technical detail. Always includes ROI quantification and a clear call-to-action.
triggers: ["exec story", "executive summary", "c-level", "business narrative", "roi story", "slide deck", "turn into slides", "present to exec", "stakeholder update", "1-pager", "business impact"]
version: 1.0.0
---

# Executive Storytelling Skill

**Prime directive:** Executives make decisions based on revenue impact, risk, and competitive advantage — not model AUC or Docker healthchecks. Translate everything into those three currencies.

---

## The SaaSGuard Business Frame (always anchor to this)

| Metric | Value | Source |
|---|---|---|
| B2B SaaS average annual churn | ~3.5% | Industry benchmark |
| Voluntary churn in first 90 days | 20–25% | Forrester / G2 |
| Revenue impact of 1% churn reduction (on $200M ARR) | **$2M+ saved** | SaaSGuard ROI model |
| CS intervention success rate | 10–15% churn reduction | Industry studies |
| Time for CS to act on a churn signal (without SaaSGuard) | Days to weeks | Manual process |
| Time for CS to act on a churn signal (with SaaSGuard) | Hours | API alert trigger |

---

## Slide Structure (10-slide template)

### Slide 1 — The Problem (Hook)
**Format:** Large number + one pain quote
```
"$2M walks out the door every time churn rises 1%"

80% of B2B buyers switch suppliers who fail to align expectations.
— Forrester Research
```
Avoid: technical jargon. Use: money, customer quotes, competitor threat.

### Slide 2 — Current State (The Gap)
**Format:** Before/After split or "How it works today" process pain
- What CS teams do today (manual, reactive, slow)
- How long it takes, what gets missed
- Cost of inaction

### Slide 3 — SaaSGuard Solution (One Sentence)
**Format:** One bold sentence + three bullet differentiators
```
SaaSGuard predicts which customers will churn 90 days in advance —
and tells your CS team exactly why.
```
- Predict: calibrated probability per customer, updated daily
- Explain: top 5 SHAP drivers so CS knows what to say
- Act: automated CS outreach trigger when risk exceeds threshold

### Slide 4 — How It Works (Simple)
**Format:** 4-box flow diagram, no tech jargon
```
Data Ingestion → Risk Scoring → CS Alert → Intervention
(product + CRM)   (AI model)    (Slack/CRM)  (call/email)
```

### Slide 5 — The Data (Credibility)
**Format:** Numbers + confidence signals
- X customers analysed
- Y usage events processed
- Model accuracy: AUC {value}, calibration score {value}
- "Predictions are explainable — CS sees the top reasons, not a black box"

### Slide 6 — ROI Model
**Format:** Simple table, three scenarios

| Scenario | Churn reduction | ARR protected | CS capacity needed |
|---|---|---|---|
| Conservative | 0.5% | $1M | 2 additional outreaches/week |
| Base case | 1.0% | $2M | 5 outreaches/week |
| Optimistic | 1.5% | $3M | 8 outreaches/week |

> "Base case assumes 10% of high-risk customers convert after CS outreach."

### Slide 7 — Pilot Results / Validation
**Format:** Before/after metric (use pilot cohort results or synthetic data for pre-launch validation)
- Cohort A (no alert): 8.2% 90-day churn
- Cohort B (SaaSGuard alert): 6.1% 90-day churn
- Delta: -26% relative reduction

### Slide 8 — Risk & Guardrails
**Format:** "What could go wrong + how we handle it"
- Model bias → quarterly fairness audit by plan tier + industry
- LLM hallucination in summaries → human review required before customer-facing use
- Data privacy → no PII in model features; GDPR-compliant event logging
- Model decay → performance monitored monthly; retrain trigger at AUC < 0.80

### Slide 9 — Rollout Plan
**Format:** 3-phase timeline (30 / 60 / 90 days)
- Day 0–30: Pilot with 50 high-MRR customers; CS team trained
- Day 31–60: Full rollout; integration with CRM alert workflow
- Day 61–90: Review ROI vs. baseline; adjust threshold and CS playbook

### Slide 10 — Ask / Next Step
**Format:** One clear ask
```
Approve pilot program for [X] customers.
Decision needed by [date].
```
Never end with "any questions?" — end with a specific next step.

---

## ROI Calculator Template
```
Annual Recurring Revenue:          $[ARR]
Current annual churn rate:         [X]%
Churned revenue / year:            $[ARR × churn_rate]
SaaSGuard churn reduction target:  [Y]%
Revenue saved:                     $[ARR × Y/100]
SaaSGuard annual cost:             $[cost]
Net ROI:                           $[saved - cost]
Payback period:                    [months]
```

---

## AI Executive Summary Format (Phase 5 LLM output)
```
Customer: {name} | Plan: {tier} | MRR: ${mrr}
Risk Level: {CRITICAL/HIGH/MEDIUM/LOW}
Churn Probability: {X}% (next 90 days)

Top Signals:
1. {feature}: {value} → {plain-English explanation}
2. {feature}: {value} → {plain-English explanation}

Recommended Action: {specific CS action with timeline}

⚠️ AI-generated. Requires human review before customer outreach.
```

---

## Rules
- Never lead with a model metric (AUC, F1) in exec output — translate to revenue impact first
- Every finding needs a "so what" that ties to $2M ARR story
- Use plain English, not ML jargon, in anything that goes above the DS team
- Always include the ethical guardrail disclaimer on LLM outputs
- Call-to-action must be specific: who does what by when
