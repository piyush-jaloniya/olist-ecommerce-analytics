-- Query 03: category performance and revenue concentration (Pareto).
-- Business question: which product categories drive revenue?
-- Definitions: delivered orders only. revenue = sum of item price (freight excluded).
--   revenue_share_pct = category revenue / total revenue. cumulative_share_pct = running total of
--   the share when categories are ordered from highest to lowest revenue (ties broken by name).
--   Category names are the English names; 'unknown' groups products without a category.
-- Window: all delivered orders (2016-2018). No minimum volume is applied here; every category
--   with delivered sales is listed.
-- Grain: one row per category. Source: fact_order_items joined to dim_product.
WITH category AS (
    SELECT dp.category_name_english AS category,
           COUNT(*) AS items_sold,
           COUNT(DISTINCT f.order_key) AS orders,
           ROUND(SUM(f.price), 2) AS revenue,
           ROUND(AVG(f.price), 2) AS avg_item_price,
           ROUND(SUM(f.freight_value), 2) AS freight
    FROM fact_order_items AS f
    JOIN dim_product AS dp ON dp.product_key = f.product_key
    WHERE f.is_delivered = 1
    GROUP BY dp.category_name_english
)
SELECT category,
       items_sold,
       orders,
       revenue,
       avg_item_price,
       freight,
       ROUND(100.0 * revenue / SUM(revenue) OVER (), 2) AS revenue_share_pct,
       ROUND(100.0 * SUM(revenue) OVER (ORDER BY revenue DESC, category
                                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
             / SUM(revenue) OVER (), 2) AS cumulative_share_pct,
       RANK() OVER (ORDER BY revenue DESC) AS revenue_rank
FROM category
ORDER BY revenue DESC, category;
