# Growth Analytics Framework — SaaSGuard

Maps the customer lifecycle to the four bounded contexts in SaaSGuard's DDD architecture, grounding each stage in real VoC evidence.

---

## Framework Diagram

```mermaid
flowchart LR
    subgraph A["① ACTIVATION\ncustomer_domain"]
        A1[Signup + plan_tier set]
        A2[First evidence_upload\nor monitoring_run]
        A3[is_early_stage = TRUE\ntenure_days ≤ 90]
    end

    subgraph B["② ENGAGEMENT\nusage_domain"]
        B1[integration_connect events\n→ deep product embedding]
        B2[feature_adoption_score\ntrend rising or falling]
        B3[monitoring_run cadence\nestablished]
    end

    subgraph C["③ RETENTION\nprediction_domain"]
        C1[Churn model scores\nall active customers daily]
        C2[Risk score: compliance_gap\n+ usage_decay + vendor_flags]
        C3[CS outreach triggered\nat threshold ≥ 0.5]
    end

    subgraph D["④ EXPANSION\ngtm_domain"]
        D1[Open opportunities\nlinked to retained accounts]
        D2[Revenue-at-risk flag\nif churn prob high + opp open]
        D3[NRR uplift from\nearly-retained customers]
    end

    A --> B --> C --> D
    C -- "SHAP: days_since_last_event\nhigh_priority_tickets spike" --> B
    C -- "SHAP: is_early_stage\navg_adoption_score low" --> A
```

---

## Stage Definitions & Evidence

### Stage 1: Activation — `customer_domain`

**Definition:** Customer goes from signed contract to first meaningful product outcome.

**Critical window:** First 90 days (`is_early_stage = TRUE`). This is where 20–25% of voluntary churn originates.

**Real VoC evidence:**
> *"Getting started felt a bit nebulous, and there's limited direction on where to focus first."*
> — Secureframe user, G2 reviews

> *"Vanta lacked engagement and guidance — left us managing our SOC audit manually."*
> — Vanta user, via 6clicks.com verified review analysis, 2025

**Leading metric:** First `evidence_upload` or `monitoring_run` event within 14 days of signup.
**Churn signal:** No activation event in first 14 days → `is_early_stage` + low `feature_adoption_score` → top SHAP driver.

---

### Stage 2: Engagement — `usage_domain`

**Definition:** Customer establishes a recurring usage pattern. Depth (integrations) matters more than breadth (page views).

**Critical signals:**
- `integration_connect` event: strongest single retention signal — customers who connect ≥3 integrations in first 30 days have dramatically lower churn
- `monitoring_run` cadence: weekly runs → healthy; gaps >14 days → early decay signal
- `feature_adoption_score` trend: rising = expanding use; flat or declining = disengagement

**Real VoC evidence:**
> *"Some integrations felt clunky and required extra effort to set up or troubleshoot, which slowed down the process."*
> — Vanta user, Complyjet verified reviews, 2025

> *"Most of the tools I've used export .csv files for their 'evidence' and no auditor I've talked to will accept them — they want screenshots."*
> — GRC practitioner, Reddit r/netsec, collected via CyberSierra, 2024

**Leading metric:** `retention_signal_count` (integration_connect + api_call + monitoring_run events in first 30 days).

---

### Stage 3: Retention — `prediction_domain`

**Definition:** Customer successfully renews. SaaSGuard's core intervention point.

**Model inputs from prior stages:**
- From Activation: `tenure_days`, `is_early_stage`, `avg_adoption_score`
- From Engagement: `events_last_30d`, `days_since_last_event`, `retention_signal_count`
- From Support: `tickets_last_30d`, `high_priority_tickets`
- From Risk: `compliance_gap_score`, `vendor_risk_flags`

**Real VoC evidence:**
> *"The alert system has been described as overwhelming at times. Users get alarm fatigue and end up ignoring most notifications."*
> — 6clicks.com verified Vanta review analysis, 2025

> *"84% of B2B software buyers cite excellent customer support when deciding on renewals."*
> — Serpsculpt B2B Retention Statistics, 2025

**KPI:** CS intervention conversion rate (target: ≥40% of outreaches result in confirmed retention).

---

### Stage 4: Expansion — `gtm_domain`

**Definition:** Retained customer upgrades plan tier, adds seats, or buys additional frameworks.

**SaaSGuard's role:**
- Surfaces revenue-at-risk when an open expansion opportunity exists for a high-churn-risk customer
- CS team prioritises save over expansion until churn risk drops below threshold
- Retained customers generate NRR uplift (+25% with formal CS programs, per Benchmarkit 2025)

**Real VoC evidence:**
> *"Companies with formal customer success teams retain customers at higher rates, with firms having dedicated CSMs seeing up to 25% higher NRR than those without."*
> — Benchmarkit / Vitally, 2025

> *"The first 30–90 days after signup are the most important in defining account lifetime value — customers retained past 90 days expand at 3× the rate of those who nearly churned."*
> — Churnfree, B2B SaaS Benchmarks 2026

**Leading metric:** Open `gtm_opportunities` with `stage = proposal` or `qualification` linked to customers with `churn_probability < 0.25`.

---

## Metrics by Stage

| Stage | Input metric | Target | Owned by |
|---|---|---|---|
| Activation | % customers with first event ≤14 days | >80% | Product / CS |
| Engagement | % customers with ≥3 integrations in 30 days | >60% | Product |
| Retention | Churn probability AUC-ROC | ≥0.85 | Data Science |
| Retention | CS intervention conversion rate | ≥40% | CS |
| Expansion | Open opps for churn-safe customers (prob < 0.25) | >70% of pipeline | GTM |

---

## Sources

- [B2B Customer Retention Statistics 2025 — Serpsculpt](https://serpsculpt.com/b2b-customer-retention-statistics/)
- [Understanding Vanta's Limitations — 6clicks](https://www.6clicks.com/resources/blog/understanding-vantas-limitations-insights-from-real-user-experiences)
- [Vanta Review 2025 — Complyjet](https://www.complyjet.com/blog/vanta-reviews)
- [Top GRC Platforms 2025 — CyberSierra](https://cybersierra.co/blog/top-grc-platforms-2025/)
- [Drata vs. Vanta vs. Secureframe — Silent Sector](https://silentsector.com/blog/drata-vs-vanta-secureframe)
