"""Each non-Gemini adapter, against a scripted transport: the request it sends, the reply it reads, and the refusals.

Every test uses a scripted transport, so nothing reaches a network and nothing is charged. The keys in these tests are
fake strings, and the tests check that they never appear in an error message or in a download.
"""

import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from contracts import load_studio_catalog  # noqa: E402
from studio.client import placeholder_png  # noqa: E402
from studio.core import ProviderError, Store, StudioError, build_brief, run_brief, utcnow  # noqa: E402
from studio.providers import (BlackForestLabs, BytePlus, Firefly, Ideogram, OpenAIImages, Recraft, Stability,  # noqa: E402
                              ComfyUI, configured, make_client)

PNG = placeholder_png()
PNG_B64 = base64.b64encode(PNG).decode("ascii")
TIMEOUT = 30


class Script:
    """A transport that answers in order. Each reply is (status, payload); a dict payload is sent as JSON."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, method, url, headers, body, timeout, limit=None):
        self.calls.append({"method": method, "url": url, "headers": dict(headers or {}), "body": body})
        if not self.replies:
            raise AssertionError(f"unexpected call {method} {url}")
        status, payload = self.replies.pop(0)
        if not isinstance(payload, bytes):
            payload = json.dumps(payload).encode("utf-8")
        return status, payload


class FakeClock:
    """Each call to the clock moves time forward, so a poll loop can time out without real waiting."""

    def __init__(self, step):
        self.now = 0.0
        self.step = step

    def __call__(self):
        self.now += self.step
        return self.now


def brief(model, *, prompt="a red fox", aspect="1:1", size="1024x1024", refs=()):
    return {"prompt": prompt, "model": model, "aspect_ratio": aspect, "image_size": size, "references": list(refs)}


def refs(count=1):
    return [("image/png", PNG) for _ in range(count)]


class OpenAITests(unittest.TestCase):
    KEY = "sk-test-OPENAI-KEY-123"

    def make(self, *replies):
        script = Script(*replies)
        return OpenAIImages({"OPENAI_API_KEY": self.KEY}, TIMEOUT, transport=script), script

    def test_generation_posts_json_with_a_bearer_key_and_decodes_the_b64_image(self):
        client, script = self.make((200, {"data": [{"b64_json": PNG_B64}]}))
        result = client.generate(brief("gpt-image-2"), [])
        self.assertEqual(result["data"], PNG)
        call = script.calls[0]
        self.assertEqual(call["url"], "https://api.openai.com/v1/images/generations")
        self.assertEqual(call["headers"]["Authorization"], f"Bearer {self.KEY}")
        body = json.loads(call["body"])
        self.assertEqual(body, {"model": "gpt-image-2", "prompt": "a red fox", "size": "1024x1024", "n": 1})

    def test_references_go_to_the_edit_endpoint_as_image_parts(self):
        client, script = self.make((200, {"data": [{"b64_json": PNG_B64}]}))
        client.generate(brief("gpt-image-2", refs=refs(2)), refs(2))
        call = script.calls[0]
        self.assertEqual(call["url"], "https://api.openai.com/v1/images/edits")
        self.assertTrue(call["headers"]["Content-Type"].startswith("multipart/form-data"))
        self.assertEqual(call["body"].count(b'name="image[]"'), 2)
        self.assertIn(b'filename="reference-2.png"', call["body"])

    def test_the_key_is_removed_from_a_provider_error_and_the_status_is_kept(self):
        client, _ = self.make((401, {"error": {"message": f"Incorrect API key provided: {self.KEY}"}}))
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("gpt-image-2"), [])
        self.assertEqual(caught.exception.code, "http_401")
        self.assertNotIn(self.KEY, caught.exception.message)
        self.assertIn("[redacted]", caught.exception.message)

    def test_a_429_says_the_approval_is_spent(self):
        client, _ = self.make((429, {"error": {"message": "rate limit"}}))
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("gpt-image-2"), [])
        self.assertIn("approval is spent", caught.exception.message)

    def test_a_reply_without_an_image_is_no_image(self):
        client, _ = self.make((200, {"data": []}))
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("gpt-image-2"), [])
        self.assertEqual(caught.exception.code, "no_image")

    def test_a_missing_key_is_refused_before_any_call(self):
        script = Script()
        with self.assertRaises(StudioError) as caught:
            OpenAIImages({}, TIMEOUT, transport=script)
        self.assertEqual((caught.exception.code, caught.exception.status), ("missing_api_key", 412))
        self.assertEqual(script.calls, [])


class BlackForestLabsTests(unittest.TestCase):
    KEY = "bfl-test-KEY-456"
    POLL = "https://api.eu.bfl.ai/v1/get_result?id=job-1"

    def make(self, *replies, clock=None):
        script = Script(*replies)
        client = BlackForestLabs({"BFL_API_KEY": self.KEY}, TIMEOUT, transport=script,
                                 sleep=lambda seconds: None, clock=clock or FakeClock(1.0))
        return client, script

    def test_submit_then_poll_until_ready_then_download_without_the_key(self):
        client, script = self.make(
            (200, {"id": "job-1", "polling_url": self.POLL}),
            (200, {"status": "Pending"}),
            (200, {"status": "Ready", "result": {"sample": "https://cdn.bfl.example/out.png"}}),
            (200, PNG),
        )
        result = client.generate(brief("flux-3-image", aspect="16:9", size="default"), [])
        self.assertEqual(result["data"], PNG)
        submit, poll, _, download = script.calls
        self.assertEqual(submit["url"], "https://api.bfl.ai/v1/flux-3-image")
        self.assertEqual(submit["headers"]["x-key"], self.KEY)
        self.assertEqual(json.loads(submit["body"]), {"prompt": "a red fox", "aspect_ratio": "16:9"})
        self.assertEqual(poll["headers"]["x-key"], self.KEY)
        self.assertEqual(download["headers"], {}, "the download must carry no credential")

    def test_references_are_sent_as_base64_in_images(self):
        client, script = self.make((200, {"id": "job-1", "polling_url": self.POLL}),
                                   (200, {"status": "Ready", "result": {"sample": "https://cdn.bfl.example/o.png"}}),
                                   (200, PNG))
        client.generate(brief("flux-3-image", refs=refs(1)), refs(1))
        self.assertEqual(json.loads(script.calls[0]["body"])["images"], [PNG_B64])

    def test_a_moderated_request_is_a_safety_block(self):
        client, _ = self.make((200, {"id": "job-1", "polling_url": self.POLL}),
                              (200, {"status": "Request Moderated"}))
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("flux-3-image"), [])
        self.assertEqual(caught.exception.code, "safety_block")

    def test_a_polling_address_outside_bfl_is_refused_and_the_key_is_not_sent_there(self):
        client, script = self.make((200, {"id": "job-1", "polling_url": "https://evil.example.com/poll"}))
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("flux-3-image"), [])
        self.assertEqual(caught.exception.code, "bad_polling_url")
        self.assertEqual(len(script.calls), 1)

    def test_a_job_that_never_finishes_times_out(self):
        client, _ = self.make(*[(200, {"id": "job-1", "polling_url": self.POLL})] + [(200, {"status": "Pending"})] * 50,
                              clock=FakeClock(20.0))
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("flux-3-image"), [])
        self.assertEqual(caught.exception.code, "timeout")


class IdeogramTests(unittest.TestCase):
    KEY = "ideogram-test-KEY-789"

    def test_generation_sends_the_api_key_header_and_downloads_the_url(self):
        script = Script((200, {"data": [{"url": "https://ideogram-cdn.example/a.png"}]}), (200, PNG))
        client = Ideogram({"IDEOGRAM_API_KEY": self.KEY}, TIMEOUT, transport=script)
        self.assertEqual(client.generate(brief("ideogram-4-5"), [])["data"], PNG)
        self.assertEqual(script.calls[0]["url"], "https://api.ideogram.ai/v2/image/generate/ideogram-4-5")
        self.assertEqual(script.calls[0]["headers"]["Api-Key"], self.KEY)
        self.assertEqual(script.calls[1]["headers"], {}, "the download carries no credential")

    def test_an_edit_sends_one_image_as_a_multipart_file_to_precise_edit(self):
        script = Script((200, {"data": [{"url": "https://ideogram-cdn.example/b.png"}]}), (200, PNG))
        client = Ideogram({"IDEOGRAM_API_KEY": self.KEY}, TIMEOUT, transport=script)
        client.generate(brief("ideogram-4-5", refs=refs(1)), refs(1))
        call = script.calls[0]
        self.assertEqual(call["url"], "https://api.ideogram.ai/v2/image/precise-edit/ideogram-4-5")
        self.assertIn(b'name="image"', call["body"])

    def test_a_download_link_that_is_not_https_is_refused(self):
        script = Script((200, {"data": [{"url": "http://ideogram-cdn.example/a.png"}]}))
        client = Ideogram({"IDEOGRAM_API_KEY": self.KEY}, TIMEOUT, transport=script)
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("ideogram-4-5"), [])
        self.assertEqual(caught.exception.code, "bad_image_url")
        self.assertEqual(len(script.calls), 1)


class RecraftTests(unittest.TestCase):
    KEY = "recraft-test-KEY-012"

    def test_generation_asks_for_base64_with_a_bearer_key(self):
        script = Script((200, {"data": [{"b64_json": PNG_B64}]}))
        client = Recraft({"RECRAFT_API_KEY": self.KEY}, TIMEOUT, transport=script)
        self.assertEqual(client.generate(brief("recraftv4_1"), [])["data"], PNG)
        call = script.calls[0]
        self.assertEqual(call["url"], "https://external.api.recraft.ai/v1/images/generations")
        self.assertEqual(call["headers"]["Authorization"], f"Bearer {self.KEY}")
        self.assertEqual(json.loads(call["body"])["response_format"], "b64_json")

    def test_references_are_refused_because_recraft_is_used_for_generation_only(self):
        client = Recraft({"RECRAFT_API_KEY": self.KEY}, TIMEOUT, transport=Script())
        with self.assertRaises(StudioError) as caught:
            client.generate(brief("recraftv4_1", refs=refs(1)), refs(1))
        self.assertEqual(caught.exception.code, "references_not_supported")


class BytePlusTests(unittest.TestCase):
    KEY = "ark-test-KEY-345"

    def test_references_go_as_data_urls_and_one_image_is_sequential_disabled(self):
        script = Script((200, {"data": [{"b64_json": PNG_B64}]}))
        client = BytePlus({"ARK_API_KEY": self.KEY}, TIMEOUT, transport=script)
        self.assertEqual(client.generate(brief("dola-seedream-5-0-pro-260628", size="2K", refs=refs(1)), refs(1))["data"], PNG)
        call = script.calls[0]
        self.assertEqual(call["url"], "https://ark.ap-southeast.bytepluses.com/api/v3/images/generations")
        self.assertEqual(call["headers"]["Authorization"], f"Bearer {self.KEY}")
        body = json.loads(call["body"])
        self.assertEqual(body["sequential_image_generation"], "disabled")
        self.assertEqual(body["image"], [f"data:image/png;base64,{PNG_B64}"])

    def test_without_references_no_image_field_is_sent(self):
        script = Script((200, {"data": [{"b64_json": PNG_B64}]}))
        client = BytePlus({"ARK_API_KEY": self.KEY}, TIMEOUT, transport=script)
        client.generate(brief("dola-seedream-5-0-pro-260628", size="1K"), [])
        self.assertNotIn("image", json.loads(script.calls[0]["body"]))


class StabilityTests(unittest.TestCase):
    KEY = "sk-stability-test-678"

    def test_core_posts_multipart_and_returns_the_image_bytes(self):
        script = Script((200, PNG))
        client = Stability({"STABILITY_API_KEY": self.KEY}, TIMEOUT, transport=script)
        self.assertEqual(client.generate(brief("stable-image-core", aspect="16:9", size="default"), [])["data"], PNG)
        call = script.calls[0]
        self.assertEqual(call["url"], "https://api.stability.ai/v2beta/stable-image/generate/core")
        self.assertEqual(call["headers"]["authorization"], f"Bearer {self.KEY}")
        self.assertEqual(call["headers"]["accept"], "image/*")
        self.assertIn(b'name="aspect_ratio"\r\n\r\n16:9', call["body"])
        self.assertIn(b'name="output_format"\r\n\r\npng', call["body"])

    def test_ultra_has_its_own_endpoint(self):
        script = Script((200, PNG))
        Stability({"STABILITY_API_KEY": self.KEY}, TIMEOUT, transport=script).generate(
            brief("stable-image-ultra", size="default"), [])
        self.assertTrue(script.calls[0]["url"].endswith("/generate/ultra"))

    def test_a_model_without_an_endpoint_is_refused(self):
        client = Stability({"STABILITY_API_KEY": self.KEY}, TIMEOUT, transport=Script())
        with self.assertRaises(StudioError) as caught:
            client.generate(brief("sd-unknown", size="default"), [])
        self.assertEqual(caught.exception.code, "model_not_offered")


class ComfyUITests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.workflow_path = os.path.join(self._tmp.name, "workflow.json")

    def tearDown(self):
        self._tmp.cleanup()

    def write_workflow(self, nodes):
        with open(self.workflow_path, "w", encoding="utf-8") as handle:
            json.dump(nodes, handle)

    def standard(self, with_reference=False):
        nodes = {
            "1": {"class_type": "CLIPTextEncode", "_meta": {"title": "Prompt"}, "inputs": {"text": "placeholder"}},
            "2": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512}},
            "3": {"class_type": "SaveImage", "inputs": {"images": ["4", 0]}},
        }
        if with_reference:
            nodes["5"] = {"class_type": "LoadImage", "_meta": {"title": "Reference"}, "inputs": {"image": "none.png"}}
        return nodes

    def make(self, *replies, env_extra=None):
        self.write_workflow(self.standard(with_reference=bool(env_extra and env_extra.get("ref"))))
        env = {"COMFYUI_WORKFLOW": self.workflow_path}
        script = Script(*replies)
        client = ComfyUI(env, TIMEOUT, transport=script, sleep=lambda seconds: None, clock=FakeClock(1.0))
        return client, script

    def test_the_prompt_and_the_size_are_written_into_the_workflow_and_the_output_is_downloaded(self):
        output = {"3": {"images": [{"filename": "out_00001_.png", "subfolder": "", "type": "output"}]}}
        client, script = self.make(
            (200, {"prompt_id": "abc123"}),
            (200, {}),
            (200, {"abc123": {"outputs": output}}),
            (200, PNG),
        )
        result = client.generate(brief("comfyui-workflow", size="1536x1024", aspect="3:2"), [])
        self.assertEqual(result["data"], PNG)
        submitted = json.loads(script.calls[0]["body"])
        self.assertEqual(submitted["prompt"]["1"]["inputs"]["text"], "a red fox")
        self.assertEqual((submitted["prompt"]["2"]["inputs"]["width"], submitted["prompt"]["2"]["inputs"]["height"]),
                         (1536, 1024))
        self.assertIn("client_id", submitted)
        self.assertIn("/view?filename=out_00001_.png", script.calls[3]["url"])

    def test_a_reference_is_uploaded_and_named_in_the_load_node(self):
        output = {"3": {"images": [{"filename": "o.png", "subfolder": "", "type": "output"}]}}
        client, script = self.make(
            (200, {"name": "uploaded-ref.png"}),
            (200, {"prompt_id": "p1"}),
            (200, {"p1": {"outputs": output}}),
            (200, PNG),
            env_extra={"ref": True},
        )
        client.generate(brief("comfyui-workflow", refs=refs(1)), refs(1))
        self.assertTrue(script.calls[0]["url"].endswith("/upload/image"))
        submitted = json.loads(script.calls[1]["body"])
        self.assertEqual(submitted["prompt"]["5"]["inputs"]["image"], "uploaded-ref.png")

    def test_a_server_on_another_machine_is_refused_at_construction(self):
        self.write_workflow(self.standard())
        with self.assertRaises(StudioError) as caught:
            ComfyUI({"COMFYUI_WORKFLOW": self.workflow_path, "COMFYUI_URL": "http://192.168.1.20:8188"}, TIMEOUT,
                    transport=Script())
        self.assertEqual(caught.exception.code, "comfyui_not_local")

    def test_a_workflow_without_the_prompt_node_is_refused_before_any_call(self):
        nodes = self.standard()
        del nodes["1"]["_meta"]
        self.write_workflow(nodes)
        script = Script()
        with self.assertRaises(StudioError) as caught:
            ComfyUI({"COMFYUI_WORKFLOW": self.workflow_path}, TIMEOUT, transport=script)
        self.assertEqual(caught.exception.code, "comfyui_workflow")
        self.assertEqual(script.calls, [])

    def test_a_missing_workflow_file_is_refused_at_construction(self):
        with self.assertRaises(StudioError) as caught:
            ComfyUI({"COMFYUI_WORKFLOW": os.path.join(self._tmp.name, "absent.json")}, TIMEOUT, transport=Script())
        self.assertEqual(caught.exception.code, "comfyui_workflow")

    def test_a_reference_without_a_reference_node_is_refused_by_preflight_before_any_call(self):
        self.write_workflow(self.standard(with_reference=False))
        script = Script()
        client = ComfyUI({"COMFYUI_WORKFLOW": self.workflow_path}, TIMEOUT, transport=script)
        client.preflight(brief("comfyui-workflow"))  # no references: nothing to check
        with self.assertRaises(StudioError) as caught:
            client.preflight(brief("comfyui-workflow", refs=refs(1)))
        self.assertEqual(caught.exception.code, "comfyui_workflow")
        self.assertEqual(script.calls, [])


class ClientFactoryTests(unittest.TestCase):
    def test_every_provider_refuses_without_its_variables_before_any_call(self):
        catalog = load_studio_catalog()
        for key, info in catalog["providers"].items():
            with self.subTest(provider=key):
                self.assertFalse(configured(key, env={}))
                script = Script()
                if key == "comfyui":
                    continue  # ComfyUI needs a workflow file; its refusal is covered above
                with self.assertRaises(StudioError) as caught:
                    make_client(key, TIMEOUT, env={}, transport=script)
                self.assertEqual(caught.exception.code, "missing_api_key")
                self.assertEqual(script.calls, [])

    def test_an_unknown_provider_is_refused(self):
        with self.assertRaises(StudioError) as caught:
            make_client("midjourney", TIMEOUT, env={})
        self.assertEqual(caught.exception.code, "unknown_provider")

    def test_configured_reads_only_presence_and_never_returns_the_value(self):
        self.assertTrue(configured("stability", env={"STABILITY_API_KEY": "sk-visible-value"}))
        self.assertFalse(configured("stability", env={"STABILITY_API_KEY": "   "}))


if __name__ == "__main__":
    unittest.main()


class EndToEndTests(unittest.TestCase):
    """Plan, approve, run and reuse, through the same core rules the page and the command line use."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Store(self._tmp.name)
        self.catalog = load_studio_catalog()

    def tearDown(self):
        self._tmp.cleanup()

    def test_an_openai_run_spends_one_approval_and_saves_the_image(self):
        plan = build_brief(self.catalog, self.store, prompt="a red fox", model_id="gpt-image-2", aspect_ratio="1:1",
                           image_size="1024x1024", references=[])
        approval = self.store.issue_approval(plan["brief_sha256"])
        script = Script((200, {"data": [{"b64_json": PNG_B64}]}))
        factory = lambda provider: make_client(provider, TIMEOUT, env={"OPENAI_API_KEY": "sk-e2e-KEY"}, transport=script)
        record = run_brief(self.catalog, self.store, factory, plan["brief_sha256"], approval["approval_id"], utcnow())
        self.assertEqual(record["status"], "generated")
        self.assertEqual(record["provider"], "openai")
        self.assertEqual(record["model"], "gpt-image-2")
        self.assertTrue(os.path.exists(self.store.output_path(record["output"])))
        self.assertEqual(len(script.calls), 1)
        with self.assertRaises(StudioError) as caught:
            run_brief(self.catalog, self.store, factory, plan["brief_sha256"], approval["approval_id"], utcnow())
        self.assertEqual(caught.exception.code, "approval_used")
        self.assertEqual(len(script.calls), 1, "a reused approval must not reach the provider")

    def test_an_auto_aspect_run_completes_and_records_no_ratio_check(self):
        # Seedream takes no ratio: its brief says "auto". The run must finish, not fail after the approval is spent.
        plan = build_brief(self.catalog, self.store, prompt="a red fox", model_id="dola-seedream-5-0-pro-260628",
                           aspect_ratio="auto", image_size="2K", references=[])
        approval = self.store.issue_approval(plan["brief_sha256"])
        script = Script((200, {"data": [{"b64_json": PNG_B64}]}))
        factory = lambda provider: make_client(provider, TIMEOUT, env={"ARK_API_KEY": "ark-e2e-KEY"}, transport=script)
        record = run_brief(self.catalog, self.store, factory, plan["brief_sha256"], approval["approval_id"], utcnow())
        self.assertEqual(record["status"], "generated")
        self.assertIsNone(record["checks"]["aspect_ratio_ok"])

    def test_a_failed_provider_call_keeps_the_approval_spent(self):
        plan = build_brief(self.catalog, self.store, prompt="a red fox", model_id="recraftv4_1", aspect_ratio="1:1",
                           image_size="1024x1024", references=[])
        approval = self.store.issue_approval(plan["brief_sha256"])
        script = Script((400, {"error": {"message": "bad request"}}))
        factory = lambda provider: make_client(provider, TIMEOUT, env={"RECRAFT_API_KEY": "rc-e2e-KEY"}, transport=script)
        record = run_brief(self.catalog, self.store, factory, plan["brief_sha256"], approval["approval_id"], utcnow())
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["error"], "http_400")
        with self.assertRaises(StudioError) as caught:
            self.store.consume_approval(approval["approval_id"], plan["brief_sha256"], utcnow())
        self.assertEqual(caught.exception.code, "approval_used")


