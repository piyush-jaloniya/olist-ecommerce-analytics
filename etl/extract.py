"""Extract the nine raw Olist CSV files into pandas DataFrames."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger(__name__)

RAW_FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

DATE_COLUMNS = {
    "orders": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "order_items": ["shipping_limit_date"],
    "reviews": ["review_creation_date", "review_answer_timestamp"],
}


def extract_tables(raw_dir: Path) -> dict[str, pd.DataFrame]:
    """Read all expected raw tables and parse date columns."""
    tables: dict[str, pd.DataFrame] = {}
    for name, filename in RAW_FILES.items():
        path = raw_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing raw input: {path}")
        LOGGER.info("Extracting %s", path.name)
        # The default float parser is not correctly rounded across platforms; round_trip makes parsed values identical everywhere.
        table = pd.read_csv(path, float_precision="round_trip")
        for column in DATE_COLUMNS.get(name, []):
            if column in table.columns:
                non_null_before = int(table[column].notna().sum())
                table[column] = pd.to_datetime(table[column], errors="coerce")
                unparseable = int(non_null_before - table[column].notna().sum())
                LOGGER.info(
                    "%s.%s: %s unparseable date values",
                    name,
                    column,
                    unparseable,
                )
        tables[name] = table
    return tables
