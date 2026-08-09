# E-Commerce Inventory & Demand Forecasting Analytics

## Inventory Optimization, ABC Analysis, Demand Forecasting & Reorder Alerts

An end-to-end **e-commerce fulfillment inventory analytics project**
that combines **Excel, SQL, Python-based machine learning, and an
AI-automation layer** to move from SKU-level demand analysis to
actionable replenishment decisions.

------------------------------------------------------------------------

## 📌 Business Problem

E-commerce fulfillment networks have to balance two competing inventory
risks:

-   **Stockouts** → lost sales and poor product availability
-   **Overstock** → excess inventory and inefficient working capital

The project is designed to answer:

1.  Which SKUs contribute the most revenue?
2.  How much demand does each SKU normally generate?
3.  How variable is that demand?
4.  How much safety stock should be maintained?
5.  At what inventory level should replenishment be triggered?
6.  Which demand-forecasting approach performs best?
7.  Which SKUs need immediate replenishment attention?
8.  What is the simulated impact of replacing the baseline replenishment
    policy with an ABC-tiered, forecast-driven reorder-point policy?

------------------------------------------------------------------------

# 🔄 End-to-End Project Flow

``` text
                    E-COMMERCE INVENTORY DATA
                              │
                              ▼
                    ┌──────────────────┐
                    │   SKU MASTER     │
                    │  Product / Cost  │
                    │  Price / Lead    │
                    │  Time / MOQ      │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  DEMAND DATA     │
                    │  Daily SKU Sales │
                    └────────┬─────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
      90-Day Demand Stats              12-Month Revenue
              │                             │
              ▼                             ▼
      Avg Demand + Std Dev             ABC Analysis
              │                             │
              └──────────────┬──────────────┘
                             ▼
                    Safety Stock & ROP
                             │
                             ▼
                    Weekly Demand ML
                             │
                             ▼
                Forecast Model Comparison
                             │
                             ▼
                    Next-Week Forecast
                             │
                             ▼
                    AI Automation Layer
                             │
               ┌─────────────┴─────────────┐
               ▼                           ▼
        Demand Anomalies             Reorder Alerts
               │                           │
               └─────────────┬─────────────┘
                             ▼
                       EXCEL MODEL
                             │
                             ▼
                    BUSINESS DECISION
```

------------------------------------------------------------------------

# 🗂️ Excel Workbook Structure

The final workbook is:

``` text
Inventory_Demand_Forecasting_Model.xlsx
```

It contains the following 8 sheets:

  -----------------------------------------------------------------------
  Sheet                               Purpose
  ----------------------------------- -----------------------------------
  `README`                            Workbook guide and sheet
                                      descriptions

  `SKU_Master`                        SKU catalog and operational input
                                      data

  `Demand_Stats`                      90-day demand statistics sourced
                                      from SQL

  `ABC_Analysis`                      Revenue-based Pareto ABC
                                      classification using live Excel
                                      formulas

  `Reorder_Point_Calc`                Safety stock and reorder-point
                                      calculation

  `Fill_Rate_Impact`                  Baseline vs simulated
                                      improved-policy impact

  `Forecast_Model`                    Forecast-model benchmark and WMAPE
                                      results

  `Reorder_Alerts`                    Automated, prioritized
                                      reorder-alert output
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 📦 1. SKU Master

The `SKU_Master` sheet contains the SKU-level reference data used by the
inventory model.

### Fields

-   SKU ID
-   SKU Name
-   Category
-   Unit Cost
-   Unit Price
-   Supplier Lead Time
-   MOQ (Minimum Order Quantity)
-   Fulfillment Centers

The workbook contains **150 SKUs**.

------------------------------------------------------------------------

# 📊 2. Demand Statistics

The `Demand_Stats` sheet contains SKU-level demand statistics sourced
from the SQL demand-statistics layer.

### Metrics

-   SKU ID
-   Days Observed
-   Average Daily Demand
-   Standard Deviation of Daily Demand

The workbook uses a **trailing 90-day demand window**.

### Why these metrics matter

**Average Daily Demand** answers:

> How much does the SKU normally sell per day?

**Standard Deviation** answers:

> How much does the SKU's daily demand fluctuate?

For example, two SKUs may both average 50 units/day, but the one with
higher standard deviation has more uncertain demand and may require more
safety stock.

------------------------------------------------------------------------

