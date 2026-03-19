# Expansion Propensity Methodology

## NRR Strategy Context

**Net Revenue Retention (NRR)** has two components:

| Component | Model | Goal |
|-----------|-------|------|
| Churn prevention | `churn_model` | Keep existing ARR |
| Expansion revenue | `expansion_model` | Grow ARR within existing accounts |

A SaaS business with 100% NRR merely replaces churned ARR. A business with 120% NRR grows even if it acquires zero new customers. The expansion propensity module directly attacks the second component.

**Why this matters for Dropbox-style product metrics:** The classic B2B SaaS growth motion is land-and-expand — acquire at a lower tier, prove value, upgrade to the next. The expansion model identifies the "expand" signal before Sales has to guess which accounts are ready.

---

## `mrr_tier_ceiling_pct` — Tier Pressure

The most novel of the 5 expansion features. It answers the question: **"How much of their current tier's capacity has this customer already consumed?"**

```
mrr_tier_ceiling_pct = (mrr − tier_floor) / (tier_ceiling − tier_floor)
```

| Plan tier | Floor | Ceiling |
|-----------|-------|---------|
| Starter | $500/mo | $2,000/mo |
| Growth | $2,000/mo | $8,000/mo |
| Enterprise | $8,000/mo | $50,000/mo |

**Interpretation:**
- 0.0 = Customer just entered this tier (plenty of headroom)
- 1.0 = Customer is at the top of their tier — the natural trigger for an upgrade conversation
- > 0.8 = Tier-pressure zone — combine with premium trial signal for high-confidence expansion

**Why it beats raw MRR:** A $7,500/mo Growth customer has 92% tier pressure and is nearly ready for Enterprise. A $48,000/mo Enterprise customer at 95% pressure is due for a CUSTOM expansion conversation. Raw MRR conflates these two very different signals.

---

## Propensity Quadrant Interpretation

The Propensity Quadrant plots all active customers on two axes:

- **X-axis:** Churn probability (from `churn_model`)
- **Y-axis:** Upgrade propensity (from `expansion_model`)

Four action quadrants:

```
High Propensity │ Growth Engines  │ Flight Risks
                │ (Low Churn,     │ (High Churn,
                │  High Expansion)│  High Expansion)
────────────────┼─────────────────┼─────────────────
Low Propensity  │ Stable Base     │ Churn Candidates
                │ (Low Churn,     │ (High Churn,
                │  Low Expansion) │  Low Expansion)
                └─────────────────┴─────────────────
                  Low Churn         High Churn
```

### Growth Engines (top-left)
Low churn risk + high expansion propensity. **Primary target for upgrade campaigns.** Schedule QBR with upgrade conversation agenda. These accounts have proven the platform's value and are organically asking for more.

### Flight Risks (top-right)
High churn risk + high expansion propensity. **Counterintuitive danger zone.** Do NOT start an upsell motion — upselling a churning customer accelerates churn. Senior Exec intervention required: fix the underlying issue first (usually onboarding friction or integration failure), then revisit expansion in 60–90 days.

### Stable Base (bottom-left)
Low churn + low expansion. Healthy but not growing. Nurture via product-led expansion signals: in-app prompts for premium features, peer benchmarking, feature adoption campaigns.

### Churn Candidates (bottom-right)
High churn + low expansion. Retention priority. No expansion conversation warranted. Focus CS effort on support quality and compliance gap remediation.

---

## ARR Uplift Formula

```
expected_arr_uplift = (MRR × 12) × (multiplier − 1) × propensity
```

**Why `(multiplier − 1)`:** A 3× jump from Starter to Growth is a 200% increase. The *net* uplift is 2× current ARR, not 3×. Using `(multiplier − 1)` captures only the additional revenue, making the figure defensible in a VP review where double-counting is scrutinised.

**Why probability-weighted:** A 100% propensity at $10k expected uplift is worth more Sales time than a 15% propensity at the same amount. The weighted figure integrates both dimensions into a single prioritisation metric.

### Tier multipliers

| Tier | Multiplier | Rationale |
|------|-----------|-----------|
| Starter → Growth | 3.0× | ~$1k → ~$3k MRR median ACV jump |
| Growth → Enterprise | 5.0× | ~$5k → ~$25k MRR — largest tier leap |
| Enterprise → Custom | 1.2× | Seat/add-on upsell, not a full tier flip |
| Custom → (ceiling) | 0.0× | No automated propensity above this |

---

## Conflict Resolution: Churn vs. Expansion

When both models are available (via `/customers/{id}/360`), the conflict matrix prevents harmful upsell motions:

| Churn Risk | Expansion Propensity | Action |
|------------|---------------------|--------|
| Low (< 0.25) | High (≥ 0.50) | Growth Engine — schedule upgrade conversation |
| High (≥ 0.50) | High (≥ 0.50) | ⚠️ Flight Risk — Exec intervention required |
| High (≥ 0.50) | Low (< 0.25) | Retention priority — defer expansion |
| Low (< 0.25) | Low (< 0.25) | Stable Base — nurture via product signals |

This logic lives in `ExpansionResult.recommended_action(churn_probability=...)` — it is deterministic domain code, not an LLM output.
