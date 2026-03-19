# Economic Model — NRR Impact of SaaSGuard

SaaSGuard attacks Net Revenue Retention from both sides: preventing churn and capturing expansion. This document is the financial bridge between the two propensity models.

---

## NRR Formula

```
NRR = (ARR_start + ARR_expansion − ARR_churn) / ARR_start
```

Best-in-class SaaS companies achieve NRR > 120%. The median for B2B SaaS is ~104%.
SaaSGuard targets a **+2–4 NRR point improvement** on a $200M ARR base.

---

## Churn-Only Baseline (from `roi-calculator.md`)

| Scenario | Churn reduction | ARR protected |
|----------|----------------|---------------|
| Conservative | 0.5% | $1.0M |
| Base case | 1.0% | $2.0M |
| Optimistic | 1.5% | $3.0M |

Platform cost: **$150K/year**. Payback period in base case: **< 1 month.**

---

## Expansion Addendum — P(upgrade in 90d) Model

The expansion propensity model (v0.9.0, AUC=0.928) scores all active non-upgraded
customers. The **top-10% propensity decile** is the intervention cohort.

**Expected uplift formula** (mirrors `TargetTier.calculate_expected_uplift()`):

```
expected_arr_uplift = (MRR × 12) × (tier_multiplier − 1) × upgrade_propensity
```

Tier multipliers from the domain model:

| From tier | To tier | Multiplier |
|-----------|---------|------------|
| Starter | Growth | 3.0× |
| Growth | Enterprise | 5.0× |
| Enterprise | Custom | 1.2× |

**Expansion scenario inputs (base case):**

- Active expansion candidates: ~3,000 customers
- Top-10% decile: ~300 customers
- Mean propensity in decile: ~0.65
- Assumed CS conversion rate: 25% of flagged accounts

**Captured ARR uplift:** ~$1.2M (base case, 25% conversion)

The sensitivity analysis below shows conversion rate is the primary lever.

---

## Combined NRR Scenario Table

| Scenario | Churn reduction | Expansion capture | Total NRR impact |
|----------|----------------|-------------------|-----------------|
| **Conservative** | $1.0M | $0.5M | **$1.5M** |
| **Base case** | $2.0M | $1.2M | **$3.2M** |
| **Optimistic** | $3.0M | $2.5M | **$5.5M** |

> All figures on $200M ARR base. Expansion at 25% conversion rate (base), 15% (conservative), 40% (optimistic).

---

## Payback Period

```
Platform cost:        $150,000 / year
Base case NRR impact: $3,200,000 / year

Payback = $150,000 / ($3,200,000 / 12) = 0.56 months ≈ 17 days
```

The platform pays for itself in under 30 days in the base case.

---

## Sensitivity Analysis — Key Lever: Conversion Rate

The expansion model's ROI is most sensitive to the CS conversion rate (the % of
flagged accounts that actually upgrade following outreach).

| Conversion rate | Captured ARR uplift | Total NRR (base churn) |
|----------------|--------------------|-----------------------|
| 10% | $0.48M | $2.48M |
| 15% | $0.72M | $2.72M |
| **25% (base)** | **$1.20M** | **$3.20M** |
| 35% | $1.68M | $3.68M |
| 40% | $1.92M | $3.92M |

**Insight:** A 10-percentage-point swing in conversion rate = ±$480K in expansion ARR.
The SHAP explanation layer ("here's why this customer is ready to upgrade") is the
primary driver of higher conversion — CS arrives on the call with data, not gut feel.

---

## What Changes Operationally

| Without SaaSGuard | With SaaSGuard |
|---|---|
| AE pursues expansion opps based on deal size | AE prioritises by propensity × ARR uplift |
| CS + Sales work in silos — churn risk invisible to AEs | Conflict matrix routes "Flight Risk" customers to CS first |
| Expansion pipeline has ~30% conversion leakage from churn-risk accounts | Rescue & Expand quadrant routes to CS before AE |
| No measurable expansion attribution | `/predictions/upgrade` endpoint tracks propensity over time |

---

## Sources

- Expansion model metrics: `docs/expansion-model-card.md`
- ROI methodology: `docs/roi-calculator.md`
- Domain logic: `src/domain/expansion/value_objects.py` — `TargetTier.calculate_expected_uplift()`
- Benchmark: *"B2B SaaS median NRR is 104%; top quartile exceeds 120%"* — SaaStr Annual 2025
