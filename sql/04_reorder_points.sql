-- ============================================================================
-- 04_reorder_points.sql
-- Reorder Point (ROP) and Safety Stock (SS) per SKU, using the standard
-- inventory-control formulas:
--
--   Safety Stock  = Z * stddev_daily_demand * SQRT(lead_time_days)
--   Reorder Point = (avg_daily_demand * lead_time_days) + Safety Stock
--
-- Z is the service-level factor (from the standard normal distribution).
-- We differentiate service level by ABC class -- this is the key policy
-- lever of the project: A-items get a 98% service level (Z=2.05), B-items
-- 95% (Z=1.65), C-items 90% (Z=1.28). Tighter control -> less capital tied
-- up in low-value C-item safety stock, tighter control preserved for the
-- 80% of revenue sitting in A-items.
-- ============================================================================

DROP VIEW IF EXISTS v_reorder_points;
CREATE VIEW v_reorder_points AS
SELECT
    d.sku_id,
    a.abc_class,
    d.avg_daily_demand,
    d.stddev_daily_demand,
    sm.supplier_lead_time_days,
    CASE a.abc_class WHEN 'A' THEN 2.05 WHEN 'B' THEN 1.65 ELSE 1.28 END AS service_level_z,
    ROUND(
        CASE a.abc_class WHEN 'A' THEN 2.05 WHEN 'B' THEN 1.65 ELSE 1.28 END
        * d.stddev_daily_demand * SQRT(sm.supplier_lead_time_days)
    , 1) AS safety_stock_units,
    ROUND(
        d.avg_daily_demand * sm.supplier_lead_time_days
        +
        CASE a.abc_class WHEN 'A' THEN 2.05 WHEN 'B' THEN 1.65 ELSE 1.28 END
        * d.stddev_daily_demand * SQRT(sm.supplier_lead_time_days)
    , 1) AS reorder_point_units,
    sm.moq_units
FROM v_sku_demand_stats_90d d
JOIN v_abc_classification a ON a.sku_id = d.sku_id
JOIN sku_master sm ON sm.sku_id = d.sku_id;

-- Current network on-hand stock vs reorder point -> action list
DROP VIEW IF EXISTS v_reorder_action_list;
CREATE VIEW v_reorder_action_list AS
SELECT
    r.sku_id,
    r.abc_class,
    ROUND(SUM(i.on_hand_units), 0)   AS network_on_hand_units,
    r.reorder_point_units,
    r.safety_stock_units,
    r.avg_daily_demand,
    r.supplier_lead_time_days,
    CASE WHEN SUM(i.on_hand_units) <= r.reorder_point_units THEN 'REORDER NOW' ELSE 'OK' END AS action,
    MAX(r.moq_units, ROUND(
        (r.avg_daily_demand * 21) - SUM(i.on_hand_units) + r.safety_stock_units
    , 0)) AS suggested_order_qty  -- top up to ~3 weeks of cover + safety stock, floor at MOQ
FROM v_reorder_points r
JOIN inventory_snapshot i ON i.sku_id = r.sku_id
GROUP BY r.sku_id, r.abc_class, r.reorder_point_units, r.safety_stock_units,
         r.avg_daily_demand, r.supplier_lead_time_days, r.moq_units
ORDER BY action DESC, r.abc_class;

-- How many SKUs currently need reordering, by ABC class
SELECT abc_class, action, COUNT(*) AS sku_count
FROM v_reorder_action_list
GROUP BY abc_class, action
ORDER BY abc_class, action;
