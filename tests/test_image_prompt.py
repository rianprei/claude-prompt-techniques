"""Rendering one visual brief for each image target. Native settings must stay apart from the prompt text. No network."""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import image_prompt  # noqa: E402
from validate_prompt import validate  # noqa: E402

SCENE = {
    "subject": "a ceramic teapot",
    "environment": "a wooden kitchen table by a window",
    "composition": "centred, with empty space above",
    "lighting": "soft morning light from the left",
    "color": "terracotta and cream",
    "medium": "product photograph",
    "aspect_ratio": "4:5",
    "constraints": ["no watermark", "no extra text"],
}


def brief(**changes):
    value = dict(SCENE)
    value.update(changes)
    return value


class ResolveAndRedirectTests(unittest.TestCase):
    def test_nano_banana_is_refused_as_a_render_and_pointed_to_template_n(self):
        result = image_prompt.render(brief(), "nano banana")
        self.assertEqual(result["status"], "redirect")
        self.assertNotIn("prompt", result)
        self.assertIn("Template N", result["use"])
        self.assertIn("studio", result["use"])

    def test_an_unknown_target_gets_a_portable_prompt_and_a_limitation(self):
        result = image_prompt.render(brief(), "some tool nobody listed")
        self.assertEqual(result["status"], "unknown")
        self.assertTrue(result["prompt"])
        self.assertEqual(result["native_settings"], {})
        self.assertIsNone(result["negative_prompt"])
        self.assertTrue(any("not in the registry" in w for w in result["warnings"]))

    def test_no_target_named_is_a_generic_fallback_that_says_so(self):
        result = image_prompt.render(brief(), "")
        self.assertEqual(result["status"], "unknown")
        self.assertTrue(any("No target was named" in w for w in result["warnings"]))
        self.assertEqual(result["native_settings"], {})

    def test_an_ambiguous_target_renders_nothing_and_lists_candidates(self):
        result = image_prompt.render(brief(), "flux")
        self.assertEqual(result["status"], "ambiguous")
        self.assertNotIn("prompt", result)
        self.assertIn("flux-3", result["candidates"])


class BriefValidationTests(unittest.TestCase):
    def test_unknown_brief_keys_are_refused(self):
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(colour="red"), "flux-3")

    def test_text_entries_need_content(self):
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(text=[{"placement": "top"}]), "gpt-image")

    def test_constraints_must_be_a_list_of_strings(self):
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(constraints="no logo"), "midjourney")

    def test_a_decimal_aspect_ratio_is_refused_because_midjourney_forbids_it(self):
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(aspect_ratio="1.5:1"), "midjourney")


class MidjourneyTests(unittest.TestCase):
    def setUp(self):
        self.result = image_prompt.render(brief(), "midjourney")

    def test_parameters_are_native_and_not_in_the_prompt_text(self):
        self.assertNotIn("--", self.result["prompt"])
        self.assertEqual(self.result["native_parameters"], "--ar 4:5 --no watermark, extra text")

    def test_the_paste_form_is_prompt_then_parameters(self):
        self.assertTrue(self.result["paste"].startswith(self.result["prompt"]))
        self.assertTrue(self.result["paste"].endswith("--ar 4:5 --no watermark, extra text"))

    def test_negative_is_the_no_flag_and_is_reported_as_flag(self):
        self.assertEqual(self.result["negative_mechanism"], "flag")
        self.assertEqual(self.result["negative_prompt"], "watermark, extra text")

    def test_the_moderation_note_about_no_is_a_limitation(self):
        self.assertTrue(any("each word" in item for item in self.result["limitations"]))

    def test_a_style_reference_becomes_the_sref_placeholder(self):
        result = image_prompt.render(brief(references=[{"role": "style", "use": "the palette"}]), "midjourney")
        self.assertIn("--sref <image URL or style code>", result["native_parameters"])

    def test_edit_needs_image_urls_and_says_so(self):
        result = image_prompt.render(brief(edit={"change": "make the teapot green", "preserve": ["the table"]}),
                                     "midjourney")
        self.assertIn("--edit", result["native_parameters"])
        self.assertTrue(any("URL" in w for w in result["warnings"]))

    def test_text_rendering_is_not_verified_for_midjourney(self):
        result = image_prompt.render(brief(text=[{"content": "TEA", "placement": "on the label"}]), "midjourney")
        self.assertIn('"TEA"', result["prompt"])
        self.assertTrue(any("not verified" in w for w in result["warnings"]))


