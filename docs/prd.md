# Product Requirements Document — SaaSGuard

**Version:** 1.0.0
**Status:** Approved
**Owner:** Joseph M
**Last updated:** 2026-03-14

---

## Problem Statement

B2B compliance/GRC SaaS platforms are haemorrhaging customers in the first 90 days — not because the product is bad, but because CS teams have no early signal to act on.

Real customer evidence (see `stakeholder-notes.md`):

- >90% of customers say onboarding could be better *(Vitally, 2025)*
- >20% of voluntary churn is directly linked to poor onboarding *(Recurly, 2025)*
- 84% of B2B buyers cite support quality as a renewal factor *(Serpsculpt, 2025)*
- Customers who complete ≥3 product integrations in first 30 days retain at dramatically higher rates

CS teams currently rely on gut feel, account age, and support ticket volume. By the time a customer is visibly disengaged, it is too late to intervene cost-effectively.

---

## Proposed Solution

SaaSGuard is a churn and risk prediction layer that sits on top of existing product telemetry, CRM, and support data. It gives CS teams a 60–90 day early warning with:

1. **Churn probability score** — P(churn in next 90 days) per customer, updated daily
2. **Risk score** — composite of usage decay, compliance gap, and vendor risk signals
3. **Explainability** — top 5 SHAP drivers so CS knows what to say on the intervention call
4. **Recommended action** — plain-English CS instruction (escalate / watch list / no action)
5. **Executive summaries** — AI-generated Llama-3 account briefs for CSM call prep

---

## Success Metrics

| Metric | Baseline (industry) | SaaSGuard Target |
|---|---|---|
| 90-day churn rate (starter tier) | ~20–25% | Reduce by 15% relative |
| Time CS receives churn signal | At cancellation | ≥60 days before predicted churn |
| CS intervention conversion rate | Unknown / unmeasured | ≥40% of outreaches retained |
| Model AUC-ROC | N/A | ≥0.85 on held-out test set |
| Revenue protected (demo scenario) | — | $2M+ on $200M ARR |

---

## Scope

### In scope

- Synthetic data pipeline (5,000 customers, 5 tables) with realistic churn correlations
- dbt transformation layer over DuckDB
- XGBoost + survival analysis churn model with SHAP explanations
- Risk score model (compliance gap + usage decay + vendor flags)
- FastAPI serving layer with `/predictions/churn` and `/predictions/risk-score`
- Apache Superset Customer 360 dashboard
- Llama-3 executive summary generator with hallucination guardrails
- Change management deck for CS team rollout

### Out of scope (v1.0)

- Real-time event streaming (Kafka/Kinesis) — batch daily refresh is sufficient
- Self-serve customer portal
- Multi-tenant SaaS deployment
- Native CRM integration (Salesforce/HubSpot) — API-first, CRM integration is a v2 feature

---

## Personas

### Primary: Customer Success Manager (CSM)

- **Goal:** Know which customers to call this week, and what to say
- **Pain:** Currently relies on gut feel + support ticket count; no structured signal
- **How SaaSGuard helps:** Daily ranked list of at-risk customers with SHAP-driven talking points

### Secondary: VP of Customer Success

- **Goal:** Understand portfolio-level churn risk and report to board
- **How SaaSGuard helps:** Superset dashboard with churn heatmap + revenue-at-risk view

### Tertiary: CTO / CPO

- **Goal:** Validate ROI of SaaSGuard investment
- **How SaaSGuard helps:** AI executive summary + ROI calculator output

---

## Assumptions & Constraints

- Synthetic data used for all development and demo; no real customer PII
- Model retraining cadence: monthly or when AUC drops below 0.80
- LLM summaries require human review before any customer-facing use
- DuckDB file size stays manageable for a single-node demo (<2GB)

---

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Model bias by industry or plan tier | Medium | Fairness audit by cohort |
| Alert fatigue (too many CS outreaches) | Medium | Precision threshold tuning; ≥40% conversion gate |
| LLM hallucination in summaries | Low-Medium | Human-in-loop gate + confidence disclaimer |
| Data staleness reducing prediction quality | Low | DVC pipeline + freshness SLA checks in dbt |

---

## Expansion Propensity Addendum (v0.9.0)

**Last updated:** 2026-03-19

### Problem Extension

The original PRD addressed only the retention half of the NRR equation: who to save.
It left unanswered: *who is ready to buy more?*

CS and Sales operate independently. Sales pursues expansion based on deal size and
relationship. CS focuses on retention. Neither team has a signal for **which customers
are organically ready to upgrade** — leading to:

- Expansion conversations with customers who are silently at risk (high conversion
  leakage when churns follow weeks after upsell)
- Missed expansion opportunities with high-propensity customers who never receive an
  outreach because they're "not at risk"

### Solution Extension

A second propensity model — **P(upgrade in 90 days)** — running alongside the churn
model. Together they produce the **Propensity Quadrant**:

| Quadrant | churn_prob | upgrade_propensity | GTM Action |
|----------|-----------|-------------------|------------|
| Growth Engine | Low | High | Book expansion call immediately |
| Rescue & Expand | High | High | CS retention play first, then expand |
| Flight Risk | High | Low | Immediate CS intervention |
| Stable | Low | Low | Nurture / self-serve |

**New API endpoint:** `POST /predictions/upgrade` → `UpgradePredictionResponse`
(upgrade_propensity, target_tier, expected_arr_uplift, top_shap_features, recommended_action)

### New Success Metrics

| Metric | Target |
|--------|--------|
| Expansion model AUC-ROC | ≥ 0.75 (achieved: 0.928) |
| Precision at top-10% decile | ≥ 20% (achieved: 21.7%) |
| Top-10% decile ARR captured | ≥ $1M at 25% conversion |
| Combined NRR impact (base case) | $3.2M ($2M churn + $1.2M expansion) |

### New Personas

**Sales AE — `POST /predictions/upgrade`**
> "Show me which of my accounts are organically ready to expand — I want to call them
> before they come to me. Give me the top reason why they're ready and the expected
> deal size."

**RevOps — Propensity Quadrant Dashboard**
> "I need a single view that tells me which accounts Sales should work, which CS should
> own, and which are at risk of being poached into an expansion conversation before
> the retention risk is resolved."

### Expansion Features (5 new, on top of 15 churn features)

| Feature | Signal |
|---------|--------|
| `premium_feature_trials_30d` | Customer trialling above-tier features → intent to upgrade |
| `feature_request_tickets_90d` | Requesting capabilities they don't have → tier pressure |
| `has_open_expansion_opp` | Sales already aware → coordinate, don't duplicate |
| `expansion_opp_amount` | Size of identified opportunity |
| `mrr_tier_ceiling_pct` | How close current MRR is to top of their tier |