# 3. ABC Analysis

The `ABC_Analysis` sheet performs revenue-based Pareto classification.

### Metrics

-   SKU ID
-   Category
-   Units Sold over 12 months
-   Revenue over 12 months
-   Revenue Rank
-   Cumulative Revenue %
-   ABC Class

The workbook uses the following classification logic:

``` text
Cumulative Revenue % ≤ 80%   → A
Cumulative Revenue % ≤ 95%   → B
Cumulative Revenue % > 95%   → C
```

### Excel Formula

``` excel
=IF(F2<=0.8,"A",IF(F2<=0.95,"B","C"))
```

### Why 80% and 95%?

These are **cumulative revenue contribution boundaries**.

They do **not** mean that 80% of the SKUs are A.

The purpose is to identify which products contribute most strongly to
the revenue base and therefore deserve greater inventory-management
attention.

### Current workbook split

  ABC Class     SKU Count
  ----------- -----------
  A                    60
  B                    44
  C                    46
  **Total**       **150**

------------------------------------------------------------------------

# 🧮 ABC Excel Formulas

The workbook intentionally keeps the ABC calculations as live Excel
formulas.

### 1. Revenue Rank

``` excel
=RANK(D2,$D$2:$D$151)
```

This ranks each SKU according to its 12-month revenue.

Higher revenue receives a better rank.

------------------------------------------------------------------------

### 2. Cumulative Revenue %

``` excel
=SUMPRODUCT(($E$2:$E$151<=E2)*$D$2:$D$151)/SUM($D$2:$D$151)
```

This calculates the cumulative revenue contribution associated with the
current revenue rank.

------------------------------------------------------------------------

### 3. ABC Classification

``` excel
=IF(F2<=0.8,"A",IF(F2<=0.95,"B","C"))
```

This converts the cumulative revenue percentage into an A/B/C business
category.

------------------------------------------------------------------------

# 📦 4. Reorder Point Calculator

The `Reorder_Point_Calc` sheet connects:

``` text
ABC Class
+
Average Demand
+
Demand Variability
+
Lead Time
+
Service Level
        ↓
Safety Stock
        ↓
Reorder Point
```

### Columns

-   SKU ID
-   ABC Class
-   Average Daily Demand
-   Standard Deviation of Demand
-   Lead Time
-   Service Level Z
-   Safety Stock
-   Reorder Point
-   Net On-Hand
-   Action

------------------------------------------------------------------------

# 🛡️ Safety Stock

The model uses:

``` text
Safety Stock = Z × σ × √Lead Time
```

Where:

  Variable    Meaning
  ----------- ------------------------------------
  Z           Service-level factor
  σ           Standard deviation of daily demand
  Lead Time   Supplier lead time in days

### ABC-specific Z values

The workbook uses:

``` text
A → 2.05
B → 1.65
C → 1.28
```

This means higher-priority A SKUs receive a larger service-level buffer.

### Excel Formula

``` excel
=ROUND(F2*D2*SQRT(E2),1)
```

------------------------------------------------------------------------

# 🔁 Reorder Point

The reorder point is calculated as:

``` text
ROP =
(Average Daily Demand × Lead Time)
+ Safety Stock
```

### Excel Formula

``` excel
=ROUND((C2*E2)+G2,1)
```

### Interpretation

If inventory falls to or below the calculated reorder point, the model
recommends replenishment.

------------------------------------------------------------------------

# 🚨 Reorder Action

The workbook uses:

``` excel
=IF(I2<=H2,"REORDER NOW","OK")
```

Meaning:

``` text
Current Inventory ≤ Reorder Point
             │
        ┌────┴────┐
       YES        NO
        │          │
        ▼          ▼
  REORDER NOW      OK
```

------------------------------------------------------------------------

# 📅 Days of Cover

Days of Cover is an operational inventory metric that estimates how long
current stock can support demand.

Conceptually:

``` text
Days of Cover =
Current Inventory / Average Daily Demand
```

A low number of days of cover indicates that inventory may be depleted
quickly.

------------------------------------------------------------------------

# 🚚 5. Fill Rate Impact

The `Fill_Rate_Impact` sheet compares the baseline replenishment policy
with the simulated improved policy over the **last 12 weeks**.

The workbook describes the improved policy as:

> ABC-tiered, forecast-driven reorder-point policy.

