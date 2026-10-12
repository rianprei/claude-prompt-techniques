import datetime as dt
import hashlib
import os
import stat
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from contracts import load_catalog  # noqa: E402
from studio import core  # noqa: E402
from studio.client import FakeClient, placeholder_png  # noqa: E402
from studio.core import (  # noqa: E402
    APPROVAL_TTL, MAX_LIVE_APPROVALS, ProviderError, Store, StudioError, allowed_sizes, build_brief,
    offered_models, preferences, record_evaluation, record_review, run_brief, sniff_image, summarize_run,
)

# Built from two parts so that this file does not contain the forbidden text itself.
KEY_PARAM = "?" + "key="
NOW = dt.datetime(2026, 10, 12, 12, 0, 0, tzinfo=dt.timezone.utc)
PNG = placeholder_png()
NANO = "gemini-nano-banana-2.1"


class OfferTests(unittest.TestCase):
    def test_only_current_and_active_models_without_preview_are_offered(self):
        ids = {offer["id"] for offer in offered_models(load_catalog())}
        self.assertEqual(ids, {"gemini-nano-banana-2.1", "gemini-3.1-flash-image",
                               "gemini-3.1-flash-lite-image", "gemini-3-pro-image"})

    def test_512_px_stays_hidden_until_the_catalog_confirms_it(self):
        catalog = load_catalog()
        flash = next(m for m in catalog["models"] if m["id"] == "gemini-3.1-flash-image")
        self.assertEqual(allowed_sizes(catalog, flash), ["1K", "2K", "4K"])
        catalog["image_sizes"]["512_json_value_confirmed"] = True
        self.assertIn("512", allowed_sizes(catalog, flash))

    def test_reference_cap_is_the_smallest_documented_limit(self):
        caps = {offer["id"]: offer["max_references"] for offer in offered_models(load_catalog())}
        self.assertEqual(caps, {"gemini-nano-banana-2.1": 4, "gemini-3.1-flash-image": 4,
                                "gemini-3.1-flash-lite-image": 14, "gemini-3-pro-image": 3})


class StoreCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = Store(tmp.name)
        self.catalog = load_catalog()

    def brief(self, **overrides):
        fields = {"prompt": "Make a flat logo of a lighthouse.", "model_id": NANO,
                  "aspect_ratio": "1:1", "image_size": "1K", "references": []}
        fields.update(overrides)
        return build_brief(self.catalog, self.store, **fields)

    def approved(self, brief_sha, now=NOW):
        return self.store.issue_approval(brief_sha, now)["approval_id"]

    def execute(self, client_factory=FakeClient, sha=None, token=None):
        """Plan if needed, approve, and run once. Returns (run record, brief sha, approval token)."""
        sha = sha or self.brief()["brief_sha256"]
        token = token or self.approved(sha)
        return run_brief(self.catalog, self.store, client_factory, sha, token, NOW), sha, token


