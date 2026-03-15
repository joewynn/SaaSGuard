# Speaker Notes — SaaSGuard Executive Presentation

> Full notes for a **15-minute presentation** or a **5-minute lightning pitch**.
> Vanta-specific language highlighted in **bold**. Time targets in `[brackets]`.

---

## How to Use These Notes

**15-minute version:** Use the full notes for each slide. Pace: ~90 seconds per slide.
**5-minute lightning:** Use only the lines marked `[LIGHTNING]`. Skip the evidence sections.
**Interview question:** "Walk me through your portfolio project" → start at Slide 1, go to Slide 3, jump to Slide 6, end at Slide 10. 4 slides, 4 minutes.

**Tone principle:** Every technical detail earns its place by connecting to ARR first.
Pattern: *Business impact* → *What the platform does* → *Why you built it that way*.

---

## Slide 1 — The Burning Problem `[2 min]`

**Opening line (say this exactly):**
> "Every B2B SaaS company I've spoken to has the same story: a customer churns, and when you
> pull the data, the warning signs were there 60 days earlier. The usage dropped. The tickets
> piled up. Nobody intervened because nobody had a signal."

**Evidence layer:**
- Forrester: 20–25% of voluntary churn happens inside the first 90 days
- The silent decay period — customer disengages between Day 14 and Day 75 — is invisible to today's tools
- Salesforce activity data lags by weeks; usage dashboards show events but not context; no prioritisation

**Why this matters to Vanta specifically:**
Vanta's customers are going through **GRC compliance implementations** — a high-friction onboarding that
is exactly the 90-day window where churn happens. The problem is acute.

`[LIGHTNING]` "20–25% of B2B SaaS churn is preventable if you catch it 60 days earlier.
SaaSGuard is the system that does that."

---

## Slide 2 — Why Today's Approach Fails `[1.5 min]`

**The quantified pain:**
> "A CS team of 15, each managing 20 accounts, spends 15 minutes per account pulling data
> before every QBR or at-risk call. That's 75 hours a week — nearly two full-time employees —
> doing manual research instead of actually talking to customers."

**The timing problem:**
The signal arrives 5–7 days before a customer cancels. At that point, the customer has already
made their decision. The intervention window is closed. A CSM calling on Day 83 of a 90-day
churn arc isn't saving anyone — they're doing damage control.

**The AI problem:**
CS teams have tried using general-purpose LLM tools to prep for calls. The problem: hallucination.
An AI that invents a feature adoption metric that doesn't exist, or misquotes a ticket, destroys
trust faster than not using AI at all.

**Transition:** "SaaSGuard was designed to solve all three of these failure modes specifically."

`[LIGHTNING]` "The current approach gives CS teams a signal 5 days too late, after 15 minutes
of research, with no way to prioritise. That's the problem SaaSGuard fixes."

---

## Slide 3 — The Platform `[1.5 min]`

**One-sentence pitch:**
> "SaaSGuard gives CS teams a 60-day early warning signal for customer churn —
> turning reactive firefighting into systematic revenue protection."

**On the three differentiators:**

1. **Interpretable predictions:**
   Don't just say "this customer is high risk." Tell the CSM *why*: "Usage dropped 60% in the
   last 30 days. Four open support tickets, two marked critical. No integration connects completed."
   That's actionable. A probability alone is not.

2. **AI-augmented summaries:**
   The AI brief is grounded in the actual DuckDB data — not hallucinated. Every output is
   watermarked and requires human review before external distribution. It's a research accelerator,
   not a replacement for judgement.

3. **Production-ready:**
   This isn't a Jupyter notebook. It's a system with a CI/CD pipeline, 137 tests, a Docker
   compose stack, a Prometheus metrics endpoint, and an operations runbook. **You could run this
   in your infra today.**

**On the Vanta JD language:**
This directly maps to "build and scale the analytics practice." Not "build a model." Build the
entire practice — data, models, AI, dashboards, change management.

`[LIGHTNING]` Three differentiators: interpretable predictions, AI briefs with guardrails, and
production-ready on day one.

---

## Slide 4 — How It Works `[1 min]`

**Quick tour, left to right:**

