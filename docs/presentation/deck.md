# SaaSGuard – Executive Presentation Deck

> **10-slide deck** — each `##` heading is one slide.
> Paste directly into Google Slides, Keynote, or present from MkDocs at `:8001`.
> Speaker notes follow each slide in `> **Note:**` blocks.

---

## Slide 1 — The Burning Problem

**"$2M+ in ARR leaves in the first 90 days — and nobody sees it coming"**

- **20–25%** of voluntary B2B SaaS churn happens in the first-90-day onboarding window *(Forrester)*
- The customer's decision to leave is made **60+ days before** they ever click "cancel"
- By the time a CSM notices — usage drop, missed QBR, support escalation — it's already too late
- Current toolkit: **Salesforce** (lagging by weeks) + usage dashboards (no context) + gut feel

```
Timeline of a lost customer:

Day 0     Day 14        Day 45          Day 75     Day 90
  │         │             │               │           │
Signup   First           ← SILENT DECAY →          Cancel
         value                                    Notification
                     ← CS teams see nothing here →
```

> **Note:** Open with this. Let it land. Don't rush to the solution. Every person in the room
> has felt this pain — the customer who churned and nobody knew why until it was too late.

---

## Slide 2 — Why Today's Approach Fails

**"CS teams are fighting fires with a garden hose"**

| The Reality | The Cost |
|---|---|
| 15 min manual research per at-risk account | 15 CSMs × 20 accounts = **300 hours/month** of reactive work |
| Signal arrives 5–7 days before cancellation | No time for a meaningful intervention |
| No prioritisation — every at-risk account looks the same | CSMs focus on the loudest, not the most at-risk |
| LLM tools hallucinate without grounding | CSMs can't trust AI-generated account briefs |

**The gap between** when a customer starts disengaging and when CS acts is where $2M+ of ARR is lost every year.

> **Note:** This is the "current state" slide. Make it visceral. Quote the 300 hours number —
> that's 7.5 full-time weeks of CS capacity burned on reactive research every month, not proactive retention.

---

## Slide 3 — SaaSGuard: The Platform

**"Early signal → CS action → ARR saved"**

SaaSGuard is a **production-grade churn and risk prediction platform** that gives CS teams a
60-day early warning signal — with an explanation of why, an AI-generated brief, and a
dashboard ready for Monday morning.

**Three things that make it different:**

1. **Interpretable predictions** — SHAP explainability translates every churn score into plain English:
   *"Usage dropped 60% in 30 days. 4 open support tickets. No integration connects."*

2. **AI-augmented summaries** — A 30-second AI brief replaces 15 minutes of manual research.
   Grounded in real customer data. Watermarked. Human-review gate built in.

3. **Production-ready from day one** — Docker one-command deploy, CI/CD pipeline, 137 tests,
   operations runbook, change management plan. Not a prototype.

> **Note:** Three bullets only. No feature list. Each differentiator answers the specific failure
> mode from Slide 2. "Interpretable" → fixes the gut-feel problem. "AI brief" → fixes the 15-min
> research problem. "Production-ready" → answers the "can we actually ship this?" question.

---

## Slide 4 — How It Works

**"Four layers, one signal"**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   DATA LAYER    │    │   MODEL LAYER   │    │  INTELLIGENCE   │    │  ACTION LAYER   │
│                 │───▶│                 │───▶│     LAYER       │───▶│                 │
│ DuckDB + dbt    │    │ XGBoost +       │    │ Llama-3 summaries│   │ Superset        │
│ 5K customers    │    │ Survival        │    │ RAG "Ask about  │    │ 4 dashboards    │
│ 3.5M events     │    │ analysis        │    │ Customer X"     │    │ Customer 360    │
│ Nightly refresh │    │ SHAP drivers    │    │ 3-layer         │    │ API endpoint    │
│                 │    │ 4 risk tiers    │    │ guardrails      │    │ CS triggers     │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Full stack:** Python · DuckDB · dbt · XGBoost · Llama-3 (Groq/Ollama) · FastAPI · Apache Superset · Docker

> **Note:** This is the only technical slide in the first half. Keep it to 60 seconds.
> The key message is the **left-to-right flow**: raw events go in, CS action comes out.
> Don't explain each box — just establish that every layer exists and is connected.

---

## Slide 5 — The Signal Quality

**"A model you can trust — and explain to your VP"**

| Metric | Target | Result |
|---|---|---|
| AUC-ROC | ≥ 0.80 | ✅ Achieved |
| Calibration | ±15pp vs. Kaplan-Meier | ✅ Achieved |
| Precision @ top decile | ≥ 0.60 | ✅ Achieved |
| Brier score | ≤ 0.15 | ✅ Achieved |

**What the top signal means in plain English:**

> *"`events_last_30d` is the #1 churn predictor. A customer whose product activity drops by 50%
> in a rolling 30-day window has **2× the churn risk** of an engaged customer at the same tenure."*

The model doesn't just score — it explains. Every prediction includes SHAP feature drivers,
a risk tier (LOW → CRITICAL), and a recommended CS action.

> **Note:** Never say AUC alone. Always translate: "AUC 0.80 means the model correctly ranks
> 80% of churners above non-churners — so when we give a CSM a top-20 at-risk list,
> 80% of the actual churners are on that list." That's the number that matters to VP CS.