class BriefTests(StoreCase):
    def test_hash_is_stable_and_sensitive_to_every_field(self):
        first = self.brief()["brief_sha256"]
        self.assertEqual(first, self.brief()["brief_sha256"])
        self.assertNotEqual(first, self.brief(prompt="Make a flat logo of a harbor.")["brief_sha256"])
        self.assertNotEqual(first, self.brief(image_size="2K")["brief_sha256"])

    def test_brief_file_is_named_by_the_hash_of_its_bytes(self):
        digest = self.brief()["brief_sha256"]
        with open(self.store._path("briefs", digest + ".json"), "rb") as handle:
            self.assertEqual(hashlib.sha256(handle.read()).hexdigest(), digest)

    def test_plan_reports_the_nominal_price(self):
        self.assertEqual(self.brief()["estimated_cost_usd"], 0.0336)

    def test_preview_model_is_refused(self):
        with self.assertRaises(StudioError) as ctx:
            self.brief(model_id="gemini-3.1-flash-image-preview")
        self.assertEqual(ctx.exception.code, "model_not_offered")

    def test_unofficial_aspect_ratio_is_refused(self):
        with self.assertRaises(StudioError) as ctx:
            self.brief(aspect_ratio="3:1")
        self.assertEqual(ctx.exception.code, "aspect_ratio_not_official")

    def test_512_px_is_refused_while_unconfirmed(self):
        with self.assertRaises(StudioError) as ctx:
            self.brief(model_id="gemini-3.1-flash-image", image_size="512")
        self.assertEqual(ctx.exception.code, "image_size_not_allowed")

    def test_too_many_references_is_refused(self):
        ref = {"sha256": "0" * 64, "mime_type": "image/png"}
        with self.assertRaises(StudioError) as ctx:
            self.brief(references=[ref] * 5)
        self.assertEqual(ctx.exception.code, "too_many_references")

    def test_unknown_reference_is_refused(self):
        with self.assertRaises(StudioError) as ctx:
            self.brief(references=[{"sha256": "a" * 64, "mime_type": "image/png"}])
        self.assertEqual(ctx.exception.code, "reference_unknown")

    def test_key_in_a_prompt_blocks_the_plan(self):
        with self.assertRaises(StudioError) as ctx:
            self.brief(prompt="Call https://example.test/v1/run" + KEY_PARAM + "X")
        self.assertEqual(ctx.exception.code, "prompt_blocked")

    def test_empty_prompt_is_refused(self):
        with self.assertRaises(StudioError) as ctx:
            self.brief(prompt="   ")
        self.assertEqual(ctx.exception.code, "empty_prompt")

    def test_non_text_model_id_is_refused(self):
        with self.assertRaises(StudioError) as ctx:
            self.brief(model_id=["gemini-nano-banana-2.1"])
        self.assertEqual(ctx.exception.code, "model_not_offered")

    def test_warnings_are_returned_and_do_not_block(self):
        plan = self.brief(prompt="Make a banner. Aspect ratio 3:1.")
        self.assertIn("W-ASPECT-RATIO", {f["code"] for f in plan["warnings"]})


class ReferenceTests(StoreCase):
    def test_uploaded_image_is_stored_under_its_hash(self):
        ref = self.store.save_reference("image/png", PNG)
        self.assertEqual(ref["sha256"], hashlib.sha256(PNG).hexdigest())
        self.assertTrue(os.path.exists(self.store._path("inputs", ref["sha256"])))

    def test_content_must_match_the_declared_type(self):
        with self.assertRaises(StudioError) as ctx:
            self.store.save_reference("image/jpeg", PNG)
        self.assertEqual(ctx.exception.code, "image_signature_mismatch")

    def test_unsupported_type_is_refused(self):
        with self.assertRaises(StudioError) as ctx:
            self.store.save_reference("image/gif", PNG)
        self.assertEqual(ctx.exception.code, "unsupported_image")

    def test_empty_and_oversized_uploads_are_refused(self):
        with self.assertRaises(StudioError) as ctx:
            self.store.save_reference("image/png", b"")
        self.assertEqual(ctx.exception.code, "empty_image")
        too_big = PNG + b"\x00" * core.MAX_REFERENCE_BYTES
        with self.assertRaises(StudioError) as ctx:
            self.store.save_reference("image/png", too_big)
        self.assertEqual(ctx.exception.code, "image_too_large")

    def test_a_reference_changed_after_upload_is_detected(self):
        ref = self.store.save_reference("image/png", PNG)
        with open(self.store._path("inputs", ref["sha256"]), "wb") as handle:
            handle.write(PNG + b"tampered")
        with self.assertRaises(StudioError) as ctx:
            self.store.read_references({"references": [ref]})
        self.assertEqual(ctx.exception.code, "reference_tampered")

    def test_non_text_type_is_refused(self):
        with self.assertRaises(StudioError) as ctx:
            self.store.save_reference(["image/png"], PNG)
        self.assertEqual(ctx.exception.code, "unsupported_image")

    def test_webp_signature_is_recognised(self):
        self.assertEqual(sniff_image(b"RIFF\x00\x00\x00\x00WEBPVP8 "), "image/webp")


