-- ============================================================================
-- 05_fill_rate_impact.sql
-- Fill Rate = units actually sold / units actually demanded.
-- This measures the baseline (naive reorder logic used in raw data generation)
-- and is compared, in the Python/Excel layer, against a simulated fill rate
-- under the new ABC-tiered reorder-point policy.
-- ============================================================================

DROP VIEW IF EXISTS v_fill_rate_by_class;
CREATE VIEW v_fill_rate_by_class AS
SELECT
    a.abc_class,
    SUM(ds.demand_units)                                   AS total_demand_units,
    SUM(ds.sold_units)                                     AS total_sold_units,
    SUM(ds.lost_sales_units)                                AS total_lost_units,
    ROUND(100.0 * SUM(ds.sold_units) / NULLIF(SUM(ds.demand_units), 0), 2) AS fill_rate_pct
FROM daily_sales ds
JOIN v_abc_classification a ON a.sku_id = ds.sku_id
GROUP BY a.abc_class
ORDER BY a.abc_class;

-- Network-wide baseline fill rate
SELECT
    ROUND(100.0 * SUM(sold_units) / NULLIF(SUM(demand_units), 0), 2) AS network_fill_rate_pct,
    SUM(demand_units)  AS total_demand,
    SUM(sold_units)    AS total_sold,
    SUM(lost_sales_units) AS total_lost_sales,
    ROUND(SUM(lost_sales_units) * 1.0 / SUM(demand_units) * 100, 2) AS pct_demand_lost
FROM daily_sales;

-- Worst-performing SKUs by fill rate (biggest opportunity for the new policy)
SELECT
    ds.sku_id,
    sm.category,
    a.abc_class,
    SUM(ds.demand_units) AS demand,
    SUM(ds.sold_units)   AS sold,
    ROUND(100.0 * SUM(ds.sold_units) / NULLIF(SUM(ds.demand_units), 0), 2) AS fill_rate_pct
FROM daily_sales ds
JOIN sku_master sm ON sm.sku_id = ds.sku_id
JOIN v_abc_classification a ON a.sku_id = ds.sku_id
GROUP BY ds.sku_id, sm.category, a.abc_class
HAVING demand > 0
ORDER BY fill_rate_pct ASC
LIMIT 15;
