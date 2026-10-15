"""The merged model catalog, the offer rules (sizes, ratios, cost), the plan and the models command.

The catalog is read from references/studio-models.json and the Gemini file. The keys used here are canaries: a test
checks that a canary placed in the environment never appears in any output.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from contracts import load_studio_catalog, load_studio_models  # noqa: E402
from studio.cli import main  # noqa: E402
from studio.client import real_client  # noqa: E402
from studio.core import Store, StudioError, build_brief, offered_models, provider_of  # noqa: E402
from studio.providers import ADAPTERS  # noqa: E402


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_studio_catalog()

    def test_each_model_id_is_listed_once_and_names_a_declared_provider(self):
        declared = set(self.catalog["providers"]) | {"gemini"}
        ids = [model["id"] for model in self.catalog["models"]]
        self.assertEqual(len(ids), len(set(ids)))
        for model in self.catalog["models"]:
            self.assertIn(model.get("provider", "gemini"), declared, model["id"])

    def test_every_provider_declares_the_variables_its_adapter_reads(self):
        for key, info in self.catalog["providers"].items():
            with self.subTest(provider=key):
                self.assertEqual(tuple(info["env"]), ADAPTERS[key].env)

    def test_every_source_is_an_https_address_on_a_vendor_site(self):
        sources = [url for info in self.catalog["providers"].values() for url in info["sources"]]
        sources += [url for model in load_studio_models()["models"] for url in model["sources"]]
        self.assertTrue(sources)
        for url in sources:
            self.assertTrue(url.startswith("https://"), url)

    def test_an_unverified_row_carries_no_price_and_a_verified_row_prices_each_offered_size(self):
        for model in load_studio_models()["models"]:
            with self.subTest(model=model["id"]):
                if model.get("cost") == "unverified":
                    self.assertNotIn("prices_usd_per_image", model)
                elif model.get("cost") == "verified" and model["provider"] != "gemini":
                    self.assertEqual(set(model["prices_usd_per_image"]), set(model["sizes"]))

    def test_every_size_that_names_a_ratio_has_that_ratio_in_the_ratio_list(self):
        for model in self.catalog["models"]:
            for size, ratio in (model.get("size_ratio") or {}).items():
                with self.subTest(model=model["id"], size=size):
                    self.assertIn(ratio, model.get("aspect_ratios", self.catalog["aspect_ratios"]))

    def test_the_older_verified_date_drives_the_age_warning(self):
        with open(ROOT / "references" / "gemini-image-models.json", encoding="utf-8") as handle:
            gemini_verified = json.load(handle)["verified_on"]
        self.assertEqual(self.catalog["verified_on"], min(load_studio_models()["verified_on"], gemini_verified))


class OfferRuleTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_studio_catalog()
        self.offers = {offer["id"]: offer for offer in offered_models(self.catalog)}

    def test_an_unverified_model_is_offered_at_all_its_sizes_with_no_estimate(self):
        offer = self.offers["gpt-image-2"]
        self.assertEqual(offer["cost"], "unverified")
        self.assertEqual(offer["sizes"], ["1024x1024", "1536x1024", "1024x1536"])
        self.assertEqual(offer["prices_usd_per_image"], {})

    def test_a_verified_model_is_offered_only_at_its_priced_sizes(self):
        self.assertEqual(self.offers["stable-image-core"]["prices_usd_per_image"], {"default": 0.03})
        self.assertEqual(self.offers["stable-image-core"]["cost"], "verified")

    def test_gemini_offers_keep_their_prices_and_provider(self):
        offer = self.offers["gemini-nano-banana-2.1"]
        self.assertEqual(offer["provider"], "gemini")
        self.assertEqual(offer["prices_usd_per_image"]["1K"], 0.0336)
        self.assertEqual(offer["cost"], "verified")

    def test_a_preview_or_a_legacy_model_is_never_offered(self):
        self.assertNotIn("gemini-3.1-flash-image-preview", self.offers)
        self.assertNotIn("flux-kontext-pro", self.offers)

    def test_provider_of_names_the_provider_of_each_offer(self):
        for model_id, offer in self.offers.items():
            self.assertEqual(provider_of(self.catalog, model_id), offer["provider"])


class PlanTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Store(self._tmp.name)
        self.catalog = load_studio_catalog()

    def tearDown(self):
        self._tmp.cleanup()

    def plan(self, model, aspect, size):
        return build_brief(self.catalog, self.store, prompt="a red fox", model_id=model, aspect_ratio=aspect,
                           image_size=size, references=[])

    def test_an_unverified_plan_has_no_estimate(self):
        plan = self.plan("gpt-image-2", "1:1", "1024x1024")
        self.assertIsNone(plan["estimated_cost_usd"])

    def test_a_verified_plan_has_its_estimate(self):
        plan = self.plan("stable-image-core", "1:1", "default")
        self.assertEqual(plan["estimated_cost_usd"], 0.03)

    def test_a_size_that_fixes_a_ratio_must_be_planned_with_that_ratio(self):
        with self.assertRaises(StudioError) as caught:
            self.plan("gpt-image-2", "1:1", "1536x1024")
        self.assertEqual(caught.exception.code, "size_aspect_mismatch")

    def test_a_model_that_does_not_take_a_ratio_accepts_only_auto(self):
        with self.assertRaises(StudioError) as caught:
            self.plan("ideogram-4-5", "16:9", "default")
        self.assertEqual(caught.exception.code, "aspect_ratio_not_official")
        self.assertEqual(self.plan("ideogram-4-5", "auto", "default")["estimated_cost_usd"], None)

    def test_a_reference_limit_is_the_providers_own(self):
        with self.assertRaises(StudioError) as caught:
            build_brief(self.catalog, self.store, prompt="a red fox", model_id="recraftv4_1", aspect_ratio="1:1",
                        image_size="1024x1024", references=[{"sha256": "0" * 64, "mime_type": "image/png"}])
        self.assertEqual(caught.exception.code, "too_many_references")

    def test_a_missing_key_refuses_before_the_approval_is_spent(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(StudioError) as caught:
                real_client("openai")
        self.assertEqual(caught.exception.code, "missing_api_key")


class ModelsCommandTests(unittest.TestCase):
    CANARY = "sk-canary-DO-NOT-PRINT-7731"

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(list(argv))
        return code, out.getvalue()

    def test_models_lists_every_provider_and_no_key_value(self):
        with tempfile.TemporaryDirectory() as data_dir:
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": self.CANARY}):
                code, text = self.run_cli("models", "--data-dir", data_dir)
        self.assertEqual(code, 0)
        self.assertNotIn(self.CANARY, text)
        payload = json.loads(text)
        keys = {row["key"]: row["configured"] for row in payload["providers"]}
        self.assertTrue(keys["openai"])
        self.assertFalse(keys["bfl"])
        self.assertIn("gpt-image-2", {model["id"] for model in payload["models"]})

    def test_a_plan_for_an_unverified_model_says_there_is_no_estimate(self):
        with tempfile.TemporaryDirectory() as data_dir:
            code, text = self.run_cli("plan", "--model", "gpt-image-2", "--aspect-ratio", "1:1", "--size", "1024x1024",
                                      "--prompt", "a red fox", "--data-dir", data_dir)
        self.assertEqual(code, 0)
        payload = json.loads(text)
        self.assertIsNone(payload["estimated_cost_usd"])
        self.assertIn("no estimate", payload["cost_note"])
        self.assertFalse(payload["spent"])


if __name__ == "__main__":
    unittest.main()
