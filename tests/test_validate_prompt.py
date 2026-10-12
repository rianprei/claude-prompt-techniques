import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "validate_prompt.py")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from validate_prompt import exit_status, requests_cot, validate  # noqa: E402


class RequestsCot(unittest.TestCase):
    def test_positive_request(self):
        self.assertTrue(requests_cot("Think step by step."))
        self.assertTrue(requests_cot("Pense passo a passo."))

    def test_negated_request_is_not_flagged(self):
        self.assertFalse(requests_cot("Do not think step by step."))
        self.assertFalse(requests_cot("Não pense passo a passo."))

    def test_no_phrase(self):
        self.assertFalse(requests_cot("Summarize the notes."))


class Validate(unittest.TestCase):
    def test_empty_prompt_is_an_error(self):
        self.assertEqual([f["code"] for f in validate("   ")], ["E-EMPTY"])

    def test_target_is_case_insensitive(self):
        codes = [f["code"] for f in validate("Think step by step. Return JSON.", "GPT-6-Astra")]
        self.assertIn("E-COT-REASONING", codes)


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


if __name__ == "__main__":
    unittest.main()
