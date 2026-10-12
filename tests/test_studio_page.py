import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from studio.client import FakeClient  # noqa: E402
from studio.server import Studio, make_server  # noqa: E402

HARNESS = os.path.join(ROOT, "tests", "studio_page_check.mjs")
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "node is not installed; the page script check is skipped")
class PageScriptTest(unittest.TestCase):
    """Runs static/app.js against the real server, through a small DOM stub. Localhost only."""

    def test_page_script_drives_the_real_api(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        quiet = mock.patch("sys.stderr", new=io.StringIO())
        quiet.start()
        self.addCleanup(quiet.stop)
        httpd = make_server(Studio(tmp.name, client_factory=FakeClient, provider="fake"), port=0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (httpd.shutdown(), httpd.server_close()))
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}  # the page check needs no key
        env["STUDIO_BASE"] = base
        result = subprocess.run([NODE, HARNESS], env=env,
                                capture_output=True, text=True, timeout=120, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all checks passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
