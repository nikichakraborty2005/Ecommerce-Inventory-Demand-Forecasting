"""
01_generate_data.py
Generates a realistic synthetic dataset for an
"Inventory & Demand Forecasting Analytics for E-commerce Fulfillment" project.

Outputs (saved to /home/claude/project/data/):
  - sku_master.csv          : SKU catalog with category, cost, price, supplier lead time
  - fulfillment_centers.csv : FC master (city, capacity)
  - daily_sales.csv         : 2 years of daily demand/sales/stockouts per SKU per FC
  - inventory_snapshot.csv  : current on-hand stock per SKU per FC (as of dataset end date)

Design choices (so the data behaves like real e-commerce data):
  - 150 SKUs across 6 categories, sold from 5 fulfillment centers (mirrors a real
    multi-FC network like Flipkart's).
  - Each SKU has a base daily demand level, category-driven seasonality, day-of-week
    pattern, a mild growth trend, promo-day spikes, and Poisson noise (demand is a count).
  - "Big Billion Days" style sale events are injected in Oct and a smaller one in
    Jan/summer, giving festive-season spikes typical of Indian e-commerce.
  - Stock-outs are simulated: if demand > available stock on a day, sales are capped at
    available stock and the shortfall is logged as lost_sales -> this is what lets us
    later compute a genuine "fill rate" and show improvement after reorder-point tuning.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

rng = np.random.default_rng(42)

# ---------------------------------------------------------------------------
# 1. SKU MASTER
# ---------------------------------------------------------------------------
categories = {
    "Mobiles & Accessories":      {"n": 20, "price": (999, 25000),  "cost_pct": 0.80, "base_demand": (8, 40)},
    "Electronics & Appliances":   {"n": 20, "price": (799, 45000),  "cost_pct": 0.78, "base_demand": (3, 20)},
    "Fashion & Apparel":          {"n": 35, "price": (299, 3999),   "cost_pct": 0.55, "base_demand": (10, 60)},
    "Home & Kitchen":             {"n": 30, "price": (199, 5999),   "cost_pct": 0.60, "base_demand": (5, 35)},
    "Beauty & Personal Care":     {"n": 25, "price": (99, 2499),    "cost_pct": 0.50, "base_demand": (10, 50)},
    "Grocery & Essentials":       {"n": 20, "price": (49, 999),     "cost_pct": 0.70, "base_demand": (20, 90)},
}

fcs = pd.DataFrame([
    {"fc_id": "FC01", "fc_city": "Bhiwandi (Mumbai)",  "region": "West",  "capacity_units": 500000},
    {"fc_id": "FC02", "fc_city": "Bengaluru",          "region": "South", "capacity_units": 420000},
    {"fc_id": "FC03", "fc_city": "Delhi NCR",          "region": "North", "capacity_units": 480000},
    {"fc_id": "FC04", "fc_city": "Kolkata",            "region": "East",  "capacity_units": 260000},
    {"fc_id": "FC05", "fc_city": "Hyderabad",          "region": "South", "capacity_units": 300000},
])
fcs.to_csv("/home/claude/project/data/fulfillment_centers.csv", index=False)

sku_rows = []
sku_counter = 1
for cat, cfg in categories.items():
    for i in range(cfg["n"]):
        sku_id = f"SKU{sku_counter:04d}"
        price = round(rng.uniform(*cfg["price"]), 2)
        cost = round(price * cfg["cost_pct"] * rng.uniform(0.92, 1.08), 2)
        base_demand = round(rng.uniform(*cfg["base_demand"]), 1)
        lead_time = int(rng.choice([2, 3, 4, 5, 7, 10, 14], p=[0.15, 0.2, 0.2, 0.15, 0.15, 0.1, 0.05]))
        # products are assigned to 2-4 FCs (regional availability, not every SKU everywhere)
        n_fcs = int(rng.choice([2, 3, 4], p=[0.3, 0.45, 0.25]))
        assigned_fcs = list(rng.choice(fcs["fc_id"], size=n_fcs, replace=False))
        sku_rows.append({
            "sku_id": sku_id,
            "sku_name": f"{cat.split(' &')[0]} Item {i+1:03d}",
            "category": cat,
            "unit_cost": cost,
            "unit_price": price,
            "supplier_lead_time_days": lead_time,
            "base_daily_demand": base_demand,
            "assigned_fcs": "|".join(assigned_fcs),
            "moq_units": int(rng.choice([10, 20, 25, 50, 100])),  # minimum order quantity
        })
        sku_counter += 1

sku_master = pd.DataFrame(sku_rows)
sku_master.to_csv("/home/claude/project/data/sku_master.csv", index=False)
print(f"SKU master: {len(sku_master)} SKUs across {len(categories)} categories")

# ---------------------------------------------------------------------------
# 2. DAILY SALES / DEMAND SIMULATION (2 years)
# ---------------------------------------------------------------------------
start_date = datetime(2024, 1, 1)
end_date = datetime(2025, 12, 31)
dates = pd.date_range(start_date, end_date, freq="D")

# festive / sale-event calendar (typical Indian e-commerce peak windows)
sale_windows = [
    ("2024-01-15", "2024-01-20", 2.2),  # Republic Day sale
    ("2024-06-01", "2024-06-05", 1.6),  # summer sale
    ("2024-10-03", "2024-10-12", 3.0),  # Big Billion Days / Diwali
    ("2024-12-24", "2024-12-31", 1.8),  # year-end sale
    ("2025-01-15", "2025-01-20", 2.2),
    ("2025-06-01", "2025-06-05", 1.6),
    ("2025-10-01", "2025-10-10", 3.0),
    ("2025-12-24", "2025-12-31", 1.8),
]

def promo_multiplier(date):
    d = date.strftime("%Y-%m-%d")
    for s, e, mult in sale_windows:
        if s <= d <= e:
            return mult, 1
    return 1.0, 0

records = []

# starting stock per (sku, fc): ~12-18 days of base demand, split across assigned FCs
# (deliberately lean -> this is the UNDER-STOCKED baseline the project is built to fix)
stock_state = {}
lead_times = {row["sku_id"]: int(row["supplier_lead_time_days"]) for _, row in sku_master.iterrows()}
# pending_orders[(sku_id, fc)] = list of (arrival_day_idx, qty)
pending_orders = {}

for _, sku in sku_master.iterrows():
    fc_list = sku["assigned_fcs"].split("|")
    per_fc_base = sku["base_daily_demand"] / len(fc_list)
    for fc in fc_list:
        stock_state[(sku["sku_id"], fc)] = round(per_fc_base * rng.uniform(18, 25))
        pending_orders[(sku["sku_id"], fc)] = []

# naive baseline reorder policy: weekly review (real-world lag, not daily monitoring),
# trigger when on-hand < ~7 days of average demand, order arrives after the SKU's
# real supplier lead time -> this is what produces genuine, realistic stockouts
REVIEW_CYCLE_DAYS = 7

for day_idx, date in enumerate(dates):
    dow = date.weekday()  # 0=Mon
    weekend_mult = 1.25 if dow >= 5 else 1.0
    promo_mult, is_promo = promo_multiplier(date)
    # mild YoY growth trend (~15% growth over 2 yrs)
    trend_mult = 1 + 0.15 * (day_idx / len(dates))

    for _, sku in sku_master.iterrows():
        fc_list = sku["assigned_fcs"].split("|")
        per_fc_base = sku["base_daily_demand"] / len(fc_list)
        lt = lead_times[sku["sku_id"]]
        for fc in fc_list:
            key = (sku["sku_id"], fc)

            # 1) receive any orders arriving today
            arriving = [q for (arr_day, q) in pending_orders[key] if arr_day == day_idx]
            if arriving:
                stock_state[key] += sum(arriving)
                pending_orders[key] = [(a, q) for (a, q) in pending_orders[key] if a != day_idx]

            # 2) demand realized, capped by available stock
            lam = max(per_fc_base * weekend_mult * promo_mult * trend_mult, 0.1)
            demand = rng.poisson(lam)
            available = stock_state[key]
            sold = min(demand, available)
            lost = demand - sold
            stock_state[key] = available - sold

            # 3) weekly-review naive "order-up-to" policy (baseline, imperfect on
            # purpose: NO safety-stock buffer against demand variability, which is
            # exactly the gap the project's reorder-point model closes). Target level
            # covers lead time + review cycle at *average* demand only.
            if day_idx % REVIEW_CYCLE_DAYS == 0:
                on_order = sum(q for (_, q) in pending_orders[key])
                target_level = per_fc_base * (lt + REVIEW_CYCLE_DAYS)
                if stock_state[key] + on_order < target_level:
                    order_qty = max(sku["moq_units"], round(target_level - stock_state[key] - on_order))
                    pending_orders[key].append((day_idx + lt, order_qty))

            records.append((
                date.strftime("%Y-%m-%d"), sku["sku_id"], fc, dow, is_promo,
                demand, sold, lost, stock_state[key]
            ))

daily_sales = pd.DataFrame(records, columns=[
    "date", "sku_id", "fc_id", "day_of_week", "is_promo_day",
    "demand_units", "sold_units", "lost_sales_units", "closing_stock_units"
])
daily_sales.to_csv("/home/claude/project/data/daily_sales.csv", index=False)
print(f"Daily sales: {len(daily_sales):,} rows "
      f"({daily_sales['sku_id'].nunique()} SKUs x {len(dates)} days, multi-FC)")

# ---------------------------------------------------------------------------
# 3. CURRENT INVENTORY SNAPSHOT (as of end_date) -> used for reorder-point demo
# ---------------------------------------------------------------------------
snap = daily_sales[daily_sales["date"] == end_date.strftime("%Y-%m-%d")][
    ["sku_id", "fc_id", "closing_stock_units"]
].rename(columns={"closing_stock_units": "on_hand_units"})
snap = snap.merge(sku_master[["sku_id", "supplier_lead_time_days", "moq_units"]], on="sku_id")
snap.to_csv("/home/claude/project/data/inventory_snapshot.csv", index=False)
print(f"Inventory snapshot: {len(snap)} SKU-FC rows as of {end_date.date()}")

print("\nAll files written to /home/claude/project/data/")
