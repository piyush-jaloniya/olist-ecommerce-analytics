-- Query 01: monthly orders, delivered revenue, freight and growth.
-- Business question: how do revenue and order volume trend over time?
-- Definitions: month = month of purchase. orders_placed = all orders (any status).
--   delivered_orders = orders with status 'delivered'. delivered_revenue = sum of item price on
--   delivered orders (freight is reported separately and never counted as revenue).
--   avg_order_value = delivered_revenue / delivered_orders.
--   revenue_mom_growth_pct = change in delivered_revenue versus the previous month.
-- Window: full months 2017-01 to 2018-08 only. Excluded: 2016-09, 2016-10 and 2016-12 (launch
--   months with 4, 324 and 1 orders), 2016-11 (no orders at all) and 2018-09, 2018-10 (16 and
--   4 orders; the data ends).
-- Grain: one row per month. Source: fact_orders (order grain) joined to dim_date.
WITH monthly AS (
    SELECT d.year_month,
           COUNT(*) AS orders_placed,
           SUM(fo.is_delivered) AS delivered_orders,
           ROUND(SUM(CASE WHEN fo.is_delivered = 1 THEN fo.items_price_total ELSE 0 END), 2)
               AS delivered_revenue,
           ROUND(SUM(CASE WHEN fo.is_delivered = 1 THEN fo.items_freight_total ELSE 0 END), 2)
               AS delivered_freight
    FROM fact_orders AS fo
    JOIN dim_date AS d ON d.date_key = fo.purchase_date_key
    WHERE d.year_month BETWEEN '2017-01' AND '2018-08'
    GROUP BY d.year_month
)
SELECT year_month,
       orders_placed,
       delivered_orders,
       delivered_revenue,
       delivered_freight,
       ROUND(delivered_revenue * 1.0 / delivered_orders, 2) AS avg_order_value,
       ROUND(100.0 * (delivered_revenue - LAG(delivered_revenue) OVER (ORDER BY year_month))
             / LAG(delivered_revenue) OVER (ORDER BY year_month), 1) AS revenue_mom_growth_pct
FROM monthly
ORDER BY year_month;
