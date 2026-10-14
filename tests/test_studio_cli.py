"""The command line: plan, approve, run, edit, rate, compare, history and the refusals. No network.

The paid path is exercised with a simulated transport (GeminiClient(..., transport=...)) that records the request it
would have sent. The fake provider covers the rest. The API key used in these tests is a marker string, and the tests
check that it never reaches stdout, stderr, the URL or any file in the data directory.
"""

import base64
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from contracts import load_catalog  # noqa: E402
from studio.client import FakeClient, GeminiClient, placeholder_png  # noqa: E402
from studio.core import Store  # noqa: E402
from studio.cli import main  # noqa: E402
from validate_prompt import validate  # noqa: E402

KEY = "marker-key-7f3a91c2"
NANO = "gemini-nano-banana-2.1"
PRO = "gemini-3-pro-image"
PNG = placeholder_png(width=64, height=64)  # what the simulated provider returns


def simulated(calls, interaction_id="int_sim_0001", status=200, image=PNG):
    """A transport that answers like the Interactions endpoint and records each request."""
    def transport(url, headers, body, timeout):
        calls.append({"url": url, "headers": dict(headers), "body": json.loads(body)})
        payload = {"id": interaction_id, "steps": [{"type": "model_output", "content": [
            {"type": "image", "data": base64.b64encode(image).decode("ascii"), "mime_type": "image/png"}]}]}
        return status, json.dumps(payload).encode("utf-8")
    return transport


def live_factory(transport):
    return lambda: GeminiClient(KEY, transport=transport)


class CliCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_dir = tmp.name
        self.calls = []
        self.transport = simulated(self.calls)

    def cli(self, *argv, client=None, tty=False, typed=""):
        """Run one command in-process. Returns (exit code, parsed stdout or None, parsed stderr or None)."""
        out, err = io.StringIO(), io.StringIO()
        full = [argv[0], "--data-dir", self.data_dir, *argv[1:]]
        kwargs = {"stdin_isatty": lambda: tty, "input_func": lambda prompt: typed}
        if client is not None:
            kwargs["client_factory"] = client
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = main(full, **kwargs)
            except SystemExit as exc:  # argparse refusals
                code = exc.code
        text_out, text_err = out.getvalue(), err.getvalue()
        self.last_output = text_out + text_err
        parsed_out = json.loads(text_out) if text_out.strip().startswith("{") else None
        error_lines = [line for line in text_err.splitlines() if line.startswith("{")]  # the terminal may print a line first
        parsed_err = json.loads(error_lines[-1]) if error_lines else None
        return code, parsed_out, parsed_err

    def plan(self, prompt="A red teapot on a wooden table.", model=NANO, ratio="1:1", size="1K", extra=()):
        code, out, err = self.cli("plan", "--prompt", prompt, "--model", model, "--aspect-ratio", ratio,
                                  "--size", size, *extra)
        self.assertEqual(code, 0, err)
        return out

    def approve(self, digest, tty=False, typed=""):
        return self.cli("approve", digest, "--confirm", digest[:8], tty=tty, typed=typed)

    def generate(self, client=None, **plan_args):
        digest = self.plan(**plan_args)["brief_sha256"]
        code, approval, err = self.approve(digest)
        self.assertEqual(code, 0, err)
        code, run, err = self.cli("run", digest, "--approval", approval["approval_id"],
                                  client=client or FakeClient)
        return digest, code, run

    def store(self):
        return Store(self.data_dir)

    def approvals(self):
        path = os.path.join(self.data_dir, "approvals.json")
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def no_key_leaked(self):
        for base, _dirs, files in os.walk(self.data_dir):
            for name in files:
                with open(os.path.join(base, name), "rb") as handle:
                    self.assertNotIn(KEY.encode(), handle.read(), name)
        self.assertNotIn(KEY, self.last_output)


