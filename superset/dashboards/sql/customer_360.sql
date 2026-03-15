-- =============================================================================
-- DASHBOARD: Customer 360
-- Shows a complete risk snapshot for a single customer.
-- Filter: Superset native filter on customer_id
-- =============================================================================


-- ── Chart 1: Risk KPI header ─────────────────────────────────────────────────
-- Big Number + Trend – churn_score as percentage
SELECT
    ROUND(churn_score * 100, 1)  AS churn_probability_pct,
    risk_tier,
    ROUND(arr_at_risk, 0)        AS arr_at_risk_usd,
    mrr,
    plan_tier,
    industry,
    top_risk_drivers
FROM marts.mart_customer_risk_scores
WHERE customer_id = '{{ filter_values("customer_id")[0] | default("") }}'
;


-- ── Chart 2: Risk flag breakdown ─────────────────────────────────────────────
-- Horizontal bar – which risk signals are firing (1 = active, 0 = not active)
WITH flags AS (
    SELECT
        (events_last_30d < 5)                  AS flag_low_events,
        (events_last_7d = 0)                   AS flag_zero_recent,
        (avg_adoption_score < 0.25)            AS flag_low_adoption,
        (days_since_last_event > 14)           AS flag_inactive_2w,
        (high_priority_tickets >= 2)           AS flag_high_support,
        (is_early_stage AND events_last_30d < 3) AS flag_early_risk,
        (integration_connects_first_30d < 3 AND tenure_days <= 90) AS flag_low_onboarding
    FROM marts.mart_customer_risk_scores
    WHERE customer_id = '{{ filter_values("customer_id")[0] | default("") }}'
)
SELECT 'Low Product Events (30d)'       AS driver, flag_low_events::INT     AS active FROM flags
UNION ALL SELECT 'Zero 7-Day Events',   flag_zero_recent::INT               FROM flags
UNION ALL SELECT 'Low Adoption Score',  flag_low_adoption::INT              FROM flags
UNION ALL SELECT 'Inactive 14+ Days',   flag_inactive_2w::INT               FROM flags
UNION ALL SELECT 'High-Priority Tickets', flag_high_support::INT            FROM flags
UNION ALL SELECT 'Early-Stage at Risk', flag_early_risk::INT                FROM flags
UNION ALL SELECT 'Low Onboarding',      flag_low_onboarding::INT            FROM flags
;


-- ── Chart 3: Usage trend (last 90d events by week) ───────────────────────────
-- Line chart – event cadence decay
SELECT
    DATE_TRUNC('week', event_timestamp::DATE)  AS week_start,
    COUNT(*)                                   AS event_count,
    ROUND(AVG(feature_adoption_score), 3)      AS avg_adoption
FROM raw.usage_events
WHERE customer_id = '{{ filter_values("customer_id")[0] | default("") }}'
  AND event_timestamp >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY 1
ORDER BY 1
;


-- ── Chart 4: Open support tickets table ──────────────────────────────────────
SELECT
    ticket_id,
    created_date,
    priority,
    topic,
    DATEDIFF('day', created_date, CURRENT_DATE) AS age_days,
    CASE WHEN resolution_time IS NULL THEN 'Open' ELSE 'Resolved' END AS status
FROM raw.support_tickets
WHERE customer_id = '{{ filter_values("customer_id")[0] | default("") }}'
ORDER BY
    CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
    created_date DESC
LIMIT 20
;


-- ── Chart 5: Active GTM opportunity ──────────────────────────────────────────
WITH ranked_opp AS (
    SELECT
        opp_id,
        stage,
        ROUND(amount, 0)  AS amount_usd,
        sales_owner,
        close_date,
        DATEDIFF('day', CURRENT_DATE, close_date) AS days_to_close,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY close_date) AS rn
    FROM raw.gtm_opportunities
    WHERE customer_id = '{{ filter_values("customer_id")[0] | default("") }}'
      AND stage NOT IN ('closed_won', 'closed_lost')
)
SELECT opp_id, stage, amount_usd, sales_owner, close_date, days_to_close
FROM ranked_opp
WHERE rn = 1
;
