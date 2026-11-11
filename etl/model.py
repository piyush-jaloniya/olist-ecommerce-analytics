"""Build the star-schema database from the cleaned staging database."""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

from etl.reconcile_star import reconcile_star

LOGGER = logging.getLogger(__name__)

STAR_TABLES = [
    "dim_date",
    "dim_customer",
    "dim_product",
    "dim_seller",
    "fact_orders",
    "fact_order_items",
    "fact_order_payments",
]


def build_star(staging_path: Path, star_path: Path, sql_dir: Path) -> Path:
    """Rebuild the star database atomically from a read-only staging database."""
    if not staging_path.exists():
        raise FileNotFoundError(
            f"Staging database does not exist: {staging_path}. "
            "Run `python run_pipeline.py etl` first."
        )

    tmp_path = star_path.with_name(star_path.name + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    connection: sqlite3.Connection | None = None
    try:
        # Build beside the final file, then replace it atomically so failures do not
        # destroy a previously successful star database.
        connection = sqlite3.connect(str(tmp_path), uri=True)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript((sql_dir / "schema.sql").read_text(encoding="utf-8"))

        # A read-only URI prevents the model stage from modifying staging data.
        staging_uri = staging_path.resolve().as_uri() + "?mode=ro"
        connection.execute("ATTACH DATABASE ? AS stg", (staging_uri,))
        connection.executescript((sql_dir / "load_star.sql").read_text(encoding="utf-8"))
        connection.commit()
        reconcile_star(connection)

        LOGGER.info("SQLite version: %s", sqlite3.sqlite_version)
        for table in STAR_TABLES:
            count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            LOGGER.info("%s: %s rows", table, count)

        connection.execute("DETACH DATABASE stg")
        connection.close()
        connection = None
        os.replace(tmp_path, star_path)
        return star_path
    except Exception:
        if connection is not None:
            try:
                connection.execute("DETACH DATABASE stg")
            except sqlite3.Error:
                pass
            connection.close()
        if tmp_path.exists():
            tmp_path.unlink()
        raise
