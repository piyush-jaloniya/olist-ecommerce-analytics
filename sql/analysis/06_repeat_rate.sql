-- Query 06: how many delivered orders people place, and the repeat-buyer share.
-- Business question: what share of customers buy more than once?
-- Definitions: a person is a customer_unique_id (customer_id changes with every order). Only
--   delivered orders count. Rows 1-5 group people by their number of delivered orders (5 = five or
--   more); rows 6-7 are summaries that overlap with them and must not be added to rows 1-5.
--   revenue = sum of item price on the person's delivered orders (freight excluded).
--   Note: some second orders are placed on the same day as the first (see query 07), so a
--   repeat buyer is not always a returning customer.
-- Window: all delivered orders (2016-2018).
-- Grain: one row per order-count group or summary. Source: fact_orders joined to dim_customer.
WITH person AS (
    SELECT dc.customer_unique_id AS person,
           COUNT(*) AS n_orders,
           ROUND(SUM(fo.items_price_total), 2) AS revenue
    FROM fact_orders AS fo
    JOIN dim_customer AS dc ON dc.customer_key = fo.customer_key
    WHERE fo.is_delivered = 1
    GROUP BY dc.customer_unique_id
),
combined AS (
    SELECT CASE WHEN n_orders >= 5 THEN 5 ELSE n_orders END AS bucket_order,
           CASE WHEN n_orders >= 5 THEN '5 or more' ELSE CAST(n_orders AS TEXT) END
               AS orders_per_person,
           n_orders,
           revenue
    FROM person
    UNION ALL
    SELECT 6, 'SUMMARY: repeat buyers (2 or more)', n_orders, revenue FROM person WHERE n_orders >= 2
    UNION ALL
    SELECT 7, 'SUMMARY: all buyers', n_orders, revenue FROM person
)
SELECT bucket_order,
       orders_per_person,
       COUNT(*) AS people,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM person), 2) AS pct_of_people,
       SUM(n_orders) AS orders,
       ROUND(100.0 * SUM(n_orders) / (SELECT SUM(n_orders) FROM person), 2) AS pct_of_orders,
       ROUND(SUM(revenue), 2) AS revenue,
       ROUND(100.0 * SUM(revenue) / (SELECT SUM(revenue) FROM person), 2) AS pct_of_revenue
FROM combined
GROUP BY bucket_order, orders_per_person
ORDER BY bucket_order;