class GptImageTests(unittest.TestCase):
    def setUp(self):
        self.result = image_prompt.render(brief(text=[{"content": "OPEN", "placement": "above the door",
                                                       "typography": "white sans-serif capitals"}]),
                                          "gpt-image")

    def test_complex_briefs_use_labelled_sections(self):
        for label in ("Scene:", "Subject:", "Constraints:"):
            self.assertIn(label, self.result["prompt"])

    def test_text_is_quoted_with_placement_and_typography(self):
        self.assertIn('"OPEN"', self.result["prompt"])
        self.assertIn("above the door", self.result["prompt"])
        self.assertIn("white sans-serif capitals", self.result["prompt"])

    def test_exclusions_are_sentences_because_there_is_no_negative_field(self):
        self.assertIsNone(self.result["negative_prompt"])
        self.assertEqual(self.result["negative_mechanism"], "none")
        self.assertIn("no watermark", self.result["prompt"])

    def test_default_model_is_sunburst_and_flare_is_optional(self):
        self.assertEqual(self.result["native_settings"]["model"], "gpt-image-2.5-sunburst")
        flare = image_prompt.render(brief(options={"model": "gpt-image-2.5-flare"}), "gpt-image")
        self.assertEqual(flare["native_settings"]["model"], "gpt-image-2.5-flare")

    def test_a_recommended_size_is_mapped_and_an_odd_ratio_is_left_for_the_user(self):
        square = image_prompt.render(brief(aspect_ratio="1:1"), "gpt-image")
        self.assertEqual(square["native_settings"]["size"], "1024x1024")
        odd = image_prompt.render(brief(aspect_ratio="4:5"), "gpt-image")
        self.assertIsNone(odd["native_settings"]["size"])
        self.assertTrue(any("WIDTHxHEIGHT" in w for w in odd["warnings"]))

    def test_transparent_background_requires_png_or_webp(self):
        result = image_prompt.render(brief(options={"background": "transparent"}), "gpt-image")
        self.assertEqual(result["native_settings"]["background"], "transparent")
        self.assertEqual(result["native_settings"]["output_format"], "png")

    def test_quality_levels_are_the_documented_ones(self):
        ok = image_prompt.render(brief(options={"quality": "xhigh"}), "gpt-image")
        self.assertEqual(ok["native_settings"]["quality"], "xhigh")
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(options={"quality": "ultra"}), "gpt-image")

    def test_an_edit_says_change_only_and_keep_the_rest(self):
        result = image_prompt.render(brief(edit={"change": "make the teapot green", "preserve": ["the table", "the light"]}),
                                     "gpt-image")
        self.assertIn("Change only:", result["prompt"])
        self.assertIn("Keep everything else the same", result["prompt"])
        self.assertEqual(result["native_settings"]["endpoint"], "images.edit")


class Flux3Tests(unittest.TestCase):
    def test_prose_with_no_labels_and_no_parameter_syntax(self):
        result = image_prompt.render(brief(), "flux-3")
        self.assertNotIn("Scene:", result["prompt"])
        self.assertNotIn("--", result["prompt"])
        self.assertIsNone(result["negative_prompt"])

    def test_an_exclusion_is_flagged_for_rewriting_as_a_positive_description(self):
        result = image_prompt.render(brief(constraints=["no watermark"]), "flux-3")
        self.assertTrue(any("positive" in w for w in result["warnings"]))

    def test_boxes_are_appended_as_a_json_array_at_the_end(self):
        boxes = [{"id": "background_1", "bbox": [0, 0, 1000, 1000], "desc": "a flat yellow field"},
                 {"id": "silhouette_1", "bbox": [150, 150, 850, 850], "desc": "a black silhouette"}]
        result = image_prompt.render(brief(boxes=boxes), "flux-3")
        self.assertTrue(result["prompt"].endswith(json.dumps(boxes)))

    def test_boxes_outside_the_0_1000_grid_are_refused(self):
        bad = [{"id": "a", "bbox": [0, 0, 1001, 500], "desc": "x"}]
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(boxes=bad), "flux-3")

    def test_a_seed_is_not_a_native_setting_of_flux_3(self):
        result = image_prompt.render(brief(options={"seed": 7}), "flux-3")
        self.assertNotIn("seed", result["native_settings"])
        self.assertTrue(any("seed" in w for w in result["warnings"]))

    def test_aspect_ratio_must_be_in_the_documented_list(self):
        ok = image_prompt.render(brief(aspect_ratio="9:16"), "flux-3")
        self.assertEqual(ok["native_settings"]["aspect_ratio"], "9:16")
        result = image_prompt.render(brief(aspect_ratio="4:5"), "flux-3")
        self.assertEqual(result["native_settings"]["aspect_ratio"], "4:5")  # 4:5 is in the list
        odd = image_prompt.render(brief(aspect_ratio="6:5"), "flux-3")
        self.assertEqual(odd["native_settings"]["aspect_ratio"], "auto")
        self.assertTrue(any("aspect" in w for w in odd["warnings"]))

    def test_references_and_images_limit(self):
        many = [{"role": "subject", "use": "x"}] * 11
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(references=many), "flux-3")


