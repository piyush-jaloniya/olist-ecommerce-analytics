-- Query 08: delivery performance by customer state.
-- Business question: which states have the weakest delivery performance?
-- Definitions: delivered orders only, grouped by the customer's state. orders_with_delay = delivered
--   orders with a valid delay (8 delivered orders have no delivery date). late_orders = orders with
--   delivery_delay_days > 0. late_rate_pct = late_orders / orders_with_delay. avg_delay_days and
--   avg_review_score are averages over the orders that have a delay / a review. delivered_revenue
--   = sum of item price (freight excluded) over all delivered orders of the state.
--   meets_min_volume = 1 when the state has at least 300 delivered orders. Only those states get a
--   late_rate_rank (1 = highest late rate); smaller states are listed after them with a NULL rank.
-- Window: all delivered orders (2016-2018).
-- Grain: one row per customer state. Source: fact_orders joined to dim_customer.
WITH state AS (
    SELECT dc.state AS customer_state,
           COUNT(*) AS delivered_orders,
           COUNT(fo.is_late) AS orders_with_delay,
           COALESCE(SUM(fo.is_late), 0) AS late_orders,
           ROUND(AVG(fo.delivery_delay_days), 1) AS avg_delay_days,
           ROUND(AVG(fo.review_score), 2) AS avg_review_score,
           ROUND(SUM(fo.items_price_total), 2) AS delivered_revenue
    FROM fact_orders AS fo
    JOIN dim_customer AS dc ON dc.customer_key = fo.customer_key
    WHERE fo.is_delivered = 1
    GROUP BY dc.state
),
flagged AS (
    SELECT *,
           ROUND(100.0 * late_orders / orders_with_delay, 1) AS late_rate_pct,
           CASE WHEN delivered_orders >= 300 THEN 1 ELSE 0 END AS meets_min_volume
    FROM state
),
ranked AS (
    SELECT *,
           RANK() OVER (PARTITION BY meets_min_volume ORDER BY late_rate_pct DESC)
               AS rank_within_group
    FROM flagged
)
SELECT customer_state,
       delivered_orders,
       orders_with_delay,
       late_orders,
       late_rate_pct,
       avg_delay_days,
       avg_review_score,
       delivered_revenue,
       ROUND(100.0 * delivered_revenue / SUM(delivered_revenue) OVER (), 2) AS revenue_share_pct,
       meets_min_volume,
       CASE WHEN meets_min_volume = 1 THEN rank_within_group END AS late_rate_rank
FROM ranked
ORDER BY meets_min_volume DESC, late_rate_pct DESC, customer_state;
