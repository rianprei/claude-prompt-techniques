import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from validate_prompt import validate  # noqa: E402

with open(os.path.join(ROOT, "evals", "golden_cases.json"), encoding="utf-8") as fh:
    CASES = json.load(fh)


class GoldenCases(unittest.TestCase):
    def test_case_count_matches_the_docs(self):
        self.assertEqual(len(CASES), 31)  # README and evals/protocol.md say 31

    def test_each_case(self):
        for case in CASES:
            with self.subTest(case=case["id"]):
                findings = validate(case["prompt"], case.get("target", ""))
                codes = {f["code"] for f in findings}
                if case.get("clean"):
                    self.assertEqual(findings, [])
                for code in case.get("expect", []):
                    self.assertIn(code, codes)
                for code in case.get("forbid", []):
                    self.assertNotIn(code, codes)


if __name__ == "__main__":
    unittest.main()