class ApprovalTests(StoreCase):
    def test_approval_is_single_use(self):
        sha = self.brief()["brief_sha256"]
        token = self.approved(sha)
        self.store.consume_approval(token, sha, NOW)
        with self.assertRaises(StudioError) as ctx:
            self.store.consume_approval(token, sha, NOW)
        self.assertEqual(ctx.exception.code, "approval_used")

    def test_approval_expires_after_its_ttl(self):
        sha = self.brief()["brief_sha256"]
        token = self.approved(sha)
        with self.assertRaises(StudioError) as ctx:
            self.store.consume_approval(token, sha, NOW + APPROVAL_TTL)
        self.assertEqual(ctx.exception.code, "approval_expired")

    def test_approval_is_bound_to_its_brief(self):
        sha = self.brief()["brief_sha256"]
        other = self.brief(prompt="Make a flat logo of a harbor.")["brief_sha256"]
        token = self.approved(sha)
        with self.assertRaises(StudioError) as ctx:
            self.store.consume_approval(token, other, NOW)
        self.assertEqual(ctx.exception.code, "approval_mismatch")
        self.store.consume_approval(token, sha, NOW)  # a refused mismatch does not spend it

    def test_unknown_or_missing_approval_is_refused(self):
        sha = self.brief()["brief_sha256"]
        for token in ("not-issued", "", None):
            with self.subTest(token=token), self.assertRaises(StudioError) as ctx:
                self.store.consume_approval(token, sha, NOW)
            self.assertEqual(ctx.exception.code, "approval_unknown")

    def test_the_token_itself_is_never_written_to_disk(self):
        sha = self.brief()["brief_sha256"]
        token = self.approved(sha)
        with open(self.store._path("approvals.json"), encoding="utf-8") as handle:
            self.assertNotIn(token, handle.read())

    def test_live_approvals_are_capped(self):
        sha = self.brief()["brief_sha256"]
        for _ in range(MAX_LIVE_APPROVALS):
            self.approved(sha)
        with self.assertRaises(StudioError) as ctx:
            self.approved(sha)
        self.assertEqual(ctx.exception.code, "approval_capacity")

    def test_approval_needs_a_stored_brief(self):
        with self.assertRaises(StudioError) as ctx:
            self.store.issue_approval("a" * 64, NOW)
        self.assertEqual(ctx.exception.code, "brief_unknown")


class StoreFailureTests(StoreCase):
    def test_missing_reference_file_is_a_clear_failed_run(self):
        ref = self.store.save_reference("image/png", PNG)
        sha = self.brief(references=[ref])["brief_sha256"]
        os.remove(self.store._path("inputs", ref["sha256"]))
        record, _, _ = self.execute(sha=sha)
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["error"], "reference_missing")

    def test_corrupted_registry_refuses_to_spend(self):
        sha = self.brief()["brief_sha256"]
        token = self.approved(sha)
        with open(self.store._path("approvals.json"), "w", encoding="utf-8") as handle:
            handle.write("{not json")
        with self.assertRaises(StudioError) as ctx:
            self.store.consume_approval(token, sha, NOW)
        self.assertEqual(ctx.exception.code, "registry_corrupt")

    def test_data_folder_is_private(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = os.path.join(tmp.name, "studio-data")
        Store(root)
        self.assertEqual(stat.S_IMODE(os.stat(root).st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(root, "briefs")).st_mode), 0o700)


class RunTests(StoreCase):
    def test_successful_run_saves_the_image_and_spends_the_approval(self):
        record, sha, token = self.execute()
        self.assertEqual(record["status"], "generated")
        data, mime_type = self.store.read_output(record["run_id"])
        self.assertTrue(data.startswith(b"\x89PNG"))
        self.assertEqual(mime_type, "image/png")
        with self.assertRaises(StudioError) as ctx:
            self.store.consume_approval(token, sha, NOW)
        self.assertEqual(ctx.exception.code, "approval_used")

    def test_missing_key_spends_nothing(self):
        def no_key():
            raise StudioError("missing_api_key", "not set", 412)

        sha = self.brief()["brief_sha256"]
        token = self.approved(sha)
        with self.assertRaises(StudioError) as ctx:
            run_brief(self.catalog, self.store, no_key, sha, token, NOW)
        self.assertEqual(ctx.exception.code, "missing_api_key")
        self.store.consume_approval(token, sha, NOW)  # still usable once the key exists

    def test_provider_failure_is_recorded_and_keeps_the_approval_spent(self):
        class Failing:
            def generate(self, brief, references):
                raise ProviderError("http_500", "server error")

        record, sha, token = self.execute(client_factory=Failing)
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["error"], "http_500")
        with self.assertRaises(StudioError) as ctx:
            self.store.consume_approval(token, sha, NOW)
        self.assertEqual(ctx.exception.code, "approval_used")

    def test_output_that_is_not_an_image_is_a_failed_run(self):
        class NotAnImage:
            def generate(self, brief, references):
                return {"data": b"plain text", "mime_type": "image/png"}

        record, _, _ = self.execute(client_factory=NotAnImage)
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["error"], "unsupported_output")

    def test_model_that_is_no_longer_offered_stops_before_spending(self):
        sha = self.brief()["brief_sha256"]
        token = self.approved(sha)
        catalog = load_catalog()
        next(m for m in catalog["models"] if m["id"] == NANO)["status"] = "deprecated"
        with self.assertRaises(StudioError) as ctx:
            run_brief(catalog, self.store, FakeClient, sha, token, NOW)
        self.assertEqual(ctx.exception.code, "model_not_offered")
        self.store.consume_approval(token, sha, NOW)

    def test_tampered_brief_is_detected_before_spending(self):
        sha = self.brief()["brief_sha256"]
        token = self.approved(sha)
        with open(self.store._path("briefs", sha + ".json"), "wb") as handle:
            handle.write(b'{"prompt":"changed"}')
        with self.assertRaises(StudioError) as ctx:
            run_brief(self.catalog, self.store, FakeClient, sha, token, NOW)
        self.assertEqual(ctx.exception.code, "brief_tampered")
        self.store.consume_approval(token, sha, NOW)


