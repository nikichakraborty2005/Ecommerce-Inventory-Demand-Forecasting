import sqlite3
import pandas as pd

conn = sqlite3.connect("/home/claude/project/data/ecommerce_fulfillment.db")

sql_files = [
    "sql/02_demand_stats.sql",
    "sql/03_abc_analysis.sql",
    "sql/04_reorder_points.sql",
    "sql/05_fill_rate_impact.sql",
]

for f in sql_files:
    print(f"\n=== Running {f} ===")
    script = open(f"/home/claude/project/{f}").read()
    # split on ';' to run statement by statement, execute all but print result of SELECTs
    conn.executescript(script.split("-- Quick sanity check")[0] if "Quick sanity check" in script else script)

conn.commit()

# Now pull the final views out as clean dataframes for Excel / the report
demand_stats = pd.read_sql("SELECT * FROM v_sku_demand_stats_90d", conn)
abc = pd.read_sql("SELECT * FROM v_abc_classification", conn)
abc_summary = pd.read_sql("""
    SELECT abc_class, COUNT(*) sku_count,
           ROUND(100.0*COUNT(*)/(SELECT COUNT(*) FROM v_abc_classification),1) pct_of_skus,
           ROUND(SUM(revenue_12m),0) total_revenue,
           ROUND(100.0*SUM(revenue_12m)/(SELECT SUM(revenue_12m) FROM v_abc_classification),1) pct_of_revenue
    FROM v_abc_classification GROUP BY abc_class ORDER BY abc_class
""", conn)
reorder_points = pd.read_sql("SELECT * FROM v_reorder_points", conn)
reorder_actions = pd.read_sql("SELECT * FROM v_reorder_action_list", conn)
fill_rate_by_class = pd.read_sql("SELECT * FROM v_fill_rate_by_class", conn)
network_fill_rate = pd.read_sql("""
    SELECT ROUND(100.0*SUM(sold_units)/NULLIF(SUM(demand_units),0),2) network_fill_rate_pct,
           SUM(demand_units) total_demand, SUM(sold_units) total_sold,
           SUM(lost_sales_units) total_lost_sales,
           ROUND(SUM(lost_sales_units)*1.0/SUM(demand_units)*100,2) pct_demand_lost
    FROM daily_sales
""", conn)
worst_fill_rate = pd.read_sql("""
    SELECT ds.sku_id, sm.category, a.abc_class,
           SUM(ds.demand_units) demand, SUM(ds.sold_units) sold,
           ROUND(100.0*SUM(ds.sold_units)/NULLIF(SUM(ds.demand_units),0),2) fill_rate_pct
    FROM daily_sales ds
    JOIN sku_master sm ON sm.sku_id = ds.sku_id
    JOIN v_abc_classification a ON a.sku_id = ds.sku_id
    GROUP BY ds.sku_id, sm.category, a.abc_class
    HAVING demand > 0
    ORDER BY fill_rate_pct ASC LIMIT 15
""", conn)

out = "/home/claude/project/data/"
demand_stats.to_csv(out + "sql_out_demand_stats.csv", index=False)
abc.to_csv(out + "sql_out_abc_classification.csv", index=False)
abc_summary.to_csv(out + "sql_out_abc_summary.csv", index=False)
reorder_points.to_csv(out + "sql_out_reorder_points.csv", index=False)
reorder_actions.to_csv(out + "sql_out_reorder_actions.csv", index=False)
fill_rate_by_class.to_csv(out + "sql_out_fill_rate_by_class.csv", index=False)
network_fill_rate.to_csv(out + "sql_out_network_fill_rate.csv", index=False)
worst_fill_rate.to_csv(out + "sql_out_worst_fill_rate.csv", index=False)

print("\n--- ABC Summary ---")
print(abc_summary.to_string(index=False))
print("\n--- Network Fill Rate ---")
print(network_fill_rate.to_string(index=False))
print("\n--- Reorder Actions (sample) ---")
print(reorder_actions.head(10).to_string(index=False))
print("\n--- Worst Fill Rate SKUs (sample) ---")
print(worst_fill_rate.head(10).to_string(index=False))

conn.close()
print("\nAll SQL outputs exported to /home/claude/project/data/sql_out_*.csv")