class PlanTests(CliCase):
    def test_plan_spends_nothing_and_writes_no_approval(self):
        plan = self.plan()
        self.assertFalse(plan["spent"])
        self.assertEqual(plan["estimated_cost_usd"], 0.0336)
        self.assertEqual(self.approvals(), {})
        self.assertEqual(os.listdir(os.path.join(self.data_dir, "outputs")), [])
        self.assertEqual(self.calls, [])

    def test_unoffered_model_is_refused_with_status_2(self):
        code, _out, err = self.cli("plan", "--prompt", "A red teapot.", "--model", "gemini-2.5-flash-image",
                                   "--aspect-ratio", "1:1", "--size", "1K")
        self.assertEqual(code, 2)
        self.assertEqual(err["error"], "model_not_offered")

    def test_thinking_level_is_checked_against_the_model_row(self):
        code, _o, err = self.cli("plan", "--prompt", "A red teapot.", "--model", NANO, "--aspect-ratio", "1:1",
                                 "--size", "1K", "--thinking-level", "HIGH")
        self.assertEqual(code, 0, err)
        code, _o, err = self.cli("plan", "--prompt", "A red teapot.", "--model", NANO, "--aspect-ratio", "1:1",
                                 "--size", "1K", "--thinking-level", "ultra")
        self.assertEqual((code, err["error"]), (2, "thinking_level_not_allowed"))

    def test_pro_refuses_any_thinking_level(self):
        code, _o, err = self.cli("plan", "--prompt", "A red teapot.", "--model", PRO, "--aspect-ratio", "1:1",
                                 "--size", "1K", "--thinking-level", "high")
        self.assertEqual((code, err["error"]), (2, "thinking_not_supported"))

    def test_thinking_level_is_stored_lower_case_and_sent_that_way(self):
        plan = self.plan(model=NANO, extra=("--thinking-level", "HIGH"))  # the plan helper passes extra flags through
        self.assertEqual(plan["thinking_level"], "high")
        code, approval, _e = self.approve(plan["brief_sha256"])
        code, run, err = self.cli("run", plan["brief_sha256"], "--approval", approval["approval_id"],
                                  client=live_factory(self.transport))
        self.assertEqual(code, 0, err)
        self.assertEqual(self.calls[-1]["body"]["generation_config"], {"thinking_level": "high"})

    def test_missing_size_for_a_new_image_is_refused(self):
        code, _o, err = self.cli("plan", "--prompt", "A red teapot.", "--model", NANO, "--aspect-ratio", "1:1")
        self.assertEqual((code, err["error"]), (2, "missing_parameter"))

    def test_prompt_from_file_is_read(self):
        path = os.path.join(self.data_dir, "prompt.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("A red teapot on a wooden table.")
        code, out, err = self.cli("plan", "--prompt-file", path, "--model", NANO, "--aspect-ratio", "1:1", "--size", "1K")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["prompt"], "A red teapot on a wooden table.")

    def test_reference_image_is_uploaded_and_counted(self):
        path = os.path.join(self.data_dir, "ref.png")
        with open(path, "wb") as handle:
            handle.write(PNG)
        plan = self.plan(extra=("--ref", path))
        self.assertEqual(plan["references"], 1)
        self.assertEqual(len(plan["reference_sha256"][0]), 64)  # the approval shows what it uploads, by hash

    def test_reference_that_is_not_an_image_is_refused(self):
        path = os.path.join(self.data_dir, "note.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("not an image")
        code, _o, err = self.cli("plan", "--prompt", "A red teapot.", "--model", NANO, "--aspect-ratio", "1:1",
                                 "--size", "1K", "--ref", path)
        self.assertEqual((code, err["error"]), (2, "unsupported_image"))


class ApprovalTests(CliCase):
    def test_approve_without_a_terminal_needs_the_confirmation_flag(self):
        digest = self.plan()["brief_sha256"]
        code, _o, err = self.cli("approve", digest)
        self.assertEqual((code, err["error"]), (2, "confirmation_required"))
        self.assertEqual(self.approvals(), {})

    def test_approval_tokens_are_hex_so_no_token_starts_with_a_dash(self):
        # Regression: urlsafe tokens start with "-" about 1.6 % of the time, and argparse then reads
        # `--approval -...` as an option, so the run was refused with no JSON on stderr.
        digest = self.plan()["brief_sha256"]
        store = self.store()
        tokens = [store.issue_approval(digest)["approval_id"] for _ in range(60)]  # under MAX_LIVE_APPROVALS
        for token in tokens:
            self.assertRegex(token, r"[0-9a-f]{48}")

    def test_wrong_confirmation_approves_nothing(self):
        digest = self.plan()["brief_sha256"]
        code, _o, err = self.cli("approve", digest, "--confirm", "00000000")
        self.assertEqual((code, err["error"]), (2, "confirmation_mismatch"))
        self.assertEqual(self.approvals(), {})

    def test_terminal_prompt_reads_the_confirmation(self):
        digest = self.plan()["brief_sha256"]
        code, out, err = self.cli("approve", digest, tty=True, typed=digest[:8])
        self.assertEqual(code, 0, err)
        self.assertEqual(out["scope"], "single_use")
        self.assertIn(out["approval_id"], self.last_output)

    def test_closing_the_terminal_prompt_approves_nothing(self):
        digest = self.plan()["brief_sha256"]

        def closed(prompt):
            raise EOFError

        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["approve", digest, "--data-dir", self.data_dir], stdin_isatty=lambda: True, input_func=closed)
        self.assertEqual(code, 2)
        self.assertIn("confirmation_mismatch", err.getvalue())
        self.assertEqual(self.approvals(), {})

    def test_terminal_prompt_with_a_wrong_answer_approves_nothing(self):
        digest = self.plan()["brief_sha256"]
        code, _o, err = self.cli("approve", digest, tty=True, typed="ffffffff")
        self.assertEqual((code, err["error"]), (2, "confirmation_mismatch"))
        self.assertEqual(self.approvals(), {})

    def test_approval_is_single_use(self):
        digest, code, run = self.generate(client=FakeClient)
        self.assertEqual(code, 0)
        code, approval, _e = self.cli("approve", digest, "--confirm", digest[:8])
        code, _o, err = self.cli("run", digest, "--approval", approval["approval_id"], client=FakeClient)
        self.assertEqual(code, 0)
        code, _o, err = self.cli("run", digest, "--approval", approval["approval_id"], client=FakeClient)
        self.assertEqual((code, err["error"]), (2, "approval_used"))

    def test_approval_for_one_brief_cannot_run_another(self):
        first = self.plan(prompt="A red teapot.")["brief_sha256"]
        second = self.plan(prompt="A blue teapot.")["brief_sha256"]
        _c, approval, _e = self.cli("approve", first, "--confirm", first[:8])
        code, _o, err = self.cli("run", second, "--approval", approval["approval_id"], client=FakeClient)
        self.assertEqual((code, err["error"]), (2, "approval_mismatch"))

    def test_run_without_key_refuses_before_spending_the_approval(self):
        digest = self.plan()["brief_sha256"]
        _c, approval, _e = self.approve(digest)
        with mock.patch.dict(os.environ, {}, clear=True):
            code, _o, err = self.cli("run", digest, "--approval", approval["approval_id"])
        self.assertEqual((code, err["error"]), (2, "missing_api_key"))
        self.no_key_leaked()
        code, run, err = self.cli("run", digest, "--approval", approval["approval_id"],
                                  client=live_factory(self.transport))
        self.assertEqual(code, 0, err)  # the approval was still unspent


