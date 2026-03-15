-- =============================================================================
-- DASHBOARD: Risk Drill-Down
-- Actionable CS intervention list — at-risk customers ranked by ARR impact.
-- =============================================================================


-- ── Chart 1: At-risk customer table (main view) ───────────────────────────────
-- Table with conditional formatting: risk_tier → background colour
SELECT
    r.customer_id,
    r.plan_tier,
    r.industry,
    ROUND(r.mrr, 0)                AS mrr_usd,
    ROUND(r.arr, 0)                AS arr_usd,
    ROUND(r.churn_score * 100, 1)  AS churn_score_pct,
    r.risk_tier,
    ROUND(r.arr_at_risk, 0)        AS arr_at_risk_usd,
    r.events_last_30d,
    r.avg_adoption_score,
    r.high_priority_tickets,
    r.days_since_last_event,
    r.top_risk_drivers,
    r.tenure_days,
    -- CS recommended action (mirrors domain logic)
    CASE
        WHEN r.churn_score >= 0.75 THEN 'CRITICAL – Escalate to senior CSM. EBR within 7d.'
        WHEN r.churn_score >= 0.50 THEN 'HIGH RISK – Outreach within 48h. Review top drivers.'
        WHEN r.churn_score >= 0.25 THEN 'MEDIUM – Add to watch list. Schedule check-in.'
        ELSE                            'LOW RISK – Monitor monthly.'
    END                            AS recommended_action,
    -- Is there an active GTM opportunity?
    COALESCE(g.stage, 'none')      AS gtm_stage,
    COALESCE(ROUND(g.amount, 0), 0) AS gtm_amount_usd
FROM marts.mart_customer_risk_scores r
LEFT JOIN (
    SELECT DISTINCT ON (customer_id)
        customer_id, stage, amount
    FROM raw.gtm_opportunities
    WHERE stage NOT IN ('closed_won', 'closed_lost')
    ORDER BY customer_id, close_date DESC
) g USING (customer_id)
WHERE r.risk_tier IN ('critical', 'high')
ORDER BY r.arr_at_risk DESC
LIMIT 200
;


-- ── Chart 2: Scatter – churn_score vs events_last_30d ────────────────────────
-- Reveals the usage-decay → churn correlation (Phase 3 EDA finding #1)
SELECT
    customer_id,
    churn_score,
    events_last_30d,
    avg_adoption_score,
    risk_tier,
    mrr,
    plan_tier
FROM marts.mart_customer_risk_scores
ORDER BY churn_score DESC
LIMIT 500
;


-- ── Chart 3: Usage decay funnel ──────────────────────────────────────────────
-- Count of customers at each engagement level
SELECT
    CASE
        WHEN events_last_7d >= 5  THEN '1. Active (5+ events/7d)'
        WHEN events_last_7d >= 1  THEN '2. Engaged (1-4 events/7d)'
        WHEN events_last_30d >= 1 THEN '3. Declining (0/7d, activity/30d)'
        ELSE                           '4. Dormant (0 events in 30d)'
    END                         AS engagement_stage,
    COUNT(*)                    AS customer_count,
    ROUND(AVG(churn_score)*100,1) AS avg_churn_pct,
    ROUND(SUM(arr_at_risk), 0)  AS arr_at_risk_usd
FROM marts.mart_customer_risk_scores
GROUP BY 1
ORDER BY MIN(events_last_7d) DESC NULLS LAST
;


-- ── Chart 4: Support load vs churn risk ──────────────────────────────────────
-- Bar: high_priority_tickets bucket → avg churn_score
SELECT
    CASE
        WHEN high_priority_tickets = 0 THEN '0 HP tickets'
        WHEN high_priority_tickets = 1 THEN '1 HP ticket'
        WHEN high_priority_tickets = 2 THEN '2 HP tickets'
        ELSE '3+ HP tickets'
    END                             AS ticket_bucket,
    COUNT(*)                        AS customer_count,
    ROUND(AVG(churn_score)*100, 1)  AS avg_churn_score_pct,
    ROUND(AVG(mrr), 0)              AS avg_mrr
FROM marts.mart_customer_risk_scores
GROUP BY 1
ORDER BY MIN(high_priority_tickets)
;


-- ── Chart 5: Onboarding activation vs 90-day retention ───────────────────────
-- Phase 4 key finding: ≥3 integration connects in first 30d → 2.7× lower churn
SELECT
    CASE
        WHEN integration_connects_first_30d = 0  THEN '0 integrations'
        WHEN integration_connects_first_30d < 3  THEN '1-2 integrations'
        WHEN integration_connects_first_30d < 6  THEN '3-5 integrations'
        ELSE '6+ integrations'
    END                              AS onboarding_tier,
    COUNT(*)                         AS customer_count,
    ROUND(AVG(churn_score)*100, 1)   AS avg_churn_pct,
    SUM(CASE WHEN is_early_stage THEN 1 ELSE 0 END) AS early_stage_count
FROM marts.mart_customer_risk_scores
GROUP BY 1
ORDER BY MIN(integration_connects_first_30d)
;
