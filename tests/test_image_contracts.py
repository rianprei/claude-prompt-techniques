import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from contracts import (load_catalog, model_ids_named, model_ratios, reference_total,  # noqa: E402
                       resolve_target)
from validate_prompt import (check_edit_preservation, check_negative_list,  # noqa: E402
                             check_reference_roles, check_text_quotes, validate)

OFFICIAL_RATIOS = ["1:1", "1:4", "4:1", "1:8", "8:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
CURRENT = ("gemini-nano-banana-2.1", "gemini-3.1-flash-image", "gemini-3.1-flash-lite-image", "gemini-3-pro-image")


class AliasTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()

    def named(self, text):
        return model_ids_named(text, self.catalog)

    def test_commercial_names_resolve_to_their_ids(self):
        self.assertEqual(self.named("Nano Banana 2.1 for the hero"), ["gemini-nano-banana-2.1"])
        self.assertEqual(self.named("Nano Banana 2"), ["gemini-3.1-flash-image"])
        self.assertEqual(self.named("Nano Banana 2 Lite"), ["gemini-3.1-flash-lite-image"])
        self.assertEqual(self.named("Nano Banana Pro"), ["gemini-3-pro-image"])
        self.assertEqual(self.named("Gemini 2.5 Flash Image"), ["gemini-2.5-flash-image"])

    def test_nano_banana_two_is_not_read_inside_two_point_one_or_lite(self):
        self.assertNotIn("gemini-3.1-flash-image", self.named("Nano Banana 2.1"))
        self.assertNotIn("gemini-3.1-flash-image", self.named("Nano Banana 2 Lite"))
        self.assertEqual(self.named("Nano Banana 2.10"), [])

    def test_bare_family_name_is_not_a_model(self):
        self.assertEqual(self.named("Nano Banana"), [])
        self.assertEqual(resolve_target("nano banana", self.catalog)["id"], "gemini-nano-banana-2.1")
        self.assertEqual(resolve_target("Gemini Image", self.catalog)["id"], "gemini-nano-banana-2.1")

    def test_family_name_with_a_version_is_not_guessed(self):
        # 'Nano Banana 3' is not in the catalog: it must not silently become the default model.
        self.assertIsNone(resolve_target("Nano Banana 3", self.catalog))
        self.assertIsNone(resolve_target("Gemini Image Lite Max", self.catalog))

    def test_preview_names_resolve_to_their_shut_down_ids(self):
        self.assertEqual(self.named("Nano Banana 2 preview"), ["gemini-3.1-flash-image-preview"])

    def test_two_names_in_one_text_are_ambiguous_for_a_target(self):
        self.assertIsNone(resolve_target("Nano Banana 2.1 and Nano Banana Pro", self.catalog))

    def test_text_model_names_are_not_image_aliases(self):
        self.assertEqual(self.named("gemini-2.5-pro"), [])
        self.assertIsNone(resolve_target("gemini-2.5-pro", self.catalog))

    def test_every_alias_maps_to_one_model(self):
        seen = {}
        for model in self.catalog["models"]:
            for name in model.get("aliases", []):
                self.assertNotIn(name, seen, f"{name} is an alias of two models")
                seen[name] = model["id"]


class PerModelLimitsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()
        cls.models = {m["id"]: m for m in cls.catalog["models"]}

    def test_each_current_model_accepts_only_official_ratios(self):
        for model_id in CURRENT:
            for ratio in model_ratios(self.catalog, self.models[model_id]):
                self.assertIn(ratio, OFFICIAL_RATIOS, model_id)

    def test_fourteen_ratios_only_for_the_two_models_the_guide_lists_them_for(self):
        full = {m for m in CURRENT if len(model_ratios(self.catalog, self.models[m])) == 14}
        self.assertEqual(full, {"gemini-nano-banana-2.1", "gemini-3.1-flash-image"})

    def test_pro_has_no_extreme_ratios(self):
        ratios = model_ratios(self.catalog, self.models["gemini-3-pro-image"])
        for ratio in ("1:4", "4:1", "1:8", "8:1"):
            self.assertNotIn(ratio, ratios)

    def test_reference_total_is_fourteen_for_each_current_model(self):
        for model_id in CURRENT:
            self.assertEqual(reference_total(self.models[model_id]), 14, model_id)

    def test_per_type_limits_add_up_to_the_total_where_they_are_listed(self):
        for model_id in ("gemini-nano-banana-2.1", "gemini-3.1-flash-image", "gemini-3-pro-image"):
            limits = [v for v in self.models[model_id]["reference_limits"].values() if v]
            self.assertEqual(sum(limits), self.models[model_id]["reference_total_max"], model_id)

    def test_thinking_levels_are_a_subset_of_the_enum(self):
        enum = set(self.catalog["thinking_levels"])
        for model in self.catalog["models"]:
            levels = (model.get("thinking") or {}).get("levels") or []
            self.assertTrue(set(levels) <= enum, model["id"])

    def test_only_one_model_is_current_and_it_is_the_default(self):
        current = [m["id"] for m in self.catalog["models"] if m["status"] == "current"]
        self.assertEqual(current, [self.catalog["bare_family_name"]["default_model"]])

    def test_release_dates_are_stated_in_the_markdown(self):
        with open(os.path.join(ROOT, "references", "gemini-image-models.md"), encoding="utf-8") as fh:
            md = fh.read()
        for model in self.catalog["models"]:
            if model.get("released"):
                self.assertIn(model["released"], md, model["id"])


class ImageChecksTest(unittest.TestCase):
    def test_edit_needs_a_preservation_clause(self):
        self.assertTrue(check_edit_preservation("Edit the provided photo: change the sofa to leather."))
        self.assertFalse(check_edit_preservation(
            "Edit the provided photo: change the sofa to leather. Keep everything else exactly the same."))

    def test_generation_without_a_reference_needs_no_preservation_clause(self):
        self.assertEqual(check_edit_preservation("Make a lighthouse at dusk with a change of weather."), [])

    def test_portuguese_edit_and_preservation_are_read(self):
        self.assertEqual(check_edit_preservation("Na foto anexada, troque o sofá por couro. Mantenha o resto igual."), [])
        self.assertTrue(check_edit_preservation("Na foto anexada, troque o sofá por couro."))

    def test_two_numbered_references_need_two_roles(self):
        self.assertTrue(check_reference_roles("Combine image 1 and image 2 on a street."))
        self.assertEqual(check_reference_roles(
            "Use the character from image 1 for identity and the palette of image 2."), [])

    def test_one_reference_needs_no_role(self):
        self.assertEqual(check_reference_roles("Use the reference image for the pose."), [])

    def test_text_needs_quotation_marks_unless_none_is_wanted(self):
        self.assertTrue(check_text_quotes("A sign with the text Open today."))
        self.assertEqual(check_text_quotes('A sign with the text "Open today".'), [])
        self.assertEqual(check_text_quotes("A sign, no text in the image."), [])

    def test_a_long_list_of_negations_is_flagged_and_a_short_one_is_not(self):
        self.assertTrue(check_negative_list("No cars, no people, no signs and never any birds."))
        self.assertEqual(check_negative_list("An empty street with no signs."), [])


class FamilyTargetTest(unittest.TestCase):
    """A family name used as a validator target gets the image checks of the default model."""

    def test_gemini_image_target_is_checked_as_an_image_model(self):
        findings = validate("Make a poster of a harbor. Aspect ratio 3:1.", "Gemini Image", load_catalog())
        self.assertIn("W-ASPECT-RATIO", {f["code"] for f in findings})

    def test_nano_banana_target_is_checked_as_an_image_model(self):
        findings = validate("Make a poster of a harbor. Aspect ratio 3:1.", "Nano Banana", load_catalog())
        self.assertIn("W-ASPECT-RATIO", {f["code"] for f in findings})


class DocumentedFactsTest(unittest.TestCase):
    def test_routing_names_every_current_model_id_and_alias(self):
        with open(os.path.join(ROOT, "references", "tool-routing.md"), encoding="utf-8") as fh:
            routing = fh.read()
        catalog = load_catalog()
        for model in catalog["models"]:
            if model["status"] in ("current", "active"):
                self.assertIn(f"`{model['id']}`", routing, model["id"])
                for alias in model.get("aliases", []):
                    self.assertIn(f'"{alias}"', routing, f"{model['id']}: alias {alias!r} is not in the profile")


class SourceHostsTest(unittest.TestCase):
    """Image facts cite only Google's own pages, and the API endpoint, so each one can be checked at its source."""
    ALLOWED = {"ai.google.dev", "deepmind.google", "cloud.google.com", "generativelanguage.googleapis.com"}

    def test_image_files_cite_only_google_hosts(self):
        files = [os.path.join(ROOT, "references", name) for name in
                 ("gemini-image-models.json", "gemini-image-models.md", "gemini-image-examples.md")]
        for path in files:
            with open(path, encoding="utf-8") as fh:
                hosts = set(re.findall(r"https?://([^/\s\")\]]+)", fh.read()))
            self.assertTrue(hosts <= self.ALLOWED, f"{os.path.basename(path)} cites {sorted(hosts - self.ALLOWED)}")


class MarkdownAgreementTest(unittest.TestCase):
    """The per-model tables in gemini-image-models.md must list exactly the values in the JSON."""

    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()
        with open(os.path.join(ROOT, "references", "gemini-image-models.md"), encoding="utf-8") as fh:
            cls.md = fh.read()

    def test_ratio_rows_list_exactly_the_json_ratios_of_each_model(self):
        # The ratio table has three cells: model, ratios, basis. Only the ratio cell is read.
        by_model = {}
        for row in self.md.split("\n"):
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if len(cells) == 3 and cells[0].startswith("`gemini-") and re.search(r"\d+:\d+", cells[1]):
                by_model[cells[0].strip("`")] = set(re.findall(r"\d+:\d+", cells[1]))
        for model in self.catalog["models"]:
            if model["status"] in ("current", "active", "deprecated"):
                self.assertIn(model["id"], by_model, model["id"])
                self.assertEqual(by_model[model["id"]], set(model.get("aspect_ratios", [])), model["id"])

    def test_thinking_rows_list_exactly_the_json_levels_and_default(self):
        for model in self.catalog["models"]:
            thinking = model.get("thinking")
            if not thinking:
                continue
            # The thinking table has three cells: model, levels, default. The reference table has four, so it is skipped.
            rows = []
            for ln in self.md.split("\n"):
                cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                if len(cells) == 3 and cells[0] == f"`{model['id']}`" and re.search(r"\b(?:MINIMAL|LOW|MEDIUM|HIGH)\b|not listed", cells[1]):
                    rows.append(ln)
            self.assertEqual(len(rows), 1, model["id"])
            row = rows[0]
            if thinking["levels"] is None:
                self.assertIn("not listed", row, model["id"])
                continue
            self.assertEqual(set(re.findall(r"\b(?:MINIMAL|LOW|MEDIUM|HIGH)\b", row)), set(thinking["levels"]), model["id"])
            self.assertIn(thinking["default"], row, model["id"])

    def test_reference_limits_in_the_markdown_match_the_json(self):
        pro_row = next(ln for ln in self.md.split("\n") if ln.startswith("| `gemini-3-pro-image` | 6 | 5 | 3 |"))
        pro = next(m for m in self.catalog["models"] if m["id"] == "gemini-3-pro-image")
        for value in pro["reference_limits"].values():
            self.assertIn(str(value), pro_row)


class ProfileCoverageTest(unittest.TestCase):
    """The Nano Banana profile must name each scenario the request asks for, and each commercial name."""

    TERMS = ("storyboard", "thumbnail", "product", "advertis", "website", "infographic", "slide", "edit",
             "reference", "refine", "preservation", "nano banana 2.1", "nano banana 2 lite", "nano banana pro",
             "gemini 3.1 flash image", "gemini 3 pro image", "quotation marks", "localiz", "hierarchy", "mood")

    def test_profile_names_each_requested_scenario_and_model_name(self):
        with open(os.path.join(ROOT, "references", "tool-routing.md"), encoding="utf-8") as fh:
            routing = fh.read()
        section = routing.split("**Nano Banana / Gemini Image**", 1)[1].split("**Image AI — Reference Editing**", 1)[0]
        section = section.lower()
        for term in self.TERMS:
            self.assertIn(term, section, term)


if __name__ == "__main__":
    unittest.main()
