"""Reconcile the built star database with its attached staging database."""

from __future__ import annotations

import logging
import sqlite3

LOGGER = logging.getLogger(__name__)

FIDELITY_CHECKS = [
    (
        "fidelity: order items",
        """SELECT i.order_id, i.order_item_id, i.product_id, i.seller_id, i.price,
                  i.freight_value, i.shipping_limit_date,
                  (o.order_status = 'delivered'), SUBSTR(o.order_purchase_timestamp, 1, 10)
           FROM stg.order_items AS i
           JOIN stg.orders AS o ON o.order_id = i.order_id""",
        """SELECT fo.order_id, f.order_item_id, dp.product_id, ds.seller_id, f.price,
                  f.freight_value, f.shipping_limit_timestamp, f.is_delivered, d.full_date
           FROM fact_order_items AS f
           JOIN fact_orders AS fo ON fo.order_key = f.order_key
           JOIN dim_product AS dp ON dp.product_key = f.product_key
           JOIN dim_seller AS ds ON ds.seller_key = f.seller_key
           JOIN dim_date AS d ON d.date_key = f.purchase_date_key""",
    ),
    (
        "fidelity: orders",
        """SELECT o.order_id, o.customer_id, o.order_status, (o.order_status = 'delivered'),
                  o.order_purchase_timestamp, o.order_approved_at,
                  o.order_delivered_carrier_date, o.order_delivered_customer_date,
                  o.delivery_date_inconsistent, o.delivery_delay_days, o.is_late,
                  r.review_score
           FROM stg.orders AS o
           LEFT JOIN stg.reviews AS r ON r.order_id = o.order_id""",
        """SELECT fo.order_id, dc.customer_id, fo.order_status, fo.is_delivered,
                  fo.purchase_timestamp, fo.approved_timestamp, fo.carrier_timestamp,
                  fo.delivered_timestamp, fo.delivery_date_inconsistent,
                  fo.delivery_delay_days, fo.is_late, fo.review_score
           FROM fact_orders AS fo
           JOIN dim_customer AS dc ON dc.customer_key = fo.customer_key""",
    ),
    (
        "fidelity: order measures",
        """SELECT o.order_id, COALESCE(i.item_count, 0), ROUND(COALESCE(i.price_total, 0), 2),
                  ROUND(COALESCE(i.freight_total, 0), 2), COALESCE(p.payment_count, 0),
                  ROUND(COALESCE(p.payment_total, 0), 2)
           FROM stg.orders AS o
           LEFT JOIN (SELECT order_id, COUNT(*) AS item_count, SUM(price) AS price_total,
                             SUM(freight_value) AS freight_total
                      FROM stg.order_items GROUP BY order_id) AS i ON i.order_id = o.order_id
           LEFT JOIN (SELECT order_id, COUNT(*) AS payment_count, SUM(payment_value) AS payment_total
                      FROM stg.payments GROUP BY order_id) AS p ON p.order_id = o.order_id""",
        """SELECT order_id, item_count, ROUND(items_price_total, 2), ROUND(items_freight_total, 2),
                  payment_count, ROUND(payment_total, 2)
           FROM fact_orders""",
    ),
    (
        "fidelity: order dates",
        """SELECT o.order_id, SUBSTR(o.order_purchase_timestamp, 1, 10),
                  SUBSTR(o.order_approved_at, 1, 10), SUBSTR(o.order_delivered_carrier_date, 1, 10),
                  SUBSTR(o.order_delivered_customer_date, 1, 10),
                  SUBSTR(o.order_estimated_delivery_date, 1, 10),
                  SUBSTR(r.review_creation_date, 1, 10)
           FROM stg.orders AS o
           LEFT JOIN stg.reviews AS r ON r.order_id = o.order_id""",
        """SELECT fo.order_id, d1.full_date, d2.full_date, d3.full_date, d4.full_date,
                  d5.full_date, d6.full_date
           FROM fact_orders AS fo
           JOIN dim_date AS d1 ON d1.date_key = fo.purchase_date_key
           LEFT JOIN dim_date AS d2 ON d2.date_key = fo.approved_date_key
           LEFT JOIN dim_date AS d3 ON d3.date_key = fo.carrier_date_key
           LEFT JOIN dim_date AS d4 ON d4.date_key = fo.delivered_date_key
           JOIN dim_date AS d5 ON d5.date_key = fo.estimated_delivery_date_key
           LEFT JOIN dim_date AS d6 ON d6.date_key = fo.review_creation_date_key""",
    ),
    (
        "fidelity: payments",
        """SELECT p.order_id, p.payment_sequential, p.payment_type, p.payment_installments,
                  p.payment_value, p.payment_value_non_positive
           FROM stg.payments AS p""",
        """SELECT fo.order_id, fp.payment_sequential, fp.payment_type, fp.payment_installments,
                  fp.payment_value, fp.payment_value_non_positive
           FROM fact_order_payments AS fp
           JOIN fact_orders AS fo ON fo.order_key = fp.order_key""",
    ),
    (
        "fidelity: customers",
        """SELECT c.customer_id, c.customer_unique_id, c.customer_zip_code_prefix,
                  c.customer_city, c.customer_state, g.geolocation_lat, g.geolocation_lng
           FROM stg.customers AS c
           LEFT JOIN stg.geolocation AS g
                  ON g.geolocation_zip_code_prefix = c.customer_zip_code_prefix""",
        """SELECT customer_id, customer_unique_id, zip_code_prefix, city, state, latitude, longitude
           FROM dim_customer""",
    ),
    (
        "fidelity: products",
        """SELECT p.product_id, p.product_category_name, t.product_category_name_english,
                  p.product_name_length, p.product_description_length, p.product_photos_qty,
                  p.product_weight_g, p.product_length_cm, p.product_height_cm, p.product_width_cm
           FROM stg.products AS p
           LEFT JOIN stg.category_translation AS t
                  ON t.product_category_name = p.product_category_name""",
        """SELECT product_id, category_name, category_name_english, name_length, description_length,
                  photos_qty, weight_g, length_cm, height_cm, width_cm
           FROM dim_product""",
    ),
    (
        "fidelity: sellers",
        """SELECT s.seller_id, s.seller_zip_code_prefix, s.seller_city, s.seller_state,
                  g.geolocation_lat, g.geolocation_lng
           FROM stg.sellers AS s
           LEFT JOIN stg.geolocation AS g
                  ON g.geolocation_zip_code_prefix = s.seller_zip_code_prefix""",
        """SELECT seller_id, zip_code_prefix, city, state, latitude, longitude
           FROM dim_seller""",
    ),
]


