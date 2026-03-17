# Experiment Design: CS Intervention Effectiveness (SGD-009)

**Status:** Approved
**Version:** 1.0
**Author:** SaaSGuard Platform Team
**Date:** 2026-03-14
**Related tickets:** SGD-009 (A/B Test Simulation), SGD-008 (Survival Analysis)

---

## 1. Hypothesis

### Business Hypothesis

A structured CS outreach programme targeting at-risk customers in the 30–90 day window
reduces 90-day churn rate relative to standard (reactive) CS support.

### Statistical Hypotheses

| | Statement |
|---|---|
| **H₀ (null)** | P(churn \| CS intervention) = P(churn \| standard support) — the intervention has no effect on 90-day churn rate |
| **H₁ (alternative)** | P(churn \| CS intervention) < P(churn \| standard support) — the intervention reduces 90-day churn rate |

**Direction:** One-tailed (we only care if the intervention *reduces* churn; an increase would
trigger immediate programme review regardless of statistical significance).

---

## 2. Unit of Randomisation

**Unit:** Individual customer account (`customer_id`)

**Randomisation method:** Stratified random assignment within risk tier (starter / growth /
enterprise), executed at the point of risk score update. Stratification prevents accidental
imbalances — e.g., assigning all starter accounts to control by chance.

**Assignment ratio:** 50/50 (equal treatment/control allocation maximises power for a given
total sample size).

**Exclusion criteria:**

