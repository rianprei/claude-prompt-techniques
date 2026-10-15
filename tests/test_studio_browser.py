"""The studio page in a real headless browser: the page's script runs and fills it in. The server runs with the fake
provider (no network, no cost). Skipped when no Chrome or Chromium is on PATH; set STUDIO_REQUIRE_BROWSER=1 to fail
instead, for example in CI."""

import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BROWSERS = ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser", "chrome")


def find_browser():
    for name in BROWSERS:
        found = shutil.which(name)
        if found:
            return found
    return None


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class BrowserRenderTest(unittest.TestCase):
    def setUp(self):
        self.browser = find_browser()
        if self.browser is None:
            if os.environ.get("STUDIO_REQUIRE_BROWSER") == "1":
                self.fail("no Chrome or Chromium on PATH, and STUDIO_REQUIRE_BROWSER=1")
            self.skipTest("no Chrome or Chromium on PATH")
        self.data = tempfile.TemporaryDirectory()
        self.addCleanup(self.data.cleanup)
        self.profile = tempfile.TemporaryDirectory()  # a fresh profile: never the person's own browser profile
        self.addCleanup(self.profile.cleanup)
        self.port = free_port()
        self.server = subprocess.Popen(
            [sys.executable, "-m", "studio", "serve", "--port", str(self.port), "--data-dir", self.data.name,
             "--fake-provider"],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self.stop_server)
        self.wait_for_server()

    def stop_server(self):
        self.server.terminate()
        try:
            self.server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.server.kill()
            self.server.wait()

    def wait_for_server(self):
        deadline = time.monotonic() + 20
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/", timeout=2):
                    return
            except OSError:
                if time.monotonic() > deadline:
                    self.fail("the studio server did not answer on 127.0.0.1")
                time.sleep(0.2)

    def rendered_dom(self):
        flags = ["--headless", "--disable-gpu", f"--user-data-dir={self.profile.name}",
                 "--virtual-time-budget=8000", "--dump-dom"]
        if hasattr(os, "geteuid") and os.geteuid() == 0:  # root cannot use the browser sandbox
            flags.insert(0, "--no-sandbox")
        done = subprocess.run([self.browser, *flags, f"http://127.0.0.1:{self.port}/"],
                              capture_output=True, text=True, timeout=180)
        return done.stdout

    def test_the_page_script_runs_and_reports_the_fake_provider(self):
        dom = self.rendered_dom()
        self.assertIn("<title>Image studio</title>", dom)
        match = re.search(r'id="provider-status"[^>]*>(.*?)</', dom, re.S)
        self.assertIsNotNone(match, "the provider status element is missing from the rendered page")
        self.assertIn("Fake provider", re.sub(r"\s+", " ", match.group(1)))


if __name__ == "__main__":
    unittest.main()