class FluxTwoTests(unittest.TestCase):
    def test_subject_action_style_context_order_and_length_band(self):
        result = image_prompt.render(brief(), "flux-2")
        self.assertIn("a ceramic teapot", result["prompt"])
        self.assertEqual(result["native_settings"], {})  # API field names were not read: none assumed
        self.assertTrue(any("not read" in w for w in result["warnings"]))

    def test_a_very_short_brief_gets_a_length_warning(self):
        result = image_prompt.render({"subject": "a red cube"}, "flux-2")
        self.assertTrue(any("words" in w for w in result["warnings"]))


class KontextTests(unittest.TestCase):
    def test_an_edit_describes_only_the_change_and_states_what_to_keep(self):
        result = image_prompt.render(brief(edit={"change": "the teapot becomes blue", "preserve": ["the table"]},
                                           aspect_ratio=None), "flux-kontext")
        self.assertIn("The teapot becomes blue.", result["prompt"])
        self.assertIn("Keep the table", result["prompt"])
        self.assertEqual(result["native_settings"]["endpoint"], "/v1/flux-kontext-pro")
        self.assertTrue(any("other visual fields" in w for w in result["warnings"]))

    def test_a_text_replacement_is_written_as_quoted_before_and_after(self):
        result = image_prompt.render({"edit": {"change": "change the sign text"},
                                      "text": [{"content": "FLUX & JOY", "replaces": "Sync & Bloom"}]},
                                     "flux-kontext")
        self.assertIn("'Sync & Bloom' changed to 'FLUX & JOY'", result["prompt"])

    def test_aspect_ratio_override_must_be_within_3_7_to_7_3(self):
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(aspect_ratio="1:4", edit={"change": "x"}), "flux-kontext")

    def test_generation_without_an_edit_is_warned_as_not_the_recommended_path(self):
        result = image_prompt.render(brief(), "flux-kontext")
        self.assertTrue(any("previous-generation" in w or "FLUX.2" in w for w in result["warnings"]))


class IdeogramTests(unittest.TestCase):
    def test_text_is_quoted_and_the_quality_default_is_recorded(self):
        result = image_prompt.render(brief(text=[{"content": "COFFEE", "placement": "top"}]), "ideogram")
        self.assertIn('"COFFEE"', result["prompt"])
        self.assertEqual(result["native_settings"]["rendering_quality"], "high")  # default without source images
        self.assertNotIn("background", result["native_settings"])  # no default is sent unless the brief sets one

    def test_an_edit_uses_precise_edit_with_context_window_none(self):
        result = image_prompt.render(brief(edit={"change": "make the mug blue", "preserve": ["the table"]}), "ideogram")
        self.assertEqual(result["native_settings"]["endpoint"], "/v2/image/precise-edit/ideogram-4-5")
        self.assertEqual(result["native_settings"]["context_window"], "none")
        self.assertIn("Keep the table", result["prompt"])

    def test_an_exclusion_is_written_as_a_positive_description_with_a_warning(self):
        result = image_prompt.render(brief(constraints=["no watermark"]), "ideogram")
        self.assertIsNone(result["negative_prompt"])
        self.assertTrue(any("positive" in w for w in result["warnings"]))


