"""Apply the approved cleaning rules to extracted Olist tables."""

from __future__ import annotations

import logging

import pandas as pd

LOGGER = logging.getLogger(__name__)

# Include Fernando de Noronha, whose eastern longitude is about -32.4.
BRAZIL_LAT_RANGE = (-34, 6)
BRAZIL_LNG_RANGE = (-74, -32)

MANUAL_CATEGORY_TRANSLATIONS = {
    "pc_gamer": "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "portable_kitchen_and_food_preparers",
}


def _clean_geolocation(table: pd.DataFrame) -> pd.DataFrame:
    in_brazil = (
        table["geolocation_lat"].between(*BRAZIL_LAT_RANGE)
        & table["geolocation_lng"].between(*BRAZIL_LNG_RANGE)
    )
    filtered = table.loc[in_brazil].copy()
    dropped_rows = len(table) - len(filtered)
    original_prefixes = set(table["geolocation_zip_code_prefix"])
    remaining_prefixes = set(filtered["geolocation_zip_code_prefix"])
    dropped_prefixes = original_prefixes - remaining_prefixes
    LOGGER.info(
        "Dropped %s geolocation rows outside Brazil bounds; %s ZIP prefixes "
        "disappeared completely",
        dropped_rows,
        len(dropped_prefixes),
    )

    coordinates = filtered.groupby("geolocation_zip_code_prefix", as_index=False).agg(
        geolocation_lat=("geolocation_lat", "median"),
        geolocation_lng=("geolocation_lng", "median"),
    )
    pair_counts = (
        filtered.groupby(
            ["geolocation_zip_code_prefix", "geolocation_city", "geolocation_state"],
            dropna=False,
        )
        .size()
        .rename("pair_count")
        .reset_index()
        .sort_values(
            [
                "geolocation_zip_code_prefix",
                "pair_count",
                "geolocation_city",
                "geolocation_state",
            ],
            ascending=[True, False, True, True],
            na_position="last",
        )
        .drop_duplicates("geolocation_zip_code_prefix")
        .drop(columns="pair_count")
    )
    result = coordinates.merge(
        pair_counts, on="geolocation_zip_code_prefix", how="left"
    )
    result = result[
        [
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
            "geolocation_city",
            "geolocation_state",
        ]
    ]
    LOGGER.info("Geolocation rows: %s -> %s", len(table), len(result))
    return result


def _clean_reviews(table: pd.DataFrame) -> pd.DataFrame:
    ordered = table.sort_values(
        ["order_id", "review_creation_date", "review_answer_timestamp", "review_id"],
        na_position="first",
    )
    result = ordered.drop_duplicates(subset=["order_id"], keep="last").reset_index(drop=True)
    LOGGER.info("Review rows: %s -> %s", len(table), len(result))
    return result


def _clean_orders(table: pd.DataFrame) -> pd.DataFrame:
    """Calculate whole-day delay and flag positive delays as late.

    The estimated delivery date is stored at midnight, so zero means delivery on
    the estimated date and ``is_late`` is true only when the delay is positive.
    """
    result = table.copy()
    delivered = result["order_status"].eq("delivered")
    has_delivery_date = result["order_delivered_customer_date"].notna()
    inconsistent = (~delivered & has_delivery_date) | (
        delivered & ~has_delivery_date
    )
    result["delivery_date_inconsistent"] = inconsistent
    result["delivery_delay_days"] = pd.NA
    valid_delay = (
        delivered
        & ~inconsistent
        & result["order_estimated_delivery_date"].notna()
        & result["order_delivered_customer_date"].notna()
    )
    result.loc[valid_delay, "delivery_delay_days"] = (
        result.loc[valid_delay, "order_delivered_customer_date"]
        - result.loc[valid_delay, "order_estimated_delivery_date"]
    ).dt.days
    result["delivery_delay_days"] = result["delivery_delay_days"].astype("Int64")
    result["is_late"] = (result["delivery_delay_days"] > 0).astype("boolean")
    return result


def _clean_products(
    products: pd.DataFrame, translations: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cleaned = products.rename(
        columns={
            "product_name_lenght": "product_name_length",
            "product_description_lenght": "product_description_length",
        }
    ).copy()
    cleaned["product_category_name"] = cleaned["product_category_name"].fillna("unknown")
    translation_table = translations.copy()
    manual = pd.DataFrame(
        [
            {
                "product_category_name": category,
                "product_category_name_english": english,
            }
            for category, english in MANUAL_CATEGORY_TRANSLATIONS.items()
        ]
    )
    translation_table = pd.concat([translation_table, manual], ignore_index=True)
    translation_table = pd.concat(
        [
            translation_table,
            pd.DataFrame(
                [
                    {
                        "product_category_name": "unknown",
                        "product_category_name_english": "unknown",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    translation_table = translation_table.drop_duplicates(
        subset=["product_category_name"], keep="last"
    )
    return cleaned, translation_table


def transform_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Return cleaned tables without mutating the extracted input dictionary."""
    cleaned = {name: table.copy() for name, table in tables.items()}
    cleaned["orders"] = _clean_orders(cleaned["orders"])
    cleaned["reviews"] = _clean_reviews(cleaned["reviews"])
    cleaned["products"], cleaned["category_translation"] = _clean_products(
        cleaned["products"], cleaned["category_translation"]
    )
    cleaned["payments"]["payment_type"] = cleaned["payments"]["payment_type"].replace(
        {"not_defined": "unknown"}
    )
    cleaned["payments"]["payment_value_non_positive"] = (
        cleaned["payments"]["payment_value"] <= 0
    )
    cleaned["geolocation"] = _clean_geolocation(cleaned["geolocation"])
    return cleaned
