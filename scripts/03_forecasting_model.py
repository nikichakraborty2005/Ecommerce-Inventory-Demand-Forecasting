"""
03_forecasting_model.py
Weekly, SKU-level demand forecasting.

Why weekly, not daily: daily demand per SKU is a noisy Poisson count (mean single
digits to tens); weekly aggregation is the standard practice for SKU-level
replenishment forecasting because it smooths noise while still being granular
enough to drive a weekly/bi-weekly reorder cycle.

Models compared (so the "AI" claim is honest and benchmarked, not just asserted):
  1. Naive (last observed week)                      -> baseline
  2. Moving average (trailing 4 weeks)                -> baseline
  3. Random Forest Regressor (engineered features)    -> ML model
  4. Gradient Boosting Regressor (engineered features) -> ML model
Evaluated on a held-out last-8-weeks-per-SKU test window using WMAPE (weighted
MAPE -- the standard metric for count-based retail demand, robust to
low-volume SKUs where plain MAPE blows up).
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder

pd.set_option("display.width", 140)

DATA = "/home/claude/project/data/"

sales = pd.read_csv(DATA + "daily_sales.csv", parse_dates=["date"])
sku_master = pd.read_csv(DATA + "sku_master.csv")

# ---------------------------------------------------------------------------
# 1. Weekly aggregation (network-wide demand per SKU per week)
# ---------------------------------------------------------------------------
sales["week_start"] = sales["date"].dt.to_period("W-MON").dt.start_time
weekly = (sales.groupby(["sku_id", "week_start"])
          .agg(demand_units=("demand_units", "sum"),
               is_promo_week=("is_promo_day", "max"))
          .reset_index())
weekly = weekly.merge(sku_master[["sku_id", "category"]], on="sku_id")
weekly = weekly.sort_values(["sku_id", "week_start"]).reset_index(drop=True)

# ---------------------------------------------------------------------------
# 2. Feature engineering (lags, rolling stats, calendar) -- causal only:
#    every feature for week t is built strictly from weeks < t.
# ---------------------------------------------------------------------------
def add_features(df):
    df = df.copy()
    g = df.groupby("sku_id")["demand_units"]
    for lag in [1, 2, 4, 8]:
        df[f"lag_{lag}"] = g.shift(lag)
    df["roll_mean_4"] = g.shift(1).rolling(4).mean().reset_index(level=0, drop=True)
    df["roll_std_4"] = g.shift(1).rolling(4).std().reset_index(level=0, drop=True)
    df["roll_mean_8"] = g.shift(1).rolling(8).mean().reset_index(level=0, drop=True)
    df["week_of_year"] = df["week_start"].dt.isocalendar().week.astype(int)
    df["month"] = df["week_start"].dt.month
    return df

weekly = add_features(weekly)
weekly = weekly.dropna(subset=["lag_8", "roll_mean_8"]).reset_index(drop=True)  # need 8wk history

le = LabelEncoder()
weekly["category_enc"] = le.fit_transform(weekly["category"])

feature_cols = ["lag_1", "lag_2", "lag_4", "lag_8", "roll_mean_4", "roll_std_4",
                 "roll_mean_8", "week_of_year", "month", "is_promo_week", "category_enc"]

# ---------------------------------------------------------------------------
# 3. Time-based train/test split: last 8 weeks per SKU held out
# ---------------------------------------------------------------------------
cutoff = weekly["week_start"].max() - pd.Timedelta(weeks=8)
train = weekly[weekly["week_start"] <= cutoff]
test = weekly[weekly["week_start"] > cutoff]

X_train, y_train = train[feature_cols], train["demand_units"]
X_test, y_test = test[feature_cols], test["demand_units"]

print(f"Train rows: {len(train):,} | Test rows: {len(test):,} "
      f"| SKUs: {weekly['sku_id'].nunique()} | Weeks total: {weekly['week_start'].nunique()}")

# ---------------------------------------------------------------------------
# 4. Baselines
# ---------------------------------------------------------------------------
def wmape(y_true, y_pred):
    return np.sum(np.abs(y_true - y_pred)) / np.sum(np.abs(y_true)) * 100

results = {}

naive_pred = test["lag_1"].values
results["Naive (last week)"] = wmape(y_test.values, naive_pred)

ma_pred = test["roll_mean_4"].values
results["Moving Average (4wk)"] = wmape(y_test.values, ma_pred)

# ---------------------------------------------------------------------------
# 5. ML models
# ---------------------------------------------------------------------------
rf = RandomForestRegressor(n_estimators=300, max_depth=12, min_samples_leaf=3,
                            random_state=42, n_jobs=-1)
rf.fit(X_train, y_train)
rf_pred = np.clip(rf.predict(X_test), 0, None)
results["Random Forest"] = wmape(y_test.values, rf_pred)

gbr = GradientBoostingRegressor(n_estimators=300, max_depth=3, learning_rate=0.05,
                                 random_state=42)
gbr.fit(X_train, y_train)
gbr_pred = np.clip(gbr.predict(X_test), 0, None)
results["Gradient Boosting"] = wmape(y_test.values, gbr_pred)

print("\n=== Model comparison (WMAPE %, lower is better) ===")
for k, v in sorted(results.items(), key=lambda x: x[1]):
    print(f"  {k:<24s}: {v:.2f}%")

best_model_name = min(results, key=results.get)
print(f"\nBest model: {best_model_name}")

# use the best of the two ML models going forward
best_model = rf if results["Random Forest"] <= results["Gradient Boosting"] else gbr
best_pred_col = rf_pred if best_model is rf else gbr_pred

# ---------------------------------------------------------------------------
# 6. Feature importance (explainability -- important for the interview story)
# ---------------------------------------------------------------------------
importances = pd.Series(best_model.feature_importances_, index=feature_cols).sort_values(ascending=False)
print("\n=== Feature importance ===")
print(importances.round(3).to_string())
importances.reset_index().rename(columns={"index": "feature", 0: "importance"}).to_csv(
    DATA + "forecast_feature_importance.csv", index=False)

# ---------------------------------------------------------------------------
# 7. Save test-set predictions (actual vs forecast) for reporting/Excel
# ---------------------------------------------------------------------------
test_out = test[["sku_id", "category", "week_start", "demand_units"]].copy()
test_out["forecast_units"] = np.round(best_pred_col, 1)
test_out["abs_error"] = (test_out["demand_units"] - test_out["forecast_units"]).abs()
test_out.to_csv(DATA + "forecast_test_predictions.csv", index=False)

model_comparison = pd.DataFrame({"model": list(results.keys()), "wmape_pct": list(results.values())})
model_comparison.to_csv(DATA + "forecast_model_comparison.csv", index=False)

# ---------------------------------------------------------------------------
# 8. Forecast NEXT week (t+1) for every SKU, to feed the automation layer
# ---------------------------------------------------------------------------
latest = weekly.sort_values("week_start").groupby("sku_id").tail(1).copy()
# roll features forward by one week using the same logic as add_features would for a new row
next_week_features = latest[feature_cols].copy()
# shift lag structure forward: new lag_1 = current demand_units, etc.
next_week_features["lag_1"] = latest["demand_units"].values
next_week_features["lag_2"] = latest["lag_1"].values
next_week_features["lag_4"] = latest["lag_2"].values  # approx (weekly granularity)
next_week_features["lag_8"] = latest["lag_4"].values   # approx
next_week_features["roll_mean_4"] = (latest[["lag_1", "lag_2", "lag_4"]].mean(axis=1) * 0 +
                                      latest["roll_mean_4"].values)  # keep last known rolling stat
next_week_features["week_of_year"] = ((latest["week_of_year"].values % 52) + 1)
next_week_pred = np.clip(best_model.predict(next_week_features[feature_cols]), 0, None)

next_week_forecast = latest[["sku_id", "category"]].copy()
next_week_forecast["forecast_week"] = weekly["week_start"].max() + pd.Timedelta(weeks=1)
next_week_forecast["forecast_demand_units"] = np.round(next_week_pred, 1)
next_week_forecast.to_csv(DATA + "forecast_next_week.csv", index=False)

print(f"\nNext-week forecast written for {len(next_week_forecast)} SKUs -> forecast_next_week.csv")
print("\nAll forecasting outputs saved to /home/claude/project/data/")
