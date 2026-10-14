import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from contracts import find_model, load_catalog, model_ratios  # noqa: E402
from validate_prompt import validate  # noqa: E402

EXAMPLES = os.path.join(ROOT, "references", "gemini-image-examples.md")


def sections():
    with open(EXAMPLES, encoding="utf-8") as fh:
        text = fh.read()
    return [s for s in text.split("\n## ")[1:]]


class GeminiExamplesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()

    def test_there_are_eight_examples(self):
        self.assertEqual(len(sections()), 8)

    def test_every_pasted_prompt_passes_the_validator_for_its_model(self):
        checked = 0
        for section in sections():
            title = section.split("\n", 1)[0]
            model = re.search(r"model `([^`]+)`", section)
            blocks = re.findall(r"```text\n(.*?)\n```", section, re.DOTALL)
            self.assertTrue(blocks, title)
            for block in blocks:
                checked += 1
                target = model.group(1) if model else ""
                findings = validate(block, target, self.catalog)
                self.assertEqual(findings, [], f"{title}: {[f['code'] for f in findings]}")
        self.assertGreaterEqual(checked, 9)

    def test_quoted_text_in_a_pasted_prompt_names_its_language(self):
        language = re.compile(r"portugu[eê]s|english|ingl[eê]s|idioma|language|pt-BR|en-US", re.IGNORECASE)
        for section in sections():
            title = section.split("\n", 1)[0]
            for block in re.findall(r"```text\n(.*?)\n```", section, re.DOTALL):
                if re.search(r"[\"“]", block):
                    self.assertIsNotNone(language.search(block), title)

    def test_every_pasted_prompt_states_its_composition(self):
        composition = re.compile(r"plano|shot|enquadramento|frame|quadro|ângulo|angle|nível|eye level|composi|"
                                 r"perspectiv|perspective|topo|centro|esquerda|direita|left|right|top|center|lens|lente",
                                 re.IGNORECASE)
        for section in sections():
            title = section.split("\n", 1)[0]
            for block in re.findall(r"```text\n(.*?)\n```", section, re.DOTALL):
                self.assertIsNotNone(composition.search(block), title)

    def test_each_stated_ratio_is_one_the_named_model_accepts(self):
        for section in sections():
            title = section.split("\n", 1)[0]
            model_match = re.search(r"model `([^`]+)`", section)
            ratio_match = re.search(r"aspect ratio `([^`]+)`", section)
            if not (model_match and ratio_match):
                continue
            model = find_model(self.catalog, model_match.group(1))
            self.assertIn(ratio_match.group(1), model_ratios(self.catalog, model), title)

    def test_examples_use_only_ids_from_the_catalog(self):
        with open(EXAMPLES, encoding="utf-8") as fh:
            text = fh.read()
        known = {m["id"] for m in self.catalog["models"]}
        for model_id in re.findall(r"`(gemini-[a-z0-9.\-]+)`", text):
            self.assertIn(model_id, known)


if __name__ == "__main__":
    unittest.main()