class RunTests(CliCase):
    def test_live_path_sends_the_key_only_in_the_header(self):
        digest, code, run = self.generate(client=live_factory(self.transport))
        self.assertEqual(code, 0)
        sent = self.calls[-1]
        self.assertEqual(sent["url"], "https://generativelanguage.googleapis.com/v1beta/interactions")
        self.assertEqual(sent["headers"]["x-goog-api-key"], KEY)
        self.assertNotIn(KEY, sent["url"])
        self.assertEqual(sent["body"]["response_format"]["image_size"], "1K")
        self.assertNotIn("previous_interaction_id", sent["body"])
        self.assertNotIn("generation_config", sent["body"])
        self.no_key_leaked()

    def test_run_record_keeps_checks_interaction_id_and_provider(self):
        digest, code, run = self.generate(client=live_factory(self.transport))
        self.assertEqual(run["status"], "generated")
        self.assertEqual(run["provider"], "gemini")
        self.assertEqual(run["checks"]["width"], 64)
        self.assertEqual(run["checks"]["aspect_ratio_ok"], True)
        with open(os.path.join(self.data_dir, "runs", run["run_id"] + ".json"), encoding="utf-8") as handle:
            record = json.load(handle)
        self.assertEqual(record["interaction_id"], "int_sim_0001")
        self.assertTrue(os.path.exists(run["output_path"]))

    def test_fake_provider_output_is_marked_fake(self):
        _d, code, run = self.generate(client=FakeClient)
        self.assertEqual(run["provider"], "fake")
        code, history, _e = self.cli("history")
        self.assertEqual(history["runs"][0]["provider"], "fake")  # visible in the history, not only in the record

    def test_provider_refusal_is_recorded_as_a_failed_run(self):
        transport = simulated([], status=400)
        _d, code, run = self.generate(client=live_factory(transport))
        self.assertEqual(code, 1)
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["error"], "http_400")
        self.no_key_leaked()

    def test_missing_image_in_response_is_a_failed_run(self):
        def empty(url, headers, body, timeout):
            return 200, json.dumps({"id": "int_x", "steps": []}).encode("utf-8")
        _d, code, run = self.generate(client=live_factory(empty))
        self.assertEqual((code, run["error"]), (1, "no_image"))

    def test_show_returns_the_brief_and_the_output_path(self):
        _d, code, run = self.generate(client=FakeClient)
        code, out, err = self.cli("show", run["run_id"])
        self.assertEqual(code, 0, err)
        self.assertEqual(out["brief"]["prompt"], "A red teapot on a wooden table.")
        self.assertTrue(os.path.exists(out["output_path"]))