- Customers in their first 14 days (too early for intervention signal)
- Customers already past day 90 of tenure (outside the intervention window)
- Customers with an open escalation ticket (CSM already engaged, can't randomise away support)

---

## 3. Intervention Description

### Treatment arm

Proactive CS outreach: a structured 3-touch sequence over 14 days.

| Touch | Channel | Content |
|---|---|---|
| Day 0 | Email | Personalised health score report + 2 adoption recommendations |
| Day 7 | In-app | Feature activation nudge (integration_connect prompt if score < 3) |
| Day 14 | CS call | 15-minute check-in with prepared risk briefing |

### Control arm

Standard (reactive) CS support: no proactive outreach. Customers receive standard in-app
help, documentation access, and reactive ticket support as usual.

**Ethical note:** Control arm customers are not denied support — they receive the current
standard of care. The intervention is *additive*, not *substitutive*.

---

## 4. Metrics

### Primary metric

**90-day churn rate** — proportion of customers who churn within 90 days of enrolment
into the experiment.

- Measured at the customer level (binary outcome: churned = 1, retained = 0)
- Observation period: 90 days from randomisation date

### Secondary metrics

| Metric | Purpose |
|---|---|
| Integration connect rate (30-day) | Measures whether the intervention drives activation behaviour |
| Feature adoption score (60-day) | Captures broader product engagement uplift |
| CS outreach conversion rate | Touch 1 email open + call acceptance rate — measures intervention delivery |
| Support ticket volume (30-day) | Negative outcome check — intervention should not increase support load |

### Guardrail metrics (stop if violated)

- **P(harm) > 0.10**: If posterior probability of treatment *increasing* churn exceeds 10%,
  stop experiment and review intervention design.
- **CS capacity breach**: If treatment arm CS call acceptance > 80%, throttle assignment rate.

---

## 5. Minimum Detectable Effect (MDE) and Sample Size

### Prior belief

From survival analysis:

- Starter tier 90-day churn rate (baseline): **~33%** (KM estimate at day 90)
- Growth tier 90-day churn rate (baseline): **~15%**

### Target MDE

**5 percentage-point absolute reduction** (e.g., 33% → 28% for starter tier).

Business context: A 5pp reduction on 500 starter accounts with $800 avg MRR = $240K ARR
saved per quarter — well above the programme cost threshold.

### Frequentist sample size (for reference)

Using `scipy.stats.norm` power analysis (alpha=0.05, power=0.80, one-tailed):

```
Baseline = 0.33, MDE = 0.05 (absolute), alpha = 0.05, power = 0.80
Required n per arm ≈ 340
```

At a typical B2B CS programme scale of **40–60 at-risk customers per quarter**, this
means a frequentist test would take **5–8 quarters** to reach significance. This is
why the Bayesian approach is used instead.

### Bayesian sample size

Using a Beta-Bernoulli conjugate model with an informative prior `Beta(2, 8)` (encoding
a prior belief that baseline churn ≈ 20%):

| n per arm | P(treatment > control) for 5pp effect |
|---|---|
| 20 | ~0.71 |
| 40 | ~0.82 |
| 60 | ~0.88 |
| 80 | ~0.92 |
| 100 | ~0.95 |

**Recommended minimum:** **n = 60 per arm** to achieve ≥ 88% confidence that a real
5pp effect is detected. This is achievable in 1–2 quarters for starter tier.

See `notebooks/bayesian_ab_test_simulation.ipynb` for the full simulation.

---

## 6. Bayesian Decision Framework

### Prior specification

`Beta(α=2, β=8)` — informative prior encoding the belief that baseline churn ≈ 20%.

**Defensibility:** The prior is based on the synthetic data (enterprise + growth
blended rate) and is intentionally conservative (slightly lower than the starter-specific
baseline) to avoid over-claiming intervention benefit.

### Posterior update

After observing `s` successes (retentions) and `f` failures (churns) in each arm:

```
Posterior = Beta(α + s, β + f)
```

### Decision criteria

| Outcome | Decision |
|---|---|
| P(treatment > control) ≥ 0.90 | Declare intervention effective; expand to full CS team |
| P(treatment > control) ∈ [0.70, 0.90) | Inconclusive; extend for one more quarter |
| P(treatment > control) < 0.70 | Intervention not effective at this scale; redesign |
| P(harm) > 0.10 | Stop immediately; review intervention design |

### Credible interval requirement

Report **95% credible interval for the absolute churn rate difference** alongside
P(treatment > control). A wide CI even with high P(treatment > control) should prompt
caution — it means high confidence in direction but uncertainty about magnitude.

---

## 7. Experiment Governance

### Approval gate

The experiment design is reviewed and approved by:
- **VP of Customer Success** — accountable for CS resource allocation
- **Head of Data** — responsible for statistical methodology
- **Legal/Compliance** — confirms control arm customers receive standard support SLA

### Blinding

- CS reps executing outreach are **not blinded** (they must know which customers to contact)
- CS reps reviewing outcome data are **blinded** to treatment assignment during analysis
- A dedicated analyst (not involved in CS delivery) runs the posterior update

### Cadence

- **Week 2:** Interim safety check — review guardrail metrics (P(harm), CS capacity)
- **Week 8:** Mid-point posterior update — share with CS leadership for early readouts
- **Week 13:** Final posterior report — primary decision point

### Data capture

Required data fields to be logged to DuckDB per customer:

| Field | Source |
|---|---|
| `experiment_id` | Assignment system |
| `customer_id` | CRM |
| `arm` | treatment \| control |
| `assignment_date` | Assignment system |
| `churned_90d` | Warehouse (computed at day 90) |
| `integration_connects_30d` | Usage events table |
| `feature_adoption_score_60d` | Usage events table |
| `cs_touches_delivered` | CS outreach log |

### Human-in-the-loop gate

Before any posterior-driven decision changes the CS SOP, results are reviewed by
a human analyst and VP of CS. No automated decision rule triggers SOP changes
without sign-off.

---

## 8. Limitations and Risks

| Risk | Mitigation |
|---|---|
| SUTVA violation (control customers receive treatment info from treated peers) | Randomise at account level, not user level; monitor cross-contamination |
| Novelty effect (CS team more attentive during experiment) | Measure CS activity rates in control arm; flag if elevated |
| Selection bias in risk scoring (model assigns wrong customers to experiment) | Validate risk score distribution is balanced between arms at assignment |
| Regression to the mean | Ensure assignment is based on a forward-looking risk score, not a recent spike |

---

## 9. Reporting Template

At the end of the experiment, the report must include:

1. **Assignment summary:** n per arm, balance check on key covariates (tier, MRR, tenure)
2. **Primary outcome:** Posterior distribution plot (control vs. treatment), P(treatment > control), 95% CI for absolute effect
3. **Secondary outcomes:** Integration rate, adoption score delta, ticket volume
4. **Guardrail check:** Was P(harm) ever > 0.10?
5. **Business interpretation:** ARR impact at 95% CI lower bound (conservative case)
6. **Recommendation:** Expand / extend / redesign + rationale

---

*For the simulation validating this design, see:*
*`notebooks/bayesian_ab_test_simulation.ipynb`*