> "Data layer: DuckDB + dbt ingests 5,000 customers and 3.5 million product events, refreshed
> nightly. Model layer: XGBoost and survival analysis predict P(churn in 90 days) with SHAP
> explainability. Intelligence layer: Llama-3 turns that prediction into a 30-second brief for
> the CSM, with guardrails. Action layer: Four Superset dashboards and a Customer 360 API endpoint
> that any CRM can call."

**What to emphasise:**
The flow is end-to-end. Raw events go in at the left; a CS action triggers at the right.
Every layer is connected, tested, and deployed.

**On the tech stack:**
Don't dwell on individual tools. The point is that **every layer is production-grade** —
DuckDB with a schema and tests, not a CSV; a calibrated model, not a notebook; a guarded LLM,
not a raw API call.

`[LIGHTNING]` "Four layers: data pipeline, ML model, AI summaries, BI dashboards. End-to-end."

---

## Slide 5 — The Signal Quality `[1.5 min]`

**Translating the metrics:**

> "AUC 0.80 means this: if I show you one churned customer and one active customer, the model
> ranks the churner higher 80% of the time. In practice, if your CS team has bandwidth for 20
> at-risk calls this week, 80% of the customers on that list will be the ones who would have
> churned without intervention."

**On calibration:**
> "Calibration is the metric that matters for trust. If the model says a customer has a 70%
> churn probability, they should churn 70% of the time — not 40%, not 90%. We validated this
> against the Kaplan-Meier baseline, within ±15 percentage points across all risk tiers."

**The SHAP insight:**
> "The single strongest predictor — across all 5,000 customers — is `events_last_30d`. Usage
> decay in the last month is more predictive than tenure, plan tier, support ticket volume, or
> GTM stage. A 50% drop in 30-day product activity doubles churn risk. That's the alert
> condition we built the dashboard around."

**Why this matters to a cross-functional audience:**
SHAP makes the model legible to VP CS, legal, and IT/security — not just data scientists.
**Cross-functional influence** requires explainability.

`[LIGHTNING]` "AUC 0.80. Calibrated against survival analysis. Top driver: 30-day usage decay.
The model explains every score in plain English."

---

## Slide 6 — The ROI `[1.5 min]`

**Lead with the conservative case:**
> "Let's take the most conservative scenario. We reduce churn by half a percent — 0.5%.
> On $200M ARR, that's $1M in protected revenue. Net of the $150K platform cost, that's $850K.
> The payback period is under one month."

**On the base case:**
> "The base case — 1% churn reduction — is supported by Vitally and Churnfree benchmarks for
> structured CS intervention programs. That's $1.85M net. A 12.3× ROI multiple."

**The lever framing:**
> "The biggest sensitivity in the model isn't the churn prediction accuracy — it's the CS
> conversion rate. Every 5 percentage point improvement in how often a CS outreach actually
> retains a customer adds $925K to the ROI. That's the human-in-the-loop multiplier."

**Closing the ROI slide:**
> "This isn't a cost centre. It's a revenue engine. The question isn't whether to build it —
> it's how fast."

`[LIGHTNING]` "Conservative: $850K net on $150K investment. Base case: $1.85M. Payback: one month."

---

## Slide 7 — The Experiment `[1.5 min]`

**On sceptics:**
> "The most common pushback on any predictive system is 'how do we know it works?' The answer
> here is that the experiment is already designed. 60 accounts per arm gives you 88% confidence
> in 1–2 quarters. That's not a timeline we invented — it's the Bayesian sample size calculation
> from the experiment design notebook."

**On Bayesian vs. frequentist:**
> "The frequentist alternative requires 340 accounts per arm and 5–8 quarters to reach
> significance. By then you've missed two annual renewal cycles. Bayesian lets you start with
> 60 accounts and update the evidence each month."

**The decision rule framing:**
> "We built in a safety gate at week 2. If the treatment group is churning faster — any signal
> of harm — the experiment stops automatically. This isn't just responsible research design;
> it's what legal and CS leadership need to approve the pilot."

**The closing line:**
> "You don't have to trust the model. You can prove it in 90 days with 60 accounts. That's the
> ask on the last slide."

`[LIGHTNING]` "Pre-built Bayesian A/B framework. 60 accounts, 88% confidence, one quarter.
The experiment is ready to run."

