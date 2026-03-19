-- Staging model for customers table.
-- Casts types, applies naming conventions, and flags early-stage customers.
-- upgrade_date / is_upgraded added for the expansion propensity module.

SELECT
    customer_id,
    industry,
    plan_tier,
    CAST(signup_date AS DATE)                               AS signup_date,
    CAST(mrr AS DECIMAL(10, 2))                             AS mrr,
    CAST(churn_date AS DATE)                                AS churn_date,
    churn_date IS NULL                                      AS is_active,
    DATEDIFF('day', signup_date, COALESCE(churn_date, CURRENT_DATE)) AS tenure_days,
    DATEDIFF('day', signup_date, CURRENT_DATE) <= 90        AS is_early_stage,
    CAST(upgrade_date AS DATE)                              AS upgrade_date,
    upgrade_date IS NOT NULL                                AS is_upgraded
FROM {{ source('raw', 'customers') }}
