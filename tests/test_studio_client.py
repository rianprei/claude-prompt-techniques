import base64
import http.server
import json
import os
import struct
import subprocess
import sys
import threading
import unittest
import urllib.error
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from studio.client import (  # noqa: E402
    ENDPOINT, FakeClient, GeminiClient, build_request, find_image, parse_response, placeholder_png,
    real_client, urllib_transport,
)
from studio.core import ProviderError, StudioError  # noqa: E402

# Built from two parts so that this file does not contain the forbidden text itself.
KEY_PARAM = "?" + "key="
SECRET = "test-secret-value-123"
PNG = placeholder_png()
BRIEF = {"prompt": "A calm harbor", "model": "gemini-nano-banana-2.1",
         "aspect_ratio": "16:9", "image_size": "2K", "references": []}


def image_payload(data=PNG, mime="image/png"):
    block = {"type": "image", "data": base64.b64encode(data).decode("ascii"), "mime_type": mime}
    return json.dumps({"steps": [{"type": "model_output", "content": [block]}]}).encode("utf-8")


class RequestShape(unittest.TestCase):
    def test_url_is_the_interactions_endpoint_and_carries_no_key(self):
        url, headers, body = build_request(BRIEF, [])
        self.assertEqual(url, ENDPOINT)
        self.assertNotIn(KEY_PARAM, url)
        self.assertNotIn("x-goog-api-key", headers)  # added only when the call is made
        self.assertNotIn(SECRET, body.decode("utf-8"))

    def test_body_follows_the_guide_shape(self):
        _, _, body = build_request(BRIEF, [])
        data = json.loads(body)
        self.assertEqual(data["model"], "gemini-nano-banana-2.1")
        self.assertEqual(data["input"], [{"type": "text", "text": "A calm harbor"}])
        self.assertEqual(data["response_format"], {"type": "image", "aspect_ratio": "16:9", "image_size": "2K"})

    def test_reference_images_travel_as_base64_with_their_mime_type(self):
        _, _, body = build_request(BRIEF, [("image/png", b"\x89PNG-bytes")])
        part = json.loads(body)["input"][1]
        self.assertEqual(part["type"], "image")
        self.assertEqual(part["mime_type"], "image/png")
        self.assertEqual(base64.b64decode(part["data"]), b"\x89PNG-bytes")