class FireflyTests(unittest.TestCase):
    CLIENT_ID = "firefly-test-CLIENT-ID-901"
    CLIENT_SECRET = "firefly-test-CLIENT-SECRET-902"
    TOKEN = "eyJ-test-ACCESS-TOKEN-903"

    def make(self, *replies):
        script = Script(*replies)
        client = Firefly({"FIREFLY_SERVICES_CLIENT_ID": self.CLIENT_ID,
                           "FIREFLY_SERVICES_CLIENT_SECRET": self.CLIENT_SECRET}, TIMEOUT, transport=script)
        return client, script

    def test_signs_in_with_client_credentials_then_generates_and_downloads_without_a_credential(self):
        client, script = self.make(
            (200, {"access_token": self.TOKEN}),
            (200, {"outputs": [{"seed": 1, "image": {"url": "https://pre-signed.example.com/out.png"}}]}),
            (200, PNG),
        )
        self.assertEqual(client.generate(brief("firefly_image", aspect="16:9", size="default"), [])["data"], PNG)
        token_call, generate_call, download_call = script.calls
        self.assertEqual(token_call["url"], "https://ims-na1.adobelogin.com/ims/token/v3")
        form = token_call["body"].decode("ascii")
        self.assertIn("grant_type=client_credentials", form)
        self.assertIn(f"client_id={self.CLIENT_ID}", form)
        self.assertIn("scope=openid%2CAdobeID", form)
        self.assertEqual(generate_call["url"], "https://firefly-api.adobe.io/v3/images/generate")
        self.assertEqual(generate_call["headers"]["x-api-key"], self.CLIENT_ID)
        self.assertEqual(generate_call["headers"]["Authorization"], f"Bearer {self.TOKEN}")
        body = json.loads(generate_call["body"])
        self.assertEqual(body["modelId"], "firefly_image")
        self.assertEqual(body["aspectRatio"], "16:9")
        self.assertEqual(download_call["headers"], {}, "the pre-signed link needs no credential, and gets none")

    def test_the_token_and_the_secret_never_appear_in_an_error_message(self):
        client, _ = self.make((200, {"access_token": self.TOKEN}),
                              (401, {"error": {"message": f"bad token {self.TOKEN} for {self.CLIENT_SECRET}"}}))
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("firefly_image", aspect="16:9", size="default"), [])
        self.assertNotIn(self.TOKEN, caught.exception.message)
        self.assertNotIn(self.CLIENT_SECRET, caught.exception.message)

    def test_references_are_refused(self):
        client, _ = self.make()
        with self.assertRaises(StudioError) as caught:
            client.generate(brief("firefly_image", aspect="16:9", size="default", refs=refs(1)), refs(1))
        self.assertEqual(caught.exception.code, "references_not_supported")


