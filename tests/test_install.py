"""The installer: links into each CLI's skill folder, refusals, removal, the conflict rule and the snippet. Nothing is
written outside a temporary home, and no network is used."""

import contextlib
import io
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import install  # noqa: E402


def run(*args, home):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = install.main(["--home", str(home), *args])
    return code, out.getvalue()


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def link(self, target):
        return self.home / install.TARGETS[target] / install.SKILL_NAME

    def test_each_target_gets_a_link_to_this_repository_and_its_skill_is_readable_through_it(self):
        code, _ = run("install", home=self.home)
        self.assertEqual(code, 0)
        for target in install.TARGETS:
            link = self.link(target)
            self.assertTrue(link.is_symlink(), target)
            self.assertEqual(Path(os.path.realpath(link)), ROOT.resolve(), target)
            self.assertIn("name: prompt-techniques", (link / "SKILL.md").read_text(encoding="utf-8"), target)

    def test_the_relative_links_of_skill_md_resolve_through_the_link(self):
        run("install", "--target", "codex", home=self.home)
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        links = re.findall(r"\]\(((?:references|scripts|evals)/[^)#]+)\)", text)
        self.assertTrue(links)
        for target in links:
            self.assertTrue((self.link("codex") / target).exists(), target)

    def test_a_second_install_changes_nothing(self):
        run("install", home=self.home)
        code, out = run("install", home=self.home)
        self.assertEqual(code, 0)
        self.assertEqual(out.count("keep"), len(install.TARGETS))
        self.assertNotIn("create", out)

    def test_a_real_folder_in_the_way_is_refused_and_kept(self):
        real = self.link("codex")
        real.mkdir(parents=True)
        (real / "notes.txt").write_text("mine", encoding="utf-8")
        code, out = run("install", "--target", "codex", home=self.home)
        self.assertEqual(code, 1)
        self.assertIn("refuse", out)
        self.assertFalse(real.is_symlink())
        self.assertEqual((real / "notes.txt").read_text(encoding="utf-8"), "mine")

    def test_a_link_to_another_folder_is_refused_and_not_replaced(self):
        other = self.home / "elsewhere"
        other.mkdir()
        self.link("codex").parent.mkdir(parents=True)
        os.symlink(other, self.link("codex"), target_is_directory=True)
        code, _ = run("install", "--target", "codex", home=self.home)
        self.assertEqual(code, 1)
        self.assertEqual(Path(os.path.realpath(self.link("codex"))), other.resolve())

    def test_this_repository_sitting_in_a_target_folder_counts_as_installed_and_is_never_removed(self):
        repo = self.home / install.TARGETS["claude"] / install.SKILL_NAME
        repo.mkdir(parents=True)
        (repo / "SKILL.md").write_text("---\nname: prompt-techniques\n---\n", encoding="utf-8")
        rows = install.apply_plan(install.plan(self.home, ["claude"], root=repo), dry_run=False, root=repo)
        self.assertEqual(rows[0]["action"], "keep")
        rows[0]["action"] = "remove"  # even a remove request must not touch a real folder
        install.apply_plan(rows, dry_run=False, root=repo)
        self.assertTrue((repo / "SKILL.md").exists())
        self.assertFalse(repo.is_symlink())

    def test_another_prompt_skill_in_the_folder_blocks_the_install_unless_forced(self):
        folder = self.home / install.TARGETS["agents"]
        (folder / "gpt-5-4-prompting").mkdir(parents=True)
        code, out = run("install", "--target", "agents", home=self.home)
        self.assertEqual(code, 1)
        self.assertIn("gpt-5-4-prompting", out)
        self.assertFalse(self.link("agents").exists())
        code, _ = run("install", "--target", "agents", "--force", home=self.home)
        self.assertEqual(code, 0)
        self.assertTrue(self.link("agents").is_symlink())

    def test_a_link_that_cannot_be_made_is_reported_not_a_traceback(self):
        with mock.patch("install.os.symlink", side_effect=OSError(1, "Operation not permitted")):
            code, out = run("install", "--target", "codex", home=self.home)
        self.assertEqual(code, 1)
        self.assertIn("could not create the link", out)
        self.assertFalse(self.link("codex").exists())

    def test_dry_run_creates_nothing(self):
        code, out = run("install", "--dry-run", home=self.home)
        self.assertEqual(code, 0)
        self.assertIn("create", out)
        self.assertFalse(any(self.home.iterdir()))

    def test_remove_deletes_only_this_repositorys_link(self):
        run("install", "--target", "codex", home=self.home)
        run("remove", home=self.home)
        self.assertFalse(self.link("codex").exists())
        other = self.home / "keep-me"
        other.mkdir()
        self.link("agents").parent.mkdir(parents=True)
        os.symlink(other, self.link("agents"), target_is_directory=True)
        run("remove", "--target", "agents", home=self.home)
        self.assertTrue(self.link("agents").is_symlink())

    def test_status_names_the_conflict_without_changing_anything(self):
        (self.home / install.TARGETS["codex"]).mkdir(parents=True)
        (self.home / install.TARGETS["codex"] / "deep-research-prompt").mkdir()
        code, out = run("status", home=self.home)
        self.assertEqual(code, 0)
        self.assertIn("deep-research-prompt", out)
        self.assertFalse(self.link("codex").exists())

    def test_the_snippet_gives_the_absolute_skill_path_and_no_claude_code_tool_names(self):
        code, out = run("snippet", home=self.home)
        self.assertEqual(code, 0)
        self.assertIn(str(ROOT / "SKILL.md"), out)
        self.assertNotIn("Read tool", out)
        self.assertNotIn("Skill tool", out)


class SourceTests(unittest.TestCase):
    def test_the_source_declares_the_name_the_link_uses_and_its_links_exist(self):
        self.assertEqual(install.source_problems(), [])


if __name__ == "__main__":
    unittest.main()
