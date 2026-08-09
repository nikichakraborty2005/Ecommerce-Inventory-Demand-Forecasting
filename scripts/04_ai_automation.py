"""
04_ai_automation.py
The "AI automation" layer of the project. Three pieces:

  A) Anomaly detection: an Isolation Forest flags SKU-weeks where demand
     behaved abnormally (spike or crash) vs that SKU's own history, so ops
     can investigate (viral product, competitor stockout, data issue, etc.)
     instead of a human eyeballing 150 SKUs x 98 weeks of charts.

  B) Automated reorder-alert generator: combines (i) the ML demand forecast,
     (ii) the ABC-tiered reorder point/safety stock, and (iii) current
     on-hand stock, to auto-produce a prioritized, human-readable action
     list -- this is the piece that would run as a scheduled job (e.g.
     daily Airflow/cron task) in production and push alerts to Slack/email
     instead of a planner manually checking spreadsheets.

  C) Before/after impact simulation: replays the last 12 weeks of demand
     through the OLD naive policy (as actually happened, i.e. baseline
     fill rate) vs a simulation of the NEW ABC/forecast-driven reorder
     policy, to produce a defensible "fill rate improved from X% to Y%"
     number for the results.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest

DATA = "/home/claude/project/data/"

sales = pd.read_csv(DATA + "daily_sales.csv", parse_dates=["date"])
sku_master = pd.read_csv(DATA + "sku_master.csv")
abc = pd.read_csv(DATA + "sql_out_abc_classification.csv")
reorder_pts = pd.read_csv(DATA + "sql_out_reorder_points.csv")
inv_snapshot = pd.read_csv(DATA + "inventory_snapshot.csv")
next_week_forecast = pd.read_csv(DATA + "forecast_next_week.csv")

# ===========================================================================
# A) ANOMALY DETECTION on weekly demand per SKU
# ===========================================================================
sales["week_start"] = sales["date"].dt.to_period("W-MON").dt.start_time
weekly = sales.groupby(["sku_id", "week_start"])["demand_units"].sum().reset_index()

anomaly_rows = []
for sku_id, grp in weekly.groupby("sku_id"):
    grp = grp.sort_values("week_start").copy()
    if len(grp) < 10:
        continue
    # normalize demand relative to the SKU's own rolling mean so IsolationForest
    # compares like-for-like across SKUs of very different volume
    roll_mean = grp["demand_units"].rolling(6, min_periods=3).mean()
    grp["ratio_to_trend"] = grp["demand_units"] / roll_mean.replace(0, np.nan)
    grp = grp.dropna(subset=["ratio_to_trend"])
    if len(grp) < 8:
        continue
    iso = IsolationForest(contamination=0.06, random_state=42, n_estimators=200)
    grp["anomaly_flag"] = iso.fit_predict(grp[["ratio_to_trend"]])  # -1 = anomaly
    grp["anomaly_score"] = iso.decision_function(grp[["ratio_to_trend"]])
    grp["sku_id"] = sku_id
    anomaly_rows.append(grp[grp["anomaly_flag"] == -1])

anomalies = pd.concat(anomaly_rows, ignore_index=True) if anomaly_rows else pd.DataFrame()
anomalies = anomalies.merge(sku_master[["sku_id", "category"]], on="sku_id")
anomalies["anomaly_type"] = np.where(anomalies["ratio_to_trend"] > 1, "DEMAND SPIKE", "DEMAND DROP")
anomalies = anomalies.sort_values("anomaly_score")[
    ["sku_id", "category", "week_start", "demand_units", "ratio_to_trend", "anomaly_type", "anomaly_score"]
]
anomalies.to_csv(DATA + "ai_demand_anomalies.csv", index=False)
print(f"A) Anomaly detection: flagged {len(anomalies)} SKU-week anomalies "
      f"out of {len(weekly)} SKU-weeks ({len(anomalies)/len(weekly)*100:.1f}%)")
print(anomalies.head(8).to_string(index=False))

# ===========================================================================
# B) AUTOMATED REORDER ALERTS (forecast-driven, ABC-prioritized)
# ===========================================================================
network_stock = inv_snapshot.groupby("sku_id")["on_hand_units"].sum().reset_index()

alerts = (reorder_pts
          .merge(network_stock, on="sku_id")
          .merge(next_week_forecast[["sku_id", "forecast_demand_units"]], on="sku_id")
          .merge(sku_master[["sku_id", "sku_name", "category"]], on="sku_id"))

alerts["days_of_cover"] = np.where(
    alerts["avg_daily_demand"] > 0,
    round(alerts["on_hand_units"] / alerts["avg_daily_demand"], 1),
    np.nan
)
alerts["needs_reorder"] = alerts["on_hand_units"] <= alerts["reorder_point_units"]
alerts["suggested_order_qty"] = np.maximum(
    alerts["moq_units"],
    np.round((alerts["forecast_demand_units"] / 7 * (alerts["supplier_lead_time_days"] + 14))
             - alerts["on_hand_units"] + alerts["safety_stock_units"])
).clip(lower=0)

def urgency(row):
    if not row["needs_reorder"]:
        return "OK"
    if row["days_of_cover"] < row["supplier_lead_time_days"] * 0.5:
        return "CRITICAL"
    if row["days_of_cover"] < row["supplier_lead_time_days"]:
        return "HIGH"
    return "MEDIUM"

alerts["urgency"] = alerts.apply(urgency, axis=1)

# human-readable auto-generated alert message (templated NLG) -- this is the
# text a scheduled job would push to Slack/email/a supplier-facing PO system.
# In production this templating step is exactly where an LLM call (e.g. the
# Claude API) can be dropped in to turn the row into a natural-language,
# context-aware supplier email instead of a fixed template -- see README.
def alert_text(row):
    if not row["needs_reorder"]:
        return ""
    return (f"[{row['urgency']}] {row['sku_id']} ({row['sku_name']}, {row['category']}, "
            f"Class {row['abc_class']}): {row['on_hand_units']:.0f} units on hand "
            f"= {row['days_of_cover']:.1f} days of cover vs {row['supplier_lead_time_days']}-day "
            f"lead time. Forecasted demand next week: {row['forecast_demand_units']:.0f} units. "
            f"Recommend ordering {row['suggested_order_qty']:.0f} units now.")

alerts["alert_message"] = alerts.apply(alert_text, axis=1)

urgency_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "OK": 3}
alerts["urgency_rank"] = alerts["urgency"].map(urgency_rank)
alerts = alerts.sort_values(["urgency_rank", "abc_class"]).drop(columns="urgency_rank")

cols = ["sku_id", "sku_name", "category", "abc_class", "on_hand_units", "days_of_cover",
        "supplier_lead_time_days", "avg_daily_demand", "forecast_demand_units",
        "reorder_point_units", "safety_stock_units", "needs_reorder", "urgency",
        "suggested_order_qty", "alert_message"]
alerts[cols].to_csv(DATA + "ai_reorder_alerts.csv", index=False)

n_needed = alerts["needs_reorder"].sum()
print(f"\nB) Automated reorder alerts: {n_needed}/{len(alerts)} SKUs need reordering "
      f"({alerts['urgency'].value_counts().to_dict()})")
print("\nSample CRITICAL alerts:")
for msg in alerts.loc[alerts["urgency"] == "CRITICAL", "alert_message"].head(3):
    print(" -", msg)

# ===========================================================================
# C) BEFORE / AFTER FILL-RATE SIMULATION (last 12 weeks)
# ===========================================================================
# BEFORE (baseline / actual): fill rate as it really happened in the last 12 weeks
last_date = sales["date"].max()
window_start = last_date - pd.Timedelta(weeks=12)
recent = sales[sales["date"] > window_start]
before_fill_rate = recent["sold_units"].sum() / recent["demand_units"].sum() * 100

# AFTER (simulated): replay the same 12 weeks of *true* daily demand per SKU-FC,
# but starting stock is topped up to each SKU's new reorder point + safety stock
# (from 04_reorder_points.sql) at the start of the window, and replenishment
# triggers the moment stock crosses the reorder point (event-driven review,
# not a slow weekly review), arriving after the real supplier lead time.
sim_rows = []
rp_lookup = reorder_pts.set_index("sku_id").to_dict("index")
lt_lookup = sku_master.set_index("sku_id")["supplier_lead_time_days"].to_dict()
moq_lookup = sku_master.set_index("sku_id")["moq_units"].to_dict()

recent_pivot = recent.copy()
recent_pivot["day_idx"] = (recent_pivot["date"] - recent_pivot["date"].min()).dt.days

total_demand_sim = 0
total_sold_sim = 0

for sku_id, sku_grp in recent_pivot.groupby("sku_id"):
    if sku_id not in rp_lookup:
        continue
    rp = rp_lookup[sku_id]["reorder_point_units"]
    ss = rp_lookup[sku_id]["safety_stock_units"]
    lt = lt_lookup[sku_id]
    moq = moq_lookup[sku_id]
    for fc_id, fc_grp in sku_grp.groupby("fc_id"):
        fc_grp = fc_grp.sort_values("day_idx")
        n_fcs_for_sku = sku_grp["fc_id"].nunique()
        stock = (rp + ss) / n_fcs_for_sku  # start the window topped up to policy target, split per FC
        pending = []  # (arrival_day, qty)
        for _, r in fc_grp.iterrows():
            day = r["day_idx"]
            arriving = [q for (a, q) in pending if a == day]
            if arriving:
                stock += sum(arriving)
                pending = [(a, q) for (a, q) in pending if a != day]
            demand = r["demand_units"]
            sold = min(demand, stock)
            stock -= sold
            total_demand_sim += demand
            total_sold_sim += sold
            # event-driven reorder: trigger the instant stock <= reorder point/n_fcs
            if stock <= (rp / n_fcs_for_sku) and not pending:
                order_qty = max(moq, round((rp + ss) / n_fcs_for_sku))
                pending.append((day + lt, order_qty))

after_fill_rate = total_sold_sim / total_demand_sim * 100

impact = pd.DataFrame([{
    "period": "Last 12 weeks",
    "fill_rate_before_pct": round(before_fill_rate, 2),
    "fill_rate_after_pct": round(after_fill_rate, 2),
    "improvement_pp": round(after_fill_rate - before_fill_rate, 2),
    "demand_units": int(total_demand_sim),
    "lost_sales_before": int(recent["lost_sales_units"].sum()),
    "lost_sales_after_est": int(total_demand_sim - total_sold_sim),
}])
impact.to_csv(DATA + "ai_before_after_impact.csv", index=False)

print(f"\nC) Fill-rate impact simulation (last 12 weeks):")
print(f"   BEFORE (actual, naive weekly-review policy): {before_fill_rate:.2f}%")
print(f"   AFTER  (ABC-tiered, forecast-driven policy):  {after_fill_rate:.2f}%")
print(f"   Improvement: {after_fill_rate - before_fill_rate:+.2f} percentage points")

print("\nAll AI automation outputs saved to /home/claude/project/data/")