class EditTests(CliCase):
    def test_edit_sends_the_parent_output_as_its_reference(self):
        _d, code, parent = self.generate(client=live_factory(self.transport))
        plan = self.cli("plan", "--from", parent["run_id"], "--edit", "change the teapot to blue")
        code, plan_out, err = plan
        self.assertEqual(code, 0, err)
        self.assertEqual(plan_out["parent_run_id"], parent["run_id"])
        self.assertEqual(plan_out["references"], 1)
        self.assertIsNone(plan_out["previous_interaction_id"])  # no chain unless asked
        approval = self.cli("approve", plan_out["brief_sha256"], "--confirm", plan_out["brief_sha256"][:8])[1]
        code, child, err = self.cli("run", plan_out["brief_sha256"], "--approval", approval["approval_id"],
                                    client=live_factory(self.transport))
        self.assertEqual(code, 0, err)
        sent = self.calls[-1]["body"]["input"]
        self.assertEqual(sent[1]["type"], "image")
        self.assertEqual(sent[1]["mime_type"], "image/png")
        with open(parent["output_path"], "rb") as handle:
            self.assertEqual(base64.b64decode(sent[1]["data"]), handle.read())
        self.assertEqual(child["parent_run_id"], parent["run_id"])

    def test_edit_prompt_keeps_the_preservation_clause(self):
        _d, _c, parent = self.generate(client=FakeClient)
        code, plan_out, _e = self.cli("plan", "--from", parent["run_id"], "--edit", "change the teapot to blue")
        findings = validate(plan_out["prompt"], NANO, load_catalog())
        codes = {f["code"] for f in findings}
        self.assertNotIn("W-EDIT-NO-PRESERVATION", codes)
        self.assertNotIn("W-TEXT-UNQUOTED", codes)  # the template must not trip the text-cue rule by itself

    def test_chain_needs_an_interaction_id_from_the_parent(self):
        _d, _c, parent = self.generate(client=FakeClient)
        code, _o, err = self.cli("plan", "--from", parent["run_id"], "--edit", "change the teapot to blue", "--chain")
        self.assertEqual((code, err["error"]), (2, "chain_unavailable"))

    def test_chain_sends_previous_interaction_id_for_the_same_model(self):
        _d, _c, parent = self.generate(client=live_factory(self.transport))
        code, plan_out, err = self.cli("plan", "--from", parent["run_id"], "--edit", "change the teapot to blue", "--chain")
        self.assertEqual(code, 0, err)
        self.assertEqual(plan_out["previous_interaction_id"], "int_sim_0001")
        approval = self.cli("approve", plan_out["brief_sha256"], "--confirm", plan_out["brief_sha256"][:8])[1]
        self.cli("run", plan_out["brief_sha256"], "--approval", approval["approval_id"], client=live_factory(self.transport))
        self.assertEqual(self.calls[-1]["body"]["previous_interaction_id"], "int_sim_0001")

    def test_chain_refuses_a_different_model(self):
        _d, _c, parent = self.generate(client=live_factory(self.transport))
        code, _o, err = self.cli("plan", "--from", parent["run_id"], "--edit", "change the teapot to blue",
                                 "--model", PRO, "--chain")
        self.assertEqual((code, err["error"]), (2, "chain_model_mismatch"))

    def test_only_a_generated_run_can_be_edited(self):
        transport = simulated([], status=500)
        _d, _c, failed = self.generate(client=live_factory(transport))
        code, _o, err = self.cli("plan", "--from", failed["run_id"], "--edit", "change the teapot to blue")
        self.assertEqual((code, err["error"]), (2, "run_not_generated"))

    def test_edit_without_text_is_refused(self):
        _d, _c, parent = self.generate(client=FakeClient)
        code, _o, err = self.cli("plan", "--from", parent["run_id"])
        self.assertEqual((code, err["error"]), (2, "empty_edit"))

    def test_edit_of_an_unknown_run_is_refused(self):
        code, _o, err = self.cli("plan", "--from", "run_0000000000000000", "--edit", "change the teapot")
        self.assertEqual((code, err["error"]), (2, "run_unknown"))