class BflStatusContractTests(unittest.TestCase):
    """The FLUX 3 status table, as the official Results and errors section lists it, against the adapter."""

    KEY = "bfl-contract-KEY-321"
    POLL = "https://api.us.bfl.ai/v1/get_result?id=task-7"

    def make(self, *replies, clock=None):
        script = Script((200, {"id": "task-7", "polling_url": self.POLL, "cost": 0.048, "input_mp": 0, "output_mp": 0.59}),
                        *replies)
        client = BlackForestLabs({"BFL_API_KEY": self.KEY}, TIMEOUT, transport=script,
                                 sleep=lambda seconds: None, clock=clock or FakeClock(1.0))
        return client, script

    def test_reasoning_and_generating_are_polled_through_until_ready(self):
        client, script = self.make((200, {"status": "Reasoning"}), (200, {"status": "Generating"}),
                                   (200, {"status": "Ready", "result": {"sample": "https://delivery.example/x.jpeg"}}),
                                   (200, PNG))
        self.assertEqual(client.generate(brief("flux-3-image"), [])["data"], PNG)
        self.assertEqual(len(script.calls), 5)

    def test_failed_and_task_not_found_are_provider_errors_at_once(self):
        for state, code in (("Error", "provider_error"), ("Failed", "provider_error"), ("Task not found", "provider_error")):
            with self.subTest(state=state):
                client, script = self.make((200, {"status": state}))
                with self.assertRaises(ProviderError) as caught:
                    client.generate(brief("flux-3-image"), [])
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(len(script.calls), 2)  # submit and one poll; no more polling

    def test_content_moderated_is_a_safety_block(self):
        client, _ = self.make((200, {"status": "Content Moderated"}))
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("flux-3-image"), [])
        self.assertEqual(caught.exception.code, "safety_block")

    def test_a_failed_task_with_http_503_and_a_status_body_is_read_as_that_status(self):
        client, _ = self.make((503, {"status": "Error", "details": "transient"}))
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("flux-3-image"), [])
        self.assertEqual(caught.exception.code, "provider_error")

    def test_http_503_without_a_status_is_an_http_error(self):
        client, _ = self.make((503, {"message": "try later"}))
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("flux-3-image"), [])
        self.assertEqual(caught.exception.code, "http_503")

    def test_a_state_the_guide_does_not_list_stops_the_run_without_more_polling(self):
        client, script = self.make((200, {"status": "Queued"}))
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("flux-3-image"), [])
        self.assertEqual(caught.exception.code, "unexpected_status")
        self.assertEqual(len(script.calls), 2)

    def test_a_job_that_stays_pending_times_out_with_the_approval_spent(self):
        client, _ = self.make(*[(200, {"status": "Pending"})] * 40, clock=FakeClock(20.0))
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("flux-3-image"), [])
        self.assertEqual(caught.exception.code, "timeout")


