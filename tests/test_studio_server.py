import base64
import datetime as dt
import io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from studio.client import FakeClient, placeholder_png  # noqa: E402
from studio.core import Store, iso  # noqa: E402
from studio.server import Studio, main, make_server  # noqa: E402

PNG = placeholder_png()
SECRET = "test-secret-value-123"
NANO = "gemini-nano-banana-2.1"


def _stop_server(httpd):
    httpd.shutdown()
    httpd.server_close()


class ServerCase(unittest.TestCase):
    """Runs the real HTTP server on a free 127.0.0.1 port, with the fake provider unless a test says otherwise."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_dir = tmp.name
        quiet = mock.patch("sys.stderr", new=io.StringIO())  # keep the test output readable
        quiet.start()
        self.addCleanup(quiet.stop)
        self.start(Studio(self.data_dir, client_factory=FakeClient, provider="fake"))

    def start(self, studio):
        httpd = make_server(studio, port=0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(_stop_server, httpd)
        self.studio = studio
        self.port = httpd.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"

    def call(self, method, path, body=None, raw=None, headers=None, host=None, token=True):
        """One request. Returns (status, response headers, body bytes)."""
        if raw is not None:
            data = raw
        elif body is not None:
            data = json.dumps(body).encode("utf-8")
        else:
            data = None
        request = urllib.request.Request(self.base + path, data=data, method=method)
        request.add_header("Host", host or f"127.0.0.1:{self.port}")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        if method == "POST" and token:
            request.add_header("X-Studio-Token", self.studio.token)
        for name, value in (headers or {}).items():
            request.add_header(name, value)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers, exc.read()

    def json_call(self, method, path, body=None, **kwargs):
        status, _, data = self.call(method, path, body, **kwargs)
        return status, json.loads(data.decode("utf-8")) if data else {}

    def upload(self):
        status, payload = self.json_call("POST", "/api/inputs", {
            "mime_type": "image/png", "data": base64.b64encode(PNG).decode("ascii")})
        self.assertEqual(status, 201, payload)
        return payload

    def plan(self, references=(), prompt="Make a flat logo of a lighthouse."):
        status, payload = self.json_call("POST", "/api/briefs", {
            "prompt": prompt, "model": NANO, "aspect_ratio": "1:1", "image_size": "1K",
            "references": list(references)})
        self.assertEqual(status, 201, payload)
        return payload

    def approve(self, brief_sha):
        status, payload = self.json_call("POST", "/api/approvals", {"brief_sha256": brief_sha})
        self.assertEqual(status, 201, payload)
        return payload["approval_id"]


class PageAndHostTests(ServerCase):
    def test_page_carries_the_token_and_never_the_key(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": SECRET}):
            status, headers, body = self.call("GET", "/")
        page = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn(self.studio.token, page)
        self.assertNotIn(SECRET, page)
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_static_assets_are_served(self):
        for path, kind in (("/app.js", "javascript"), ("/style.css", "css")):
            with self.subTest(path=path):
                status, headers, _ = self.call("GET", path)
                self.assertEqual(status, 200)
                self.assertIn(kind, headers["Content-Type"])

    def test_a_foreign_host_header_is_refused(self):
        status, payload = self.json_call("GET", "/api/state", host=f"evil.example:{self.port}")
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "bad_host")

    def test_unknown_paths_are_not_found(self):
        for path in ("/api/runs/../../secrets", "/static/../server.py", "/nope"):
            with self.subTest(path=path):
                status, payload = self.json_call("GET", path)
                self.assertEqual(status, 404)
                self.assertEqual(payload["error"], "not_found")


class PostGuardTests(ServerCase):
    def test_post_without_the_token_is_refused(self):
        status, payload = self.json_call("POST", "/api/inputs",
                                         {"mime_type": "image/png", "data": ""}, token=False)
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "bad_token")

    def test_post_must_be_json(self):
        status, payload = self.json_call("POST", "/api/inputs", raw=b"hello",
                                         headers={"Content-Type": "text/plain"})
        self.assertEqual(status, 415)
        self.assertEqual(payload["error"], "bad_content_type")

    def test_malformed_json_is_refused(self):
        status, payload = self.json_call("POST", "/api/inputs", raw=b"{not json")
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "bad_json")

    def test_json_body_must_be_an_object(self):
        status, payload = self.json_call("POST", "/api/inputs", raw=b"[1, 2]")
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "bad_json")

    def test_state_never_shows_the_key(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": SECRET}):
            status, state = self.json_call("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertNotIn(SECRET, json.dumps(state))
        self.assertEqual(state["provider"], "fake")


class FlowTests(ServerCase):
    def test_full_flow_with_the_fake_provider(self):
        plan = self.plan(references=[self.upload()])
        token = self.approve(plan["brief_sha256"])
        run_body = {"brief_sha256": plan["brief_sha256"], "approval_id": token}
        status, run = self.json_call("POST", "/api/runs", run_body)
        self.assertEqual(status, 200)
        self.assertEqual(run["status"], "generated")

        status, headers, image = self.call("GET", f"/api/runs/{run['run_id']}/image")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "image/png")
        self.assertTrue(image.startswith(b"\x89PNG"))

        status, again = self.json_call("POST", "/api/runs", run_body)
        self.assertEqual((status, again["error"]), (409, "approval_used"))

        status, payload = self.json_call("POST", f"/api/runs/{run['run_id']}/review",
                                         {"verdict": "targeted_fix", "note": ""})
        self.assertEqual((status, payload["error"]), (400, "note_required"))
        status, payload = self.json_call("POST", f"/api/runs/{run['run_id']}/review",
                                         {"verdict": "targeted_fix", "note": "crop the left edge"})
        self.assertEqual((status, payload["verdict"]), (200, "targeted_fix"))

        status, payload = self.json_call("POST", f"/api/runs/{run['run_id']}/evaluation",
                                         {"rating": 4, "note": "clean"})
        self.assertEqual((status, payload["rating"]), (200, 4))

        status, state = self.json_call("GET", "/api/state")
        self.assertEqual(state["runs"][0]["run_id"], run["run_id"])
        self.assertEqual(state["runs"][0]["verdict"], "targeted_fix")
        self.assertEqual(state["preferences"]["model"][NANO], {"count": 1, "average": 4.0})

    def test_an_unknown_approval_is_refused(self):
        plan = self.plan()
        status, payload = self.json_call("POST", "/api/runs",
                                         {"brief_sha256": plan["brief_sha256"], "approval_id": "made-up"})
        self.assertEqual((status, payload["error"]), (409, "approval_unknown"))

    def test_an_approval_for_a_changed_brief_is_refused(self):
        token = self.approve(self.plan()["brief_sha256"])
        other = self.plan(prompt="Make a flat logo of a harbor.")
        status, payload = self.json_call("POST", "/api/runs",
                                         {"brief_sha256": other["brief_sha256"], "approval_id": token})
        self.assertEqual((status, payload["error"]), (409, "approval_mismatch"))

    def test_live_run_without_a_key_is_refused_and_the_approval_survives(self):
        live = Studio(self.data_dir, provider="gemini")  # the real client, which reads the key per run
        self.start(live)
        with mock.patch.dict(os.environ) as env:
            env.pop("GEMINI_API_KEY", None)
            plan = self.plan()
            token = self.approve(plan["brief_sha256"])
            status, payload = self.json_call("POST", "/api/runs",
                                             {"brief_sha256": plan["brief_sha256"], "approval_id": token})
            _, state = self.json_call("GET", "/api/state")
        self.assertEqual((status, payload["error"]), (412, "missing_api_key"))
        self.assertFalse(state["api_key_configured"])
        live.store.consume_approval(token, plan["brief_sha256"])  # not spent: still usable once a key exists


class StartupTests(ServerCase):
    def test_starting_the_studio_marks_a_run_cut_off_by_a_stop_as_failed(self):
        run_id = "run_" + "d" * 16
        started = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
        Store(self.data_dir).write_run({"run_id": run_id, "brief_sha256": "0" * 64, "model": NANO,
                                        "aspect_ratio": "1:1", "image_size": "1K", "status": "running",
                                        "started_at": iso(started), "reviews": [], "evaluations": []})
        Studio(self.data_dir, client_factory=FakeClient, provider="fake")
        record = Store(self.data_dir).load_run(run_id)
        self.assertEqual((record["status"], record["error"]), ("failed", "interrupted"))


class CommandLineTests(unittest.TestCase):
    def test_timeout_must_be_a_positive_number_of_seconds(self):
        with mock.patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit) as ctx:
            main(["serve", "--timeout", "0"])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
