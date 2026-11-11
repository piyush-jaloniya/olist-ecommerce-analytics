from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from etl.dashboard import export_dashboard_data


ROOT = Path(__file__).resolve().parents[1]
STAR_PATH = ROOT / "data" / "processed" / "olist_star.sqlite"
ANALYSIS_PATH = ROOT / "docs" / "analysis"


class DashboardExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not STAR_PATH.exists():
            raise unittest.SkipTest("Run `python run_pipeline.py model` before dashboard tests.")

    def test_export_matches_verified_totals_and_row_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            export_dashboard_data(STAR_PATH, output_dir, ROOT / "sql" / "analysis")

            expected_counts = {
                "overview": 1,
                "monthly": 20,
                "yoy": 2,
                "categories": 74,
                "category_freight": 74,
                "delivery_delay": 8,
                "repeat": 7,
                "cohort": 21,
                "states": 27,
                "sellers": 2970,
                "payment_mix": 11,
            }
            for name, expected_count in expected_counts.items():
                rows = json.loads((output_dir / f"{name}.json").read_text(encoding="utf-8"))
                self.assertEqual(expected_count, len(rows), name)

            overview = json.loads((output_dir / "overview.json").read_text(encoding="utf-8"))[0]
            self.assertEqual(96478, overview["delivered_orders"])
            self.assertEqual(13221498.11, overview["delivered_revenue"])
            self.assertEqual(93358, overview["buyers"])
            self.assertEqual(2801, overview["repeat_buyers"])
            metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
            self.assertTrue(metadata["static_export"])
            self.assertEqual(11, metadata["dataset_count"])
            self.assertEqual(20, metadata["datasets"]["monthly"]["rows"])

    def test_analysis_json_matches_analysis_csvs(self) -> None:
        mapping = {
            "monthly": "01_monthly_revenue_orders.csv",
            "yoy": "02_yoy_growth.csv",
            "categories": "03_category_performance.csv",
            "category_freight": "04_category_freight_burden.csv",
            "delivery_delay": "05_delay_vs_review.csv",
            "repeat": "06_repeat_rate.csv",
            "cohort": "07_cohort_retention.csv",
            "states": "08_state_delivery_performance.csv",
            "sellers": "09_seller_delivery_performance.csv",
            "payment_mix": "10_payment_mix.csv",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            export_dashboard_data(STAR_PATH, output_dir, ROOT / "sql" / "analysis")
            for name, csv_name in mapping.items():
                with (ANALYSIS_PATH / csv_name).open(encoding="utf-8", newline="") as csv_file:
                    csv_rows = list(csv.DictReader(csv_file))
                json_rows = json.loads((output_dir / f"{name}.json").read_text(encoding="utf-8"))
                normalized_json = [
                    {key: "" if value is None else str(value) for key, value in row.items()}
                    for row in json_rows
                ]
                self.assertEqual(csv_rows, normalized_json, name)

    def test_missing_database_fails_clearly(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "Run `python run_pipeline.py model` first"):
            export_dashboard_data(
                ROOT / "data" / "processed" / "missing.sqlite",
                ROOT / "frontend" / "data",
                ROOT / "sql" / "analysis",
            )


if __name__ == "__main__":
    unittest.main()
