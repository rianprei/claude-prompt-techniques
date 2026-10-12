import json
import os
import re
import unittest
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "references")


class ImageCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REF, "gemini-image-models.json"), encoding="utf-8") as fh:
            cls.catalog = json.load(fh)
        with open(os.path.join(REF, "gemini-image-models.md"), encoding="utf-8") as fh:
            cls.md = fh.read()

    def test_verification_date_is_a_real_date(self):
        date.fromisoformat(self.catalog["verified_on"])

    def test_aspect_ratios_are_the_fourteen_official_values(self):
        expected = ["1:1", "1:4", "4:1", "1:8", "8:1", "2:3", "3:2", "3:4",
                    "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
        self.assertEqual(self.catalog["aspect_ratios"], expected)

    def test_image_sizes_use_uppercase_k(self):
        sizes = self.catalog["image_sizes"]["values"]
        self.assertEqual(sizes, ["512", "1K", "2K", "4K"])
        for size in sizes:
            self.assertNotIn("k", size)
        self.assertTrue(self.catalog["image_sizes"]["uppercase_k_required"])

    def test_thinking_levels_are_the_uppercase_enum(self):
        self.assertEqual(self.catalog["thinking_levels"], ["MINIMAL", "LOW", "MEDIUM", "HIGH"])

    def test_batch_and_grounding_numbers(self):
        self.assertEqual(self.catalog["batch_discount"], 0.5)
        self.assertEqual(self.catalog["grounding_search"]["free_requests_per_month"], 5000)
        self.assertEqual(self.catalog["grounding_search"]["price_per_1000_after_free_usd"], 14.0)

    def test_exactly_one_current_model(self):
        current = [m["id"] for m in self.catalog["models"] if m["status"] == "current"]
        self.assertEqual(current, ["gemini-nano-banana-2.1"])

    def test_shut_down_models_have_a_shutdown_date_and_no_prices(self):
        for m in self.catalog["models"]:
            if m["status"] == "shut_down":
                self.assertIsNotNone(m["shutdown"], m["id"])
                self.assertNotIn("prices_usd_per_image", m, m["id"])

    def test_open_conflict_is_recorded_not_resolved(self):
        flash25 = next(m for m in self.catalog["models"] if m["id"] == "gemini-2.5-flash-image")
        self.assertIn("shutdown_conflict", flash25)

    def test_priced_sizes_match_declared_sizes(self):
        for m in self.catalog["models"]:
            if "prices_usd_per_image" in m:
                self.assertEqual(sorted(m["sizes"]), sorted(m["prices_usd_per_image"]), m["id"])

    def _table_row(self, model_id):
        models_section = self.md.split("## Models", 1)[1].split("## Enumerations", 1)[0]
        rows = [ln for ln in models_section.split("\n") if ln.startswith("|") and f"`{model_id}`" in ln]
        self.assertEqual(len(rows), 1, f"expected exactly one table row for {model_id}")
        return rows[0]

    def test_each_model_row_carries_its_own_prices(self):
        for m in self.catalog["models"]:
            row = self._table_row(m["id"])
            for price in m.get("prices_usd_per_image", {}).values():
                self.assertIn(str(price), row, f"{m['id']}: {price}")

    def test_markdown_aspect_ratio_line_matches_the_catalog(self):
        line = next(ln for ln in self.md.split("\n") if ln.startswith("**Aspect ratios"))
        self.assertEqual(re.findall(r"\d+:\d+", line), self.catalog["aspect_ratios"])

    def test_markdown_and_json_share_the_verification_date(self):
        self.assertIn(self.catalog["verified_on"], self.md)


if __name__ == "__main__":
    unittest.main()
