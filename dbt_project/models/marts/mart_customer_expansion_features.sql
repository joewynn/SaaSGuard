-- ML feature store for expansion propensity model.
-- Scope: active customers who have NOT yet upgraded (expansion candidates only).
-- Reuses all 15 churn features via JOIN on mart_customer_churn_features — no logic duplication.
-- 5 new expansion signals capture tier-pressure, premium-trial activity, and Sales intent.

WITH churn_features AS (
    -- Reuse the full 15-feature churn mart as the base — avoids duplicating aggregation logic
    SELECT * FROM {{ ref('mart_customer_churn_features') }}
),

customer_base AS (
    SELECT *
    FROM {{ ref('stg_customers') }}
    WHERE is_active = TRUE
      AND is_upgraded = FALSE   -- expansion candidates only
),

premium_trial_summary AS (
    SELECT
        customer_id,
        COUNT(*) FILTER (
            WHERE event_timestamp >= CURRENT_DATE - INTERVAL '30 days'
              AND is_premium_trial = TRUE
        )                                   AS premium_feature_trials_30d
    FROM {{ ref('stg_usage_events') }}
    GROUP BY customer_id
),

feature_request_summary AS (
    SELECT
        customer_id,
        COUNT(*) FILTER (
            WHERE created_date >= CURRENT_DATE - INTERVAL '90 days'
              AND topic = 'feature_request'
        )                                   AS feature_request_tickets_90d
    FROM {{ ref('stg_support_tickets') }}
    GROUP BY customer_id
),

expansion_opp_summary AS (
    SELECT
        customer_id,
        MAX(is_open_expansion_opp::INT)::BOOLEAN   AS has_open_expansion_opp,
        COALESCE(SUM(
            CASE WHEN is_open_expansion_opp THEN amount ELSE 0 END
        ), 0)                                       AS expansion_opp_amount
    FROM {{ ref('stg_gtm_opportunities') }}
    GROUP BY customer_id
),

-- Tier floor/ceiling for mrr_tier_ceiling_pct computation
-- Free: always 0.0 (no MRR pressure signal — use feature_limit_hit instead)
-- Starter: 500-2000, Growth: 2000-8000, Enterprise: 8000-50000
tier_pressure AS (
    SELECT
        customer_id,
        plan_tier,
        mrr,
        CASE plan_tier
            WHEN 'free'       THEN 0.0
            WHEN 'starter'    THEN 500.0
            WHEN 'growth'     THEN 2000.0
            WHEN 'enterprise' THEN 8000.0
            ELSE 0.0
        END AS tier_floor,
        CASE plan_tier
            WHEN 'free'       THEN 0.01   -- sentinel: prevents div-by-zero; result clamped to 0
            WHEN 'starter'    THEN 2000.0
            WHEN 'growth'     THEN 8000.0
            WHEN 'enterprise' THEN 50000.0
            ELSE 1.0
        END AS tier_ceiling
    FROM customer_base
),

feature_limit_summary AS (
    SELECT
        customer_id,
        COUNT(*) FILTER (
            WHERE event_timestamp >= CURRENT_DATE - INTERVAL '30 days'
              AND is_feature_limit_hit = TRUE
        )                                   AS feature_limit_hit_30d
    FROM {{ ref('stg_usage_events') }}
    GROUP BY customer_id
),

outreach_summary AS (
    SELECT
        customer_id,
        TRUE                                AS was_contacted,
        MIN(days_since_outreach)            AS days_since_last_outreach
    FROM {{ ref('stg_expansion_outreach') }}
    GROUP BY customer_id
)

SELECT
    -- Identity
    cb.customer_id,

    -- ── Base churn features (15) ───────────────────────────────────────────────
    -- Reused via JOIN; no logic duplicated here
    cf.mrr,
    cf.tenure_days,
    cf.is_early_stage,
    cf.total_events,
    cf.events_last_30d,
    cf.events_last_7d,
    cf.avg_adoption_score,
    cf.days_since_last_event,
    cf.retention_signal_count,
    cf.integration_connects_first_30d,
    cf.activated_at_30d,
    cf.tickets_last_30d,
    cf.high_priority_tickets,
    cf.avg_resolution_hours,
    cf.plan_tier,
    cf.industry,

    -- ── Expansion-specific features (5) ───────────────────────────────────────
    -- 1. Premium trial activity: customers trialing features above their current tier
    COALESCE(pt.premium_feature_trials_30d, 0)                  AS premium_feature_trials_30d,

    -- 2. Feature request tickets: asking for capabilities they don't have yet
    COALESCE(fr.feature_request_tickets_90d, 0)                 AS feature_request_tickets_90d,

    -- 3. Sales expansion intent signal
    COALESCE(eo.has_open_expansion_opp, FALSE)                  AS has_open_expansion_opp,

    -- 4. Dollar value of open expansion opportunity (0 if none)
    COALESCE(eo.expansion_opp_amount, 0.0)                      AS expansion_opp_amount,

    -- 5. Tier ceiling pressure: how close current MRR is to the top of their tier
    -- Formula: (mrr - floor) / (ceiling - floor), clamped to [0, 1]
    -- High value (~1.0) = customer has outgrown their tier → ripe for upgrade conversation
    -- FREE tier: always 0.0 (no MRR pressure; use feature_limit_hit_30d instead)
    CASE
        WHEN tp.plan_tier = 'free' THEN 0.0
        ELSE LEAST(1.0, GREATEST(0.0,
            (tp.mrr - tp.tier_floor) / NULLIF(tp.tier_ceiling - tp.tier_floor, 0)
        ))
    END                                                          AS mrr_tier_ceiling_pct,

    -- 6. Feature limit hits in last 30 days (Feature 21 — primary free-tier signal)
    -- For free-tier customers, this replaces mrr_tier_ceiling_pct as the tier-pressure signal
    COALESCE(fl.feature_limit_hit_30d, 0)                       AS feature_limit_hit_30d,

    -- Reporting columns (NOT ML features — excluded from model training)
    COALESCE(os.was_contacted, FALSE)                           AS was_contacted,
    os.days_since_last_outreach                                 AS days_since_last_outreach

FROM customer_base cb
JOIN churn_features             cf USING (customer_id)
JOIN tier_pressure              tp USING (customer_id)
LEFT JOIN premium_trial_summary pt USING (customer_id)
LEFT JOIN feature_request_summary fr USING (customer_id)
LEFT JOIN expansion_opp_summary eo USING (customer_id)
LEFT JOIN feature_limit_summary fl USING (customer_id)
LEFT JOIN outreach_summary      os USING (customer_id)
