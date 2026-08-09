-- ============================================================================
-- 02_demand_stats.sql
-- Computes SKU-level (network-wide, i.e. summed across FCs) daily demand
-- statistics over the trailing 90 days. These feed directly into the
-- safety-stock / reorder-point formulas in 03_reorder_points.sql
-- ============================================================================

DROP VIEW IF EXISTS v_daily_demand_by_sku;
CREATE VIEW v_daily_demand_by_sku AS
SELECT
    date,
    sku_id,
    SUM(demand_units)      AS demand_units,     -- true demand (incl. what was lost to stockouts)
    SUM(sold_units)        AS sold_units,
    SUM(lost_sales_units)  AS lost_sales_units
FROM daily_sales
GROUP BY date, sku_id;

DROP VIEW IF EXISTS v_sku_demand_stats_90d;
CREATE VIEW v_sku_demand_stats_90d AS
WITH last_90 AS (
    SELECT *
    FROM v_daily_demand_by_sku
    WHERE date >= (SELECT date(MAX(date), '-89 day') FROM v_daily_demand_by_sku)
),
stats AS (
    SELECT
        sku_id,
        COUNT(*)                                   AS days_observed,
        AVG(demand_units)                           AS avg_daily_demand,
        AVG(demand_units * demand_units) - AVG(demand_units) * AVG(demand_units) AS variance_demand
    FROM last_90
    GROUP BY sku_id
)
SELECT
    sku_id,
    days_observed,
    ROUND(avg_daily_demand, 2)                       AS avg_daily_demand,
    ROUND(SQRT(MAX(variance_demand, 0)), 2)           AS stddev_daily_demand
FROM stats;

-- Quick sanity check
SELECT * FROM v_sku_demand_stats_90d ORDER BY avg_daily_demand DESC LIMIT 10;
