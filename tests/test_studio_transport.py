"""The shared HTTP layer: multipart bodies, refused redirects, the reply limit, network errors and the image download.

A local server on 127.0.0.1 stands in for a provider. No test reaches the internet, and no test costs anything.
"""

import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from studio.core import ProviderError  # noqa: E402
from studio.transport import fetch_image, http_request, multipart  # noqa: E402


class _Routes(BaseHTTPRequestHandler):
    routes = {}  # path -> (status, headers, body); set per test

    def do_GET(self):
        status, headers, body = self.routes.get(self.path, (404, {}, b"not here"))
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep the test output clean
        pass


class LocalServerTest(unittest.TestCase):
    def setUp(self):
        _Routes.routes = {}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Routes)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)


class MultipartTests(unittest.TestCase):
    def test_fields_and_files_are_parts_with_the_boundary_in_the_type(self):
        content_type, body = multipart([("prompt", "a red fox")], [("image", "source.png", "image/png", b"\x89PNG")])
        boundary = content_type.split("boundary=", 1)[1]
        self.assertTrue(content_type.startswith("multipart/form-data; boundary=studio"))
        self.assertEqual(body.count(f"--{boundary}".encode()), 3)  # one per part, and the closing line "--boundary--"
        self.assertTrue(body.endswith(f"--{boundary}--\r\n".encode()))
        self.assertIn(b'name="prompt"\r\n\r\na red fox', body)
        self.assertIn(b'name="image"; filename="source.png"\r\nContent-Type: image/png\r\n\r\n\x89PNG', body)

    def test_filenames_are_reduced_to_a_safe_set(self):
        _, body = multipart([], [("image", "../../etc passwd.png", "image/png", b"x")])
        header = [line for line in body.split(b"\r\n") if line.startswith(b"Content-Disposition")][0]
        self.assertNotIn(b"/", header)
        self.assertNotIn(b" passwd", header)
        self.assertIn(b'filename="', header)


class HttpRequestTests(LocalServerTest):
    def test_a_redirect_is_returned_not_followed(self):
        _Routes.routes = {"/start": (302, {"Location": "/final"}, b""), "/final": (200, {}, b"reached")}
        status, payload = http_request("GET", f"{self.base}/start", {}, None, 5)
        self.assertEqual(status, 302)
        self.assertEqual(payload, b"")

    def test_a_reply_over_the_limit_is_refused(self):
        _Routes.routes = {"/big": (200, {}, b"x" * 100)}
        with self.assertRaises(ProviderError) as caught:
            http_request("GET", f"{self.base}/big", {}, None, 5, limit=10)
        self.assertEqual(caught.exception.code, "response_too_large")

    def test_a_network_failure_names_the_host_but_not_the_path_or_query(self):
        with socket.socket() as probe:  # a port that nothing listens on
            probe.bind(("127.0.0.1", 0))
            closed = probe.getsockname()[1]
        with self.assertRaises(ProviderError) as caught:
            http_request("GET", f"http://127.0.0.1:{closed}/secret/path?token=abc", {}, None, 2)
        self.assertEqual(caught.exception.code, "network_error")
        self.assertIn("127.0.0.1", caught.exception.message)
        self.assertNotIn("token=abc", caught.exception.message)
        self.assertNotIn("secret/path", caught.exception.message)


class FetchImageTests(LocalServerTest):
    def test_only_https_is_fetched(self):
        with self.assertRaises(ProviderError) as caught:
            fetch_image("http://cdn.example.com/out.png", 5, transport=lambda *a: (200, b""))
        self.assertEqual(caught.exception.code, "bad_image_url")

    def test_an_address_with_credentials_is_refused(self):
        with self.assertRaises(ProviderError) as caught:
            fetch_image("https://user:pass@cdn.example.com/out.png", 5, transport=lambda *a: (200, b""))
        self.assertEqual(caught.exception.code, "bad_image_url")

    def test_the_download_sends_no_header_at_all(self):
        seen = {}

        def transport(method, url, headers, body, timeout, limit):
            seen.update(method=method, headers=headers, body=body)
            return 200, b"\x89PNG"

        self.assertEqual(fetch_image("https://cdn.example.com/out.png", 5, transport=transport), b"\x89PNG")
        self.assertEqual(seen, {"method": "GET", "headers": {}, "body": None})

    def test_a_failed_download_is_reported_with_its_status(self):
        with self.assertRaises(ProviderError) as caught:
            fetch_image("https://cdn.example.com/out.png", 5, transport=lambda *a: (404, b""))
        self.assertEqual(caught.exception.code, "image_download_http_404")


if __name__ == "__main__":
    unittest.main()