class RecraftTests(unittest.TestCase):
    def test_the_v4_api_has_no_negative_field_so_the_exclusion_stays_in_the_prompt(self):
        result = image_prompt.render(brief(constraints=["no watermark"]), "recraft")
        self.assertNotIn("negative_prompt", result["native_settings"])
        self.assertIn("No watermark.", result["prompt"])
        self.assertEqual(result["negative_prompt"], "watermark")
        self.assertTrue(any("V2 and V3" in w for w in result["warnings"]))

    def test_the_default_model_is_recorded_and_no_format_default_is_invented(self):
        result = image_prompt.render(brief(), "recraft")
        self.assertEqual(result["native_settings"]["model"], "recraftv4_1")
        self.assertNotIn("image_format", result["native_settings"])
        self.assertEqual(image_prompt.render(brief(options={"image_format": "png"}), "recraft")["native_settings"]["image_format"], "png")

    def test_text_layout_is_v3_only(self):
        result = image_prompt.render(brief(text=[{"content": "HELLO", "placement": "top"}]), "recraft")
        self.assertNotIn("text_layout", result["native_settings"])
        self.assertTrue(any("V3" in w for w in result["warnings"]))

    def test_a_negated_main_prompt_is_flagged(self):
        result = image_prompt.render(brief(subject="no people, just a teapot"), "recraft")
        self.assertTrue(any("negation" in w for w in result["warnings"]))


class SecondaryTargetTests(unittest.TestCase):
    def test_firefly_keeps_the_negative_out_of_native_settings(self):
        result = image_prompt.render(brief(constraints=["no watermark"]), "firefly")
        self.assertNotIn("negativePrompt", result["native_settings"])
        self.assertEqual(result["verification"], "PARTIAL")

    def test_firefly_structure_reference_strength_defaults_to_50_and_is_bounded(self):
        result = image_prompt.render(brief(references=[{"role": "structure", "use": "the outline"}]), "firefly")
        self.assertEqual(result["native_settings"]["structure"]["strength"], 50)
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(references=[{"role": "structure", "use": "x"}], options={"structure_strength": 101}),
                                "firefly")

    def test_seedream_is_partial_and_renders_no_native_settings(self):
        result = image_prompt.render(brief(), "seedream")
        self.assertEqual(result["native_settings"], {})
        self.assertEqual(result["verification"], "PARTIAL")

    def test_stable_diffusion_3_5_has_no_weight_syntax_and_says_so(self):
        result = image_prompt.render(brief(), "sd-3-5")
        self.assertNotRegex(result["prompt"], r"\(\w+:\d")
        self.assertEqual(result["verification"], "PARTIAL")
        self.assertTrue(any("not verified" in w for w in result["warnings"]))

    def test_sdxl_is_unknown_and_emits_no_weights_or_cfg(self):
        result = image_prompt.render(brief(), "sdxl")
        self.assertEqual(result["verification"], "PARTIAL")  # resolution and refiner are verified; weights and CFG are not
        self.assertEqual(result["native_settings"], {})
        self.assertNotIn("cfg", json.dumps(result).lower())


class ComfyUiTests(unittest.TestCase):
    def test_positive_and_negative_are_separate_blocks(self):
        result = image_prompt.render(brief(options={"checkpoint": "my-checkpoint.safetensors"}), "comfyui")
        self.assertIn("Positive Prompt", result["blocks"])
        self.assertIn("Negative Prompt", result["blocks"])
        self.assertEqual(result["blocks"]["Negative Prompt"], "watermark, extra text")  # no 'no' in a negative block
        self.assertNotIn("no watermark", result["blocks"]["Positive Prompt"])

    def test_the_checkpoint_is_asked_for_because_node_values_depend_on_it(self):
        result = image_prompt.render(brief(), "comfyui")
        self.assertTrue(any("checkpoint" in w for w in result["warnings"]))


class RegressionTests(unittest.TestCase):
    """Bugs found while reading the first renders. Each one stays fixed."""

    def test_recraft_keeps_the_requested_text_in_the_prompt(self):
        result = image_prompt.render(brief(text=[{"content": "TEA", "placement": "on the label"}]), "recraft")
        self.assertIn('The text reads "TEA"', result["prompt"])

    def test_flux_3_sentences_start_with_a_capital_letter(self):
        result = image_prompt.render(brief(), "flux-3")
        for sentence in re.split(r"(?<=\.)\s+", result["prompt"].split('"')[0]):
            if sentence:
                self.assertTrue(sentence[0].isupper() or sentence[0].isdigit(), sentence)

    def test_an_exclusion_is_kept_in_the_prompt_when_the_target_has_no_negative_field(self):
        for target in ("flux-3", "ideogram", "flux-2", "recraft", "sdxl"):
            result = image_prompt.render(brief(constraints=["no watermark"]), target)
            self.assertIn("No watermark.", result["prompt"], target)

    def test_a_midjourney_text_warning_is_not_repeated(self):
        result = image_prompt.render(brief(text=[{"content": "TEA", "placement": "on the label"}]), "midjourney")
        self.assertEqual(sum("not verified" in w for w in result["warnings"]), 1, result["warnings"])


