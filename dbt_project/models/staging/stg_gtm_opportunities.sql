-- Staging model for gtm_opportunities.
-- Casts types and flags open opportunities for customers with elevated churn risk.
-- is_expansion_risk = open stage opportunity linked to a currently active customer
-- with a churn signal (usage decay or high ticket volume) — surfaced in GTM domain.
-- opportunity_type / is_open_expansion_opp added for the expansion propensity module.

SELECT
    o.opp_id,
    o.customer_id,
    o.stage,
    CAST(o.close_date AS DATE)              AS close_date,
    CAST(o.amount AS DECIMAL(12, 2))        AS amount,
    o.sales_owner,
    o.opportunity_type,
    o.stage NOT IN ('closed_won', 'closed_lost') AS is_open,
    -- Revenue-at-risk: open opp for a customer who subsequently churned
    o.stage NOT IN ('closed_won', 'closed_lost')
        AND c.churn_date IS NOT NULL         AS is_expansion_risk,
    -- Active expansion conversation with Sales: type=expansion AND not yet closed
    o.opportunity_type = 'expansion'
        AND o.stage NOT IN ('closed_won', 'closed_lost') AS is_open_expansion_opp
FROM {{ source('raw', 'gtm_opportunities') }} o
LEFT JOIN {{ source('raw', 'customers') }}    c USING (customer_id)
