"""Search prompt style names and example headings: this skill's references, and optionally a local folder.

Only headings (lines that start with '#') are read. Each result gives the file, the line and the heading, and no
body text is returned or copied. The YouMind-OpenLab prompt library has no licence file, so nothing here downloads
it. A person can point --library at a local copy they already have; without that, the search covers only the
references in this skill. Stdlib only, no network.
"""

import os

from contracts import ROOT

REFERENCE_DIR = os.path.join(ROOT, "references")
MAX_FILES = 2000  # local cap: a folder with more Markdown files than this is searched only up to the cap
MAX_FILE_BYTES = 1024 * 1024  # local cap per file
MAX_RESULTS = 50


def _markdown_files(root):
    found = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            if not name.endswith(".md") or os.path.islink(path):
                continue
            if os.path.getsize(path) > MAX_FILE_BYTES:
                continue
            yield path
            found += 1
            if found >= MAX_FILES:
                return


def search(query, library=None):
    """Headings that contain every word of the query, case-insensitively. Returns at most MAX_RESULTS hits."""
    words = [word for word in (query or "").lower().split() if word]
    if not words:
        return {"query": query, "results": [], "note": "Give at least one word."}
    roots = [REFERENCE_DIR]
    notes = []
    if library:
        if os.path.isdir(library):
            roots.append(library)
        else:
            notes.append("The library folder does not exist; only the skill's own references were searched.")
    else:
        notes.append("No --library folder given; only the skill's own references were searched.")
    results = []
    for root in roots:
        for path in _markdown_files(root):
            with open(path, encoding="utf-8", errors="replace") as handle:
                for number, line in enumerate(handle, start=1):
                    if not line.startswith("#"):
                        continue
                    heading = line.strip("# \n")
                    if all(word in heading.lower() for word in words):
                        shown = os.path.relpath(path, ROOT) if path.startswith(ROOT + os.sep) else path
                        results.append({"file": shown, "line": number, "heading": heading})
                        if len(results) >= MAX_RESULTS:
                            return {"query": query, "results": results, "note": " ".join(notes)}
    return {"query": query, "results": results, "note": " ".join(notes)}
