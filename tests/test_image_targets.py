"""The image-target registry: its facts, its status labels, its sources and alias resolution. No network."""

import copy
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import image_targets  # noqa: E402

REGISTRY = image_targets.load_registry()
STATUSES = {"VERIFIED", "PARTIAL", "UNKNOWN"}
EXPECTED_TARGETS = {"midjourney", "gpt-image", "flux-3", "flux-2", "flux-kontext", "ideogram", "recraft",
                    "firefly", "seedream", "sd-3-5", "sdxl", "comfyui", "nano-banana"}


class RegistryShapeTests(unittest.TestCase):
    def test_every_required_target_is_present_once(self):
        ids = [target["id"] for target in REGISTRY["targets"]]
        self.assertEqual(sorted(ids), sorted(set(ids)))
        self.assertEqual(set(ids), EXPECTED_TARGETS)

    def test_the_shipped_registry_has_no_problems(self):
        self.assertEqual(image_targets.validate_registry(REGISTRY), [])

    def test_every_claim_carries_a_status_and_a_source(self):
        for target in REGISTRY["targets"]:
            for claim in image_targets.claims_of(target):
                self.assertIn(claim["status"], STATUSES, (target["id"], claim["name"]))
                self.assertTrue(claim.get("source") or claim["status"] == "UNKNOWN", (target["id"], claim["name"]))

    def test_every_verified_claim_points_to_a_listed_source(self):
        for target in REGISTRY["targets"]:
            listed = {source["url"] for source in target["sources"]}
            for claim in image_targets.claims_of(target):
                if claim["status"] == "VERIFIED":
                    self.assertIn(claim["source"], listed, (target["id"], claim["name"]))

    def test_every_source_has_a_url_and_a_check_date(self):
        for target in REGISTRY["targets"]:
            for source in target["sources"]:
                self.assertRegex(source["url"], r"^https://")
                self.assertRegex(source["checked"], r"^\d{4}-\d{2}-\d{2}$")

    def test_each_target_names_its_access_path(self):
        for target in REGISTRY["targets"]:
            self.assertTrue(target["access"].get("api") or target["access"].get("ui"), target["id"])

    def test_a_bad_status_is_reported(self):
        broken = copy.deepcopy(REGISTRY)
        broken["targets"][0]["negative_prompt"]["status"] = "MAYBE"
        self.assertTrue(any("status" in p for p in image_targets.validate_registry(broken)))

    def test_a_verified_claim_without_a_listed_source_is_reported(self):
        broken = copy.deepcopy(REGISTRY)
        broken["targets"][0]["negative_prompt"]["source"] = "https://example.invalid/not-listed"
        self.assertTrue(any("source" in p for p in image_targets.validate_registry(broken)))


class NegativePromptFactsTests(unittest.TestCase):
    """The facts that most often go wrong, pinned against the pages read on 2026-10-14."""

    def mechanism(self, target_id):
        return image_targets.target(REGISTRY, target_id)["negative_prompt"]["mechanism"]

    def test_flux_3_and_flux_2_and_ideogram_and_gpt_image_have_no_negative_field(self):
        for target_id in ("flux-3", "flux-2", "ideogram", "gpt-image", "flux-kontext"):
            self.assertEqual(self.mechanism(target_id), "none", target_id)

    def test_midjourney_negative_is_the_no_parameter(self):
        self.assertEqual(self.mechanism("midjourney"), "flag")

    def test_recraft_v4_has_no_api_negative_field(self):
        recraft = image_targets.target(REGISTRY, "recraft")
        self.assertEqual(recraft["negative_prompt"]["mechanism"], "ui-only")
        self.assertIn("Studio", recraft["negative_prompt"]["text"])
        setting = next(s for s in recraft["native_settings"] if s["name"] == "negative_prompt")
        self.assertIn("V2 and V3", setting["values"])


class FactPinTests(unittest.TestCase):
    """Facts corrected on 2026-10-14 after comparing each claim with the page it cites. Each stays pinned."""

    def setting(self, target_id, name):
        item = image_targets.target(REGISTRY, target_id)
        return next(s for s in item["native_settings"] if s["name"] == name)

    def test_ideogram_context_window_is_four_integers_in_y_x_order(self):
        values = self.setting("ideogram", "context_window")["values"]
        self.assertIn("y_min,x_min,y_max,x_max", values)
        self.assertNotIn("x,y,w,h", values)

    def test_flux_3_boxes_are_documented_with_element_ids_in_the_caption(self):
        values = self.setting("flux-3", "boxes")["values"]
        self.assertIn("<id>", values)
        self.assertIn("[top, left, bottom, right]", values)

    def test_midjourney_raw_is_cited_to_the_parameter_list_that_contains_it(self):
        self.assertEqual(self.setting("midjourney", "--raw")["source"],
                         "https://docs.midjourney.com/hc/en-us/articles/32859204029709-Parameter-List")

    def test_midjourney_whole_number_aspect_rule_is_cited_to_the_aspect_page(self):
        self.assertEqual(self.setting("midjourney", "--ar")["source"],
                         "https://docs.midjourney.com/hc/en-us/articles/31894244298125-Aspect-Ratio")

    def test_midjourney_edit_is_cited_to_the_edit_model_page(self):
        self.assertEqual(image_targets.target(REGISTRY, "midjourney")["edit"]["source"],
                         "https://docs.midjourney.com/hc/en-us/articles/48495453462797-Edit-Model")

    def test_sd_3_5_negative_field_is_unknown_because_its_page_does_not_show_it(self):
        self.assertEqual(image_targets.target(REGISTRY, "sd-3-5")["negative_prompt"]["status"], "UNKNOWN")

    def test_every_verified_claim_cites_a_page_that_was_read(self):
        for target in REGISTRY["targets"]:
            kinds = {source["url"]: source["kind"] for source in target["sources"]}
            for claim in image_targets.claims_of(target):
                if claim["status"] == "VERIFIED":
                    self.assertEqual(kinds.get(claim["source"]), "primary-read", (target["id"], claim["name"]))

    def test_midjourney_style_flag_is_raw_not_style_raw(self):
        names = {setting["name"] for setting in image_targets.target(REGISTRY, "midjourney")["native_settings"]}
        self.assertIn("--raw", names)
        self.assertNotIn("--style raw", names)


