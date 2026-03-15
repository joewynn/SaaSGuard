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
    industry
FROM marts.mart_customer_risk_scores
WHERE customer_id = '{{ filter_values("customer_id")[0] | default("") }}'
;


-- ── Chart 2: Risk flag breakdown ─────────────────────────────────────────────
-- Horizontal bar – which risk signals are firing
SELECT
    'Low Product Events (30d)'          AS driver,
    flag_very_low_events::INT           AS active
FROM (
    SELECT
        (events_last_30d < 5)           AS flag_very_low_events,
        (events_last_7d = 0)            AS flag_zero_recent_events,
        (avg_adoption_score < 0.25)     AS flag_low_adoption,
        (days_since_last_event > 14)    AS flag_inactive_2w,
        (high_priority_tickets >= 2)    AS flag_high_support
    FROM marts.mart_customer_risk_scores
    WHERE customer_id = '{{ filter_values("customer_id")[0] | default("") }}'
) flags
UNION ALL SELECT 'Zero 7-Day Events',     flag_zero_recent_events FROM (...) flags
UNION ALL SELECT 'Low Adoption Score',    flag_low_adoption        FROM (...) flags
UNION ALL SELECT 'Inactive 14+ Days',     flag_inactive_2w         FROM (...) flags
UNION ALL SELECT 'High-Priority Tickets', flag_high_support        FROM (...) flags
;


-- ── Chart 3: Usage trend (last 30d events by week) ───────────────────────────
-- Line chart – event cadence decay
SELECT
    DATE_TRUNC('week', event_timestamp::DATE)  AS week_start,
    COUNT(*)                                   AS event_count,
    AVG(feature_adoption_score)                AS avg_adoption
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
    COALESCE(resolution_time::VARCHAR, 'Open')  AS status
FROM raw.support_tickets
WHERE customer_id = '{{ filter_values("customer_id")[0] | default("") }}'
ORDER BY
    CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
    created_date DESC
LIMIT 20
;


-- ── Chart 5: Active GTM opportunity ──────────────────────────────────────────
SELECT
    opp_id,
    stage,
    ROUND(amount, 0)  AS amount_usd,
    sales_owner,
    close_date,
    DATEDIFF('day', CURRENT_DATE, close_date) AS days_to_close
FROM raw.gtm_opportunities
WHERE customer_id = '{{ filter_values("customer_id")[0] | default("") }}'
  AND stage NOT IN ('closed_won', 'closed_lost')
ORDER BY close_date
LIMIT 1
;
