"""Persist transformed Olist tables as CSV exports and SQLite staging tables."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger(__name__)


def load_tables(tables: dict[str, pd.DataFrame], processed_dir: Path) -> Path:
    """Write cleaned CSVs and a replaceable SQLite staging database."""
    processed_dir.mkdir(parents=True, exist_ok=True)
    database_path = processed_dir / "olist_staging.sqlite"
    for name, table in tables.items():
        table.to_csv(processed_dir / f"{name}.csv", index=False)
    with sqlite3.connect(database_path) as connection:
        for name, table in tables.items():
            table.to_sql(name, connection, if_exists="replace", index=False)
    LOGGER.info("Loaded cleaned CSVs and SQLite database at %s", database_path)
    return database_path
