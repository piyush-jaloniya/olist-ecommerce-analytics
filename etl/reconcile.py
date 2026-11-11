"""Reconcile transformed tables with raw inputs and SQLite outputs."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from etl.transform import (
    BRAZIL_LAT_RANGE,
    BRAZIL_LNG_RANGE,
    MANUAL_CATEGORY_TRANSLATIONS,
)

LOGGER = logging.getLogger(__name__)


class ReconciliationError(ValueError):
    """Raised when expected, cleaned, and SQLite row counts do not agree."""


def reconcile_tables(
    raw_tables: dict[str, pd.DataFrame],
    cleaned_tables: dict[str, pd.DataFrame],
    database_path: Path,
) -> None:
    """Compare expected row counts with cleaned DataFrames and SQLite tables."""
    unchanged_tables = [
        "orders",
        "order_items",
        "payments",
        "customers",
        "products",
        "sellers",
    ]
    expected = {name: len(raw_tables[name]) for name in unchanged_tables}
    expected["reviews"] = raw_tables["reviews"]["order_id"].nunique()

    raw_geolocation = raw_tables["geolocation"]
    in_brazil = (
        raw_geolocation["geolocation_lat"].between(*BRAZIL_LAT_RANGE)
        & raw_geolocation["geolocation_lng"].between(*BRAZIL_LNG_RANGE)
    )
    expected["geolocation"] = raw_geolocation.loc[
        in_brazil, "geolocation_zip_code_prefix"
    ].nunique()

    translation_keys = set(raw_tables["category_translation"]["product_category_name"])
    translation_keys.update(MANUAL_CATEGORY_TRANSLATIONS)
    translation_keys.add("unknown")
    expected["category_translation"] = len(translation_keys)

    raw_counts = {name: len(table) for name, table in raw_tables.items()}
    cleaned_counts = {name: len(table) for name, table in cleaned_tables.items()}
    connection = sqlite3.connect(database_path)
    try:
        sqlite_counts = {
            name: int(
                connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            )
            for name in expected
        }
    finally:
        connection.close()

    LOGGER.info("Reconciliation results:")
    LOGGER.info("%-22s %8s %9s %9s %8s %s", "table", "raw", "expected", "cleaned", "sqlite", "status")
    mismatches: list[str] = []
    for name in expected:
        status = "OK"
        if (
            expected[name] != cleaned_counts[name]
            or cleaned_counts[name] != sqlite_counts[name]
        ):
            status = "MISMATCH"
            mismatches.append(
                f"{name}: expected={expected[name]}, cleaned={cleaned_counts[name]}, "
                f"sqlite={sqlite_counts[name]}"
            )
        LOGGER.info(
            "%-22s %8d %9d %9d %8d %s",
            name,
            raw_counts[name],
            expected[name],
            cleaned_counts[name],
            sqlite_counts[name],
            status,
        )
    if mismatches:
        raise ReconciliationError("Row-count reconciliation failed: " + "; ".join(mismatches))
    LOGGER.info("Reconciliation passed for all %s tables", len(expected))
