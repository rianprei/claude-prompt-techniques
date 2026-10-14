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


class UltragoalFactTests(unittest.TestCase):
    """Facts and routes added on 2026-10-14 (ultragoal), each pinned to the page that states it."""

    def claim(self, target_id, field):
        return image_targets.target(REGISTRY, target_id)[field]

    def setting(self, target_id, name):
        item = image_targets.target(REGISTRY, target_id)
        return next(s for s in item["native_settings"] if s["name"] == name)

    def test_new_routes_resolve_to_their_targets(self):
        cases = {"FLUX.2 klein": "flux-2", "flux 2 max": "flux-2", "SD 3.5 Turbo": "sd-3-5",
                 "stable diffusion 3.5 turbo": "sd-3-5", "Seedream 5.0 lite": "seedream", "Seedream 4.5": "seedream",
                 "Recraft V4.1 Flash": "recraft"}
        for name, target_id in cases.items():
            with self.subTest(name=name):
                self.assertEqual(image_targets.resolve(name, REGISTRY).get("target"), target_id)

    def test_gpt_image_2_alias_is_still_one_target_after_the_new_model_notes(self):
        self.assertEqual(image_targets.resolve("gpt image 2", REGISTRY)["target"], "gpt-image")

    def test_the_ideogram_text_rule_is_verified_for_the_image_app_only(self):
        claim = self.claim("ideogram", "text_in_image")
        self.assertEqual(claim["status"], "VERIFIED")
        self.assertIn("quotation marks", claim["text"])
        self.assertIn("API documentation pages", claim["text"])

    def test_the_ideogram_json_bbox_order_is_y_min_x_min_y_max_x_max(self):
        self.assertIn("[y_min, x_min, y_max, x_max]", self.claim("ideogram", "prompt_style")["text"])

    def test_the_recraft_v41_does_not_take_negative_prompts(self):
        self.assertIn("V2 and V3", self.setting("recraft", "negative_prompt")["values"])
        self.assertIn("V4.1", self.setting("recraft", "negative_prompt")["values"])

    def test_the_recraft_edit_endpoints_are_documented(self):
        edit = self.claim("recraft", "edit")
        self.assertEqual(edit["status"], "VERIFIED")
        self.assertIn("/v1/images/imageToImage", edit["text"])
        self.assertIn("/v1/images/inpaint", edit["text"])

    def test_the_seedream_reference_limits_are_verified_per_family(self):
        refs = self.claim("seedream", "references")
        self.assertEqual(refs["status"], "VERIFIED")
        self.assertIn("up to 10", refs["text"])
        self.assertIn("up to 14", refs["text"])

    def test_the_seedream_negative_field_is_partial_because_one_page_was_read(self):
        self.assertEqual(self.claim("seedream", "negative_prompt")["status"], "PARTIAL")

    def test_the_sd35_turbo_steps_and_cfg_come_from_the_comfyui_example(self):
        setting = self.setting("sd-3-5", "Large Turbo in ComfyUI")
        self.assertIn("steps 4", setting["values"])
        self.assertIn("cfg 1.2", setting["values"])
        self.assertEqual(setting["source"], "https://comfyanonymous.github.io/ComfyUI_examples/sd3/")

    def test_the_sdxl_resolution_comes_from_the_comfyui_example(self):
        self.assertIn("1024x1024", self.setting("sdxl", "resolution")["values"])

    def test_the_comfyui_denoise_rule_is_verified_on_the_image_to_image_page(self):
        setting = self.setting("comfyui", "denoise")
        self.assertEqual(setting["status"], "VERIFIED")
        self.assertIn("below 1", setting["values"])

    def test_the_gpt_image_input_fidelity_is_partial_because_2_5_is_not_stated(self):
        setting = self.setting("gpt-image", "input_fidelity")
        self.assertEqual(setting["status"], "PARTIAL")
        self.assertIn("2.5: not stated", setting["values"])

    def test_the_firefly_style_strength_default_is_50(self):
        self.assertIn("default 50", self.setting("firefly", "style reference strength")["values"])

    def test_the_objective_urls_that_failed_are_recorded_as_not_found(self):
        kinds = {source["url"]: source["kind"] for target in REGISTRY["targets"] for source in target["sources"]}
        self.assertEqual(kinds.get("https://developers.openai.com/api/reference/resources/images/methods/edit"), "not-found")

    def test_the_client_rendered_stability_pages_are_recorded_as_unreadable(self):
        kinds = {source["url"]: source["kind"] for source in image_targets.target(REGISTRY, "sd-3-5")["sources"]}
        self.assertEqual(kinds.get("https://platform.stability.ai/docs/features/multi-prompting"), "primary-unreadable")