class AliasResolutionTests(unittest.TestCase):
    def assertResolves(self, name, target_id):
        result = image_targets.resolve(name, REGISTRY)
        self.assertEqual(result["status"], "ok", (name, result))
        self.assertEqual(result["target"], target_id, name)

    def test_common_names_resolve_to_their_target(self):
        cases = {
            "Midjourney": "midjourney", "midjourney v8.2": "midjourney", "MJ": "midjourney",
            "GPT Image": "gpt-image", "gpt-image-2.5-sunburst": "gpt-image", "chatgpt images": "gpt-image",
            "FLUX 3": "flux-3", "flux-3-image": "flux-3", "FLUX.2 pro": "flux-2",
            "Kontext": "flux-kontext", "flux kontext": "flux-kontext",
            "Ideogram 4.5": "ideogram", "Recraft": "recraft", "recraft v4.1": "recraft",
            "Adobe Firefly": "firefly", "firefly": "firefly",
            "Seedream 5.0 Pro": "seedream", "Dreamina": "seedream",
            "SD 3.5": "sd-3-5", "sd3.5": "sd-3-5", "Stable Diffusion 3.5 Large": "sd-3-5",
            "SDXL": "sdxl", "ComfyUI": "comfyui", "Comfy": "comfyui",
            "Nano Banana Pro": "nano-banana", "gemini-nano-banana-2.1": "nano-banana",
        }
        for name, target_id in cases.items():
            with self.subTest(name=name):
                self.assertResolves(name, target_id)

    def test_an_ambiguous_name_lists_its_candidates_and_renders_nothing(self):
        result = image_targets.resolve("flux", REGISTRY)
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual({"flux-3", "flux-2", "flux-kontext"} & set(result["candidates"]),
                         {"flux-3", "flux-2", "flux-kontext"})
        self.assertNotIn("prompt", result)

    def test_stable_diffusion_without_a_version_is_ambiguous(self):
        result = image_targets.resolve("stable diffusion", REGISTRY)
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(set(result["candidates"]), {"sd-3-5", "sdxl"})

    def test_an_unknown_name_is_reported_as_unknown(self):
        result = image_targets.resolve("some tool nobody listed", REGISTRY)
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["target"])

    def test_nano_banana_is_a_redirect_not_a_renderer(self):
        result = image_targets.resolve("nano banana", REGISTRY)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["target"], "nano-banana")
        self.assertEqual(image_targets.target(REGISTRY, "nano-banana")["route"], "gemini")

    def test_aliases_do_not_collide_between_targets(self):
        seen = {}
        for target in REGISTRY["targets"]:
            for alias in target["aliases"]:
                key = image_targets.normalize(alias)
                self.assertNotIn(key, seen, f"{alias!r} is listed for {target['id']} and {seen.get(key)}")
                seen[key] = target["id"]


class GeneratedReferenceTests(unittest.TestCase):
    def test_the_markdown_reference_is_the_generated_text(self):
        with open(image_targets.MARKDOWN_PATH, encoding="utf-8") as handle:
            committed = handle.read()
        self.assertEqual(committed, image_targets.render_markdown(REGISTRY),
                         "references/image-targets.md is stale: run python3 scripts/image_targets.py markdown")

    def test_generation_is_deterministic(self):
        self.assertEqual(image_targets.render_markdown(REGISTRY), image_targets.render_markdown(REGISTRY))

    def test_every_target_appears_in_the_markdown_index(self):
        text = image_targets.render_markdown(REGISTRY)
        for item in REGISTRY["targets"]:
            self.assertIn(f"`{item['id']}`", text, item["id"])

    def test_the_markdown_carries_each_source_url_and_check_date(self):
        text = image_targets.render_markdown(REGISTRY)
        for item in REGISTRY["targets"]:
            for source in item["sources"]:
                self.assertIn(source["url"], text)
                self.assertIn(source["checked"], text)

    def test_the_registry_check_command_passes(self):
        import io
        import contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = image_targets.main(["check"])
        self.assertEqual(code, 0, out.getvalue())


if __name__ == "__main__":
    unittest.main()
