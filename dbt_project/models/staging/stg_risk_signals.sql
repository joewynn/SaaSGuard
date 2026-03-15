-- Staging model for risk_signals.
-- Casts types and derives a categorical risk_tier for dashboard filtering.
-- risk_tier thresholds are aligned with the prediction_domain risk score model.

SELECT
    customer_id,
    CAST(compliance_gap_score AS FLOAT)                     AS compliance_gap_score,
    CAST(vendor_risk_flags AS INTEGER)                      AS vendor_risk_flags,
    CASE
        WHEN compliance_gap_score >= 0.70 THEN 'high'
        WHEN compliance_gap_score >= 0.35 THEN 'medium'
        ELSE 'low'
    END                                                     AS risk_tier
FROM {{ source('raw', 'risk_signals') }}
