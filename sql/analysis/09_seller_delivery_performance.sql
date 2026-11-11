-- Query 09: delivery performance by seller.
-- Business question: which sellers have the weakest delivery performance?
-- Definitions: delivered orders only. Each seller is credited once per order, even when the order
--   holds several of the seller's items (distinct seller-order pairs). An order with several
--   sellers counts toward EACH of them (shared_orders = this seller's orders that also contain
--   another seller), so a late order can appear in more than one seller's late count.
--   orders_with_delay, late_orders, late_rate_pct, avg_delay_days and avg_review_score follow the
--   definitions in query 08 and are measured at order level. revenue = sum of the seller's own
--   item price on delivered orders (freight excluded).
--   meets_min_volume = 1 when the seller has at least 30 delivered orders. Only those sellers get a
--   late_rate_rank (1 = highest late rate); smaller sellers are listed after them with a NULL rank
--   because their rates are too noisy to rank.
-- Window: all delivered orders (2016-2018).
-- Grain: one row per seller. Source: fact_order_items and fact_orders joined to dim_seller.
WITH seller_orders AS (
    SELECT DISTINCT f.seller_key, f.order_key
    FROM fact_order_items AS f
    WHERE f.is_delivered = 1
),
order_sellers AS (
    SELECT order_key, COUNT(*) AS sellers_in_order
    FROM seller_orders
    GROUP BY order_key
),
seller_revenue AS (
    SELECT seller_key, ROUND(SUM(price), 2) AS revenue
    FROM fact_order_items
    WHERE is_delivered = 1
    GROUP BY seller_key
),
seller AS (
    SELECT ds.seller_id,
           ds.state AS seller_state,
           COUNT(*) AS delivered_orders,
           SUM(CASE WHEN os.sellers_in_order > 1 THEN 1 ELSE 0 END) AS shared_orders,
           COUNT(fo.is_late) AS orders_with_delay,
           COALESCE(SUM(fo.is_late), 0) AS late_orders,
           ROUND(AVG(fo.delivery_delay_days), 1) AS avg_delay_days,
           ROUND(AVG(fo.review_score), 2) AS avg_review_score,
           sr.revenue AS revenue
    FROM seller_orders AS so
    JOIN fact_orders AS fo ON fo.order_key = so.order_key
    JOIN order_sellers AS os ON os.order_key = so.order_key
    JOIN dim_seller AS ds ON ds.seller_key = so.seller_key
    JOIN seller_revenue AS sr ON sr.seller_key = so.seller_key
    GROUP BY ds.seller_id, ds.state, sr.revenue
),
flagged AS (
    SELECT *,
           ROUND(100.0 * late_orders / orders_with_delay, 1) AS late_rate_pct,
           CASE WHEN delivered_orders >= 30 THEN 1 ELSE 0 END AS meets_min_volume
    FROM seller
),
ranked AS (
    SELECT *,
           RANK() OVER (PARTITION BY meets_min_volume ORDER BY late_rate_pct DESC)
               AS rank_within_group
    FROM flagged
)
SELECT seller_id,
       seller_state,
       delivered_orders,
       shared_orders,
       orders_with_delay,
       late_orders,
       late_rate_pct,
       avg_delay_days,
       avg_review_score,
       revenue,
       meets_min_volume,
       CASE WHEN meets_min_volume = 1 THEN rank_within_group END AS late_rate_rank
FROM ranked
ORDER BY meets_min_volume DESC, late_rate_pct DESC, delivered_orders DESC, seller_id;
