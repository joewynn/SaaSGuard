-- Staging model for usage_events.
-- Adds retention signal flag matching domain logic.

SELECT
    event_id,
    customer_id,
    CAST(timestamp AS TIMESTAMP)                            AS event_timestamp,
    event_type,
    CAST(feature_adoption_score AS FLOAT)                   AS feature_adoption_score,
    event_type IN ('integration_connect', 'api_call', 'monitoring_run') AS is_retention_signal
FROM {{ source('raw', 'usage_events') }}