class FourFamiliesTests(unittest.TestCase):
    """The same visual brief, adapted to four model families: the outputs must differ in form, not only in wording."""

    def test_four_families_give_four_different_native_forms(self):
        outputs = {target: image_prompt.render(brief(text=[{"content": "TEA", "placement": "on the label"}]), target)
                   for target in ("midjourney", "gpt-image", "flux-3", "ideogram")}
        prompts = [result["prompt"] for result in outputs.values()]
        self.assertEqual(len(set(prompts)), 4)
        self.assertIn("--ar 4:5", outputs["midjourney"]["paste"])
        self.assertIn("Scene:", outputs["gpt-image"]["prompt"])
        self.assertNotIn("Scene:", outputs["flux-3"]["prompt"])
        self.assertIn('"TEA"', outputs["ideogram"]["prompt"])
        self.assertEqual(outputs["ideogram"]["native_settings"]["rendering_quality"], "high")

    def test_every_rendered_prompt_passes_the_generic_validator_without_errors(self):
        for target in ("midjourney", "gpt-image", "flux-3", "flux-2", "flux-kontext", "ideogram", "recraft",
                       "firefly", "seedream", "sd-3-5", "sdxl", "comfyui"):
            result = image_prompt.render(brief(), target)
            findings = validate(result["prompt"], "")
            self.assertEqual([f for f in findings if f["level"] == "ERROR"], [], target)


