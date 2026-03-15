-- Churn feature mart – the ML feature store served to the prediction domain.
-- One row per active customer with all features required by the churn model.

WITH customer_base AS (
    SELECT * FROM {{ ref('stg_customers') }}
    WHERE is_active = TRUE
),

event_summary AS (
    SELECT
        customer_id,
        COUNT(*)                                                    AS total_events,
        COUNT(*) FILTER (WHERE event_timestamp >= CURRENT_DATE - 30) AS events_last_30d,
        COUNT(*) FILTER (WHERE event_timestamp >= CURRENT_DATE - 7)  AS events_last_7d,
        AVG(feature_adoption_score)                                 AS avg_adoption_score,
        MAX(event_timestamp)                                        AS last_event_at,
        DATEDIFF('day', MAX(event_timestamp), CURRENT_DATE)         AS days_since_last_event,
        SUM(is_retention_signal::INT)                               AS retention_signal_count
    FROM {{ ref('stg_usage_events') }}
    GROUP BY customer_id
),

ticket_summary AS (
    SELECT
        customer_id,
        COUNT(*) FILTER (WHERE created_date >= CURRENT_DATE - 30)   AS tickets_last_30d,
        SUM(is_high_priority::INT)                                   AS high_priority_tickets,
        AVG(resolution_time)                                         AS avg_resolution_hours
    FROM {{ ref('stg_support_tickets') }}
    GROUP BY customer_id
)

SELECT
    c.customer_id,
    c.industry,
    c.plan_tier,
    c.mrr,
    c.tenure_days,
    c.is_early_stage,
    -- Usage features
    COALESCE(e.total_events, 0)              AS total_events,
    COALESCE(e.events_last_30d, 0)           AS events_last_30d,
    COALESCE(e.events_last_7d, 0)            AS events_last_7d,
    COALESCE(e.avg_adoption_score, 0)        AS avg_adoption_score,
    COALESCE(e.days_since_last_event, 999)   AS days_since_last_event,
    COALESCE(e.retention_signal_count, 0)    AS retention_signal_count,
    -- Support features
    COALESCE(t.tickets_last_30d, 0)          AS tickets_last_30d,
    COALESCE(t.high_priority_tickets, 0)     AS high_priority_tickets,
    COALESCE(t.avg_resolution_hours, 0)      AS avg_resolution_hours
FROM customer_base c
LEFT JOIN event_summary e USING (customer_id)
LEFT JOIN ticket_summary t USING (customer_id)
