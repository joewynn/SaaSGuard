-- =============================================================================
-- DASHBOARD: Uplift Simulator
-- What-if analysis: how much ARR can CS recover by intervening on top-N customers?
-- Assumes 10% / 15% / 20% churn reduction from CS intervention.
-- =============================================================================


-- ── Chart 1: Cumulative ARR recovery vs accounts targeted ────────────────────
-- Line chart showing diminishing returns as more accounts are added to outreach
-- Ordered by highest ARR at risk first (optimal intervention order)
SELECT
    ROW_NUMBER() OVER (ORDER BY arr_at_risk DESC)    AS accounts_targeted,
    customer_id,
    risk_tier,
    ROUND(arr_at_risk, 0)                             AS arr_at_risk_individual,
    ROUND(SUM(arr_at_risk) OVER (
        ORDER BY arr_at_risk DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ), 0)                                             AS cumulative_arr_at_risk,
    -- Estimated recoverable ARR at three intervention effectiveness levels
    ROUND(SUM(arr_at_risk * 0.10) OVER (
        ORDER BY arr_at_risk DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ), 0)                                             AS recoverable_arr_10pct,
    ROUND(SUM(arr_at_risk * 0.15) OVER (
        ORDER BY arr_at_risk DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ), 0)                                             AS recoverable_arr_15pct,
    ROUND(SUM(arr_at_risk * 0.20) OVER (
        ORDER BY arr_at_risk DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ), 0)                                             AS recoverable_arr_20pct,
    mrr,
    plan_tier,
    churn_score
FROM marts.mart_customer_risk_scores
WHERE risk_tier IN ('critical', 'high', 'medium')
ORDER BY arr_at_risk DESC
LIMIT 500
;


-- ── Chart 2: Intervention ROI – top-N thresholds ─────────────────────────────
-- Table: top-10 / top-25 / top-50 / top-100 customer buckets
WITH ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (ORDER BY arr_at_risk DESC) AS rank_by_impact
    FROM marts.mart_customer_risk_scores
    WHERE risk_tier IN ('critical', 'high')
),
buckets AS (
    SELECT 10 AS cohort_size UNION ALL
    SELECT 25 UNION ALL
    SELECT 50 UNION ALL
    SELECT 100
)
SELECT
    b.cohort_size                               AS top_n_customers,
    ROUND(SUM(r.arr_at_risk), 0)               AS total_arr_at_risk,
    ROUND(SUM(r.arr_at_risk * 0.10), 0)        AS recoverable_10pct,
    ROUND(SUM(r.arr_at_risk * 0.15), 0)        AS recoverable_15pct,
    ROUND(SUM(r.arr_at_risk * 0.20), 0)        AS recoverable_20pct,
    COUNT(*)                                    AS actual_customer_count,
    ROUND(AVG(r.churn_score) * 100, 1)         AS avg_churn_score_pct,
    -- Assuming $300 CSM cost per intervention hour, 2 hours per account
    b.cohort_size * 300 * 2                    AS intervention_cost_usd,
    ROUND((SUM(r.arr_at_risk * 0.10) - (b.cohort_size * 600)) / NULLIF(b.cohort_size * 600, 0) * 100, 1) AS roi_10pct
FROM ranked r
JOIN buckets b ON r.rank_by_impact <= b.cohort_size
GROUP BY b.cohort_size
ORDER BY b.cohort_size
;


-- ── Chart 3: Segment-level uplift opportunity ────────────────────────────────
-- Which plan_tier × industry combos have highest recoverable ARR?
SELECT
    plan_tier,
    industry,
    COUNT(*)                                   AS at_risk_customers,
    ROUND(SUM(arr_at_risk), 0)                 AS total_arr_at_risk,
    ROUND(SUM(arr_at_risk * 0.15), 0)          AS recoverable_arr_15pct,
    ROUND(AVG(churn_score) * 100, 1)           AS avg_churn_pct,
    ROUND(AVG(mrr), 0)                         AS avg_mrr
FROM marts.mart_customer_risk_scores
WHERE risk_tier IN ('critical', 'high')
GROUP BY plan_tier, industry
ORDER BY total_arr_at_risk DESC
LIMIT 15
;


-- ── Chart 4: KPI summary – total recoverable ARR ─────────────────────────────
SELECT
    COUNT(*)                                    AS at_risk_customers,
    ROUND(SUM(arr_at_risk), 0)                  AS total_arr_at_risk,
    ROUND(SUM(arr_at_risk * 0.10), 0)           AS recoverable_arr_10pct,
    ROUND(SUM(arr_at_risk * 0.15), 0)           AS recoverable_arr_15pct,
    ROUND(SUM(arr_at_risk * 0.20), 0)           AS recoverable_arr_20pct,
    -- Payback ratio: recoverable ARR / intervention cost (top 50 accounts)
    ROUND(SUM(arr_at_risk * 0.15) / NULLIF(50 * 600, 0), 1) AS payback_ratio_top50
FROM marts.mart_customer_risk_scores
WHERE risk_tier IN ('critical', 'high')
;


-- ── Chart 5: Early-stage intervention value ───────────────────────────────────
-- Business context: 20–25% of churn occurs in first 90 days (Phase 1 finding)
SELECT
    is_early_stage,
    COUNT(*)                                    AS customer_count,
    ROUND(AVG(churn_score) * 100, 1)           AS avg_churn_pct,
    ROUND(SUM(arr_at_risk), 0)                  AS total_arr_at_risk,
    ROUND(SUM(arr_at_risk * 0.15), 0)           AS recoverable_15pct,
    ROUND(AVG(integration_connects_first_30d), 1) AS avg_onboarding_integrations
FROM marts.mart_customer_risk_scores
WHERE risk_tier IN ('critical', 'high', 'medium')
GROUP BY is_early_stage
;
