-- Staging model for support_tickets.
-- Casts types, normalises priority ordering, and adds is_churn_signal flag.
-- A ticket is a churn signal when it is high/critical AND created within 60
-- days of any recorded churn_date for that customer.

SELECT
    t.ticket_id,
    t.customer_id,
    CAST(t.created_date AS DATE)                                        AS created_date,
    t.priority,
    t.topic,
    CAST(t.resolution_time AS INTEGER)                                  AS resolution_time,
    t.priority IN ('high', 'critical')                                  AS is_high_priority,
    -- Churn signal: high/critical ticket within 60 days before churn
    t.priority IN ('high', 'critical')
        AND c.churn_date IS NOT NULL
        AND DATEDIFF('day', t.created_date, c.churn_date) BETWEEN 0 AND 60 AS is_churn_signal
FROM {{ source('raw', 'support_tickets') }} t
LEFT JOIN {{ source('raw', 'customers') }}  c USING (customer_id)
