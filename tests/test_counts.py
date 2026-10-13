"""Numbers that the docs state must match the data they describe.

Each count is computed here from its source and compared with every place that states it,
so a changed row, golden case or taxonomy name fails a test instead of drifting silently.
"""

import glob
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "references", "technique-catalog.md")
TAXONOMY = os.path.join(ROOT, "references", "taxonomy.md")
GOLDEN = os.path.join(ROOT, "evals", "golden_cases.json")
CATEGORY_LINE = re.compile(r"^\*\*([^*]+)\*\*(?: \([^)]*\))?: (.*)$")
STATUSES = ("VERIFIED", "NOT VERIFIED")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def taxonomy_names():
    """Names on the category lines of taxonomy.md, split on '; '. The White et al. block is not a category."""
    names, categories = [], 0
    for line in read(TAXONOMY).splitlines():
        match = CATEGORY_LINE.match(line.strip())
        if match is None or match.group(1).startswith("White"):
            continue
        categories += 1
        names += [name.strip().rstrip(".") for name in match.group(2).split("; ") if name.strip()]
    return names, categories


def catalog_rows():
    """(heading, cells) for each catalog row whose status cell is VERIFIED or NOT VERIFIED."""
    heading, rows = "", []
    for line in read(CATALOG).splitlines():
        if line.startswith(("## ", "### ")):
            heading = line
        if not line.startswith("| ") or "---" in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 7 and cells[4] in STATUSES:
            rows.append((heading, cells))
    return rows


def section_six_counts():
    """The Metric | Count table at the end of the catalog, as a dict."""
    tail = read(CATALOG).split("## 6. Counts", 1)[1]
    return {m.group(1).strip(): int(m.group(2))
            for m in re.finditer(r"^\| ([^|\n]+?) \| (\d+) \|$", tail, re.MULTILINE)}


class CatalogCountTests(unittest.TestCase):
    def test_section_six_matches_the_rows(self):
        rows = [cells for _, cells in catalog_rows()]
        expected = {
            "Total rows": len(rows),
            "VERIFIED": sum(c[4] == "VERIFIED" for c in rows),
            "NOT VERIFIED": sum(c[4] == "NOT VERIFIED" for c in rows),
            "NEW": sum(c[5] == "NEW" for c in rows),
            "ALREADY-IN": sum(c[5] == "ALREADY-IN" for c in rows),
            "PROMPT": sum(c[6] == "PROMPT" for c in rows),
            "VENDOR": sum(c[6] == "VENDOR" for c in rows),
            "TRAINING-TIME": sum(c[6] == "TRAINING-TIME" for c in rows),
        }
        self.assertEqual(section_six_counts(), expected)

    def test_taxonomy_lists_each_verified_row_outside_white_once(self):
        names, _ = taxonomy_names()
        verified = [cells for heading, cells in catalog_rows()
                    if "White" not in heading and cells[4] == "VERIFIED"]
        self.assertEqual(len(names), len(verified))
        self.assertEqual(len(set(names)), len(names), "a taxonomy name is listed twice")


class StatedCountTests(unittest.TestCase):
    def test_golden_case_count_is_stated_correctly(self):
        count = len(json.loads(read(GOLDEN)))
        stated = []
        for relative in ("README.md", os.path.join("evals", "protocol.md")):
            text = read(os.path.join(ROOT, relative))
            stated += re.findall(r"(\d+) (?:casos fixos|prompts fixos|golden cases)", text)
        self.assertTrue(stated, "no statement of the golden case count was found")
        self.assertEqual({int(n) for n in stated}, {count})

    def test_taxonomy_size_is_stated_correctly(self):
        names, categories = taxonomy_names()
        stated = []
        for path in glob.glob(os.path.join(ROOT, "**", "*.md"), recursive=True):
            stated += re.findall(r"(\d+) nomes em (\d+) categorias", read(path))
        self.assertTrue(stated, "no statement of the taxonomy size was found")
        self.assertEqual({(int(n), int(c)) for n, c in stated}, {(len(names), categories)})


if __name__ == "__main__":
    unittest.main()
