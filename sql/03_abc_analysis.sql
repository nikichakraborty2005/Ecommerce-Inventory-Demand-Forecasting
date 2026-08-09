-- ============================================================================
-- 03_abc_analysis.sql
-- Classic ABC analysis: rank SKUs by revenue contribution over the last 12
-- months, take a cumulative % of total revenue, and bucket:
--   A = top ~80% of cumulative revenue   (tight control, frequent review)
--   B = next ~15%                        (moderate control)
--   C = remaining ~5%                    (loose control, bulk/periodic review)
-- ============================================================================

DROP VIEW IF EXISTS v_sku_revenue_12m;
CREATE VIEW v_sku_revenue_12m AS
SELECT
    ds.sku_id,
    sm.category,
    SUM(ds.sold_units)                          AS units_sold_12m,
    SUM(ds.sold_units * sm.unit_price)          AS revenue_12m,
    SUM(ds.sold_units * (sm.unit_price - sm.unit_cost)) AS gross_margin_12m
FROM daily_sales ds
JOIN sku_master sm ON sm.sku_id = ds.sku_id
WHERE ds.date >= (SELECT date(MAX(date), '-364 day') FROM daily_sales)
GROUP BY ds.sku_id, sm.category;

DROP VIEW IF EXISTS v_abc_classification;
CREATE VIEW v_abc_classification AS
WITH ranked AS (
    SELECT
        sku_id,
        category,
        units_sold_12m,
        revenue_12m,
        gross_margin_12m,
        RANK() OVER (ORDER BY revenue_12m DESC) AS revenue_rank,
        SUM(revenue_12m) OVER (ORDER BY revenue_12m DESC
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_revenue,
        SUM(revenue_12m) OVER ()                 AS total_revenue
    FROM v_sku_revenue_12m
),
pct AS (
    SELECT *,
           ROUND(100.0 * running_revenue / total_revenue, 2) AS cumulative_pct_revenue
    FROM ranked
)
SELECT
    sku_id,
    category,
    units_sold_12m,
    ROUND(revenue_12m, 2)        AS revenue_12m,
    ROUND(gross_margin_12m, 2)   AS gross_margin_12m,
    revenue_rank,
    cumulative_pct_revenue,
    CASE
        WHEN cumulative_pct_revenue <= 80 THEN 'A'
        WHEN cumulative_pct_revenue <= 95 THEN 'B'
        ELSE 'C'
    END AS abc_class
FROM pct
ORDER BY revenue_rank;

-- Summary: SKU count / revenue % held by each class (validates the 80/15/5 Pareto split)
SELECT
    abc_class,
    COUNT(*)                                                    AS sku_count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_abc_classification), 1) AS pct_of_skus,
    ROUND(SUM(revenue_12m), 0)                                  AS total_revenue,
    ROUND(100.0 * SUM(revenue_12m) /
          (SELECT SUM(revenue_12m) FROM v_abc_classification), 1)            AS pct_of_revenue
FROM v_abc_classification
GROUP BY abc_class
ORDER BY abc_class;
