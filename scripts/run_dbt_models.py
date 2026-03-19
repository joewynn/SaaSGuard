"""Run dbt SQL models directly against DuckDB (no Docker required).

This script replaces `docker compose exec dbt dbt run` when Docker is not
available. It reads the SQL files, resolves {{ ref() }} and {{ source() }}
references, and executes them in dependency order.

Usage: uv run python scripts/run_dbt_models.py
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb

DB_PATH = Path("data/saasguard.duckdb")
DBT_DIR = Path("dbt_project/models")

# ── Inline staging SQL (resolves {{ source() }} → raw.table) ──────────────────

STAGING_CUSTOMERS = """
CREATE OR REPLACE VIEW staging.stg_customers AS
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
FROM raw.customers
"""

STAGING_USAGE_EVENTS = """
CREATE OR REPLACE VIEW staging.stg_usage_events AS
SELECT
    event_id,
    customer_id,
    CAST(timestamp AS TIMESTAMP)                            AS event_timestamp,
    event_type,
    CAST(feature_adoption_score AS FLOAT)                   AS feature_adoption_score,
    event_type IN ('integration_connect', 'api_call', 'monitoring_run') AS is_retention_signal,
    event_type = 'premium_feature_trial'                    AS is_premium_trial
FROM raw.usage_events
"""

STAGING_SUPPORT_TICKETS = """
CREATE OR REPLACE VIEW staging.stg_support_tickets AS
SELECT
    ticket_id,
    customer_id,
    CAST(created_date AS DATE)                              AS created_date,
    priority,
    resolution_time,
    topic,
    priority = 'high'                                       AS is_high_priority
FROM raw.support_tickets
"""

STAGING_GTM_OPPORTUNITIES = """
CREATE OR REPLACE VIEW staging.stg_gtm_opportunities AS
SELECT
    o.opp_id,
    o.customer_id,
    o.stage,
    CAST(o.close_date AS DATE)              AS close_date,
    CAST(o.amount AS DECIMAL(12, 2))        AS amount,
    o.sales_owner,
    o.opportunity_type,
    o.stage NOT IN ('closed_won', 'closed_lost') AS is_open,
    o.stage NOT IN ('closed_won', 'closed_lost')
        AND c.churn_date IS NOT NULL         AS is_expansion_risk,
    o.opportunity_type = 'expansion'
        AND o.stage NOT IN ('closed_won', 'closed_lost') AS is_open_expansion_opp
FROM raw.gtm_opportunities o
LEFT JOIN raw.customers    c USING (customer_id)
"""

STAGING_RISK_SIGNALS = """
CREATE OR REPLACE VIEW staging.stg_risk_signals AS
SELECT
    customer_id,
    compliance_gap_score,
    vendor_risk_flags
FROM raw.risk_signals
"""

MART_CHURN_FEATURES = """
CREATE OR REPLACE TABLE marts.mart_customer_churn_features AS
WITH customer_base AS (
    SELECT * FROM staging.stg_customers
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
    FROM staging.stg_usage_events
    GROUP BY customer_id
),

integration_summary AS (
    SELECT
        e.customer_id,
        COUNT(*) FILTER (
            WHERE e.event_type = 'integration_connect'
              AND e.event_timestamp::DATE
                  <= c.signup_date::DATE + INTERVAL '30 days'
        )                                                           AS integration_connects_first_30d
    FROM staging.stg_usage_events e
    JOIN customer_base c USING (customer_id)
    GROUP BY e.customer_id
),

ticket_summary AS (
    SELECT
        customer_id,
        COUNT(*) FILTER (WHERE created_date >= CURRENT_DATE - 30)   AS tickets_last_30d,
        SUM(is_high_priority::INT)                                   AS high_priority_tickets,
        AVG(resolution_time)                                         AS avg_resolution_hours
    FROM staging.stg_support_tickets
    GROUP BY customer_id
)

SELECT
    c.customer_id,
    c.industry,
    c.plan_tier,
    c.mrr,
    c.tenure_days,
    c.is_early_stage,
    COALESCE(e.total_events, 0)              AS total_events,
    COALESCE(e.events_last_30d, 0)           AS events_last_30d,
    COALESCE(e.events_last_7d, 0)            AS events_last_7d,
    COALESCE(e.avg_adoption_score, 0)        AS avg_adoption_score,
    COALESCE(e.days_since_last_event, 999)   AS days_since_last_event,
    COALESCE(e.retention_signal_count, 0)    AS retention_signal_count,
    COALESCE(i.integration_connects_first_30d, 0) AS integration_connects_first_30d,
    COALESCE(t.tickets_last_30d, 0)          AS tickets_last_30d,
    COALESCE(t.high_priority_tickets, 0)     AS high_priority_tickets,
    COALESCE(t.avg_resolution_hours, 0)      AS avg_resolution_hours
FROM customer_base c
LEFT JOIN event_summary      e USING (customer_id)
LEFT JOIN integration_summary i USING (customer_id)
LEFT JOIN ticket_summary      t USING (customer_id)
"""

MART_EXPANSION_FEATURES = """
CREATE OR REPLACE TABLE marts.mart_customer_expansion_features AS
WITH churn_features AS (
    SELECT * FROM marts.mart_customer_churn_features
),

