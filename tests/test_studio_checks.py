"""Deterministic image checks, the library search, and the fixed cases. No network and no image library.

The JPEG and WebP inputs are built byte by byte here, so the header readers are tested on exact layouts.
"""

import json
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from contracts import load_catalog  # noqa: E402
from studio.checks import aspect_matches, check_output, image_size  # noqa: E402
from studio.client import placeholder_png  # noqa: E402
from studio.evalset import CASE_KINDS, compare_case, load_cases, validate_cases  # noqa: E402
from studio.library import search  # noqa: E402


def jpeg(width, height, app_segments=0):
    """A minimal JPEG: SOI, optional APP0 segments, SOF0 with the size, EOI."""
    body = b"".join(b"\xff\xe0" + struct.pack(">H", 16) + b"\x00" * 14 for _ in range(app_segments))
    sof = b"\xff\xc0" + struct.pack(">H", 11) + b"\x08" + struct.pack(">HH", height, width) + b"\x01\x01\x22\x00"
    return b"\xff\xd8" + body + sof + b"\xff\xd9"


def webp_lossy(width, height):
    frame = b"\x00\x00\x00" + b"\x9d\x01\x2a" + struct.pack("<HH", width, height)
    chunk = b"VP8 " + struct.pack("<I", len(frame)) + frame
    return b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk


def webp_lossless(width, height):
    bits = (width - 1) | ((height - 1) << 14)
    payload = b"\x2f" + bits.to_bytes(4, "little")
    chunk = b"VP8L" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk


def webp_extended(width, height):
    payload = b"\x00\x00\x00\x00" + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
    chunk = b"VP8X" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk


class ImageSizeTests(unittest.TestCase):
    def test_png_size_comes_from_the_header(self):
        self.assertEqual(image_size(placeholder_png(width=120, height=60), "image/png"), (120, 60))

    def test_jpeg_size_is_found_after_other_segments(self):
        self.assertEqual(image_size(jpeg(640, 480, app_segments=2), "image/jpeg"), (640, 480))

    def test_webp_lossy_lossless_and_extended_sizes(self):
        self.assertEqual(image_size(webp_lossy(300, 200), "image/webp"), (300, 200))
        self.assertEqual(image_size(webp_lossless(1024, 768), "image/webp"), (1024, 768))
        self.assertEqual(image_size(webp_extended(4096, 2048), "image/webp"), (4096, 2048))

    def test_unreadable_data_has_no_size(self):
        self.assertIsNone(image_size(b"not an image at all", "image/png"))
        self.assertIsNone(image_size(jpeg(640, 480), "image/png"))  # wrong declared type
        self.assertIsNone(image_size(b"\xff\xd8\xff\xe0", "image/jpeg"))  # truncated


class AspectTests(unittest.TestCase):
    def test_exact_and_within_tolerance_match(self):
        self.assertTrue(aspect_matches(1000, 1000, "1:1"))
        self.assertTrue(aspect_matches(1020, 1000, "1:1"))  # exactly 2 %: the boundary counts as a match
        self.assertTrue(aspect_matches(2048, 512, "4:1"))

    def test_outside_tolerance_does_not_match(self):
        self.assertFalse(aspect_matches(1030, 1000, "1:1"))
        self.assertFalse(aspect_matches(1024, 1024, "16:9"))

    def test_check_output_reports_facts_and_a_hash(self):
        data = placeholder_png(width=160, height=90)
        result = check_output(data, "image/png", "16:9")
        self.assertEqual((result["width"], result["height"]), (160, 90))
        self.assertTrue(result["aspect_ratio_ok"])
        self.assertEqual(result["bytes"], len(data))
        self.assertEqual(len(result["sha256"]), 64)

    def test_check_output_without_a_readable_size_says_so(self):
        result = check_output(b"garbage", "image/png", "1:1")
        self.assertIsNone(result["width"])
        self.assertIsNone(result["aspect_ratio_ok"])


class LibraryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.library = tmp.name
        with open(os.path.join(self.library, "styles.md"), "w", encoding="utf-8") as handle:
            handle.write("# Portrait studio\n\nSECRET BODY LINE about lighting.\n## Night portrait\n")

    def test_only_headings_are_returned_never_the_body(self):
        result = search("portrait", library=self.library)
        headings = [item["heading"] for item in result["results"] if item["file"].endswith("styles.md")]
        self.assertEqual(sorted(headings), ["Night portrait", "Portrait studio"])
        self.assertNotIn("SECRET", json.dumps(result))

    def test_every_word_must_match(self):
        result = search("night studio", library=self.library)
        self.assertFalse([item for item in result["results"] if item["file"].endswith("styles.md")])

    def test_a_missing_library_folder_falls_back_to_the_skill_references(self):
        result = search("gemini", library=os.path.join(self.library, "missing"))
        self.assertIn("does not exist", result["note"])
        self.assertTrue(result["results"])
        self.assertTrue(all(item["file"].startswith("references") for item in result["results"]))

    def test_no_library_means_only_the_skill_references(self):
        result = search("gemini")
        self.assertIn("No --library folder given", result["note"])

    def test_symbolic_links_are_not_followed(self):
        target = os.path.join(self.library, "outside.md")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("# Linked heading\n")
        link_dir = tempfile.TemporaryDirectory()
        self.addCleanup(link_dir.cleanup)
        os.symlink(target, os.path.join(link_dir.name, "link.md"))
        result = search("linked", library=link_dir.name)
        self.assertEqual(result["results"], [])

    def test_empty_query_returns_nothing(self):
        self.assertEqual(search("   ")["results"], [])


class CaseTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()

    def test_the_shipped_cases_are_valid(self):
        cases = load_cases()
        self.assertEqual(validate_cases(cases, self.catalog), [])
        self.assertTrue(all(case["kind"] in CASE_KINDS for case in cases))

    def test_a_broken_case_is_named_with_each_problem(self):
        base = load_cases()[0]
        broken = dict(base, id="broken", model="gemini-2.5-flash-image", prompt="")
        problems = validate_cases([broken], self.catalog)
        self.assertTrue(any("is not offered" in p for p in problems))
        bad_ratio = dict(base, id="bad-ratio", aspect_ratio="7:3")
        self.assertTrue(any("not a ratio" in p for p in validate_cases([bad_ratio], self.catalog)))
        bad_criteria = dict(base, id="bad-criteria", criteria=["beauty"])
        self.assertTrue(any("criteria" in p for p in validate_cases([bad_criteria], self.catalog)))
        bad_level = dict(base, id="bad-level", thinking_level="ultra")
        self.assertTrue(any("thinking level" in p for p in validate_cases([bad_level], self.catalog)))

    def test_malformed_values_are_reported_not_raised(self):
        base = load_cases()[0]
        problems = validate_cases([dict(base, id="str-criteria", criteria="fidelity"),
                                   dict(base, id="num-prompt", prompt=42)], self.catalog)
        self.assertTrue(any("str-criteria" in p and "criteria" in p for p in problems), problems)
        self.assertTrue(any("num-prompt" in p and "as text" in p for p in problems), problems)

    def test_an_unreadable_cases_file_is_a_named_error(self):
        from studio.core import StudioError
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "image_cases.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        with self.assertRaises(StudioError) as caught:
            load_cases(path)
        self.assertEqual(caught.exception.code, "cases_unreadable")

    def test_duplicate_ids_and_missing_fields_are_reported(self):
        base = load_cases()[0]
        problems = validate_cases([base, dict(base)], self.catalog)
        self.assertTrue(any("repeated" in p for p in problems))
        partial = {"id": "partial"}
        self.assertTrue(any("missing" in p for p in validate_cases([partial], self.catalog)))

    def test_an_error_level_prompt_finding_makes_the_case_invalid(self):
        # Whitespace passes the "no prompt" check but is an ERROR for the validator. (A key in a URL would be the
        # other ERROR, but the repository check forbids that string in any file, tests included.)
        base = load_cases()[0]
        problems = validate_cases([dict(base, id="blank", prompt="   ")], self.catalog)
        self.assertTrue(any("E-EMPTY" in p for p in problems), problems)


class CompareTests(unittest.TestCase):
    def run_record(self, run_id, **fields):
        base = {"run_id": run_id, "case_id": "scene-basic", "model": "gemini-nano-banana-2.1",
                "aspect_ratio": "1:1", "image_size": "1K", "thinking_level": None, "status": "generated",
                "checks": {"aspect_ratio_ok": True}, "evaluations": [], "provider": "gemini"}
        base.update(fields)
        return base

    def test_fake_runs_are_never_compared(self):
        runs = [self.run_record("run_a", provider="fake", evaluations=[{"rating": 5, "criteria": {}}])]
        self.assertEqual(compare_case(runs, "scene-basic")["variants"], [])

    def test_counts_and_means_per_variant_with_no_ranking(self):
        runs = [
            self.run_record("run_1", evaluations=[{"rating": 4, "criteria": {"fidelity": 5}}]),
            self.run_record("run_2", evaluations=[{"rating": 2, "criteria": {"fidelity": 3}}]),
            self.run_record("run_3", status="failed", checks=None),
            self.run_record("run_4", thinking_level="high", evaluations=[{"rating": 5, "criteria": {}}]),
        ]
        result = compare_case(runs, "scene-basic")
        self.assertEqual(len(result["variants"]), 2)
        default = next(v for v in result["variants"] if "thinking=default" in v["variant"])
        self.assertEqual((default["runs"], default["generated"], default["failed"]), (3, 2, 1))
        self.assertEqual(default["aspect_ratio_ok"], 2)
        self.assertEqual(default["rated"], 2)
        self.assertEqual(default["overall_mean"], 3.0)
        self.assertEqual(default["criteria_mean"], {"fidelity": 4.0})
        self.assertNotIn("winner", result)

    def test_an_edit_run_is_a_separate_variant(self):
        runs = [self.run_record("run_e", parent_run_id="run_p", evaluations=[{"rating": 3, "criteria": {}}])]
        variant = compare_case(runs, "scene-basic")["variants"][0]
        self.assertIn("| edit", variant["variant"])


if __name__ == "__main__":
    unittest.main()
