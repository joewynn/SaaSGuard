# Stakeholder Research & Voice-of-Customer Notes

**Research method:** Aggregated from G2, Capterra, Software Advice, 6clicks.com analysis of Vanta/Drata/Secureframe reviews, Reddit (r/sysadmin, r/netsec, r/compliance), and published B2B SaaS churn benchmarks (Vitally, Recurly, Genesys Growth, Churnfree).

**Market:** B2B compliance/GRC SaaS platforms — direct analogues to SaaSGuard's feature set (evidence upload, monitoring runs, compliance gap scoring, vendor risk).

---

## Section 1 — Industry Churn Benchmarks (Quantified)

| Metric | Value | Source |
|---|---|---|
| Average B2B SaaS monthly churn | 3.5% | Vitally, 2025 |
| Voluntary churn linked to poor onboarding | >20% | Recurly / Vitally |
| New customer churn driven by first-90-day friction | ~70% | Churnfree, 2025 |
| Customers who say onboarding could be better | >90% | Genesysgrowth, 2025 |
| B2B buyers citing support quality as renewal factor | 84% | Serpsculpt B2B Retention Stats, 2025 |
| NRR uplift from dedicated CSMs vs. none | +25% | Benchmarkit / Vitally, 2025 |
| Retention uplift from structured onboarding | +25% (first year) | Churnfree, 2025 |
| Revenue protected per 1% churn reduction ($200M ARR) | $2M+ | SaaSGuard ROI model |

---

## Section 2 — Real Customer Quotes by Pain Category

### Pain 1: Onboarding is opaque — customers don't know where to start

> *"Getting started felt a bit nebulous, and there's limited direction on where to focus first."*
> — Secureframe user, G2 review (via Sprinto comparison, 2024)

> *"Some task instructions could be clearer and more comprehensive, in a bid for less back-and-forth."*
> — Secureframe user, G2 review (via Sprinto comparison, 2024)

> *"You cannot deviate from this onboarding process!"*
> — Drata user, G2 review (via Silent Sector comparison, 2024) — citing inflexibility during structured onboarding

> *"Vanta lacked engagement and guidance — left us managing our SOC audit manually."*
> — Vanta user, reported via 6clicks.com analysis of verified G2 reviews, 2024

**Pattern:** Across all three platforms, first-90-day activation friction is the primary churn driver. Customers who do not achieve a concrete compliance milestone in the first 30 days show measurably higher churn in the data.

---

### Pain 2: More manual input than the product implied

> *"Most of the tools I've used export .csv files for their 'evidence' and no auditor I've talked to will accept them — they want screenshots."*
> — r/netsec / r/sysadmin community, collected via web aggregation (cybersierr.co GRC discussion, 2024)

> *"How easy is it to onboard IT application owners on these tools so that they can add control-related evidence?"*
> — GRC practitioner, Reddit thread on compliance tool selection, 2024

> *"Some integrations felt clunky and required extra effort to set up or troubleshoot, which slowed down the process."*
> — Vanta user, Complyjet verified review compilation, 2025

> *"Some workflows aren't flexible enough and end up requiring manual handling outside the platform."*
> — Secureframe user, G2 review (via Sprinto comparison, 2024)

> *"Auditors were reluctant to use Drata — evidence was available in the platform but auditors still wanted us to walk them through all controls over video calls."*
> — Drata user, G2 review (via Silent Sector comparison, 2024)

**Pattern:** The integration-to-evidence workflow is the highest-friction step. Customers who complete ≥3 integration connections in the first 30 days retain at significantly higher rates — this is the `integration_connect` event type in SaaSGuard's schema and a top SHAP feature in the churn model.

---

### Pain 3: Very difficult to reach them when you have a problem

> *"Vanta's customer support leaves a lot to be desired — their limited support often results in clients being referred to a guide or asking an auditor for help."*
> — 6clicks.com analysis of verified Vanta G2 reviews, 2025

> *"There is no direct phone contact method. Users report lost documents, complaints about unauthorised charges, and challenges cancelling subscriptions."*
> — Complyjet Vanta Review, verified review analysis, 2025

> *"A customer success rep was not able to answer questions and had to schedule separate meetings for engineering experts."*
> — Drata user, G2 review (via Silent Sector comparison, 2024)

**Pattern:** Reactive support = churn accelerant. 84% of B2B buyers cite support quality as a renewal factor (Serpsculpt, 2025). Each high-priority support ticket in the 60 days before renewal is a statistically significant churn predictor — modelled as `high_priority_tickets` feature in `mart_customer_churn_features`.

---

### Pain 4: Alert fatigue leads to disengagement

