-- Loads the star schema from the staging database, which the caller ATTACHes as `stg`.
-- Run after schema.sql, on a connection with PRAGMA foreign_keys = ON.
-- Surrogate keys come from ROW_NUMBER() ordered by the natural id, so every rebuild gives
-- the same keys. Lookups use LEFT JOIN on purpose: if a lookup ever failed, a NOT NULL
-- column would raise an error instead of rows being dropped silently.

-- dim_date: one row per calendar day from 2016-01-01 to 2018-12-31 (1,096 rows).
-- STRFTIME('%w') gives 0 = Sunday ... 6 = Saturday; day_of_week here is 1 = Monday ... 7 = Sunday.
WITH RECURSIVE days (d) AS (
    SELECT DATE('2016-01-01')
    UNION ALL
    SELECT DATE(d, '+1 day') FROM days WHERE d < '2018-12-31'
)
INSERT INTO dim_date (date_key, full_date, year, quarter, month, month_name, year_month,
                      day_of_month, day_of_week, day_name, is_weekend)
SELECT CAST(STRFTIME('%Y%m%d', d) AS INTEGER),
       d,
       CAST(STRFTIME('%Y', d) AS INTEGER),
       (CAST(STRFTIME('%m', d) AS INTEGER) + 2) / 3,
       CAST(STRFTIME('%m', d) AS INTEGER),
       CASE STRFTIME('%m', d)
           WHEN '01' THEN 'January'   WHEN '02' THEN 'February' WHEN '03' THEN 'March'
           WHEN '04' THEN 'April'     WHEN '05' THEN 'May'      WHEN '06' THEN 'June'
           WHEN '07' THEN 'July'      WHEN '08' THEN 'August'   WHEN '09' THEN 'September'
           WHEN '10' THEN 'October'   WHEN '11' THEN 'November' WHEN '12' THEN 'December'
       END,
       STRFTIME('%Y-%m', d),
       CAST(STRFTIME('%d', d) AS INTEGER),
       CASE STRFTIME('%w', d) WHEN '0' THEN 7 ELSE CAST(STRFTIME('%w', d) AS INTEGER) END,
       CASE STRFTIME('%w', d)
           WHEN '0' THEN 'Sunday'   WHEN '1' THEN 'Monday'   WHEN '2' THEN 'Tuesday'
           WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday'
           WHEN '6' THEN 'Saturday'
       END,
       CASE WHEN STRFTIME('%w', d) IN ('0', '6') THEN 1 ELSE 0 END
FROM days
ORDER BY d;

-- dim_customer: one row per customer_id. Coordinates come from the cleaned geolocation table
-- (one row per ZIP prefix); they stay NULL when the ZIP has no geolocation row.
INSERT INTO dim_customer (customer_key, customer_id, customer_unique_id, zip_code_prefix,
                          city, state, latitude, longitude)
SELECT ROW_NUMBER() OVER (ORDER BY c.customer_id),
       c.customer_id,
       c.customer_unique_id,
       c.customer_zip_code_prefix,
       c.customer_city,
       c.customer_state,
       g.geolocation_lat,
       g.geolocation_lng
FROM stg.customers AS c
LEFT JOIN stg.geolocation AS g
       ON g.geolocation_zip_code_prefix = c.customer_zip_code_prefix
ORDER BY c.customer_id;

-- dim_product: one row per product, with the English category name from the translation table
-- (which also contains 'unknown').
INSERT INTO dim_product (product_key, product_id, category_name, category_name_english,
                         name_length, description_length, photos_qty, weight_g,
                         length_cm, height_cm, width_cm)
SELECT ROW_NUMBER() OVER (ORDER BY p.product_id),
       p.product_id,
       p.product_category_name,
       t.product_category_name_english,
       p.product_name_length,
       p.product_description_length,
       p.product_photos_qty,
       p.product_weight_g,
       p.product_length_cm,
       p.product_height_cm,
       p.product_width_cm
FROM stg.products AS p
LEFT JOIN stg.category_translation AS t
       ON t.product_category_name = p.product_category_name
ORDER BY p.product_id;

-- dim_seller: one row per seller, with coordinates like dim_customer.
INSERT INTO dim_seller (seller_key, seller_id, zip_code_prefix, city, state, latitude, longitude)
SELECT ROW_NUMBER() OVER (ORDER BY s.seller_id),
       s.seller_id,
       s.seller_zip_code_prefix,
       s.seller_city,
       s.seller_state,
       g.geolocation_lat,
       g.geolocation_lng
