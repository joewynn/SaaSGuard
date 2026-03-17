# Ethical Guardrails – AI/LLM Layer

## Why Guardrails Matter

In a B2B SaaS customer success context, an incorrect AI-generated summary can have real consequences:

- A **hallucinated churn probability** (e.g. "78%" when the model returned 45%) could trigger an unnecessary escalation, wasting CS resources or alarming a healthy customer.
- A **made-up feature name** (e.g. "days_until_renewal") suggests the LLM is fabricating an explanation rather than reporting what the model actually found — eroding CS trust in the tool.
- An **overconfident narrative** without a human-in-loop watermark removes the accountability signal that CS managers need to exercise judgment.

SaaSGuard applies a three-layer guardrail to every LLM output before it reaches a CS workflow.

---

## Three-Layer Defence

### Layer 1 — Prompt Grounding

The `PromptBuilder` assembles a `[CONTEXT]` block containing only verified DuckDB facts:
- Customer profile (tier, MRR, tenure, industry)
- Calibrated churn probability + risk tier (from XGBoost model)
- Top-5 SHAP feature drivers with values and impact directions
- Usage events (last 30 days, by type)
- Open support tickets (priority, topic, age)
- Active GTM opportunity (if any)
- Cohort churn rate (same tier + industry)

The system prompt and `[CONSTRAINT]` block explicitly instruct the LLM:

> "You may ONLY reference facts listed in [CONTEXT]. Do not infer or extrapolate beyond what is provided. Do not use phrases like 'I think', 'probably', or 'might be'."

This is the first and most effective hallucination-prevention mechanism — the LLM is given all the context it needs and forbidden from adding more.

### Layer 2 — Output Validation (`GuardrailsService`)

After every LLM call, `GuardrailsService.validate()` checks the raw output:

| Check | What it does | Flag raised |
|---|---|---|
| **Feature name whitelist** | Scans for tokens that look like ML features (contain `_score`, `_rate`, `_days`, `_30d`, etc.) and verifies they appear in `KNOWN_FEATURES` | `hallucinated_feature:<name>` |
| **Probability accuracy** | Extracts any percentage from the summary and compares to model output (tolerance: ±2pp) | `probability_mismatch` |

The `confidence_score` starts at `1.0` and degrades by `0.2` per flag, floored at `0.0`.

**Escalation rule:** If `confidence_score < 0.5`, the summary should be held for human review before use in any CS workflow.

### Layer 3 — Human-in-Loop Watermark

Every output — clean or flagged — has the following appended before being returned:

> ⚠️ AI-generated. Requires human review.

This watermark cannot be suppressed. It signals to CS teams and executives that the summary was AI-generated and must be verified before acting on it.

---

## Feature Name Whitelist

`KNOWN_FEATURES` in `guardrails_service.py` contains all legitimate feature names that can appear in model explanations. This set is updated whenever new features are added to the dbt feature mart.

**Rationale:** Feature names are a stable, enumerable set. An LLM inventing a feature name (e.g. `contract_renewal_score`) when no such feature exists in the model is a clear hallucination signal.

When adding new features to the mart, also add the feature name to `KNOWN_FEATURES` to prevent false-positive guardrail flags.

---

## Probability Tolerance

The guardrail allows a ±2 percentage point tolerance when checking if the stated probability matches the model output. This accounts for rounding (e.g. "72%" for a model output of 0.718).

If the LLM states a probability more than 2pp away from the model output, it means one of:
- The LLM fabricated a number
- The LLM misread the context
- The prompt context was stale (race condition between prediction and summary generation)

All three indicate the summary should not be trusted without review.

---

## Bias Considerations

LLMs trained on general-purpose corpora may have implicit biases:

- **Industry bias**: The model may associate certain industries (e.g. financial services) with different risk levels than the data supports.
- **Size bias**: Large-MRR customers may receive more optimistic narratives due to training data skew.
- **Action bias**: CSM-audience prompts may generate urgency-biased language for borderline risk tiers.

**Mitigation:** The `[CONSTRAINT]` block anchors all claims to the `[CONTEXT]` data. Periodic human review of a random sample of summaries (5%) is recommended to detect systematic bias patterns.

---

## Human-in-Loop Annotation

The following feedback loop is planned:

1. CS teams can flag summaries as "incorrect" or "helpful" via the Superset dashboard
2. Flagged summaries are logged with the original context for analysis
3. Systematic errors (wrong probability, recurring hallucinated features) inform prompt updates
4. Human correction rate is tracked as a quality metric (target: < 5% flagged per week)

This creates a lightweight RLHF-style feedback signal without requiring model fine-tuning.

---

## Escalation Path

| Confidence Score | Recommended Action |
|---|---|
| 1.0 | Use summary directly in CS workflow |
| 0.6 – 0.8 | Review summary before sending to customer-facing stakeholders |
| < 0.5 | **Hold for human review** — do not use until validated |
| 0.0 | Discard — multiple guardrail failures indicate significant hallucination risk |
