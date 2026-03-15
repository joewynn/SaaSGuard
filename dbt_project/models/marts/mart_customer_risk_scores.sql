-- Customer risk scores mart – rule-based risk tier for BI dashboard consumption.
--
-- Business Context: Superset cannot call Python ML models directly, so this mart
-- provides a SQL-computable risk approximation derived from the same feature signals
-- that drive the XGBoost model (Phase 4). The Python API (/predictions/churn) is the
-- authoritative source for calibrated probabilities; this mart powers the dashboards
-- and enables fast aggregation queries without hitting the API.
--
-- Scoring logic (transparent, explainable rule set):
--   CRITICAL (≥0.75): 2+ of: very_low_events OR high_support_load OR early_stage_at_risk
--   HIGH     (≥0.50): 1+ risk flag OR avg_adoption_score < 0.30
--   MEDIUM   (≥0.25): marginal engagement or elevated support
--   LOW      (<0.25): healthy engagement signals
--
-- Refreshed by: dbt run --select mart_customer_risk_scores

{{
    config(
        materialized='table',
        alias='mart_customer_risk_scores'
    )
}}

WITH features AS (
    SELECT * FROM {{ ref('mart_customer_churn_features') }}
),

risk_flags AS (
    SELECT
        customer_id,
        industry,
        plan_tier,
        mrr,
        tenure_days,
        is_early_stage,
        events_last_30d,
        events_last_7d,
        avg_adoption_score,
        days_since_last_event,
        retention_signal_count,
        integration_connects_first_30d,
        tickets_last_30d,
        high_priority_tickets,
        avg_resolution_hours,
        -- ── Risk signal flags ────────────────────────────────────────────────
        (events_last_30d < 5)                         AS flag_very_low_events,
        (events_last_7d = 0)                           AS flag_zero_recent_events,
        (avg_adoption_score < 0.25)                    AS flag_low_adoption,
        (days_since_last_event > 14)                   AS flag_inactive_2w,
        (high_priority_tickets >= 2)                   AS flag_high_support_load,
        (tickets_last_30d >= 5)                        AS flag_ticket_surge,
        (is_early_stage AND events_last_30d < 3)       AS flag_early_stage_at_risk,
        (integration_connects_first_30d < 3 AND tenure_days <= 90) AS flag_low_onboarding,
        (retention_signal_count = 0)                   AS flag_no_retention_signals
    FROM features
),

scored AS (
    SELECT
        *,
        -- Count of active risk flags
        (
            flag_very_low_events::INT
            + flag_zero_recent_events::INT
            + flag_low_adoption::INT
            + flag_inactive_2w::INT
            + flag_high_support_load::INT
            + flag_ticket_surge::INT
            + flag_early_stage_at_risk::INT
            + flag_low_onboarding::INT
            + flag_no_retention_signals::INT
        )                                               AS risk_flag_count,

        -- Rule-based churn probability score [0, 1]
        LEAST(1.0, GREATEST(0.0,
            0.10                                                    -- base rate
            + (flag_very_low_events::INT    * 0.18)
            + (flag_zero_recent_events::INT * 0.20)
            + (flag_low_adoption::INT       * 0.15)
            + (flag_inactive_2w::INT        * 0.12)
            + (flag_high_support_load::INT  * 0.12)
            + (flag_ticket_surge::INT       * 0.08)
            + (flag_early_stage_at_risk::INT * 0.15)
            + (flag_low_onboarding::INT     * 0.10)
            + (flag_no_retention_signals::INT * 0.10)
        ))                                              AS churn_score,

        mrr * 12                                        AS arr
    FROM risk_flags
)

SELECT
    customer_id,
    industry,
    plan_tier,
    mrr,
    arr,
    tenure_days,
    is_early_stage,
    events_last_30d,
    events_last_7d,
    avg_adoption_score,
    days_since_last_event,
    retention_signal_count,
    integration_connects_first_30d,
    tickets_last_30d,
    high_priority_tickets,
    avg_resolution_hours,
    risk_flag_count,
    ROUND(churn_score, 4)                               AS churn_score,
    CASE
        WHEN churn_score >= 0.75 THEN 'critical'
        WHEN churn_score >= 0.50 THEN 'high'
        WHEN churn_score >= 0.25 THEN 'medium'
        ELSE 'low'
    END                                                 AS risk_tier,
    -- Estimated ARR at risk (used in uplift simulator)
    ROUND(arr * churn_score, 2)                         AS arr_at_risk,
    -- CS intervention estimated recovery (10% churn reduction assumption)
    ROUND(arr * churn_score * 0.10, 2)                  AS intervention_value_10pct,
    -- Flag combination narrative (top 2 drivers)
    ARRAY_TO_STRING(
        LIST_FILTER(
            [
                CASE WHEN flag_very_low_events    THEN 'low_events'         END,
                CASE WHEN flag_zero_recent_events THEN 'zero_7d_events'     END,
                CASE WHEN flag_low_adoption       THEN 'low_adoption'       END,
                CASE WHEN flag_inactive_2w        THEN 'inactive_14d'       END,
                CASE WHEN flag_high_support_load  THEN 'support_overload'   END,
                CASE WHEN flag_early_stage_at_risk THEN 'onboarding_at_risk' END,
                CASE WHEN flag_low_onboarding     THEN 'low_integration'    END
            ],
            x -> x IS NOT NULL
        )[:2],
        ', '
    )                                                   AS top_risk_drivers
FROM scored
ORDER BY churn_score DESC
