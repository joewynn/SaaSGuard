# SaaSGuard Dashboard Setup

This directory contains SQL chart definitions for the 4 SaaSGuard dashboards.
All charts query `marts.mart_customer_risk_scores` (materialized by dbt).

## Quick Start

```bash
# 1. Start full stack
docker compose --profile dev up -d

# 2. Run dbt (materializes mart_customer_risk_scores)
docker compose exec dbt dbt run

# 3. Initialize Superset datasets + dashboard stubs
docker compose exec superset python /app/pythonpath/init_dashboards.py

# 4. Open Superset at http://localhost:8088
#    Default credentials: admin / admin
```

## Dashboard SQL Files

| File | Dashboard | Primary Use |
|---|---|---|
| `sql/customer_360.sql` | Customer 360 | Single-customer risk card |
| `sql/churn_heatmap.sql` | Churn Heatmap | Portfolio risk distribution |
| `sql/risk_drilldown.sql` | Risk Drill-Down | CS intervention list |
| `sql/uplift_simulator.sql` | Uplift Simulator | What-if intervention ROI |

## Adding Charts to Superset

For each SQL file, add charts via **Charts > + Chart** in Superset:
1. Select the dataset (`marts.mart_customer_risk_scores` or the relevant raw table)
2. Choose chart type (see `docs/dashboard-guide.md` for recommendations per chart)
3. Paste the SQL into **SQL Lab** if using a custom SQL dataset
4. Pin the chart to the corresponding dashboard