> *"The alert system has been described as overwhelming at times, with minor or false-positive notifications. Users report not knowing how to efficiently triage Vanta notifications, getting alarm fatigue and ending up ignoring most notifications."*
> — 6clicks.com verified review analysis, 2025

> *"No matter what tool you pick, none of them can fix a screwed up process. Even with the supposed Cadillac tool, our control assessment process is a nightmare."*
> — Compliance practitioner, Reddit (r/sysadmin), collected via cybersierr.co, 2024

**Pattern:** Alert fatigue is a usage decay signal. Declining `monitoring_run` event frequency in weeks 4–8 after signup is a leading churn indicator — directly mapped to the `events_last_30d` and `days_since_last_event` features in the churn model.

---

### Pain 5: Billing surprises damage trust and accelerate cancellation

> *"One user reported being charged for a second year without permission after being told they would not renew."*
> — Complyjet Vanta Review, verified review analysis, 2025

> *"Another customer received an invoice reminder for a $15,600 auto-payment bill with no note specifying it would be auto-paid, and their card was charged on the due date."*
> — Complyjet Vanta Review, verified review analysis, 2025

> *"A Core plan can become a $30,000 bill with extras. Prices jump at 20, 50, or 100+ employees, and when layering in ISO 27001 or HIPAA alongside SOC 2."*
> — Complyjet Vanta Pricing Guide, 2025

**Pattern:** Billing friction is distinct from product friction but accelerates churn when combined with it. Customers on `starter` tier with declining adoption scores AND recent `billing` support tickets show the highest 90-day churn probability.

---

## Section 3 — Synthesised Pain Point → SaaSGuard Feature Map

| Pain Point | Evidence | SaaSGuard Counter-Signal |
|---|---|---|
| Opaque onboarding | Secureframe G2, Drata G2, Vanta G2 | `is_early_stage` flag + `events_last_7d` decay alert |
| Integration friction | Vanta Complyjet, r/netsec Reddit | `integration_connect` as top retention signal in model |
| Reactive support | Vanta 6clicks, Drata G2 | `high_priority_tickets` + `resolution_time` features |
| Alert fatigue / disengagement | Vanta 6clicks, Reddit r/sysadmin | `monitoring_run` decay + `days_since_last_event` feature |
| Billing surprises | Vanta Complyjet | `churn_date` patterns at renewal windows |

---

## Section 4 — KPI Definitions (Agreed Success Metrics)

| KPI | Definition | Target |
|---|---|---|
| Churn prediction accuracy | AUC-ROC on held-out test set | ≥ 0.85 |
| CS intervention lift | % churn reduction for flagged customers who received outreach | ≥ 10% |
| Time-to-signal | Days before churn that model flags customer | ≥ 60 days |
| Feature adoption score | % of customers completing ≥3 integrations in first 30 days | Baseline TBD |
| Alert precision | % of CS outreaches that result in confirmed retention | ≥ 40% |

---

## Sources

- [Vanta Review 2025: Features, Billing Traps, and User Reviews — Complyjet](https://www.complyjet.com/blog/vanta-reviews)
- [Vanta Pricing Guide 2025: Real Costs, ROI, and Hidden Fees — Complyjet](https://www.complyjet.com/blog/vanta-pricing-guide-2025)
- [Understanding Vanta's Limitations: Insights from Real User Experiences — 6clicks](https://www.6clicks.com/resources/blog/understanding-vantas-limitations-insights-from-real-user-experiences)
- [Drata vs. Vanta vs. Secureframe: Which Compliance Tool Is Best? — Silent Sector](https://silentsector.com/blog/drata-vs-vanta-secureframe)
- [Secureframe vs. Vanta vs. Drata — Sprinto](https://sprinto.com/blog/secureframe-vs-vanta-vs-drata/)
- [B2B SaaS Churn Rate Benchmarks: What's a Healthy Churn Rate in 2025? — Vitally](https://www.vitally.io/post/saas-churn-benchmarks)
- [B2B Customer Retention Statistics 2025 — Serpsculpt](https://serpsculpt.com/b2b-customer-retention-statistics/)
- [B2B SaaS Churn Rates — 33 Statistics — Genesys Growth](https://genesysgrowth.com/blog/saas-churn-rates-stats-for-marketing-leaders)
- [B2B SaaS Benchmarks: A Complete Guide 2026 — Churnfree](https://churnfree.com/blog/b2b-saas-churn-rate-benchmarks/)
- [Top GRC Platforms for Enterprise Compliance in 2025 — CyberSierra](https://cybersierra.co/blog/top-grc-platforms-2025/)
