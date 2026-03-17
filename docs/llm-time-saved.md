# LLM Time Saved – CS Productivity ROI

## Baseline: Manual CSM Account Brief

Before SaaSGuard's AI layer, a Customer Success Manager preparing for an account review would:

1. Pull usage data from the product analytics tool (~3 min)
2. Check open support tickets (~2 min)
3. Review the CRM for recent GTM activity (~2 min)
4. Calculate risk assessment from the prediction dashboard (~3 min)
5. Write a summary for the account brief / EBR prep doc (~5 min)

**Total: ~15 minutes per account**

---

## With AI Layer: 30-Second API Call

`POST /summaries/customer` returns a 3–5 sentence narrative grounded in:
- Calibrated churn probability + SHAP drivers
- Usage events (last 30 days)
- Open support tickets
- GTM opportunity status
- Cohort benchmarks

**Total: ~30 seconds** (API call + human review of watermarked output)

---

## Time Saved per CSM per Week

| Metric | Value | Source |
|---|---|---|
| Active accounts per CSM | 20 | Industry benchmark (Gainsight 2024) |
| Account briefs written/week | 20 (weekly review cadence) | Assumption |
| Time per brief (manual) | 15 min | Baseline above |
| Time per brief (AI-assisted) | 2 min (30s + review) | measured |
| **Net time saved per CSM/week** | **~3.3 hours** | (15 − 2) × 20 / 60 |
| CSMs on platform (Year 1 assumption) | 10 | Business assumption |
| **Total time saved per week** | **~33 hours** | 3.3 × 10 |
| Fully loaded CSM cost ($/hr) | $75 | Industry estimate |
| **Weekly cost savings** | **~$2,475** | 33 × $75 |
| **Annual cost savings** | **~$129,000** | $2,475 × 52 |

---

## Quality Metrics

Time saved is only valuable if quality is maintained or improved. The system tracks:

| Metric | Target | How Measured |
|---|---|---|
| Guardrail pass rate | > 90% | % of summaries with `confidence_score = 1.0` in production logs |
| Probability accuracy | ±2pp | Guardrail `probability_mismatch` flag rate |
| CSM accuracy rating | > 80% "accurate" | Optional survey in Superset dashboard |
| Human correction rate | < 5%/week | Flagging workflow |
| API latency (Groq) | < 3s p95 | structlog timing → Prometheus |
| API latency (Ollama) | < 15s p95 | Acceptable for local dev |

---

## Compounding ROI: Churn Reduction

The primary ROI driver is not time savings — it's **faster, better-informed CS interventions**:

- SaaSGuard AI summaries surface the right customer for outreach **before** the churn signal becomes irreversible
- Early CS intervention yields 10–15% churn reduction (Forrester, 2023)
- On $200M ARR with 5% baseline churn ($10M at-risk ARR): **10% reduction = $1M saved per year**

The AI layer accelerates the human judgment loop, turning raw model predictions into actionable CS briefs in seconds rather than minutes. The compound effect — more timely interventions across more accounts — is where the largest ROI lives.

---

## Feedback Loop

To continuously improve summary quality:

1. Log every summary with: `customer_id`, `model_used`, `confidence_score`, `guardrail_flags`, `generated_at`
2. Track CSM "thumbs up / thumbs down" ratings via Superset dashboard
3. Weekly review: identify systematic errors (recurring flags, low-rated summaries)
4. Feed high-quality summaries + corrections back as few-shot examples in the prompt (no fine-tuning required)
5. Report correction rate trend to VP CS as a platform health metric
