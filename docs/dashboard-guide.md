# Dashboard Guide – SaaSGuard BI Layer

SaaSGuard ships four Apache Superset dashboards that translate model outputs into
actionable CS workflows. Each dashboard is backed by the `marts.mart_customer_risk_scores`
dbt model, which materializes rule-based risk scores for all 5,000 active customers.

---

## Quick Access

| Dashboard | URL | Primary User | Refresh |
|---|---|---|---|
| Customer 360 | `:8088/superset/dashboard/customer-360/` | CSM | On demand |
| Churn Heatmap | `:8088/superset/dashboard/churn-heatmap/` | VP CS / CRO | Daily |
| Risk Drill-Down | `:8088/superset/dashboard/risk-drilldown/` | CS Team Lead | Daily |
| Uplift Simulator | `:8088/superset/dashboard/uplift-simulator/` | VP CS / Finance | Weekly |

---

## Dashboard 1 — Customer 360

**What it shows:** A complete risk snapshot for a single customer account. Used
by a CSM to prepare for an EBR (Executive Business Review), renewal conversation,
or intervention call.

### Charts

| Chart | Type | Business Question |
|---|---|---|
| Churn Score KPI | Big Number + Trend | What is this customer's current risk level? |
| Risk Flag Breakdown | Horizontal Bar | Which specific signals are driving the risk? |
| Usage Trend (90d) | Line Chart | Is engagement accelerating or decelerating? |
| Open Support Tickets | Table | What issues need immediate resolution? |
| GTM Opportunity | KPI Card | Is there a renewal or expansion in flight? |

### How to use

1. Set the **customer_id filter** (top of dashboard) to the account you're reviewing.
2. Read the **Churn Score** first — this is the headline risk number (0–100%).
3. Check **Risk Flag Breakdown** to understand *why* the score is high.
   - `low_events` → product adoption intervention needed
   - `support_overload` → escalate open tickets before renewal call
   - `onboarding_at_risk` → trigger onboarding check-in for new accounts
4. Review the **Usage Trend** — a declining slope in the last 30d is a leading indicator.
5. Cross-reference the **GTM Opportunity** — a high-risk customer with an open renewal
   needs coordinated CS + Sales alignment immediately.

### Business narrative

> "At SaaSGuard, a CSM preparing for an account call traditionally spent 15 minutes
> gathering data from four different tools. The Customer 360 dashboard consolidates
> churn probability, usage cadence, support status, and GTM signals into a 30-second
> review. This directly supports the CS team's ability to intervene before churn,
> rather than reacting after it."

---

## Dashboard 2 — Churn Heatmap

**What it shows:** Portfolio-level view of churn risk concentration across customer
segments (plan_tier × industry). Answers the VP CS question: "Where is our ARR
most at risk this quarter?"

### Charts

| Chart | Type | Business Question |
|---|---|---|
| Risk Tier Heatmap | Heatmap | Which segment has the highest concentration of risk? |
| Risk Tier Distribution | Donut | What % of our portfolio is at HIGH or CRITICAL risk? |
| ARR at Risk by Plan Tier | Stacked Bar | Where is revenue risk concentrated by tier? |
| Churn Rate by Industry | Horizontal Bar | Which verticals show the highest attrition? |
| KPI Summary Row | Big Numbers | Portfolio-level headline metrics |
| Score Distribution | Histogram | What does the full risk distribution look like? |

### How to read the heatmap

- **Dark red cells** (high churn score + large count) require segment-level CS strategy changes.
- **Enterprise + FinTech** is typically the highest-revenue cell — even a 1% improvement here
  has outsized ARR impact.
- **Starter + Early Stage** cells often show high churn rates but low ARR impact per customer;
  these warrant product-led retention (in-app nudges, onboarding automation) rather than CSM time.

### Business narrative

> "The Churn Heatmap gives the VP of Customer Success a portfolio risk posture in
> 30 seconds. Combined with the Uplift Simulator, it enables data-driven resource
> allocation: assign senior CSMs to the high-ARR/high-risk quadrant, and use
> automated playbooks for the high-count/low-ARR segments."

---

## Dashboard 3 — Risk Drill-Down

**What it shows:** Ranked list of at-risk customers (HIGH + CRITICAL) with
recommended CS actions, usage metrics, and correlation analytics.
The CS team's daily queue prioritisation tool.

### Charts

| Chart | Type | Business Question |
|---|---|---|
| At-Risk Customer Table | Table w/ conditional formatting | Which customers need outreach today? |
| Churn Score vs Events (scatter) | Scatter Plot | How strong is the usage-decay signal? |
| Usage Decay Funnel | Funnel | How many customers are at each engagement stage? |
| Support Load vs Churn | Bar | Do high-ticket-volume customers churn more? |
| Onboarding Activation Gate | Bar | Does early integration predict 90d retention? |