customer_base AS (
    SELECT *
    FROM staging.stg_customers
    WHERE is_active = TRUE
      AND is_upgraded = FALSE
),

premium_trial_summary AS (
    SELECT
        customer_id,
        COUNT(*) FILTER (
            WHERE event_timestamp >= CURRENT_DATE - INTERVAL '30 days'
              AND is_premium_trial = TRUE
        )                                   AS premium_feature_trials_30d
    FROM staging.stg_usage_events
    GROUP BY customer_id
),

feature_request_summary AS (
    SELECT
        customer_id,
        COUNT(*) FILTER (
            WHERE created_date >= CURRENT_DATE - INTERVAL '90 days'
              AND topic = 'feature_request'
        )                                   AS feature_request_tickets_90d
    FROM staging.stg_support_tickets
    GROUP BY customer_id
),

expansion_opp_summary AS (
    SELECT
        customer_id,
        MAX(is_open_expansion_opp::INT)::BOOLEAN   AS has_open_expansion_opp,
        COALESCE(SUM(
            CASE WHEN is_open_expansion_opp THEN amount ELSE 0 END
        ), 0)                                       AS expansion_opp_amount
    FROM staging.stg_gtm_opportunities
    GROUP BY customer_id
),

tier_pressure AS (
    SELECT
        customer_id,
        plan_tier,
        mrr,
        CASE plan_tier
            WHEN 'starter'    THEN 500.0
            WHEN 'growth'     THEN 2000.0
            WHEN 'enterprise' THEN 8000.0
            ELSE 0.0
        END AS tier_floor,
        CASE plan_tier
            WHEN 'starter'    THEN 2000.0
            WHEN 'growth'     THEN 8000.0
            WHEN 'enterprise' THEN 50000.0
            ELSE 1.0
        END AS tier_ceiling
    FROM customer_base
)

SELECT
    cb.customer_id,
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
    cf.tickets_last_30d,
    cf.high_priority_tickets,
    cf.avg_resolution_hours,
    cf.plan_tier,
    cf.industry,
    COALESCE(pt.premium_feature_trials_30d, 0)                  AS premium_feature_trials_30d,
    COALESCE(fr.feature_request_tickets_90d, 0)                 AS feature_request_tickets_90d,
    COALESCE(eo.has_open_expansion_opp, FALSE)                  AS has_open_expansion_opp,
    COALESCE(eo.expansion_opp_amount, 0.0)                      AS expansion_opp_amount,
    LEAST(1.0, GREATEST(0.0,
        (tp.mrr - tp.tier_floor) / NULLIF(tp.tier_ceiling - tp.tier_floor, 0)
    ))                                                           AS mrr_tier_ceiling_pct
FROM customer_base cb
JOIN churn_features             cf USING (customer_id)
JOIN tier_pressure              tp USING (customer_id)
LEFT JOIN premium_trial_summary pt USING (customer_id)
LEFT JOIN feature_request_summary fr USING (customer_id)
LEFT JOIN expansion_opp_summary eo USING (customer_id)
"""

MART_RISK_SCORES = """
CREATE OR REPLACE TABLE marts.mart_customer_risk_scores AS
SELECT
    c.customer_id,
    c.industry,
    c.plan_tier,
    c.mrr,
    r.compliance_gap_score,
    r.vendor_risk_flags,
    CASE
        WHEN r.compliance_gap_score >= 0.7 OR r.vendor_risk_flags >= 3 THEN 'high'
        WHEN r.compliance_gap_score >= 0.4 OR r.vendor_risk_flags >= 1 THEN 'medium'
        ELSE 'low'
    END AS risk_tier
FROM staging.stg_customers c
LEFT JOIN staging.stg_risk_signals r USING (customer_id)
WHERE c.is_active = TRUE
"""


def run() -> None:
    """Execute all staging views and mart tables in dependency order."""
    print("Building DuckDB schemas and mart tables...")
    conn = duckdb.connect(str(DB_PATH))

    try:
        conn.execute("CREATE SCHEMA IF NOT EXISTS staging")
        conn.execute("CREATE SCHEMA IF NOT EXISTS marts")

        steps = [
            ("staging.stg_customers", STAGING_CUSTOMERS),
            ("staging.stg_usage_events", STAGING_USAGE_EVENTS),
            ("staging.stg_support_tickets", STAGING_SUPPORT_TICKETS),
            ("staging.stg_gtm_opportunities", STAGING_GTM_OPPORTUNITIES),
            ("staging.stg_risk_signals", STAGING_RISK_SIGNALS),
            ("marts.mart_customer_churn_features", MART_CHURN_FEATURES),
            ("marts.mart_customer_expansion_features", MART_EXPANSION_FEATURES),
            ("marts.mart_customer_risk_scores", MART_RISK_SCORES),
        ]

        for name, sql in steps:
            conn.execute(sql)
            row = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()
            count = row[0] if row else 0
            print(f"  ✓ {name:<45} {count:>10,} rows")

        conn.close()
        print("\n✅ All dbt models complete")

    except Exception:
        conn.close()
        raise


if __name__ == "__main__":
    run()