class ReviewFactTests(unittest.TestCase):
    """Corrections from the brutal review of 2026-10-14: each attribution points at the page that states the fact."""

    def setting(self, target_id, name):
        item = image_targets.target(REGISTRY, target_id)
        return next(s for s in item["native_settings"] if s["name"] == name)

    def test_the_ideogram_seed_range_is_partial_because_it_is_the_app_limit(self):
        seed = self.setting("ideogram", "seed")
        self.assertEqual(seed["status"], "PARTIAL")
        self.assertEqual(seed["source"], "https://docs.ideogram.ai/create/image-settings.md")

    def test_the_recraft_style_is_partial_and_names_the_disagreement(self):
        style = self.setting("recraft", "style")
        self.assertEqual(style["status"], "PARTIAL")
        self.assertIn("V4.1 Flash", style["values"])

    def test_the_seedream_size_range_is_cited_to_the_api_reference(self):
        self.assertEqual(self.setting("seedream", "size")["source"],
                         "https://ai.byteplus.com/ark/region:ap-southeast-1/docs/image-generation-api.md")

    def test_the_gpt_image_output_format_and_background_are_cited_to_the_images_edit_reference(self):
        edit = "https://developers.openai.com/api/reference/python/resources/images/methods/edit"
        self.assertEqual(self.setting("gpt-image", "output_format")["source"], edit)
        self.assertEqual(self.setting("gpt-image", "background")["source"], edit)

    def test_the_gpt_image_moderation_default_is_cited_to_the_images_generate_reference(self):
        moderation = self.setting("gpt-image", "moderation")
        self.assertIn("auto (default)", moderation["values"])
        self.assertTrue(moderation["source"].endswith("methods/generate"))

    def test_the_gemini_shutdown_date_is_the_earliest_possible_one_and_its_conflict_is_recorded(self):
        target = image_targets.target(REGISTRY, "nano-banana")
        text = " ".join(target["limitations"])
        self.assertIn("2027-03-15", text)
        self.assertIn("earliest possible", text)
        self.assertIn("2026-10-02", text)
        kinds = {source["url"]: source["kind"] for source in target["sources"]}
        self.assertEqual(kinds.get("https://ai.google.dev/gemini-api/docs/deprecations"), "primary-read")
        self.assertEqual(kinds.get("https://ai.google.dev/gemini-api/docs/pricing"), "primary-read")

    def test_the_seedream_limitations_no_longer_call_the_optimize_options_unread(self):
        text = " ".join(image_targets.target(REGISTRY, "seedream")["limitations"])
        self.assertNotIn("optimize_prompt_options", text)

    def test_the_sdxl_resolution_says_optimal_performance_as_the_example_page_does(self):
        value = self.setting("sdxl", "resolution")["values"]
        self.assertIn("optimal performance", value)
        self.assertNotIn("best", value)

    def test_the_flux_3_resolution_list_carries_only_the_names_the_overview_gives(self):
        self.assertEqual(self.setting("flux-3", "resolution")["values"], "768sq, 1k, 1.5k, 2k, 4k")


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