class ReviewAndEvaluationTests(StoreCase):
    def generated(self):
        record, _, _ = self.execute()
        return record["run_id"]

    def test_targeted_fix_and_blocked_need_a_note(self):
        run_id = self.generated()
        for verdict in ("targeted_fix", "blocked"):
            with self.subTest(verdict=verdict), self.assertRaises(StudioError) as ctx:
                record_review(self.store, run_id, verdict, "   ", NOW)
            self.assertEqual(ctx.exception.code, "note_required")

    def test_pass_needs_no_note_and_reviews_are_appended(self):
        run_id = self.generated()
        record_review(self.store, run_id, "pass", None, NOW)
        record = record_review(self.store, run_id, "regenerate", "wrong framing", NOW)
        self.assertEqual([r["verdict"] for r in record["reviews"]], ["pass", "regenerate"])
        self.assertEqual(summarize_run(record)["verdict"], "regenerate")

    def test_unknown_verdict_is_refused(self):
        with self.assertRaises(StudioError) as ctx:
            record_review(self.store, self.generated(), "maybe", "", NOW)
        self.assertEqual(ctx.exception.code, "invalid_verdict")

    def test_rating_must_be_a_whole_number_from_one_to_five(self):
        run_id = self.generated()
        for rating in (0, 6, 3.5, "4", True, None):
            with self.subTest(rating=rating), self.assertRaises(StudioError) as ctx:
                record_evaluation(self.store, run_id, rating, "", NOW)
            self.assertEqual(ctx.exception.code, "invalid_rating")
        self.assertEqual(record_evaluation(self.store, run_id, 4, "", NOW)["evaluations"][0]["rating"], 4)

    def test_notes_are_capped(self):
        with self.assertRaises(StudioError) as ctx:
            record_review(self.store, self.generated(), "pass", "x" * (core.MAX_NOTE_CHARS + 1), NOW)
        self.assertEqual(ctx.exception.code, "note_too_long")

    def test_failed_runs_cannot_be_reviewed_or_rated(self):
        class Failing:
            def generate(self, brief, references):
                raise ProviderError("http_500", "server error")

        record, _, _ = self.execute(client_factory=Failing)
        with self.assertRaises(StudioError) as ctx:
            record_review(self.store, record["run_id"], "pass", "", NOW)
        self.assertEqual(ctx.exception.code, "run_not_reviewable")
        with self.assertRaises(StudioError) as ctx:
            record_evaluation(self.store, record["run_id"], 3, "", NOW)
        self.assertEqual(ctx.exception.code, "run_not_evaluable")

    def test_preferences_average_each_runs_latest_rating(self):
        first = self.generated()
        record_evaluation(self.store, first, 4, "", NOW)
        record_evaluation(self.store, first, 5, "", NOW)
        second = self.generated()
        record_evaluation(self.store, second, 2, "", NOW)
        self.assertEqual(preferences(self.store)["model"][NANO], {"count": 2, "average": 3.5})


if __name__ == "__main__":
    unittest.main()
