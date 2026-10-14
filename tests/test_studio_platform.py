"""The studio's platform paths and warnings: the Windows lock (msvcrt, with a stand-in module), the catalog age warning,
and the 429 hint. The Windows path runs here against a fake msvcrt, so it checks the logic, not Windows itself."""

import datetime as dt
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from studio import core  # noqa: E402
from studio.client import parse_response  # noqa: E402
from studio.core import ProviderError, Store, StudioError, catalog_age_findings  # noqa: E402


class FakeMsvcrt:
    """Stands in for the msvcrt module: records each locking call and can report the lock as busy a set number of times."""

    LK_NBLCK = 2
    LK_UNLCK = 0

    def __init__(self, busy_times=0):
        self.calls = []
        self.busy_times = busy_times

    def locking(self, fd, mode, nbytes):
        self.calls.append(mode)
        if mode == self.LK_NBLCK and self.busy_times > 0:
            self.busy_times -= 1
            raise OSError(36, "busy")


class WindowsLockTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = Store(tmp.name)
        self.lock_path = self.store._path(".lock")

    def without_posix_locks(self, fake):
        patches = [mock.patch.object(core, "fcntl", None), mock.patch.object(core, "msvcrt", fake)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_without_fcntl_the_lock_is_taken_and_released_with_msvcrt(self):
        fake = FakeMsvcrt()
        self.without_posix_locks(fake)
        with self.store._locked():
            self.assertEqual(fake.calls, [FakeMsvcrt.LK_NBLCK])
        self.assertEqual(fake.calls, [FakeMsvcrt.LK_NBLCK, FakeMsvcrt.LK_UNLCK])

    def test_a_busy_lock_is_retried_until_it_is_free(self):
        fake = FakeMsvcrt(busy_times=2)
        self.without_posix_locks(fake)
        with self.store._locked():
            pass
        self.assertEqual(fake.calls.count(FakeMsvcrt.LK_NBLCK), 3)
        self.assertEqual(fake.calls[-1], FakeMsvcrt.LK_UNLCK)

    def test_a_lock_that_never_frees_times_out_with_store_busy(self):
        with open(self.lock_path, "a+b") as handle:
            with self.assertRaises(StudioError) as caught:
                core._msvcrt_lock(handle, FakeMsvcrt(busy_times=10**6), timeout=0.05)
        self.assertEqual(caught.exception.code, "store_busy")
        self.assertEqual(caught.exception.status, 503)

    def test_two_threads_of_one_process_never_hold_the_windows_path_at_once(self):
        # msvcrt locks belong to the process, not to the thread, so the threads of the server queue on a mutex.
        self.without_posix_locks(FakeMsvcrt())
        active, peak = [0], [0]
        guard = threading.Lock()

        def work():
            for _ in range(20):
                with self.store._locked():
                    with guard:
                        active[0] += 1
                        peak[0] = max(peak[0], active[0])
                    time.sleep(0.001)
                    with guard:
                        active[0] -= 1

        threads = [threading.Thread(target=work) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(peak[0], 1)

    def test_with_neither_lock_module_the_store_refuses_to_run(self):
        self.without_posix_locks(None)
        with self.assertRaises(StudioError) as caught:
            with self.store._locked():
                pass
        self.assertEqual(caught.exception.code, "unsupported_platform")


class CatalogAgeTests(unittest.TestCase):
    CATALOG = {"verified_on": "2026-10-13"}

    def test_a_fresh_catalog_gives_no_finding(self):
        self.assertEqual(catalog_age_findings(self.CATALOG, today=dt.date(2026, 10, 14)), [])

    def test_ninety_days_is_still_fresh_and_ninety_one_is_not(self):
        start = dt.date(2026, 10, 13)
        self.assertEqual(catalog_age_findings(self.CATALOG, today=start + dt.timedelta(days=90)), [])
        findings = catalog_age_findings(self.CATALOG, today=start + dt.timedelta(days=91))
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["code"], "catalog_stale")
        self.assertEqual(findings[0]["level"], "WARN")
        self.assertIn("91 days", findings[0]["message"])

    def test_the_finding_is_a_warning_so_it_never_blocks_a_plan(self):
        findings = catalog_age_findings(self.CATALOG, today=dt.date(2027, 6, 1))
        self.assertTrue(findings)
        self.assertTrue(all(f["level"] != "ERROR" for f in findings))


class RateLimitHintTests(unittest.TestCase):
    def test_a_429_says_where_the_limits_are_and_that_a_new_plan_is_needed(self):
        with self.assertRaises(ProviderError) as caught:
            parse_response(429, b'{"error": {"message": "Quota exceeded for this project"}}')
        self.assertEqual(caught.exception.code, "http_429")
        self.assertIn("Google AI Studio", caught.exception.message)
        self.assertIn("plan again", caught.exception.message)

    def test_the_api_key_is_still_redacted_from_a_429(self):
        body = b'{"error": {"message": "rejected key SECRET123"}}'
        with self.assertRaises(ProviderError) as caught:
            parse_response(429, body, api_key="SECRET123")
        self.assertNotIn("SECRET123", caught.exception.message)
        self.assertIn("[redacted]", caught.exception.message)


if __name__ == "__main__":
    unittest.main()
