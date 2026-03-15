-- =============================================================================
-- DASHBOARD: Churn Heatmap
-- Portfolio-level view of churn risk distribution across customer segments.
-- =============================================================================


-- ── Chart 1: Risk tier heatmap – plan_tier × industry ────────────────────────
-- Heatmap – colour = avg churn_score; size = customer_count
SELECT
    plan_tier,
    industry,
    COUNT(*)                        AS customer_count,
    ROUND(AVG(churn_score) * 100, 1) AS avg_churn_score_pct,
    ROUND(SUM(arr_at_risk), 0)       AS total_arr_at_risk,
    SUM(CASE WHEN risk_tier = 'critical' THEN 1 ELSE 0 END) AS critical_count,
    SUM(CASE WHEN risk_tier = 'high'     THEN 1 ELSE 0 END) AS high_count
FROM marts.mart_customer_risk_scores
GROUP BY plan_tier, industry
ORDER BY plan_tier, industry
;


-- ── Chart 2: Risk tier distribution – donut chart ────────────────────────────
SELECT
    risk_tier,
    COUNT(*)                              AS customer_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct_of_portfolio,
    ROUND(SUM(arr_at_risk), 0)            AS arr_at_risk_usd
FROM marts.mart_customer_risk_scores
GROUP BY risk_tier
ORDER BY
    CASE risk_tier
        WHEN 'critical' THEN 0
        WHEN 'high'     THEN 1
        WHEN 'medium'   THEN 2
        ELSE 3
    END
;


-- ── Chart 3: ARR at risk by plan tier – stacked bar ──────────────────────────
SELECT
    plan_tier,
    risk_tier,
    ROUND(SUM(arr_at_risk), 0)  AS arr_at_risk_usd,
    COUNT(*)                    AS customer_count
FROM marts.mart_customer_risk_scores
GROUP BY plan_tier, risk_tier
ORDER BY plan_tier,
    CASE risk_tier WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END
;


-- ── Chart 4: Churn rate by industry – horizontal bar ─────────────────────────
SELECT
    industry,
    COUNT(*)                                 AS total_customers,
    ROUND(AVG(churn_score) * 100, 1)         AS avg_churn_score_pct,
    SUM(CASE WHEN risk_tier IN ('critical', 'high') THEN 1 ELSE 0 END) AS at_risk_count,
    ROUND(SUM(arr_at_risk), 0)               AS total_arr_at_risk_usd
FROM marts.mart_customer_risk_scores
GROUP BY industry
ORDER BY avg_churn_score_pct DESC
;


-- ── Chart 5: KPI summary row ─────────────────────────────────────────────────
-- Big Numbers: total at-risk customers, total ARR at risk, avg churn score
SELECT
    COUNT(*)                                                 AS total_active_customers,
    SUM(CASE WHEN risk_tier IN ('critical','high') THEN 1 ELSE 0 END) AS at_risk_customers,
    ROUND(SUM(arr_at_risk), 0)                               AS total_arr_at_risk,
    ROUND(AVG(churn_score) * 100, 1)                         AS portfolio_avg_churn_pct,
    ROUND(SUM(mrr), 0)                                       AS total_mrr,
    ROUND(SUM(arr), 0)                                       AS total_arr
FROM marts.mart_customer_risk_scores
;


-- ── Chart 6: Churn score distribution – histogram ────────────────────────────
SELECT
    CASE
        WHEN churn_score < 0.10 THEN '0–10%'
        WHEN churn_score < 0.25 THEN '10–25%'
        WHEN churn_score < 0.50 THEN '25–50%'
        WHEN churn_score < 0.75 THEN '50–75%'
        ELSE '75–100%'
    END                             AS score_bucket,
    COUNT(*)                        AS customer_count,
    ROUND(SUM(mrr), 0)              AS mrr_in_bucket
FROM marts.mart_customer_risk_scores
GROUP BY 1
ORDER BY MIN(churn_score)
;
