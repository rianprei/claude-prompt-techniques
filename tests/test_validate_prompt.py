import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "validate_prompt.py")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from contracts import load_catalog  # noqa: E402
from validate_prompt import exit_status, main, reasoning_native, requests_cot, validate  # noqa: E402

# Built from two parts so that this file does not contain the forbidden text itself.
KEY_PARAM = "?" + "key="


class RequestsCot(unittest.TestCase):
    def test_positive_request(self):
        self.assertTrue(requests_cot("Think step by step."))
        self.assertTrue(requests_cot("Pense passo a passo."))

    def test_negated_request_is_not_flagged(self):
        self.assertFalse(requests_cot("Do not think step by step."))
        self.assertFalse(requests_cot("Não pense passo a passo."))

    def test_no_phrase(self):
        self.assertFalse(requests_cot("Summarize the notes."))

    def test_double_negative_asks_for_reasoning(self):
        self.assertTrue(requests_cot("Don't skip the step-by-step check."))
        self.assertTrue(requests_cot("Never skip step-by-step reasoning."))
        self.assertTrue(requests_cot("Do not avoid thinking step by step."))
        self.assertTrue(requests_cot("Não pule o passo a passo."))
        self.assertTrue(requests_cot("Sem pular o passo a passo."))
        self.assertTrue(requests_cot("Não esqueça de pensar passo a passo."))

    def test_single_negation_forbids_reasoning(self):
        self.assertFalse(requests_cot("Avoid step-by-step reasoning."))
        self.assertFalse(requests_cot("Skip the step-by-step reasoning."))
        self.assertFalse(requests_cot("Don't think step by step."))
        self.assertFalse(requests_cot("Sem passo a passo."))

    def test_neither_nor_counts_as_three(self):
        self.assertFalse(requests_cot("Neither skip nor think step by step."))

    def test_clause_break_ends_the_negation(self):
        self.assertTrue(requests_cot("Don't be verbose, think step by step."))
        self.assertTrue(requests_cot("Do not write a summary; think step by step."))
        self.assertTrue(requests_cot("Be brief, and do not skip the step-by-step check."))
        self.assertFalse(requests_cot("Be brief, and do not think step by step."))

    def test_negation_after_the_phrase_is_not_read(self):
        # Documented limit: only the clause before the phrase is read.
        self.assertTrue(requests_cot("Think step by step; do not show the notes."))


class Validate(unittest.TestCase):
    def test_empty_prompt_is_an_error(self):
        self.assertEqual([f["code"] for f in validate("   ")], ["E-EMPTY"])

    def test_target_is_case_insensitive(self):
        codes = [f["code"] for f in validate("Think step by step. Return JSON.", "GPT-6-Astra")]
        self.assertIn("E-COT-REASONING", codes)

    def test_double_negative_cot_is_an_error_on_reasoning_native(self):
        codes = [f["code"] for f in validate("Don't skip the step-by-step check. Return JSON.", "o3")]
        self.assertIn("E-COT-REASONING", codes)


class CatalogChecks(unittest.TestCase):
    def codes(self, text, target="", catalog=None):
        return {f["code"] for f in validate(text, target, catalog)}

    def test_preview_model_is_blocked(self):
        text = "Use gemini-3.1-flash-image-preview for drafts."
        self.assertIn("E-MODEL-PREVIEW", self.codes(text, "gemini-nano-banana-2.1"))

    def test_deprecated_model_is_a_warning(self):
        findings = validate("Make a flat logo.", "gemini-2.5-flash-image")
        self.assertEqual([f["code"] for f in findings], ["W-MODEL-DEPRECATED"])
        self.assertEqual(findings[0]["level"], "WARN")

    def test_current_model_raises_no_model_finding(self):
        codes = self.codes("Make a flat logo of a lighthouse.", "gemini-nano-banana-2.1")
        self.assertEqual({c for c in codes if "MODEL" in c}, set())

    def test_shut_down_model_is_blocked(self):
        catalog = load_catalog()
        catalog["models"].append({"id": "gemini-9-retired-image", "status": "shut_down", "shutdown": "2026-01-01"})
        self.assertIn("E-MODEL-SHUT-DOWN", self.codes("Make a flat logo.", "gemini-9-retired-image", catalog))

    def test_unknown_model_is_a_warning(self):
        findings = validate("Make a flat logo.", "gemini-9-ultra-image")
        self.assertEqual([f["code"] for f in findings], ["W-MODEL-UNKNOWN"])

    def test_key_in_url_is_an_error(self):
        self.assertIn("E-KEY-IN-URL", self.codes("Call https://example.test/v1/run" + KEY_PARAM + "TEST"))

    def test_key_in_header_is_not_flagged(self):
        self.assertNotIn("E-KEY-IN-URL", self.codes("Send the key in the x-goog-api-key header."))