class CaseTests(CliCase):
    def test_case_fixes_its_parameters(self):
        code, _o, err = self.cli("plan", "--case", "scene-basic", "--model", PRO)
        self.assertEqual((code, err["error"]), (2, "case_fixes_parameters"))

    def test_case_that_needs_references_refuses_without_them(self):
        code, _o, err = self.cli("plan", "--case", "reference-identity")
        self.assertEqual((code, err["error"]), (2, "case_needs_references"))

    def test_edit_case_needs_a_parent_and_generate_case_refuses_one(self):
        code, _o, err = self.cli("plan", "--case", "edit-recolour")
        self.assertEqual((code, err["error"]), (2, "case_kind_mismatch"))
        _d, _c, parent = self.generate(client=FakeClient)
        code, _o, err = self.cli("plan", "--case", "scene-basic", "--from", parent["run_id"])
        self.assertEqual((code, err["error"]), (2, "case_kind_mismatch"))

    def test_unknown_case_is_refused(self):
        code, _o, err = self.cli("plan", "--case", "no-such-case")
        self.assertEqual((code, err["error"]), (2, "unknown_case"))

    def test_case_brief_carries_its_id_and_its_parameters(self):
        code, plan, err = self.cli("plan", "--case", "thinking-high-count")
        self.assertEqual(code, 0, err)
        self.assertEqual(plan["case_id"], "thinking-high-count")
        self.assertEqual(plan["thinking_level"], "high")
        self.assertEqual(plan["image_size"], "2K")

    def test_compare_groups_runs_by_variant_without_ranking(self):
        ratings = [(5, {"fidelity": 5, "composition": 4}), (3, {"fidelity": 3, "composition": 4})]
        for rating, criteria in ratings:
            code, plan, _e = self.cli("plan", "--case", "scene-basic")
            code, approval, _e = self.approve(plan["brief_sha256"])
            code, run, _e = self.cli("run", plan["brief_sha256"], "--approval", approval["approval_id"],
                                     client=live_factory(self.transport))
            self.assertEqual(code, 0)
            args = ["rate", run["run_id"], "--rating", str(rating)]
            for name, score in criteria.items():
                args += ["--criterion", f"{name}={score}"]
            self.assertEqual(self.cli(*args)[0], 0)
        code, out, err = self.cli("compare", "scene-basic")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(out["variants"]), 1)
        variant = out["variants"][0]
        self.assertEqual(variant["runs"], 2)
        self.assertEqual(variant["rated"], 2)
        self.assertEqual(variant["overall_mean"], 4.0)
        self.assertEqual(variant["criteria_mean"]["fidelity"], 4.0)
        self.assertEqual(variant["criteria_mean"]["composition"], 4.0)
        self.assertNotIn("winner", out)
        self.assertNotIn("best", json.dumps(out))

    def test_compare_of_an_unknown_case_is_refused(self):
        code, _o, err = self.cli("compare", "no-such-case")
        self.assertEqual((code, err["error"]), (2, "unknown_case"))