class StarReconciliationError(ValueError):
    """Raised when a star-schema reconciliation check fails."""


def reconcile_star(connection: sqlite3.Connection) -> None:
    """Run row-count, value, business-rule, and foreign-key checks."""
    # Dimension and fact row counts should be reproducible from staging, not
    # copied from a previous run.
    checks = [
        ("dim_date rows", "count", "SELECT CAST(julianday('2018-12-31') - julianday('2016-01-01') AS INTEGER) + 1", "SELECT COUNT(*) FROM dim_date"),
        ("dim_customer rows", "count", "SELECT COUNT(*) FROM stg.customers", "SELECT COUNT(*) FROM dim_customer"),
        ("dim_product rows", "count", "SELECT COUNT(*) FROM stg.products", "SELECT COUNT(*) FROM dim_product"),
        ("dim_seller rows", "count", "SELECT COUNT(*) FROM stg.sellers", "SELECT COUNT(*) FROM dim_seller"),
        ("fact_orders rows", "count", "SELECT COUNT(*) FROM stg.orders", "SELECT COUNT(*) FROM fact_orders"),
        ("fact_order_items rows", "count", "SELECT COUNT(*) FROM stg.order_items", "SELECT COUNT(*) FROM fact_order_items"),
        ("fact_order_payments rows", "count", "SELECT COUNT(*) FROM stg.payments", "SELECT COUNT(*) FROM fact_order_payments"),
        ("$ item price total", "money", "SELECT SUM(price) FROM stg.order_items", "SELECT SUM(price) FROM fact_order_items"),
        ("$ item freight total", "money", "SELECT SUM(freight_value) FROM stg.order_items", "SELECT SUM(freight_value) FROM fact_order_items"),
        ("$ payment total", "money", "SELECT SUM(payment_value) FROM stg.payments", "SELECT SUM(payment_value) FROM fact_order_payments"),
        ("$ order item price total", "money", "SELECT SUM(price) FROM stg.order_items", "SELECT SUM(items_price_total) FROM fact_orders"),
        ("$ order item freight total", "money", "SELECT SUM(freight_value) FROM stg.order_items", "SELECT SUM(items_freight_total) FROM fact_orders"),
        ("$ order payment total", "money", "SELECT SUM(payment_value) FROM stg.payments", "SELECT SUM(payment_total) FROM fact_orders"),
        ("order item count total", "count", "SELECT COUNT(*) FROM stg.order_items", "SELECT SUM(item_count) FROM fact_orders"),
        ("order payment count total", "count", "SELECT COUNT(*) FROM stg.payments", "SELECT SUM(payment_count) FROM fact_orders"),
        ("delivered orders", "count", "SELECT COUNT(*) FROM stg.orders WHERE order_status = 'delivered'", "SELECT SUM(is_delivered) FROM fact_orders"),
        ("late orders", "count", "SELECT COUNT(*) FROM stg.orders WHERE is_late = 1", "SELECT COUNT(*) FROM fact_orders WHERE is_late = 1"),
        ("NULL is_late orders", "count", "SELECT COUNT(*) FROM stg.orders WHERE is_late IS NULL", "SELECT COUNT(*) FROM fact_orders WHERE is_late IS NULL"),
        ("reviewed orders", "count", "SELECT COUNT(*) FROM stg.reviews", "SELECT COUNT(review_score) FROM fact_orders"),
        ("orders without items", "count", "SELECT COUNT(*) FROM stg.orders WHERE order_id NOT IN (SELECT order_id FROM stg.order_items)", "SELECT COUNT(*) FROM fact_orders WHERE item_count = 0"),
        ("distinct people", "count", "SELECT COUNT(DISTINCT customer_unique_id) FROM stg.customers", "SELECT COUNT(DISTINCT customer_unique_id) FROM dim_customer"),
        ("$ delivered revenue", "money", "SELECT SUM(i.price) FROM stg.order_items AS i JOIN stg.orders AS o ON o.order_id = i.order_id WHERE o.order_status = 'delivered'", "SELECT SUM(price) FROM fact_order_items WHERE is_delivered = 1"),
        ("delivered item rows", "count", "SELECT COUNT(*) FROM stg.order_items AS i JOIN stg.orders AS o ON o.order_id = i.order_id WHERE o.order_status = 'delivered'", "SELECT COUNT(*) FROM fact_order_items WHERE is_delivered = 1"),
        ("unknown-category products", "count", "SELECT COUNT(*) FROM stg.products WHERE product_category_name = 'unknown'", "SELECT COUNT(*) FROM dim_product WHERE category_name_english = 'unknown'"),
    ]

    results: list[tuple[str, object, object, str]] = []
    for name, kind, expected_sql, actual_sql in checks:
        expected = connection.execute(expected_sql).fetchone()[0]
        actual = connection.execute(actual_sql).fetchone()[0]
        # Floating-point totals are compared with a half-cent tolerance because
        # SQLite stores these money values as REAL.
        if kind == "money":
            passed = expected is not None and actual is not None and abs(expected - actual) < 0.005
        else:
            passed = expected == actual
        results.append((name, expected, actual, "OK" if passed else "MISMATCH"))

    expected = 0
    actual = len(connection.execute("PRAGMA foreign_key_check").fetchall())
    results.append(("foreign-key violations", expected, actual, "OK" if actual == 0 else "MISMATCH"))

    # Counts and totals cannot detect data placed on the wrong row, so compare
    # each result row with staging through an independent join path; NULLs
    # compare as equal in EXCEPT.
    for name, expected_sql, actual_sql in FIDELITY_CHECKS:
        only_in_staging = connection.execute(
            f"SELECT COUNT(*) FROM ({expected_sql} EXCEPT {actual_sql})"
        ).fetchone()[0]
        only_in_star = connection.execute(
            f"SELECT COUNT(*) FROM ({actual_sql} EXCEPT {expected_sql})"
        ).fetchone()[0]
        differing = only_in_staging + only_in_star
        results.append((name, 0, differing, "OK" if differing == 0 else "MISMATCH"))

    LOGGER.info("Star reconciliation results:")
    LOGGER.info("%-28s %14s %14s %s", "check", "expected", "actual", "status")
    failures: list[str] = []
    for name, expected, actual, status in results:
        LOGGER.info("%-28s %14s %14s %s", name, expected, actual, status)
        if status != "OK":
            failures.append(f"{name}: expected={expected}, actual={actual}")
    if failures:
        raise StarReconciliationError(
            "Star reconciliation failed: " + "; ".join(failures)
        )
    LOGGER.info("Star reconciliation passed (%s checks)", len(results))