class FieldHandlingTests(unittest.TestCase):
    """Every brief field is either sent, written into the prompt, or named in a warning. None is dropped silently."""

    def test_an_edit_on_a_target_without_an_edit_call_becomes_a_sentence_with_a_warning(self):
        result = image_prompt.render(brief(edit={"change": "make the teapot green"}), "flux-2")
        self.assertIn("Make the teapot green.", result["prompt"])
        self.assertTrue(any("no image-edit call" in w for w in result["warnings"]))

    def test_boxes_on_a_target_other_than_flux_3_are_named_as_not_sent(self):
        boxes = [{"id": "lamp_1", "bbox": [0, 0, 500, 500], "desc": "a lamp"}]
        result = image_prompt.render(brief(boxes=boxes), "gpt-image")
        self.assertNotIn("lamp_1", result["prompt"])
        self.assertTrue(any("FLUX 3 only" in w for w in result["warnings"]))

    def test_references_on_a_target_without_reference_input_are_named_as_not_sent(self):
        result = image_prompt.render(brief(references=[{"role": "style", "use": "the palette"}]), "ideogram")
        self.assertTrue(any("references are not sent to Ideogram" in w for w in result["warnings"]))

    def test_an_aspect_ratio_on_a_target_without_one_is_named_as_not_sent(self):
        result = image_prompt.render(brief(aspect_ratio="4:5"), "ideogram")
        self.assertTrue(any("aspect_ratio is not sent to Ideogram" in w for w in result["warnings"]))

    def test_kontext_generation_keeps_the_visual_fields_and_the_positive_constraints(self):
        result = image_prompt.render({"subject": "a teapot", "medium": "product photograph",
                                      "lighting": "soft light", "constraints": ["keep the label readable"]},
                                     "flux-kontext")
        for text in ("product photograph", "soft light", "Keep the label readable."):
            self.assertIn(text, result["prompt"])

    def test_kontext_text_without_a_replacement_is_kept_as_a_text_line(self):
        result = image_prompt.render({"text": [{"content": "TEA", "placement": "on the label"}]}, "flux-kontext")
        self.assertIn('The text reads "TEA" on the label.', result["prompt"])

    def test_gpt_image_lists_the_references_by_position(self):
        result = image_prompt.render(brief(references=[{"role": "subject", "use": "the product"},
                                                       {"role": "style", "use": "the palette"}]), "gpt-image")
        self.assertIn("Inputs: image 1 is the subject: the product; image 2 is the style: the palette.", result["prompt"])

    def test_flux_3_names_each_box_with_its_id_in_the_caption_before_the_json_array(self):
        boxes = [{"id": "background_1", "bbox": [0, 0, 1000, 1000], "desc": "a flat yellow field"},
                 {"id": "silhouette_1", "bbox": [150, 150, 850, 850], "desc": "a black silhouette"}]
        result = image_prompt.render(brief(boxes=boxes), "flux-3")
        caption = result["prompt"][: -len(json.dumps(boxes))]
        self.assertIn("Element <background_1>: a flat yellow field.", caption)
        self.assertIn("Element <silhouette_1>: a black silhouette.", caption)
        self.assertTrue(result["prompt"].endswith(json.dumps(boxes)))

    def test_flux_3_names_references_by_position(self):
        result = image_prompt.render(brief(references=[{"role": "subject", "use": "the runner"}]), "flux-3")
        self.assertIn("Image 1 is the subject: the runner.", result["prompt"])

    def test_flux_3_text_has_no_comma_between_the_quoted_text_and_its_placement(self):
        result = image_prompt.render(brief(text=[{"content": "TEA", "placement": "on the label"}]), "flux-3")
        self.assertIn('The text reads "TEA" on the label', result["prompt"])
        self.assertNotIn('"TEA",', result["prompt"])

    def test_a_box_id_must_be_a_plain_identifier(self):
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(boxes=[{"id": "bad id", "bbox": [0, 0, 10, 10], "desc": "x"}]), "flux-3")

    def test_a_zero_part_aspect_ratio_is_refused_instead_of_crashing(self):
        for ratio in ("0:5", "5:0", "0:0"):
            with self.subTest(ratio=ratio), self.assertRaises(image_prompt.BriefError):
                image_prompt.render(brief(aspect_ratio=ratio), "midjourney")

    def test_an_unknown_reference_role_is_refused(self):
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(references=[{"role": "mood", "use": "x"}]), "midjourney")

    def test_an_ideogram_seed_below_zero_is_refused_and_a_large_one_is_warned_not_refused(self):
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(options={"seed": -1}), "ideogram")
        ok = image_prompt.render(brief(options={"seed": 7}), "ideogram")
        self.assertEqual(ok["native_settings"]["seed"], 7)
        big = image_prompt.render(brief(options={"seed": 2147483648}), "ideogram")
        self.assertEqual(big["native_settings"]["seed"], 2147483648)
        self.assertTrue(any("2147483647" in w for w in big["warnings"]))

    def test_a_plain_target_writes_its_exclusions_as_one_sentence(self):
        result = image_prompt.render(brief(), "sdxl")
        self.assertIn("No watermark, no extra text.", result["prompt"])
        self.assertNotIn("; No", result["prompt"])

    def test_an_ideogram_prompt_over_10000_characters_is_warned(self):
        result = image_prompt.render(brief(subject="x" * 10001), "ideogram")
        self.assertTrue(any("10000" in w for w in result["warnings"]))

    def test_firefly_says_when_a_non_structure_reference_is_not_used(self):
        result = image_prompt.render(brief(references=[{"role": "style", "use": "the palette"}]), "firefly")
        self.assertTrue(any("only structure references" in w for w in result["warnings"]))