class GenerateTests(unittest.TestCase):
    def test_key_goes_in_the_header_and_never_in_the_url(self):
        seen = {}

        def transport(url, headers, body, timeout):
            seen.update(url=url, headers=dict(headers), timeout=timeout)
            return 200, image_payload()

        result = GeminiClient(SECRET, transport=transport).generate(BRIEF, [])
        self.assertEqual(seen["headers"]["x-goog-api-key"], SECRET)
        self.assertNotIn(KEY_PARAM, seen["url"])
        self.assertNotIn(SECRET, seen["url"])
        self.assertEqual(result["data"], PNG)
        self.assertEqual(seen["timeout"], 300)

    def test_the_configured_timeout_reaches_the_transport(self):
        seen = {}

        def transport(url, headers, body, timeout):
            seen["timeout"] = timeout
            return 200, image_payload()

        GeminiClient(SECRET, transport=transport, timeout=45).generate(BRIEF, [])
        self.assertEqual(seen["timeout"], 45)

    def test_real_client_takes_the_configured_timeout(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": SECRET}):
            self.assertEqual(real_client(timeout=45)._timeout, 45)

    def test_missing_key_is_refused_before_any_call(self):
        with self.assertRaises(StudioError) as ctx:
            GeminiClient("")
        self.assertEqual(ctx.exception.code, "missing_api_key")
        self.assertEqual(ctx.exception.status, 412)

    def test_http_error_message_never_shows_the_key(self):
        def transport(url, headers, body, timeout):
            return 403, json.dumps({"error": {"message": "rejected key " + SECRET}}).encode("utf-8")

        with self.assertRaises(ProviderError) as ctx:
            GeminiClient(SECRET, transport=transport).generate(BRIEF, [])
        self.assertEqual(ctx.exception.code, "http_403")
        self.assertNotIn(SECRET, ctx.exception.message)
        self.assertIn("[redacted]", ctx.exception.message)

    def test_network_failure_becomes_a_provider_error(self):
        # Patched, so no connection is attempted.
        with mock.patch("studio.client.urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            with self.assertRaises(ProviderError) as ctx:
                urllib_transport("https://example.invalid/", {}, b"{}", 1)
        self.assertEqual(ctx.exception.code, "network_error")


class ParseTests(unittest.TestCase):
    def test_image_in_the_first_model_step_is_read(self):
        self.assertEqual(parse_response(200, image_payload())["data"], PNG)

    def test_image_after_a_text_block_in_the_model_step_is_read(self):
        payload = {"steps": [{"type": "model_output", "content": [
            {"type": "text", "text": "here"},
            {"type": "image", "data": base64.b64encode(PNG).decode("ascii"), "mime_type": "image/png"},
        ]}]}
        self.assertEqual(parse_response(200, json.dumps(payload).encode("utf-8"))["data"], PNG)

    def test_find_image_returns_none_without_an_image(self):
        self.assertIsNone(find_image({"steps": [{"type": "model_output", "content": []}]}))

    def test_response_without_image_is_reported(self):
        with self.assertRaises(ProviderError) as ctx:
            parse_response(200, b'{"steps": []}')
        self.assertEqual(ctx.exception.code, "no_image")

    def test_safety_finish_reason_gets_a_clear_message(self):
        with self.assertRaises(ProviderError) as ctx:
            parse_response(200, b'{"status": "IMAGE_SAFETY"}')
        self.assertEqual(ctx.exception.code, "safety_block")
        self.assertIn("does not rephrase", ctx.exception.message)

    def test_malformed_steps_are_ignored(self):
        with self.assertRaises(ProviderError) as ctx:
            parse_response(200, b'{"steps": "oops"}')
        self.assertEqual(ctx.exception.code, "no_image")

    def test_non_json_and_bad_base64_are_reported(self):
        with self.assertRaises(ProviderError) as ctx:
            parse_response(200, b"<html>")
        self.assertEqual(ctx.exception.code, "bad_response")
        with self.assertRaises(ProviderError) as ctx:
            parse_response(200, json.dumps({"steps": [{"type": "model_output", "content": [
                {"type": "image", "data": "%%%"}]}]}).encode("utf-8"))
        self.assertEqual(ctx.exception.code, "bad_response")


class RedirectTests(unittest.TestCase):
    def test_redirects_are_refused_so_the_key_never_moves(self):
        seen = []

        class Target(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                seen.append(self.headers.get("x-goog-api-key"))
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *args):
                pass

        class Redirector(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{target.server_address[1]}/elsewhere")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        # Local servers only: nothing leaves 127.0.0.1.
        target = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Target)
        redirector = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Redirector)
        for server in (target, redirector):
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            threading.Thread(target=server.serve_forever, daemon=True).start()
        status, _ = urllib_transport(f"http://127.0.0.1:{redirector.server_address[1]}/start",
                                     {"Content-Type": "application/json", "x-goog-api-key": SECRET}, b"{}", 5)
        self.assertEqual(status, 302)
        self.assertEqual(seen, [])


class FakeAndPlaceholderTests(unittest.TestCase):
    def test_fake_client_needs_no_key_and_returns_a_png(self):
        result = FakeClient().generate(BRIEF, [])
        self.assertEqual(result["mime_type"], "image/png")
        self.assertTrue(result["data"].startswith(b"\x89PNG\r\n\x1a\n"))

    def test_placeholder_png_has_the_requested_size(self):
        width, height = struct.unpack(">II", placeholder_png(32, 16)[16:24])
        self.assertEqual((width, height), (32, 16))


class ImportTests(unittest.TestCase):
    def test_importing_the_client_does_not_read_the_catalog(self):
        # load_catalog is replaced by None before the import, so any read at import time fails the run.
        code = ("import sys\n"
                f"sys.path[:0] = [{ROOT!r}, {os.path.join(ROOT, 'scripts')!r}]\n"
                "import contracts\n"
                "contracts.load_catalog = None\n"
                "import studio.client\n")
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
