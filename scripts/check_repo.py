#!/usr/bin/env python3
"""Checks for the tracked files: markdown links and anchors, formatting, numbering.

Usage: python3 scripts/check_repo.py
Exit status: 0 when clean, 1 when a problem is found.
"""

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK = re.compile(r"\]\(([^)\s]+)\)")
MARKER = re.compile(r"\b(TODO|FIXME|XXX|TBD)\b")
TEMPLATES = "ABCDEFGHIJKLM"


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def tracked_files():
    out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return out.split()


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


def main():
    files = tracked_files()
    problems = []
    anchor_cache = {}
    for f in files:
        if f.endswith(".md"):
            problems += check_markdown(f, read(f), anchor_cache)
    numbering, patterns, templates = check_numbering()
    problems += numbering
    print(f"tracked markdown files: {sum(f.endswith('.md') for f in files)}")
    print(f"patterns: {patterns}, templates: {templates}")
    for p in problems:
        print(f"  {p}")
    print(f"problems: {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