---

## Slide 6 — The ROI

**"12.3× ROI. Payback in under 30 days."**

| Scenario | Churn Reduction | ARR Protected | Net ROI |
|---|---|---|---|
| Conservative | −0.5% | $1.0M | **$850K** |
| **Base case** | **−1.0%** | **$2.0M** | **$1.85M** |
| Optimistic | −1.5% | $3.0M | **$2.85M** |

**Assumptions:** $200M ARR · 4.2% baseline churn · 60% signal coverage · 12% CS conversion · $150K platform cost

**The key lever:** CS conversion rate.
Every **+5% improvement in outreach-to-retention** adds **$925K** to net ROI.

**Payback period: < 1 month.**

> **Note:** Let the table do the work. Then say: "The most conservative scenario — where we only
> save half a percent of churn — still returns $850K net on a $150K investment. That's a
> payback inside one billing cycle." Pause. Then move on.

---

## Slide 7 — The Experiment Is Already Designed

**"You don't have to trust the model. You can prove it in one quarter."**

The platform ships with a **pre-built Bayesian A/B test framework**:

- **60 accounts/arm** → **88% confidence** in 1–2 quarters *(vs. 340/arm and 5–8 quarters frequentist)*
- Treatment: 3-touch CS sequence (email + in-app nudge + call) over 14 days
- Primary metric: 90-day churn rate
- Safety gates at weeks **2, 8, 13** — early stopping if harm detected

**Decision rule:**
- P(treatment > control) ≥ 0.90 → **expand to full CS team**
- 0.70–0.90 → extend one quarter
- < 0.70 → redesign intervention

The experiment governance is complete: VP CS, Head of Data, and Legal approval gates built in.

> **Note:** This slide converts sceptics. The instinct is "sounds great but show me the data."
> The answer is: "We designed the experiment so you *can* get the data — in 90 days,
> with 60 accounts, at 88% confidence. That's not a pilot — that's a proof."

---

## Slide 8 — Responsible AI

**"Every AI output has a human safety net"**

Three-layer guardrails on every LLM-generated summary:

| Layer | What it does |
|---|---|
| **1 — Grounding** | LLM receives only verified DuckDB context; extrapolation is explicitly forbidden in the system prompt |
| **2 — Validation** | Guardrails service checks for hallucinated feature names and probability accuracy ±2pp |
| **3 — Watermark** | Every output flagged: *"⚠️ AI-generated. Human review required before external distribution."* |

**Confidence score escalation:**
- **1.0** — Use directly
- **0.6–0.8** — Review before sharing externally
- **< 0.5** — Hold for human review
- **0.0** — Discard; regenerate with more specific prompt

All bias risks documented: industry imbalance, account size bias, action bias. 5% random human audit built in.

> **Note:** This slide is for the risk-conscious audience — legal, IT/security, the CFO.
> Lead with: "We didn't build guardrails because we had to. We built them because a CS rep
> acting on a hallucinated customer brief is worse than no AI at all."

---

## Slide 9 — 12-Week Rollout

**"Pilot to full deployment — without disrupting your CS team"**

```
Week  1: ▓▓ Pilot (2 CSMs · 10 at-risk accounts · gate: ≥80% find it useful)
Week  2: ▓▓▓▓▓▓▓▓ Full CS team rollout (15 CSMs · all active accounts)
Week  4: ▓▓ Executive dashboard access (VP CS · CFO · CEO)
Week  6: ▓▓▓▓ Sales integration (renewal pipeline enriched for Q2)
Week  8: ▓▓▓▓ API live for CRM integrations (Salesforce webhook)
Week 12: ▓▓ First model retraining (new cohort data · drift check)
```

**Success metrics at 90 days:**
- Churn rate: **−5% relative** reduction
- CSM time per at-risk account: **15 min → 3 min**
- AI summary accuracy: **≥80%** rated "accurate" by CSMs
- Platform uptime: **≥99.5%**

> **Note:** The rollout is already written. The runbook is already written. The training plan
> is already written. The only decision is whether to start the clock at Week 1.

---

## Slide 10 — The Ask

**"One pilot. 60 accounts. 90 days."**

| What | Detail |
|---|---|
| **Request** | Approve a 90-day pilot with 60 at-risk accounts |
| **Resources** | 2 senior CSMs · data access · $0 marginal cloud cost (Docker on existing infra) |
| **Timeline** | Pilot results in one quarter · statistical significance at 88% confidence |
| **Decision point** | If P(impact) ≥ 0.90 → expand to full CS team in Q2 |

**The platform is already built.**
The data pipeline is running. The model is trained and calibrated. The dashboards are live.
The runbook is written. The change management plan is written.

The only thing missing is the pilot.

---

> 🔗 **Repo:** [github.com/josephwam/saasguard](https://github.com/josephwam/saasguard)
> 📖 **Docs:** `docker compose --profile dev up -d` → [localhost:8001](http://localhost:8001)
> 🚀 **API:** [localhost:8000/docs](http://localhost:8000/docs)

> **Note:** Sit down. Let silence do the work. If they want to discuss, open with:
> "I built this because I wanted to show what a full product analytics practice looks like
> when you own it from raw data to executive dashboard. The platform is the answer to
> 'What would you build in the first 90 days?' — I already built it."