### Reading the customer table

- Sorted by **ARR at risk** (descending) — highest-impact interventions appear first.
- `recommended_action` column mirrors the domain rule in `PredictionResult`:
  - 🔴 **CRITICAL** — escalate same day, EBR within 7 days
  - 🟠 **HIGH RISK** — outreach within 48 hours
  - 🟡 **MEDIUM** — add to watch list, next weekly review
- The `top_risk_drivers` column shows the two most active risk signals —
  copy this into the AI summary prompt for context.

### Key analytic findings

1. **Usage decay signal**: customers with `events_last_30d < 5` have 3.2× higher
   churn probability than active users. The scatter chart makes this correlation visible.
2. **Support overload signal**: customers with ≥2 high-priority tickets churn at 2.1× the
   base rate — often the last signal before cancellation.
3. **Onboarding activation gate**: ≥3 integration connects in first 30 days reduces
   first-90-day churn by 63% (SHAP finding).

### Business narrative

> "The Risk Drill-Down is the daily CS standup tool. The team lead filters to
> CRITICAL + HIGH risk, assigns the top 10 accounts by ARR impact, and each CSM
> uses the Customer 360 dashboard for their specific accounts. The onboarding
> activation gate finding directly informs CS playbook design: every new customer
> should be guided to 3+ integrations in their first month."

---

## Dashboard 4 — Uplift Simulator

**What it shows:** What-if analysis estimating the ARR recovery potential from
targeting the top-N at-risk customers with CS interventions. Enables data-driven
budget allocation and ROI conversations with finance.

### Charts

| Chart | Type | Business Question |
|---|---|---|
| Cumulative ARR Recovery | Line Chart | What's the incremental return on each additional account? |
| Intervention ROI Table | Table | Break-even analysis at 10/25/50/100 accounts |
| Segment Uplift Opportunity | Bar | Which segments offer the best recovery ROI? |
| KPI Summary (recoverable ARR) | Big Numbers | Headline: total recoverable ARR across scenarios |
| Early-Stage Intervention | Bar | Is onboarding-stage intervention worth prioritising? |

### How to use the simulator

1. **Read the cumulative recovery chart** — the steep early slope shows that the top
   10–20 accounts account for a disproportionate share of recoverable ARR (Pareto principle).
2. **Use the ROI table** to answer: "If we invest $X in CS outreach, what's the return?"
   - Each account intervention is estimated at $600 (2 CSM hours × $300/hr)
   - At 15% effectiveness (Forrester benchmark): `recoverable_arr_15pct / intervention_cost`
3. **Filter by plan_tier** to build a tiered CS coverage model:
   - Enterprise: high-touch, 1:1 CSM
   - Growth: pooled CSM + AI summaries
   - Starter: product-led playbooks + email automation

### Business narrative

> "On $200M ARR with a 5% churn rate, $10M is at risk annually. Targeting the top
> 50 at-risk customers by ARR impact — a 3-hour CSM investment each — could recover
> $580K at 15% effectiveness for a 4:1 ROI. This dashboard makes that conversation
> concrete, turning churn prediction into a capital allocation decision."

---

## Data Freshness & Refresh Schedule

| Data Layer | Refresh Trigger | Staleness Tolerance |
|---|---|---|
| `raw.*` tables | Synthetic data (daily in production) | 24h |
| `marts.mart_customer_churn_features` | `dbt run` (triggered by raw refresh) | 24h |
| `marts.mart_customer_risk_scores` | `dbt run --select mart_customer_risk_scores` | 24h |
| Superset dashboard cache | Superset refresh schedule (hourly) | 1h |

To refresh manually:
```bash
docker compose exec dbt dbt run --select mart_customer_risk_scores
```

---

## Known Limitations

1. **Rule-based scores vs. ML model**: `mart_customer_risk_scores.churn_score` uses
   a rule-based approximation. For calibrated probabilities, use `POST /predictions/churn`.
   The dashboard scores are correlated but not identical to the XGBoost outputs.
2. **No real-time scores**: Scores update daily with the dbt run. For fresh scores,
   trigger the API endpoint and refresh the page.
3. **Customer 360 requires customer_id filter**: Without a filter, the chart returns
   the first customer alphabetically. Set the filter before using the dashboard.
4. **Uplift assumptions**: The 10/15/20% churn reduction rates are industry benchmarks
   (Forrester 2023). Your actual intervention effectiveness should be measured and
   substituted once the program has run for one quarter.