### Results

  Metric                Baseline                 Improved
  -------------- --------------- ------------------------
  Fill Rate               83.18%                   99.69%
  Lost Sales        85,604 units              1,595 units
  Total Demand     509,001 units   Same comparison window

### Simulated improvement

``` text
99.69% - 83.18%
≈ +16.5 percentage points
```

> **Important:** This is a historical simulation/backtest, not a live
> production experiment or A/B test.

------------------------------------------------------------------------

# 🤖 6. Demand Forecasting

The `Forecast_Model` sheet contains the machine-learning model
benchmark.

Demand forecasting is performed at the **weekly SKU level**.

The Python forecasting pipeline uses engineered:

-   Lag features
-   Rolling-window features
-   Calendar features

The forecasting evaluation uses a **time-based 8-week holdout** and the
workbook states that the features are causal/no-leakage.

------------------------------------------------------------------------

# 📈 Forecast Models Compared

The project benchmarks four approaches:

1.  Naive --- last week's demand
2.  Moving Average --- 4-week average
3.  Random Forest
4.  Gradient Boosting

### WMAPE Results

  Model                      WMAPE
  ------------------- ------------
  Naive                     28.22%
  Moving Average            20.84%
  Random Forest         **13.98%**
  Gradient Boosting         14.30%

### Winning Model

**Random Forest Regressor**

The workbook identifies Random Forest as the winning model based on the
lowest WMAPE.

------------------------------------------------------------------------

# 📏 WMAPE

WMAPE stands for:

**Weighted Mean Absolute Percentage Error**

Formula:

``` text
WMAPE =
Σ |Actual Demand - Forecast Demand|
------------------------------------ × 100
            Σ |Actual Demand|
```

### Interpretation

Lower WMAPE means lower overall forecasting error.

The project improves from:

``` text
Naive Forecast
28.22%

        ↓

Random Forest
13.98%
```

This is approximately a **50% reduction in WMAPE relative to the naive
benchmark**.

------------------------------------------------------------------------

# ⚠️ Preventing Data Leakage

The forecasting pipeline uses a time-based holdout.

The workbook states:

``` text
Last 8 weeks → Test / Holdout
```

Feature engineering is designed so that future demand is not used to
construct historical predictive features.

This is important because a forecasting model should only use
information that would have been available at the time the prediction
was made.

------------------------------------------------------------------------

# 🚨 7. Reorder Alerts --- AI Automation Layer

The `Reorder_Alerts` sheet is the operational output of the automation
layer.

It combines information such as:

-   SKU
-   SKU Name
-   Category
-   ABC Class
-   On-Hand Inventory
-   Days of Cover
-   Lead Time
-   Next-Week Forecast Demand
-   Urgency
-   Suggested Order Quantity

The purpose is to move from:

``` text
ANALYTICS
```

to:

``` text
ACTIONABLE PRIORITY
```

------------------------------------------------------------------------

# 🚦 Alert Prioritization

The current workbook contains:

  Urgency              SKU Count
  ------------------ -----------
  CRITICAL                   116
  HIGH                         6
  MEDIUM                       1
  **Total Alerts**       **123**

The alerts are urgency-ranked so that an operations user can focus on
the most critical inventory risks first.

------------------------------------------------------------------------

# 🔍 What the AI Automation Layer Does

The broader automation workflow uses demand behavior and inventory
signals to identify unusual conditions and prioritize replenishment.

Conceptually:

``` text
Current Inventory
       +
Days of Cover
       +
ABC Class
       +
Lead Time
       +
Forecast Demand
       +
Demand Anomaly
       ↓
Urgency
       ↓
Suggested Order Quantity
```

The project also includes an anomaly-detection component based on
**Isolation Forest** in the Python automation pipeline.

------------------------------------------------------------------------

# 🔗 Complete Data Lineage

The project follows this data flow:

``` text
SKU Master
     │
     ├──────────────┐
     │              │
     ▼              ▼
Daily Demand    Inventory
     │
     ▼
SQL Demand Statistics
     │
     ├───────────────┐
     ▼               ▼
ABC Analysis     Reorder Point
     │               │
     └───────┬───────┘
             ▼
      Forecast Model
             │
             ▼
      Next-Week Demand
             │
             ▼
      AI Automation
             │
             ▼
      Reorder Alerts
             │
             ▼
       Excel Model
```