class UltragoalRoutingTests(unittest.TestCase):
    """Facts read on 2026-10-14 (ultragoal): Seedream request options, OpenAI model IDs, Ideogram and Midjourney notes."""

    def test_seedream_sends_only_the_options_the_brief_sets(self):
        result = image_prompt.render(brief(options={"model": "dola-seedream-5-0-pro-260628", "size": "2K",
                                                    "watermark": False}), "seedream")
        self.assertEqual(result["native_settings"], {"model": "dola-seedream-5-0-pro-260628", "size": "2K",
                                                     "watermark": False})

    def test_seedream_default_watermark_is_named_as_a_warning_not_sent(self):
        result = image_prompt.render(brief(options={"model": "dola-seedream-5-0-pro-260628"}), "seedream")
        self.assertNotIn("watermark", result["native_settings"])
        self.assertTrue(any("watermark is on by default" in w for w in result["warnings"]))

    def test_seedream_fast_optimization_is_refused_on_flash_lite_and_4_5(self):
        for model in ("seedream-5-0-flash", "seedream-5-0-lite", "seedream-4-5"):
            with self.subTest(model=model), self.assertRaises(image_prompt.BriefError):
                image_prompt.render(brief(options={"model": model, "optimize_mode": "fast"}), "seedream")

    def test_seedream_sequential_is_refused_on_pro_and_flash(self):
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(options={"model": "seedream-5-0-pro", "sequential": "auto"}), "seedream")
        ok = image_prompt.render(brief(options={"model": "seedream-4-5", "sequential": "auto"}), "seedream")
        self.assertEqual(ok["native_settings"]["sequential_image_generation"], "auto")

    def test_seedream_size_is_a_tier_or_an_exact_size_in_the_pixel_range(self):
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(options={"size": "3K"}), "seedream")
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(options={"size": "512x512"}), "seedream")  # below 921,600 pixels
        ok = image_prompt.render(brief(options={"size": "2048x1024"}), "seedream")
        self.assertEqual(ok["native_settings"]["size"], "2048x1024")

    def test_seedream_reference_limits_follow_the_model_family(self):
        ten = [{"role": "subject", "use": "x"}] * 11
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(references=ten, options={"model": "seedream-5-0-pro"}), "seedream")
        fourteen = [{"role": "subject", "use": "x"}] * 14
        ok = image_prompt.render(brief(references=fourteen, options={"model": "seedream-4-5"}), "seedream")
        self.assertEqual(ok["status"], "ok")

    def test_gpt_image_2_and_1_5_are_accepted_with_a_note_that_they_are_on_other_pages(self):
        for model in ("gpt-image-2", "gpt-image-1.5"):
            with self.subTest(model=model):
                result = image_prompt.render(brief(options={"model": model}), "gpt-image")
                self.assertEqual(result["native_settings"]["model"], model)
                self.assertTrue(any("other than the generation guide" in w for w in result["warnings"]))

    def test_ideogram_quoted_text_carries_a_note_that_the_api_rendering_is_not_stated(self):
        result = image_prompt.render(brief(text=[{"content": "COFFEE", "placement": "top"}]), "ideogram")
        self.assertTrue(any("API developer pages" in w for w in result["warnings"]))

    def test_midjourney_long_prompt_is_flagged_with_the_prompt_basics_advice(self):
        long_subject = " ".join(["word"] * 45)
        result = image_prompt.render(brief(subject=long_subject), "midjourney")
        self.assertTrue(any("Prompt Basics" in w for w in result["warnings"]))


class ReviewRegressionTests(unittest.TestCase):
    """Defects found in the brutal review of 2026-10-14. Each one stays pinned."""

    def test_a_string_false_is_refused_for_grounding_and_raw_instead_of_being_read_as_true(self):
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(options={"grounding": "false"}), "flux-3")
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(options={"raw": "false"}), "midjourney")
        self.assertIs(image_prompt.render(brief(options={"grounding": False}), "flux-3")["native_settings"]["grounding"], False)
        self.assertNotIn("--raw", image_prompt.render(brief(options={"raw": False}), "midjourney")["native_parameters"])

    def test_a_boolean_is_not_accepted_as_a_safety_tolerance(self):
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(options={"safety_tolerance": True}), "flux-3")

    def test_seedream_model_names_are_matched_without_regard_to_letter_case(self):
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(options={"model": "Seedream-5-0-Flash", "optimize_mode": "fast"}), "seedream")
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(options={"model": "DOLA-SEEDREAM-5-0-PRO-260628", "sequential": "auto"}), "seedream")

    def test_briefs_with_only_text_or_only_an_exclusion_do_not_start_with_a_stop_or_a_space(self):
        for only in ({"text": [{"content": "HELLO", "placement": "top"}]}, {"constraints": ["no watermark"]}):
            for target_id in ("ideogram", "recraft", "comfyui", "seedream", "flux-2", "firefly", "sdxl", "sd-3-5"):
                prompt = image_prompt.render(only, target_id)["prompt"]
                self.assertFalse(prompt.startswith((".", " ")), (target_id, prompt))
        self.assertEqual(image_prompt.render({"text": [{"content": "HELLO"}]}, "ideogram")["prompt"],
                         'The text reads "HELLO"')

    def test_recraft_style_is_not_sent_to_v4_1_and_the_page_that_says_so_is_named(self):
        result = image_prompt.render(brief(options={"style": "digital_illustration"}), "recraft")
        self.assertNotIn("style", result["native_settings"])
        self.assertTrue(any("not supported by V4.1" in w for w in result["warnings"]))

    def test_xhigh_and_max_quality_are_refused_on_the_models_that_do_not_list_them(self):
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(options={"quality": "xhigh", "model": "gpt-image-1.5"}), "gpt-image")
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(options={"quality": "max", "model": "gpt-image-2"}), "gpt-image")
        self.assertEqual(image_prompt.render(brief(options={"quality": "max"}), "gpt-image")["native_settings"]["quality"], "max")

    def test_an_unknown_gpt_image_model_lists_all_four_documented_ids(self):
        with self.assertRaises(image_prompt.BriefError) as caught:
            image_prompt.render(brief(options={"model": "gpt-image-9"}), "gpt-image")
        for name in ("gpt-image-2.5-sunburst", "gpt-image-2.5-flare", "gpt-image-2", "gpt-image-1.5"):
            self.assertIn(name, str(caught.exception))

    def test_ideogram_count_is_refused_below_one_and_warned_above_the_app_limit(self):
        with self.assertRaises(image_prompt.BriefError):
            image_prompt.render(brief(options={"num_images": 0}), "ideogram")
        many = image_prompt.render(brief(options={"num_images": 9}), "ideogram")
        self.assertEqual(many["native_settings"]["num_images"], 9)
        self.assertTrue(any("1 to 8" in w for w in many["warnings"]))

    def test_ideogram_background_is_sent_only_when_the_brief_sets_it(self):
        self.assertNotIn("background", image_prompt.render(brief(), "ideogram")["native_settings"])
        set_ = image_prompt.render(brief(options={"background": "transparent"}), "ideogram")
        self.assertEqual(set_["native_settings"]["background"], "transparent")

    def test_kontext_without_an_edit_says_that_no_input_image_is_sent(self):
        result = image_prompt.render(brief(), "flux-kontext")
        self.assertTrue(any("input_image" in w for w in result["warnings"]))


