#!/usr/bin/env python3
"""Checks for the repo files (tracked and new, not ignored): markdown links and anchors, formatting, numbering,
and the image-model contract (model IDs against the catalog, no key in a URL).

Usage: python3 scripts/check_repo.py
Exit status: 0 when clean, 1 when a problem is found.
"""

import json
import os
import re
import subprocess
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK = re.compile(r"\]\(([^)\s]+)\)")
MARKER = re.compile(r"\b(TODO|FIXME|XXX|TBD)\b")
TEMPLATES = "ABCDEFGHIJKLM"
CATALOG = "references/gemini-image-models.json"
CATALOG_PREFIX = "references/gemini-image-models."
STALE_DAYS = 90  # the catalog is a snapshot; past this age, the script only warns
MODEL_ID = re.compile(r"gemini-(?:nano-banana|\d)[a-z0-9.\-]*")
# Built from two parts so that this file does not contain the forbidden text itself.
KEY_IN_URL = re.compile(r"[?&]" + "key=")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def read_text(rel):
    """Text of a tracked file, or None when the file is not UTF-8 text."""
    try:
        return read(rel)
    except UnicodeDecodeError:
        return None


def repo_files():
    """Tracked files plus new files that git does not ignore, so new files are checked before commit.

    A file deleted from disk but still in the index is left out instead of crashing the run.
    """
    out = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, text=True
    )
    return sorted(f for f in set(out.split()) if os.path.exists(os.path.join(ROOT, f)))


def slugify(text):
    return re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")


def anchors(text):
    out, seen, fence = set(), {}, False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            base = slugify(m.group(2))
            n = seen.get(base, 0)
            out.add(base if n == 0 else f"{base}-{n}")
            seen[base] = n + 1
    return out


def check_markdown(path, text, anchor_cache):
    problems = []
    lines = text.split("\n")
    fences = sum(1 for ln in lines if ln.lstrip().startswith("```"))
    if fences % 2:
        problems.append(f"{path}: unbalanced code fences ({fences})")
    if not text.endswith("\n"):
        problems.append(f"{path}: missing final newline")
    for i, ln in enumerate(lines, 1):
        if re.search(r"[ \t]+$", ln):
            problems.append(f"{path}:{i}: trailing whitespace")
        if "\t" in ln:
            problems.append(f"{path}:{i}: tab")
        if "\r" in ln:
            problems.append(f"{path}:{i}: CR")
        if MARKER.search(ln):
            problems.append(f"{path}:{i}: marker: {ln.strip()[:70]}")
    for m in LINK.finditer(text):
        target = m.group(1)
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        rel, _, anchor = target.partition("#")
        dest = path if rel == "" else os.path.normpath(os.path.join(os.path.dirname(path), rel))
        if rel and not os.path.exists(os.path.join(ROOT, dest)):
            problems.append(f"{path}: broken link -> {target}")
            continue
        if anchor and dest.endswith(".md"):
            if dest not in anchor_cache:
                anchor_cache[dest] = anchors(read(dest))
            if anchor not in anchor_cache[dest]:
                problems.append(f"{path}: missing anchor -> {target}")
    return problems


def check_numbering():
    problems = []
    nums = [int(n) for n in re.findall(r"^\| (\d+) \|", read("references/patterns.md"), re.M)]
    if nums != list(range(1, len(nums) + 1)):
        problems.append("references/patterns.md: pattern numbers are not sequential")
    tpl = "".join(re.findall(r"^## Template ([A-Z]) —", read("references/templates.md"), re.M))
    if tpl != TEMPLATES:
        problems.append(f"references/templates.md: templates are {tpl!r}, expected {TEMPLATES!r}")
    return problems, len(nums), len(tpl)


def check_model_ids(texts, catalog):
    """A model ID must be in the catalog; a shut-down ID may appear only inside the catalog.

    Test files are skipped: their fixtures use example IDs on purpose.
    """
    status = {m["id"]: m["status"] for m in catalog["models"]}
    problems = []
    for path, text in texts.items():
        if path.startswith(CATALOG_PREFIX) or path.startswith("tests/"):
            continue
        for i, ln in enumerate(text.split("\n"), 1):
            for m in MODEL_ID.finditer(ln):
                model_id = m.group(0).rstrip(".")
                if model_id not in status:
                    problems.append(f"{path}:{i}: model id not in {CATALOG}: {model_id}")
                elif status[model_id] == "shut_down":
                    problems.append(f"{path}:{i}: shut-down model id outside {CATALOG}: {model_id}")
    return problems


def check_key_in_url(texts):
    """The API key goes in the x-goog-api-key header, never in a URL query string."""
    problems = []
    for path, text in texts.items():
        for i, ln in enumerate(text.split("\n"), 1):
            if KEY_IN_URL.search(ln):
                problems.append(f"{path}:{i}: key in a URL query string; use the x-goog-api-key header")
    return problems


def main():
    files = repo_files()
    problems = []
    anchor_cache = {}
    texts = {}
    for f in files:
        text = read_text(f)
        if text is None:
            continue
        texts[f] = text
        if f.endswith(".md"):
            problems += check_markdown(f, text, anchor_cache)
    numbering, patterns, templates = check_numbering()
    problems += numbering
    try:
        catalog = json.loads(texts[CATALOG])
    except (KeyError, json.JSONDecodeError):
        catalog = None
        problems.append(f"{CATALOG}: missing or not valid JSON")
    if catalog is not None:
        problems += check_model_ids(texts, catalog)
        age = (date.today() - date.fromisoformat(catalog["verified_on"])).days
        if age > STALE_DAYS:
            print(f"warning: {CATALOG} was verified {age} days ago; re-check the official pages")
    problems += check_key_in_url(texts)
    print(f"markdown files: {sum(f.endswith('.md') for f in files)}")
    print(f"patterns: {patterns}, templates: {templates}")
    for p in problems:
        print(f"  {p}")
    print(f"problems: {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