class AspectRatioChecks(unittest.TestCase):
    TARGET = "gemini-nano-banana-2.1"

    def aspect(self, text, target=TARGET):
        return [f["message"] for f in validate(text, target) if f["code"] == "W-ASPECT-RATIO"]

    def test_official_ratio_passes(self):
        self.assertEqual(self.aspect("Create a banner. Aspect ratio 21:9."), [])

    def test_unlisted_ratio_gets_the_nearest_official_one(self):
        messages = self.aspect("Create a banner. Aspect ratio 3:1.")
        self.assertEqual(len(messages), 1)
        self.assertIn("nearest is 21:9", messages[0])

    def test_ratio_written_before_the_keyword_is_read(self):
        self.assertEqual(len(self.aspect("A 3:1 aspect ratio banner.")), 1)

    def test_same_ratio_is_reported_once(self):
        self.assertEqual(len(self.aspect("Aspect ratio 3:1. Keep the 3:1 aspect ratio.")), 1)

    def test_zero_is_reported_without_crashing(self):
        self.assertEqual(len(self.aspect("Aspect ratio 0:9.")), 1)

    def test_a_score_is_not_an_aspect_ratio(self):
        self.assertEqual(self.aspect("The score was 3:1 at halftime."), [])

    def test_other_targets_are_not_checked(self):
        self.assertEqual(self.aspect("Aspect ratio 3:1.", "midjourney"), [])


class ScopeChecks(unittest.TestCase):
    def test_text_gemini_model_gets_the_text_checks(self):
        codes = {f["code"] for f in validate("Explain DNS.", "gemini-2.5-pro")}
        self.assertIn("W-OUTPUT-FORMAT", codes)
        self.assertEqual({c for c in codes if "MODEL" in c}, set())

    def test_common_verbs_in_an_image_prompt_are_not_agent_errors(self):
        self.assertEqual(validate("A runner, run down the street at dusk, low angle.", "gemini-nano-banana-2.1"), [])

    def test_format_warning_does_not_apply_to_image_targets(self):
        self.assertEqual(validate("A lighthouse at dusk.", "gemini-nano-banana-2.1"), [])


class ExitStatus(unittest.TestCase):
    def test_warning_blocks_only_in_strict_mode(self):
        warn = [{"level": "WARN", "code": "W-VAGUE", "message": ""}]
        self.assertEqual(exit_status(warn), 0)
        self.assertEqual(exit_status(warn, strict=True), 1)

    def test_error_always_blocks(self):
        err = [{"level": "ERROR", "code": "E-EMPTY", "message": ""}]
        self.assertEqual(exit_status(err), 1)


class Cli(unittest.TestCase):
    def run_cli(self, text, *args):
        return subprocess.run(
            [sys.executable, SCRIPT, *args, "-"],
            input=text, capture_output=True, text=True, check=False,
        )

    def test_warning_exits_zero_by_default(self):
        result = self.run_cli("Explain DNS.")
        self.assertEqual(result.returncode, 0)
        self.assertIn("W-OUTPUT-FORMAT", result.stdout)

    def test_strict_mode_exits_one_on_warning(self):
        self.assertEqual(self.run_cli("Explain DNS.", "--strict").returncode, 1)

    def test_json_output(self):
        result = self.run_cli("Explain DNS.", "--json")
        self.assertEqual([f["code"] for f in json.loads(result.stdout)], ["W-OUTPUT-FORMAT"])


class CatalogFailure(unittest.TestCase):
    def test_unreadable_catalog_exits_two_instead_of_passing(self):
        with (mock.patch("validate_prompt.load_catalog", side_effect=OSError("missing")),
              contextlib.redirect_stderr(io.StringIO())):
            self.assertEqual(main(["--json", "-"]), 2)


class ReasoningNativeTargetTests(unittest.TestCase):
    def test_a_family_that_starts_the_name_matches(self):
        for target in ("gpt-6-astra", "gpt-6.1-sol", "o3", "o3-mini", "o4-mini", "deepseek-r1",
                       "claude-opus-5-5", "claude-fable-5-1", "openai/gpt-6-luna",
                       "deepseek-r1:8b", "ollama/deepseek-r1", "openrouter/deepseek/deepseek-r1", "together/o3-mini"):
            with self.subTest(target=target):
                self.assertTrue(reasoning_native(target))

    def test_a_name_that_only_contains_a_family_does_not_match(self):
        for target in ("my-project-gpt-6-test", "gpt-60", "notgpt-6", "gemini-nano-banana-2.1", "claude-sonnet-4-6"):
            with self.subTest(target=target):
                self.assertFalse(reasoning_native(target))


if __name__ == "__main__":
    unittest.main()