class RatingAndReviewTests(CliCase):
    def setUp(self):
        super().setUp()
        _d, _c, self.run = self.generate(client=FakeClient)
        self.run_id = self.run["run_id"]

    def test_criteria_are_checked_by_name_and_value(self):
        code, _o, err = self.cli("rate", self.run_id, "--rating", "3", "--criterion", "beauty=4")
        self.assertEqual((code, err["error"]), (2, "unknown_criterion"))
        code, _o, err = self.cli("rate", self.run_id, "--rating", "3", "--criterion", "fidelity=6")
        self.assertEqual((code, err["error"]), (2, "invalid_rating"))
        code, _o, err = self.cli("rate", self.run_id, "--rating", "3", "--criterion", "fidelity")
        self.assertEqual((code, err["error"]), (2, "bad_criteria"))

    def test_rating_is_appended_and_the_latest_counts(self):
        self.cli("rate", self.run_id, "--rating", "2")
        code, out, _e = self.cli("rate", self.run_id, "--rating", "4", "--note", "better")
        self.assertEqual(out["rating"], 4)
        with open(os.path.join(self.data_dir, "runs", self.run_id + ".json"), encoding="utf-8") as handle:
            self.assertEqual(len(json.load(handle)["evaluations"]), 2)

    def test_targeted_fix_needs_a_note(self):
        code, _o, err = self.cli("review", self.run_id, "--verdict", "targeted_fix")
        self.assertEqual((code, err["error"]), (2, "note_required"))
        code, out, err = self.cli("review", self.run_id, "--verdict", "targeted_fix", "--note", "the handle is missing")
        self.assertEqual((code, out["verdict"]), (0, "targeted_fix"))

    def test_history_respects_the_limit(self):
        self.generate(client=FakeClient)
        code, out, _e = self.cli("history", "--limit", "1")
        self.assertEqual(len(out["runs"]), 1)


class ServeTests(CliCase):
    def test_serve_help_still_reaches_the_server_parser(self):
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main(["serve", "--help"])
        self.assertEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