FROM stg.sellers AS s
LEFT JOIN stg.geolocation AS g
       ON g.geolocation_zip_code_prefix = s.seller_zip_code_prefix
ORDER BY s.seller_id;

-- fact_orders: one row per order. Items, payments and reviews are summarised in subqueries
-- first (one row per order), so joining them can never multiply order rows.
-- Date keys come from the timestamps; STRFTIME(NULL) is NULL, so missing dates stay NULL.
INSERT INTO fact_orders (order_key, order_id, customer_key, order_status, is_delivered,
                         purchase_date_key, approved_date_key, carrier_date_key,
                         delivered_date_key, estimated_delivery_date_key,
                         review_creation_date_key,
                         purchase_timestamp, approved_timestamp, carrier_timestamp,
                         delivered_timestamp,
                         delivery_date_inconsistent, delivery_delay_days, is_late,
                         item_count, items_price_total, items_freight_total,
                         payment_count, payment_total, review_score)
SELECT ROW_NUMBER() OVER (ORDER BY o.order_id),
       o.order_id,
       dc.customer_key,
       o.order_status,
       CASE WHEN o.order_status = 'delivered' THEN 1 ELSE 0 END,
       CAST(STRFTIME('%Y%m%d', o.order_purchase_timestamp) AS INTEGER),
       CAST(STRFTIME('%Y%m%d', o.order_approved_at) AS INTEGER),
       CAST(STRFTIME('%Y%m%d', o.order_delivered_carrier_date) AS INTEGER),
       CAST(STRFTIME('%Y%m%d', o.order_delivered_customer_date) AS INTEGER),
       CAST(STRFTIME('%Y%m%d', o.order_estimated_delivery_date) AS INTEGER),
       CAST(STRFTIME('%Y%m%d', r.review_creation_date) AS INTEGER),
       o.order_purchase_timestamp,
       o.order_approved_at,
       o.order_delivered_carrier_date,
       o.order_delivered_customer_date,
       o.delivery_date_inconsistent,
       o.delivery_delay_days,
       o.is_late,
       COALESCE(i.item_count, 0),
       COALESCE(i.price_total, 0),
       COALESCE(i.freight_total, 0),
       COALESCE(p.payment_count, 0),
       COALESCE(p.payment_total, 0),
       r.review_score
FROM stg.orders AS o
LEFT JOIN dim_customer AS dc ON dc.customer_id = o.customer_id
LEFT JOIN (SELECT order_id,
                  COUNT(*)           AS item_count,
                  SUM(price)         AS price_total,
                  SUM(freight_value) AS freight_total
           FROM stg.order_items
           GROUP BY order_id) AS i ON i.order_id = o.order_id
LEFT JOIN (SELECT order_id,
                  COUNT(*)           AS payment_count,
                  SUM(payment_value) AS payment_total
           FROM stg.payments
           GROUP BY order_id) AS p ON p.order_id = o.order_id
LEFT JOIN stg.reviews AS r ON r.order_id = o.order_id
ORDER BY o.order_id;

-- fact_order_items: one row per order item. is_delivered and the purchase date key are copied
-- from fact_orders so item-level queries do not always need that join.
INSERT INTO fact_order_items (order_item_key, order_key, order_item_id, product_key, seller_key,
                              purchase_date_key, is_delivered, shipping_limit_timestamp,
                              price, freight_value)
SELECT ROW_NUMBER() OVER (ORDER BY i.order_id, i.order_item_id),
       fo.order_key,
       i.order_item_id,
       dp.product_key,
       ds.seller_key,
       fo.purchase_date_key,
       fo.is_delivered,
       i.shipping_limit_date,
       i.price,
       i.freight_value
FROM stg.order_items AS i
LEFT JOIN fact_orders AS fo ON fo.order_id = i.order_id
LEFT JOIN dim_product AS dp ON dp.product_id = i.product_id
LEFT JOIN dim_seller  AS ds ON ds.seller_id  = i.seller_id
ORDER BY i.order_id, i.order_item_id;

-- fact_order_payments: one row per payment row.
INSERT INTO fact_order_payments (order_payment_key, order_key, payment_sequential, payment_type,
                                 payment_installments, payment_value,
                                 payment_value_non_positive)
SELECT ROW_NUMBER() OVER (ORDER BY p.order_id, p.payment_sequential),
       fo.order_key,
       p.payment_sequential,
       p.payment_type,
       p.payment_installments,
       p.payment_value,
       p.payment_value_non_positive
FROM stg.payments AS p
LEFT JOIN fact_orders AS fo ON fo.order_id = p.order_id
ORDER BY p.order_id, p.payment_sequential;