class ComfyUIContractTests(unittest.TestCase):
    """The completion and the timeout of a ComfyUI run, with the history shape of the official example."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "workflow.json")
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"6": {"class_type": "CLIPTextEncode", "_meta": {"title": "Prompt"}, "inputs": {"text": "x"}},
                       "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "ComfyUI", "images": ["8", 0]}}},
                      handle)

    def tearDown(self):
        self._tmp.cleanup()

    def test_history_with_an_output_image_completes_the_run_and_downloads_it_by_view(self):
        history = {"abc": {"prompt": [], "outputs": {"9": {"images": [
            {"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}]}}}}
        script = Script((200, {"prompt_id": "abc", "number": 0}), (200, {}), (200, history), (200, PNG))
        client = ComfyUI({"COMFYUI_WORKFLOW": self.path}, TIMEOUT, transport=script,
                         sleep=lambda seconds: None, clock=FakeClock(1.0))
        self.assertEqual(client.generate(brief("comfyui-workflow"), [])["data"], PNG)
        self.assertTrue(script.calls[-1]["url"].startswith("http://127.0.0.1:8188/view?"))
        self.assertIn("filename=ComfyUI_00001_.png", script.calls[-1]["url"])

    def test_a_history_entry_with_no_image_is_no_image(self):
        history = {"abc": {"outputs": {"9": {"text": ["done"]}}}}
        script = Script((200, {"prompt_id": "abc"}), (200, history))
        client = ComfyUI({"COMFYUI_WORKFLOW": self.path}, TIMEOUT, transport=script,
                         sleep=lambda seconds: None, clock=FakeClock(1.0))
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("comfyui-workflow"), [])
        self.assertEqual(caught.exception.code, "no_image")

    def test_a_workflow_that_never_writes_history_times_out(self):
        script = Script((200, {"prompt_id": "abc"}), *[(200, {})] * 60)
        client = ComfyUI({"COMFYUI_WORKFLOW": self.path}, TIMEOUT, transport=script,
                         sleep=lambda seconds: None, clock=FakeClock(20.0))
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("comfyui-workflow"), [])
        self.assertEqual(caught.exception.code, "timeout")


class PreflightContractTests(unittest.TestCase):
    """Refusals that need no call happen before the approval is spent, and a refused brief leaves the approval usable."""

    def test_each_model_that_takes_no_reference_refuses_one_in_preflight_without_a_call(self):
        cases = [
            (Recraft({"RECRAFT_API_KEY": "rc-x"}, TIMEOUT, transport=Script()), "recraftv4_1_flash"),
            (Ideogram({"IDEOGRAM_API_KEY": "ig-x"}, TIMEOUT, transport=Script()), "ideogram-3"),
            (Stability({"STABILITY_API_KEY": "st-x"}, TIMEOUT, transport=Script()), "sd3.5-large"),
            (Firefly({"FIREFLY_SERVICES_CLIENT_ID": "a", "FIREFLY_SERVICES_CLIENT_SECRET": "b"}, TIMEOUT,
                     transport=Script()), "firefly_image"),
        ]
        for client, model in cases:
            with self.subTest(model=model):
                with self.assertRaises(StudioError) as caught:
                    client.preflight(brief(model, refs=refs(1)))
                self.assertEqual(caught.exception.code, "references_not_supported")
                self.assertEqual(client._transport.calls, [])

    def test_ideogram_4_5_is_the_one_model_that_accepts_a_reference_for_its_precise_edit(self):
        client = Ideogram({"IDEOGRAM_API_KEY": "ig-x"}, TIMEOUT, transport=Script())
        client.preflight(brief("ideogram-4-5", refs=refs(1)))  # no exception

    def test_stability_refuses_an_unknown_model_in_preflight(self):
        client = Stability({"STABILITY_API_KEY": "st-x"}, TIMEOUT, transport=Script())
        with self.assertRaises(StudioError) as caught:
            client.preflight(brief("sd3.5-flash", size="default"))
        self.assertEqual(caught.exception.code, "model_not_offered")

    def test_a_refused_preflight_leaves_the_approval_usable(self):
        from studio.core import Store, build_brief, run_brief, utcnow
        with tempfile.TemporaryDirectory() as data_dir:
            store = Store(data_dir)
            catalog = load_studio_catalog()
            token_plan = build_brief(catalog, store, prompt="a red fox", model_id="stable-image-core",
                                     aspect_ratio="1:1", image_size="default", references=[])
            approval = store.issue_approval(token_plan["brief_sha256"])

            class Refuses:
                def preflight(self, brief):
                    raise StudioError("references_not_supported", "refused before the call")

                def generate(self, brief, references):
                    raise AssertionError("no call may happen after a refused preflight")

            with self.assertRaises(StudioError):
                run_brief(catalog, store, lambda provider: Refuses(), token_plan["brief_sha256"],
                          approval["approval_id"], utcnow())
            store.consume_approval(approval["approval_id"], token_plan["brief_sha256"], utcnow())  # still usable


class StabilitySd3Tests(unittest.TestCase):
    KEY = "sk-sd3-contract-KEY"

    def test_sd3_5_sends_the_model_field_to_the_sd3_endpoint_and_core_sends_none(self):
        script = Script((200, PNG), (200, PNG))
        client = Stability({"STABILITY_API_KEY": self.KEY}, TIMEOUT, transport=script)
        client.generate(brief("sd3.5-large-turbo", aspect="1:1", size="default"), [])
        client.generate(brief("stable-image-core", aspect="1:1", size="default"), [])
        sd3, core = script.calls
        self.assertEqual(sd3["url"], "https://api.stability.ai/v2beta/stable-image/generate/sd3")
        self.assertIn(b'name="model"\r\n\r\nsd3.5-large-turbo', sd3["body"])
        self.assertEqual(core["url"], "https://api.stability.ai/v2beta/stable-image/generate/core")
        self.assertNotIn(b'name="model"', core["body"])


class BflHttpErrorTests(unittest.TestCase):
    """An authentication failure is an HTTP error, even when its body carries a status field."""

    def test_a_401_with_a_numeric_status_field_is_an_http_error(self):
        script = Script((200, {"id": "t", "polling_url": "https://api.bfl.ai/v1/get_result?id=t"}), (401, {"status": 401, "detail": "no"}))
        client = BlackForestLabs({"BFL_API_KEY": "bfl-401-KEY"}, TIMEOUT, transport=script,
                                 sleep=lambda seconds: None, clock=FakeClock(1.0))
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("flux-3-image"), [])
        self.assertEqual(caught.exception.code, "http_401")

    def test_a_401_with_an_unlisted_status_string_is_an_http_error_not_a_task_state(self):
        script = Script((200, {"id": "t", "polling_url": "https://api.bfl.ai/v1/get_result?id=t"}),
                        (401, {"status": "Unauthorized"}))
        client = BlackForestLabs({"BFL_API_KEY": "bfl-401-KEY"}, TIMEOUT, transport=script,
                                 sleep=lambda seconds: None, clock=FakeClock(1.0))
        with self.assertRaises(ProviderError) as caught:
            client.generate(brief("flux-3-image"), [])
        self.assertEqual(caught.exception.code, "http_401")


class CatalogAdapterConsistencyTests(unittest.TestCase):
    """The catalog and the adapters must agree: a model the catalog says takes no reference is refused in preflight,
    and every offered non-local model has an endpoint that preflight accepts for a plain request."""

    def setUp(self):
        self.catalog = load_studio_catalog()
        self.env = {name: "placeholder-value" for info in self.catalog["providers"].values() for name in info["env"]}
        self.env.setdefault("COMFYUI_WORKFLOW", "unused")

    def adapter(self, provider):
        return make_client(provider, TIMEOUT, env=self.env, transport=Script())

    def test_reference_limit_zero_in_the_catalog_means_preflight_refuses_a_reference(self):
        for model in self.catalog["models"]:
            provider = model.get("provider", "gemini")
            if provider in ("gemini", "comfyui"):
                continue
            with self.subTest(model=model["id"]):
                refused = False
                try:
                    self.adapter(provider).preflight(brief(model["id"], refs=refs(1)))
                except StudioError as exc:
                    refused = exc.code == "references_not_supported"
                self.assertEqual(refused, model.get("reference_total_max", 0) == 0)

    def test_every_offered_non_local_model_passes_preflight_for_a_plain_request(self):
        for model in self.catalog["models"]:
            provider = model.get("provider", "gemini")
            if provider in ("gemini", "comfyui"):
                continue
            with self.subTest(model=model["id"]):
                self.adapter(provider).preflight(brief(model["id"]))  # no exception

    def test_every_stability_row_has_an_endpoint(self):
        stability = self.adapter("stability")
        for model in self.catalog["models"]:
            if model.get("provider") == "stability":
                with self.subTest(model=model["id"]):
                    self.assertIsNotNone(stability._call(model["id"]))
