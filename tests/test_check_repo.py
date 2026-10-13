import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from check_repo import check_key_in_url, check_model_ids, repo_files  # noqa: E402

CATALOG = {
    "models": [
        {"id": "gemini-3.1-flash-image", "status": "active"},
        {"id": "gemini-3-pro-image-preview", "status": "shut_down"},
        {"id": "gemini-2.5-flash-image", "status": "deprecated"},
    ]
}
# Built from two parts so that this file does not contain the forbidden text itself.
KEY_PARAM = "?" + "key="


class ModelIdContractTest(unittest.TestCase):
    def test_active_id_passes(self):
        texts = {"SKILL.md": "Use gemini-3.1-flash-image for drafts."}
        self.assertEqual(check_model_ids(texts, CATALOG), [])

    def test_trailing_period_is_not_part_of_the_id(self):
        texts = {"README.md": "Default: gemini-3.1-flash-image."}
        self.assertEqual(check_model_ids(texts, CATALOG), [])

    def test_unknown_id_is_reported(self):
        texts = {"notes.md": "Try gemini-9-ultra-image today."}
        problems = check_model_ids(texts, CATALOG)
        self.assertEqual(len(problems), 1)
        self.assertIn("gemini-9-ultra-image", problems[0])

    def test_shut_down_id_is_reported_outside_the_catalog(self):
        texts = {"tool-routing.md": "Use gemini-3-pro-image-preview."}
        problems = check_model_ids(texts, CATALOG)
        self.assertEqual(len(problems), 1)
        self.assertIn("shut-down", problems[0])

    def test_shut_down_id_is_allowed_inside_the_catalog_files(self):
        texts = {"references/gemini-image-models.md": "Shut down: gemini-3-pro-image-preview."}
        self.assertEqual(check_model_ids(texts, CATALOG), [])

    def test_deprecated_id_is_not_an_error(self):
        texts = {"README.md": "Legacy: gemini-2.5-flash-image."}
        self.assertEqual(check_model_ids(texts, CATALOG), [])

    def test_text_that_only_looks_like_an_id_is_ignored(self):
        texts = {"README.md": "Gemini 3 Pro and gemini-direct are not model IDs."}
        self.assertEqual(check_model_ids(texts, CATALOG), [])


class KeyInUrlContractTest(unittest.TestCase):
    def test_header_passes(self):
        texts = {"SKILL.md": 'headers = {"x-goog-api-key": key}'}
        self.assertEqual(check_key_in_url(texts), [])

    def test_key_in_query_string_is_reported_with_its_line(self):
        texts = {"script.py": 'url = base + ":generateContent" + "' + KEY_PARAM + 'XYZ"'}
        problems = check_key_in_url(texts)
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("script.py:1:"))


class RepositoryContractTest(unittest.TestCase):
    def test_repository_passes_its_own_checks(self):
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "check_repo.py")],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout)


class OutsideGitTest(unittest.TestCase):
    def test_copy_without_git_stops_with_a_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "scripts"))
            for name in ("check_repo.py", "contracts.py"):
                shutil.copy(os.path.join(ROOT, "scripts", name), os.path.join(tmp, "scripts", name))
            result = subprocess.run(
                [sys.executable, os.path.join(tmp, "scripts", "check_repo.py")],
                cwd=tmp, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("needs a git clone", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class FileListingTest(unittest.TestCase):
    def test_names_with_spaces_are_listed_whole(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", tmp], check=True)
            for name in ("a b.md", "c.md"):
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                    fh.write("x\n")
            subprocess.run(["git", "-C", tmp, "add", "-A"], check=True)
            self.assertEqual(repo_files(tmp), ["a b.md", "c.md"])


if __name__ == "__main__":
    unittest.main()
