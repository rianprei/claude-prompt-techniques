"""Local web page and JSON API for the studio. It listens on 127.0.0.1 only.

Every request must carry the expected Host header, which blocks DNS rebinding.
Every POST also needs the per-process token and a JSON body. No CORS headers are
sent, so a page on another site cannot read the responses.
"""

import argparse
import base64
import hmac
import json
import os
import re
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .core import (APPROVAL_TTL, MAX_REFERENCE_BYTES, Store, StudioError, build_brief, offered_models,
                   preferences, record_evaluation, record_review, run_brief, summarize_run)
from .client import KEY_ENV, FakeClient, api_key_from_env, real_client
from contracts import load_catalog  # core has put scripts/ on sys.path by now

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.join(HERE, "data")
STATIC_DIR = os.path.join(HERE, "static")
STATIC_FILES = {"/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/style.css": ("style.css", "text/css; charset=utf-8")}
RUN_IMAGE = re.compile(r"/api/runs/(run_[0-9a-f]{16})/image")
RUN_ACTION = re.compile(r"/api/runs/(run_[0-9a-f]{16})/(review|evaluation)")
MAX_BODY_BYTES = 16 * 1024 * 1024  # room for a base64 reference image plus JSON overhead
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


class Studio:
    """What the handlers need: the catalog, the store, how to reach the provider and the page token."""

    def __init__(self, data_dir, client_factory=real_client, provider="gemini", catalog=None):
        self.catalog = catalog if catalog is not None else load_catalog()
        self.store = Store(data_dir)
        self.client_factory = client_factory
        self.provider = provider
        self.token = secrets.token_urlsafe(32)


def _read_static(name):
    with open(os.path.join(STATIC_DIR, name), "rb") as handle:
        return handle.read()


def _decode_image(value):
    if not isinstance(value, str):
        raise StudioError("bad_image", "Send the image as base64 text in the data field.")
    try:
        return base64.b64decode(value, validate=True)
    except ValueError:
        raise StudioError("bad_image", "The image data is not valid base64.") from None