---

## Slide 8 — Responsible AI `[1 min]`

**Lead with the risk, not the solution:**
> "Here's the failure mode we designed around: a CSM reads an AI-generated account brief before
> a call, the brief contains a hallucinated metric, the CSM quotes it to the customer, and the
> customer loses trust. That's worse than no AI. So we built three explicit guardrails."

**On the watermark:**
> "Every single LLM output — every summary, every question answer — carries the watermark:
> '⚠️ AI-generated. Human review required.' It can't be turned off. It's in the code."

**On the confidence score:**
> "A confidence score of 1.0 means every fact in the summary maps back to a verified DuckDB
> query result. Anything under 0.5 gets discarded automatically. The CSM never sees a
> low-confidence output — the system withholds it."

**On bias:**
> "We documented three bias risks: industry imbalance in training data, account size bias in
> SHAP feature importance, and action bias in the recommended interventions. Each has a
> documented mitigation. This is in `docs/ethical-guardrails.md`."

`[LIGHTNING]` "Three-layer guardrails: grounding, validation, watermark. Every output requires
human review. Bias risks documented and mitigated."

---

## Slide 9 — 12-Week Rollout `[1 min]`

**Frame the rollout as already planned:**
> "The change management plan, the training materials, the runbook, the success metrics — all
> of it is written and in the repository. This isn't 'we'll figure it out during the pilot.'
> The plan is done."

**On the pilot gate:**
> "Week 1 is a hard gate. Two senior CSMs, 10 accounts, explicit success criteria: ≥80% of
> CSMs find the dashboard useful. If we don't clear that gate, we don't expand. If we do,
> the full CS team gets access in Week 2."

**On the success metrics:**
> "The 90-day targets: 5% relative churn reduction, CSM research time cut from 15 minutes to
> 3 minutes, AI summary accuracy ≥80% by CSM survey, 99.5% uptime. These are measurable.
> They're in the change management doc, not just on this slide."

`[LIGHTNING]` "12-week plan: pilot Week 1, full CS team Week 2, exec dashboards Week 4.
Change management plan already written."

---

## Slide 10 — The Ask `[1 min]`

**Closing line (say this exactly):**
> "The platform is built. The model is trained and calibrated. The dashboards are live.
> The guardrails are in place. The experiment is designed. The change management plan is written.
> The only thing missing is the decision to start."
>
> "I'm asking for 60 accounts and 90 days."

**If asked "why should we hire you specifically?":**
> "Because I didn't just analyse the churn problem — I built the system that solves it.
> I own every layer: the data pipeline, the ML model, the AI summaries, the dashboards,
> the deployment, and the change management plan. That's what 'owning the product analytics
> practice' means. I already demonstrated it."

**If asked about the synthetic data:**
> "The data is synthetic — designed to replicate the statistical properties of a real GRC SaaS
> dataset: usage decay correlates with churn, compliance gaps correlate with support volume,
> enterprise customers have longer survival times. The architecture is production-ready for
> real data. The first step would be a data contract with your engineering team."

**On the GitHub link:**
> "The repo is public. You can clone it, run `docker compose --profile dev up -d`, and have
> the full stack running in under 5 minutes. The MkDocs documentation site at port 8001
> walks through every design decision."

`[LIGHTNING]` "One ask: 60 accounts, 90 days, 88% confidence. The platform is already built."

---

## Timing Reference

| Slide | Title | Full | Lightning |
|---|---|---|---|
| 1 | The Burning Problem | 2:00 | 0:30 |
| 2 | Why Today's Approach Fails | 1:30 | 0:20 |
| 3 | The Platform | 1:30 | 0:20 |
| 4 | How It Works | 1:00 | 0:15 |
| 5 | The Signal Quality | 1:30 | 0:20 |
| 6 | The ROI | 1:30 | 0:20 |
| 7 | The Experiment | 1:30 | 0:20 |
| 8 | Responsible AI | 1:00 | 0:15 |
| 9 | 12-Week Rollout | 1:00 | 0:15 |
| 10 | The Ask | 1:00 | 0:25 |
| **Total** | | **~14:00** | **~3:30** |
