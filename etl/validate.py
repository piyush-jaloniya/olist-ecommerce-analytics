"""Fail-loudly validation checks for transformed Olist tables."""

from __future__ import annotations

import logging

import pandas as pd

from etl.transform import BRAZIL_LAT_RANGE, BRAZIL_LNG_RANGE

LOGGER = logging.getLogger(__name__)
ALLOWED_PAYMENT_TYPES = {
    "credit_card",
    "boleto",
    "voucher",
    "debit_card",
    "unknown",
}


class ValidationError(ValueError):
    """Raised when transformed data violates a required quality rule."""


def _require_unique(table_name: str, table: pd.DataFrame, columns: list[str]) -> None:
    duplicate_count = int(table.duplicated(subset=columns).sum())
    if duplicate_count:
        raise ValidationError(
            f"{table_name} has {duplicate_count} duplicate rows for key {columns}"
        )


def _require_no_orphans(
    child_name: str,
    child: pd.DataFrame,
    child_column: str,
    parent_name: str,
    parent: pd.DataFrame,
    parent_column: str,
) -> None:
    orphans = int((~child[child_column].isin(parent[parent_column])).sum())
    if orphans:
        raise ValidationError(
            f"{child_name}.{child_column} has {orphans} orphan values not found in "
            f"{parent_name}.{parent_column}"
        )


def validate_tables(tables: dict[str, pd.DataFrame]) -> None:
    """Validate keys, numeric rules, and referential integrity."""
    required = {
        "orders",
        "order_items",
        "payments",
        "reviews",
        "customers",
        "products",
        "sellers",
        "geolocation",
        "category_translation",
    }
    missing = required - set(tables)
    if missing:
        raise ValidationError(f"Missing transformed tables: {sorted(missing)}")

    unique_keys = [
        ("orders", ["order_id"]),
        ("order_items", ["order_id", "order_item_id"]),
        ("payments", ["order_id", "payment_sequential"]),
        ("reviews", ["order_id"]),
        ("customers", ["customer_id"]),
        ("products", ["product_id"]),
        ("sellers", ["seller_id"]),
        ("geolocation", ["geolocation_zip_code_prefix"]),
        ("category_translation", ["product_category_name"]),
    ]
    for table_name, columns in unique_keys:
        _require_unique(table_name, tables[table_name], columns)

    review_scores = tables["reviews"]["review_score"]
    null_review_scores = int(review_scores.isna().sum())
    if null_review_scores:
        raise ValidationError(
            f"reviews.review_score contains {null_review_scores} null values"
        )
    invalid_review_scores = int((~review_scores.isin({1, 2, 3, 4, 5})).sum())
    if invalid_review_scores:
        raise ValidationError(
            f"reviews.review_score contains {invalid_review_scores} values outside 1-5"
        )

    key_columns = [
        ("orders", "order_id"),
        ("orders", "customer_id"),
        ("order_items", "order_id"),
        ("order_items", "order_item_id"),
        ("order_items", "product_id"),
        ("order_items", "seller_id"),
        ("payments", "order_id"),
        ("payments", "payment_sequential"),
        ("reviews", "order_id"),
        ("customers", "customer_id"),
        ("customers", "customer_unique_id"),
        ("products", "product_id"),
        ("sellers", "seller_id"),
        ("geolocation", "geolocation_zip_code_prefix"),
        ("category_translation", "product_category_name"),
    ]
    for table_name, column in key_columns:
        null_count = int(tables[table_name][column].isna().sum())
        if null_count:
            raise ValidationError(
                f"{table_name}.{column} contains {null_count} null key values"
            )

    payment_types = tables["payments"]["payment_type"]
    invalid_payment_types = int((~payment_types.isin(ALLOWED_PAYMENT_TYPES)).sum())
    if invalid_payment_types:
        raise ValidationError(
            f"payments.payment_type contains {invalid_payment_types} values outside "
            f"{sorted(ALLOWED_PAYMENT_TYPES)}"
        )

    missing_categories = set(tables["products"]["product_category_name"]) - set(
        tables["category_translation"]["product_category_name"]
    )
    if missing_categories:
        raise ValidationError(
            "Products contain categories without translations: "
            f"{sorted(missing_categories)}"
        )

    geolocation = tables["geolocation"]
    valid_latitude = geolocation["geolocation_lat"].between(*BRAZIL_LAT_RANGE)
    valid_longitude = geolocation["geolocation_lng"].between(*BRAZIL_LNG_RANGE)
    if not (valid_latitude & valid_longitude).all():
        raise ValidationError(
            "Geolocation contains null or out-of-bounds coordinates "
            f"(latitude {BRAZIL_LAT_RANGE}, longitude {BRAZIL_LNG_RANGE})"
        )

    items = tables["order_items"]
    invalid_prices = int((items["price"] <= 0).sum())
    if invalid_prices:
        raise ValidationError(
            f"order_items.price contains {invalid_prices} values that are not greater than 0"
        )
    invalid_freight = int((items["freight_value"] < 0).sum())
    if invalid_freight:
        raise ValidationError(
            f"order_items.freight_value contains {invalid_freight} negative values"
        )

    relationships = [
        ("orders", "customer_id", "customers", "customer_id"),
        ("order_items", "order_id", "orders", "order_id"),
        ("order_items", "product_id", "products", "product_id"),
        ("order_items", "seller_id", "sellers", "seller_id"),
        ("payments", "order_id", "orders", "order_id"),
        ("reviews", "order_id", "orders", "order_id"),
    ]
    for child_name, child_column, parent_name, parent_column in relationships:
        _require_no_orphans(
            child_name,
            tables[child_name],
            child_column,
            parent_name,
            tables[parent_name],
            parent_column,
        )
    LOGGER.info("Validation passed for %s tables", len(tables))
