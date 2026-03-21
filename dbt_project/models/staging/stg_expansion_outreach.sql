-- Staging model for expansion_outreach_log.
-- Casts types, adds is_converted flag and days_since_outreach.

SELECT
    outreach_id,
    customer_id,
    CAST(contacted_date AS DATE)                                AS contacted_date,
    CAST(propensity_at_outreach AS FLOAT)                       AS propensity_at_outreach,
    outreach_channel,
    outcome,
    outcome = 'upgraded'                                        AS is_converted,
    DATEDIFF('day', CAST(contacted_date AS DATE), CURRENT_DATE) AS days_since_outreach
FROM {{ source('raw', 'expansion_outreach_log') }}
