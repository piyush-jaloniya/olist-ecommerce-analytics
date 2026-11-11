-- Query 04: freight burden by category.
-- Business question: which categories have a high freight cost?
-- Definitions: delivered orders only. freight_pct_of_price = total freight / total item price.
--   The data has no product cost, so this is a proxy for cost pressure, NOT a margin.
--   meets_min_volume = 1 when the category has at least 100 delivered items. Only those
--   categories get a freight_burden_rank (1 = highest freight % of price); smaller categories are
--   listed after them with a NULL rank because their percentages are too noisy to rank.
-- Window: all delivered orders (2016-2018).
-- Grain: one row per category. Source: fact_order_items joined to dim_product.
WITH category AS (
    SELECT dp.category_name_english AS category,
           COUNT(*) AS items_sold,
           ROUND(SUM(f.price), 2) AS revenue,
           ROUND(SUM(f.freight_value), 2) AS freight,
           ROUND(AVG(f.freight_value), 2) AS avg_freight_per_item,
           ROUND(100.0 * SUM(f.freight_value) / SUM(f.price), 1) AS freight_pct_of_price,
           CASE WHEN COUNT(*) >= 100 THEN 1 ELSE 0 END AS meets_min_volume
    FROM fact_order_items AS f
    JOIN dim_product AS dp ON dp.product_key = f.product_key
    WHERE f.is_delivered = 1
    GROUP BY dp.category_name_english
),
ranked AS (
    SELECT *,
           RANK() OVER (PARTITION BY meets_min_volume ORDER BY freight_pct_of_price DESC)
               AS rank_within_group
    FROM category
)
SELECT category,
       items_sold,
       revenue,
       freight,
       avg_freight_per_item,
       freight_pct_of_price,
       meets_min_volume,
       CASE WHEN meets_min_volume = 1 THEN rank_within_group END AS freight_burden_rank
FROM ranked
ORDER BY meets_min_volume DESC, freight_pct_of_price DESC, category;