# 🧮 Important Inventory Formulas

### 1. Safety Stock

``` text
SS = Z × σ × √LT
```

### 2. Reorder Point

``` text
ROP = Average Daily Demand × Lead Time + Safety Stock
```

### 3. Days of Cover

``` text
Days of Cover =
Current Inventory / Average Daily Demand
```

### 4. Fill Rate

``` text
Fill Rate =
Fulfilled Units / Demanded Units × 100
```

### 5. WMAPE

``` text
WMAPE =
Σ |Actual - Forecast|
---------------------- × 100
       Σ |Actual|
```

------------------------------------------------------------------------

# 📊 Key Project Results

## Demand Forecasting

``` text
Naive WMAPE
   28.22%
      │
      ▼
Random Forest WMAPE
   13.98%
```

## Replenishment Backtest

``` text
Baseline Fill Rate
     83.18%
        │
        ▼
Improved Policy
     99.69%
```

## Automated Reorder Alerts

``` text
123 SKU alerts
│
├── 116 Critical
├──   6 High
└──   1 Medium
```

## ABC Portfolio

``` text
150 Total SKUs
│
├── 60 A
├── 44 B
└── 46 C
```

------------------------------------------------------------------------

# 🎯 Business Interpretation

The project follows a progression from descriptive analytics to
operational decision support.

``` text
DESCRIPTIVE
What happened?
       ↓
DEMAND STATISTICS
How much do we normally sell?
       ↓
ABC ANALYSIS
Which SKUs are most important?
       ↓
INVENTORY OPTIMIZATION
How much buffer should we maintain?
       ↓
FORECASTING
What are we likely to need next?
       ↓
ANOMALY DETECTION
Is demand behaving unusually?
       ↓
REORDER ALERTS
What requires attention?
       ↓
BUSINESS ACTION
What should we replenish?
```

------------------------------------------------------------------------


# ▶️ Project Execution Flow

If the complete source-code pipeline is included in the repository, the
intended execution sequence is:

``` bash
python scripts/01_generate_data.py
python scripts/02_run_sql.py
python scripts/03_forecasting_model.py
python scripts/04_ai_automation.py
python scripts/05_build_excel.py
```

The exact Python/SQL source files should be kept alongside this workbook
so that the analytical outputs remain reproducible.

------------------------------------------------------------------------

# 🛠️ Technology Stack

  Technology        Role
  ----------------- -----------------------------------
  Python            Data generation, ML, automation
  Pandas            Data manipulation
  NumPy             Numerical computation
  SQLite            Database
  SQL               Inventory analytics
  Scikit-learn      Forecasting and anomaly detection
  OpenPyXL          Excel automation
  Microsoft Excel   Business-facing decision model

------------------------------------------------------------------------

# ⚠️ Limitations

This is an analytical simulation and portfolio project.

Important limitations:

-   The dataset is synthetic.
-   It is not proprietary Flipkart data.
-   The fill-rate improvement is based on historical
    simulation/backtesting.
-   It is not a live A/B test.
-   Real-world supplier constraints are simplified.
-   Forecast accuracy varies by SKU.
-   The reorder policy is a model and would require operational
    validation before production deployment.

------------------------------------------------------------------------


------------------------------------------------------------------------

# 💼 Interview-Ready Project Summary

> **I built an end-to-end e-commerce inventory analytics and demand
> forecasting model using Python, SQL, machine learning and Excel. The
> project analyzes SKU-level demand, performs revenue-based ABC
> classification, calculates safety stock and reorder points using
> demand variability and lead time, benchmarks multiple
> demand-forecasting models using WMAPE, and generates prioritized
> reorder alerts through an automation layer. Random Forest achieved the
> lowest WMAPE at 13.98% compared with 28.22% for the naive baseline. I
> also simulated the impact of replacing the baseline replenishment
> policy with an ABC-tiered, forecast-driven reorder-point policy,
> improving the modeled fill rate from 83.18% to 99.69% over the 12-week
> backtest window. The final outputs are presented in an 8-sheet Excel
> decision-support workbook with live formulas for ABC classification
> and reorder calculations.**

------------------------------------------------------------------------

# 👩‍💻 Author

## Nikita Chakraborty

**B.Tech --- Chemical Engineering**\
**Maulana Azad National Institute of Technology (MANIT), Bhopal**

------------------------------------------------------------------------