class TemplateOSyncTests(unittest.TestCase):
    """Template O's worked examples are rendered by the code; the document must show exactly what the code renders."""

    EXAMPLE = {
        "subject": "a ceramic teapot", "environment": "a pale oak table by a window",
        "composition": "centred, with empty space above", "perspective": "eye level",
        "lighting": "soft morning light from the left", "color": "terracotta and cream",
        "medium": "product photograph", "materials": "glazed stoneware", "aspect_ratio": "4:5",
        "text": [{"content": "TEA", "placement": "on a small paper label on the side", "typography": "small serif capitals"}],
        "constraints": ["no watermark", "no extra text"],
    }

    def setUp(self):
        with open(os.path.join(ROOT, "references", "templates.md"), encoding="utf-8") as handle:
            self.templates = handle.read()

    def test_template_o_is_in_the_table_of_contents_and_the_body(self):
        self.assertIn("(#template-o--visual-brief-multi-model-adapter)", self.templates)
        self.assertIn("## Template O — Visual Brief (multi-model adapter)", self.templates)

    def test_each_worked_example_prompt_is_the_rendered_text(self):
        for target_id in ("midjourney", "gpt-image", "flux-3", "ideogram", "comfyui"):
            prompt = image_prompt.render(self.EXAMPLE, target_id)["prompt"]
            self.assertIn(prompt, self.templates, target_id)

    def test_the_example_brief_in_the_document_is_the_one_rendered(self):
        self.assertIn(json.dumps(self.EXAMPLE, indent=2, ensure_ascii=False), self.templates)


class CommandLineTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "image_prompt.py"), *args],
                              capture_output=True, text=True, check=False)

    def write_brief(self, text):
        """A brief file in a temporary folder inside the repository (never /tmp), removed after the test."""
        folder = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(folder.cleanup)
        path = os.path.join(folder.name, "brief.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_render_prints_json_with_the_status(self):
        done = self.run_cli("render", "--target", "midjourney", "--brief", self.write_brief(json.dumps(SCENE)))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["status"], "ok")

    def test_a_malformed_brief_file_is_reported_without_a_traceback(self):
        done = self.run_cli("render", "--target", "midjourney", "--brief", self.write_brief("{not json"))
        self.assertEqual(done.returncode, 2)
        self.assertIn("bad_input", done.stderr)
        self.assertNotIn("Traceback", done.stderr)

    def test_a_missing_brief_file_is_reported_without_a_traceback(self):
        done = self.run_cli("render", "--target", "midjourney", "--brief", os.path.join(ROOT, "no-such-brief.json"))
        self.assertEqual(done.returncode, 2)
        self.assertNotIn("Traceback", done.stderr)

    def test_resolve_prints_candidates_for_an_ambiguous_name(self):
        done = self.run_cli("resolve", "flux")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["status"], "ambiguous")


if __name__ == "__main__":
    unittest.main()
