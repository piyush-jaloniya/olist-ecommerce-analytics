-- Query 02: year-over-year growth, January to August 2018 versus the same months of 2017.
-- Business question: how do revenue and order volume trend over time?
-- Definitions: same as query 01. growth columns compare each year with the previous row;
--   they are NULL for 2017 (no earlier year to compare with).
-- Window: months 1 to 8 of 2017 and 2018, the only months present in both years with full data.
-- Grain: one row per year. Source: fact_orders joined to dim_date.
WITH yearly AS (
    SELECT d.year,
           COUNT(*) AS orders_placed,
           SUM(fo.is_delivered) AS delivered_orders,
           ROUND(SUM(CASE WHEN fo.is_delivered = 1 THEN fo.items_price_total ELSE 0 END), 2)
               AS delivered_revenue,
           ROUND(SUM(CASE WHEN fo.is_delivered = 1 THEN fo.items_freight_total ELSE 0 END), 2)
               AS delivered_freight
    FROM fact_orders AS fo
    JOIN dim_date AS d ON d.date_key = fo.purchase_date_key
    WHERE d.year IN (2017, 2018) AND d.month BETWEEN 1 AND 8
    GROUP BY d.year
)
SELECT year,
       orders_placed,
       delivered_orders,
       delivered_revenue,
       delivered_freight,
       ROUND(delivered_revenue * 1.0 / delivered_orders, 2) AS avg_order_value,
       ROUND(100.0 * (orders_placed - LAG(orders_placed) OVER (ORDER BY year))
             / LAG(orders_placed) OVER (ORDER BY year), 1) AS orders_growth_pct,
       ROUND(100.0 * (delivered_revenue - LAG(delivered_revenue) OVER (ORDER BY year))
             / LAG(delivered_revenue) OVER (ORDER BY year), 1) AS revenue_growth_pct
FROM yearly
ORDER BY year;