class Handler(BaseHTTPRequestHandler):
    server_version = "NanoBananaStudio"
    sys_version = ""
    timeout = 30  # seconds; a stalled client must not hold a server thread forever
    studio = None  # set for each server by make_server()

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, payload):
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _fail(self, status, code, message):
        self._json(status, {"error": code, "message": message})

    def _internal(self, exc):
        # The class name only: exception messages can echo request data.
        sys.stderr.write(f"internal error: {type(exc).__name__}\n")
        self._fail(500, "internal", "Unexpected error. See the console where the studio runs.")

    def _host_allowed(self):
        port = self.server.server_address[1]
        return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def state(self):
        studio = self.studio
        return {
            "provider": studio.provider,
            "api_key_configured": studio.provider == "fake" or api_key_from_env() is not None,
            "models": offered_models(studio.catalog),
            "aspect_ratios": studio.catalog["aspect_ratios"],
            "approval_ttl_minutes": int(APPROVAL_TTL.total_seconds() // 60),
            "max_reference_bytes": MAX_REFERENCE_BYTES,
            "runs": [summarize_run(r) for r in studio.store.list_runs()],
            "preferences": preferences(studio.store),
        }

    def do_GET(self):
        if not self._host_allowed():
            return self._fail(403, "bad_host", "Open the studio at http://127.0.0.1:<port>/.")
        path = urlsplit(self.path).path
        try:
            if path == "/":
                with open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8") as handle:
                    page = handle.read().replace("__STUDIO_TOKEN__", self.studio.token)
                return self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
            if path in STATIC_FILES:
                name, content_type = STATIC_FILES[path]
                return self._send(200, _read_static(name), content_type)
            if path == "/api/state":
                return self._json(200, self.state())
            match = RUN_IMAGE.fullmatch(path)
            if match:
                data, mime_type = self.studio.store.read_output(match.group(1))
                return self._send(200, data, mime_type)
            return self._fail(404, "not_found", "No such page or endpoint.")
        except StudioError as exc:
            self._json(exc.status, exc.as_dict())
        except Exception as exc:
            self._internal(exc)

    def do_POST(self):
        if not self._host_allowed():
            return self._fail(403, "bad_host", "Open the studio at http://127.0.0.1:<port>/.")
        supplied = self.headers.get("X-Studio-Token", "")
        if not hmac.compare_digest(supplied.encode("utf-8"), self.studio.token.encode("utf-8")):
            return self._fail(403, "bad_token", "Missing or wrong studio token. Reload the page.")
        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if content_type != "application/json":
            return self._fail(415, "bad_content_type", "Send JSON (Content-Type: application/json).")
        length = self.headers.get("Content-Length", "")
        if not length.isdigit():
            return self._fail(411, "length_required", "Send a Content-Length header.")
        if int(length) > MAX_BODY_BYTES:
            return self._fail(413, "body_too_large", "The request is too large.")
        try:
            body = json.loads(self.rfile.read(int(length)) or b"{}")
        except ValueError:
            return self._fail(400, "bad_json", "The body is not valid JSON.")
        if not isinstance(body, dict):
            return self._fail(400, "bad_json", "The body must be a JSON object.")
        try:
            payload, status = self.route_post(urlsplit(self.path).path, body)
            self._json(status, payload)
        except StudioError as exc:
            self._json(exc.status, exc.as_dict())
        except Exception as exc:
            self._internal(exc)

    def route_post(self, path, body):
        """Handle one POST. Returns (payload, status), the order do_POST unpacks."""
        studio = self.studio
        if path == "/api/inputs":
            return studio.store.save_reference(body.get("mime_type"), _decode_image(body.get("data"))), 201
        if path == "/api/briefs":
            plan = build_brief(studio.catalog, studio.store, prompt=body.get("prompt"),
                               model_id=body.get("model"), aspect_ratio=body.get("aspect_ratio"),
                               image_size=body.get("image_size"), references=body.get("references", []))
            return plan, 201
        if path == "/api/approvals":
            return studio.store.issue_approval(body.get("brief_sha256")), 201
        if path == "/api/runs":
            record = run_brief(studio.catalog, studio.store, studio.client_factory,
                               body.get("brief_sha256"), body.get("approval_id"))
            return summarize_run(record), 200
        match = RUN_ACTION.fullmatch(path)
        if match:
            run_id, action = match.groups()
            if action == "review":
                record = record_review(studio.store, run_id, body.get("verdict"), body.get("note"))
            else:
                record = record_evaluation(studio.store, run_id, body.get("rating"), body.get("note"))
            return summarize_run(record), 200
        raise StudioError("not_found", "No such endpoint.", 404)


def make_server(studio, port=0):
    """Bound to 127.0.0.1 only. Port 0 picks a free port, which the tests use."""
    handler = type("StudioHandler", (Handler,), {"studio": studio})
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python3 -m studio",
                                     description="Local studio: one approval per paid run.")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="start the local page")
    serve.add_argument("--port", type=int, default=8765, help="port on 127.0.0.1 (default 8765)")
    serve.add_argument("--data-dir", default=DEFAULT_DATA_DIR,
                       help="where briefs, images and approvals are kept (default studio/data)")
    serve.add_argument("--fake-provider", action="store_true",
                       help="placeholder images, with no network call and no cost")
    args = parser.parse_args(argv)
    if args.fake_provider:
        studio = Studio(args.data_dir, client_factory=FakeClient, provider="fake")
    else:
        studio = Studio(args.data_dir, client_factory=real_client, provider="gemini")
    httpd = make_server(studio, port=args.port)
    print(f"Studio at http://127.0.0.1:{httpd.server_address[1]}/ (provider: {studio.provider})")
    if studio.provider == "fake":
        print("Fake provider: placeholder images, no network, no cost.")
    else:
        print(f"Live provider: each paid run needs a new approval, valid for "
              f"{int(APPROVAL_TTL.total_seconds() // 60)} minutes. The key is read from {KEY_ENV} on each run.")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0
