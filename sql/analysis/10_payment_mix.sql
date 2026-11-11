-- Query 10: payment mix.
-- Business question: what does the payment mix look like?
-- Definitions: payments of delivered orders only. Every row is a group of payments, and all
--   percentages are shares of ALL payments (or all payment value) on delivered orders.
--   Section 1 (rows 1-5) groups payments by payment type. Section 2 (rows 6-10) splits the CREDIT
--   CARD payments by number of installments. Section 3 (rows 11-12) groups ORDERS by how many
--   different payment types they used; its payments and value are those of the orders in the group.
--   Sections overlap (a payment is in section 1, and possibly in 2 and 3), so rows from different
--   sections must not be added together. orders = distinct orders with at least one payment in the
--   group.
-- Window: all delivered orders (2016-2018).
-- Grain: one row per group. Source: fact_order_payments joined to fact_orders.
WITH pay AS (
    SELECT fp.order_key,
           fp.payment_type,
           fp.payment_installments,
           fp.payment_value
    FROM fact_order_payments AS fp
    JOIN fact_orders AS fo ON fo.order_key = fp.order_key
    WHERE fo.is_delivered = 1
),
order_methods AS (
    SELECT order_key, COUNT(DISTINCT payment_type) AS n_types
    FROM pay
    GROUP BY order_key
),
grouped AS (
    SELECT 1 AS section_order,
           'by payment type' AS section,
           CASE payment_type WHEN 'credit_card' THEN 1 WHEN 'boleto' THEN 2 WHEN 'voucher' THEN 3
                             WHEN 'debit_card' THEN 4 ELSE 5 END AS group_order,
           payment_type AS payment_group,
           order_key, payment_value
    FROM pay
    UNION ALL
    SELECT 2, 'credit card by installments',
           CASE WHEN payment_installments <= 1 THEN 1 WHEN payment_installments <= 3 THEN 2
                WHEN payment_installments <= 6 THEN 3 WHEN payment_installments <= 10 THEN 4
                ELSE 5 END,
           CASE WHEN payment_installments <= 1 THEN '1 installment (or none)'
                WHEN payment_installments <= 3 THEN '2-3 installments'
                WHEN payment_installments <= 6 THEN '4-6 installments'
                WHEN payment_installments <= 10 THEN '7-10 installments'
                ELSE '11+ installments' END,
           order_key, payment_value
    FROM pay
    WHERE payment_type = 'credit_card'
    UNION ALL
    SELECT 3, 'orders by number of payment types',
           CASE WHEN om.n_types = 1 THEN 1 ELSE 2 END,
           CASE WHEN om.n_types = 1 THEN 'orders paid with one payment type'
                ELSE 'orders paid with 2+ payment types' END,
           p.order_key, p.payment_value
    FROM pay AS p
    JOIN order_methods AS om ON om.order_key = p.order_key
)
SELECT section_order,
       section,
       group_order,
       payment_group,
       COUNT(*) AS payments,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM pay), 2) AS pct_of_payments,
       COUNT(DISTINCT order_key) AS orders,
       ROUND(SUM(payment_value), 2) AS payment_value,
       ROUND(100.0 * SUM(payment_value) / (SELECT SUM(payment_value) FROM pay), 2) AS pct_of_value,
       ROUND(AVG(payment_value), 2) AS avg_payment_value
FROM grouped
GROUP BY section_order, section, group_order, payment_group
ORDER BY section_order, group_order;
