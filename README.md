# Ecommerce Inventory & Demand Forecasting

An end-to-end e-commerce inventory optimization and demand forecasting project using **Python, SQL, Excel and Machine Learning**.

The project analyzes SKU-level demand, performs revenue-based ABC classification, calculates safety stock and reorder points, forecasts future demand using machine learning, detects unusual demand patterns and generates prioritized reorder alerts.

The overall objective is to reduce stockouts and improve inventory availability while avoiding unnecessary inventory buildup across fulfillment locations.

---

## Business Problem

E-commerce fulfillment operations face two major inventory challenges:

- **Stockouts** → lost sales and lower customer satisfaction
- **Overstocking** → excess working capital and storage costs

The project addresses these problems by answering:

1. Which SKUs are most important from a revenue perspective?
2. How much demand does each SKU normally generate?
3. How variable is the demand?
4. How much safety stock should be maintained?
5. When should inventory be reordered?
6. What demand should be expected in the coming weeks?
7. Which SKUs currently require immediate attention?
8. Does the improved replenishment policy perform better than the baseline?

---

# Project Architecture

```text
                    BUSINESS PROBLEM
                  Stockouts / Overstock
                           |
                           v
                +----------------------+
                |   PYTHON DATA        |
                |      GENERATION      |
                +----------+-----------+
                           |
                           v
                +----------------------+
                |    SQLITE / SQL      |
                | INVENTORY ANALYTICS  |
                +----------+-----------+
                           |
               +-----------+-----------+
               |           |           |
               v           v           v
          Demand Stats   ABC        Reorder
                        Analysis      Points
               |           |           |
               +-----------+-----------+
                           |
                           v
                +----------------------+
                |   ML DEMAND          |
                |     FORECASTING      |
                +----------+-----------+
                           |
                           v
                +----------------------+
                |   AI AUTOMATION      |
                | Anomalies + Alerts   |
                +----------+-----------+
                           |
                           v
                +----------------------+
                |     EXCEL MODEL      |
                | Live Formulas +      |
                | Business Outputs     |
                +----------+-----------+
                           |
                           v
                    BUSINESS ACTION
