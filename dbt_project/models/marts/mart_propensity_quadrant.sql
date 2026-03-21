-- Propensity Quadrant mart — classifies every active customer into one of 4 quadrants
-- based on rule-based churn risk (from mart_customer_risk_scores) and
-- expansion proxy score (computed from mart_customer_expansion_features signals).
--
-- Quadrant definitions (mirrors conflict matrix in ExpansionResult.recommended_action()):
--   Flight Risk     — churn ≥ 0.5 AND expansion ≥ 0.5 → Senior Exec intervention
--   Growth Engine   — churn < 0.25 AND expansion ≥ 0.5 → Active upgrade conversation
--   Churn Candidate — churn ≥ 0.5 AND expansion < 0.25 → Retention priority
--   Stable Base     — all other combinations → Nurture / maintain
--
-- Expansion proxy score formula (weights tuned to match SHAP importance order):
--   0.30 × premium_feature_trials_30d (normalised 0-1)
--   0.25 × feature_limit_hit_30d (normalised 0-1)
--   0.15 × feature_request_tickets_90d (normalised 0-1)
--   0.20 × has_open_expansion_opp
--   0.10 × mrr_tier_ceiling_pct

WITH risk AS (
    SELECT
        customer_id,
        churn_score      AS churn_probability,
        arr_at_risk,
        mrr
    FROM {{ ref('mart_customer_risk_scores') }}
),

expansion AS (
    SELECT
        customer_id,
        mrr,
        plan_tier,
        premium_feature_trials_30d,
        feature_limit_hit_30d,
        feature_request_tickets_90d,
        has_open_expansion_opp::INT                                     AS has_open_expansion_opp,
        mrr_tier_ceiling_pct,
        was_contacted,
        days_since_last_outreach,
        -- Normalise count features using soft caps (log1p + / max)
        -- Soft normalise: map [0, N] → [0, 1] using log1p / log1p(10)
        LN(1 + premium_feature_trials_30d) / LN(1 + 10)                AS trial_norm,
        LN(1 + feature_limit_hit_30d) / LN(1 + 10)                     AS limit_norm,
        LN(1 + feature_request_tickets_90d) / LN(1 + 5)                AS req_norm
    FROM {{ ref('mart_customer_expansion_features') }}
),

scored AS (
    SELECT
        e.customer_id,
        r.churn_probability,
        -- Expansion proxy: weighted sum of normalised signals
        LEAST(1.0, GREATEST(0.0,
            0.30 * LEAST(1.0, e.trial_norm)
            + 0.25 * LEAST(1.0, e.limit_norm)
            + 0.15 * LEAST(1.0, e.req_norm)
            + 0.20 * e.has_open_expansion_opp
            + 0.10 * e.mrr_tier_ceiling_pct
        ))                                                               AS upgrade_propensity_proxy,
        r.arr_at_risk,
        r.mrr,
        e.plan_tier,
        e.was_contacted,
        e.days_since_last_outreach
    FROM expansion e
    JOIN risk r USING (customer_id)
)

SELECT
    customer_id,
    churn_probability,
    upgrade_propensity_proxy,
    -- Quadrant classification
    CASE
        WHEN churn_probability >= 0.50 AND upgrade_propensity_proxy >= 0.50
            THEN 'Flight Risk'
        WHEN churn_probability < 0.25  AND upgrade_propensity_proxy >= 0.50
            THEN 'Growth Engine'
        WHEN churn_probability >= 0.50 AND upgrade_propensity_proxy < 0.25
            THEN 'Churn Candidate'
        ELSE 'Stable Base'
    END                                                                  AS quadrant_label,
    arr_at_risk,
    mrr,
    plan_tier,
    -- Expected ARR uplift proxy (Starter floor for FREE, 2× MRR for others)
    CASE
        WHEN plan_tier = 'free' THEN 500.0 * 12 * upgrade_propensity_proxy
        ELSE mrr * 12 * upgrade_propensity_proxy
    END                                                                  AS expected_arr_uplift_proxy,
    was_contacted,
    days_since_last_outreach
FROM scored
