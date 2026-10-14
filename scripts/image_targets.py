#!/usr/bin/env python3
"""Registry of image targets: load it, resolve names to a target, and check that its facts carry their status and source.

Stdlib only. The facts live in references/image-targets.json; nothing here calls a network or a paid API.
"""

import json
import os
import re

from contracts import ROOT

REGISTRY_PATH = os.path.join(ROOT, "references", "image-targets.json")
STATUSES = ("VERIFIED", "PARTIAL", "UNKNOWN")
MECHANISMS = ("flag", "field", "none", "ui-only", "unknown")
TARGET_KEYS = ("id", "name", "vendor", "route", "access", "aliases", "verification", "prompt_style",
               "negative_prompt", "text_in_image", "references", "edit", "native_settings", "limitations", "sources")
CLAIM_FIELDS = ("prompt_style", "negative_prompt", "text_in_image", "references", "edit")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize(name):
    """Lower case, with everything but letters and digits removed: 'SD 3.5' and 'sd3.5' are the same key."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def load_registry(path=REGISTRY_PATH):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def target(registry, target_id):
    for item in registry["targets"]:
        if item["id"] == target_id:
            return item
    raise KeyError(target_id)


def claims_of(item):
    """Every statement in a target that carries a status: the five fields and each native setting."""
    claims = []
    for field in CLAIM_FIELDS:
        value = item.get(field)
        if isinstance(value, dict):
            claims.append(dict(value, name=field))
    for setting in item.get("native_settings", []):
        claims.append(dict(setting, name=setting.get("name", "?")))
    return claims


def validate_registry(registry):
    """Problems in the registry, as strings. An empty list means every fact has a status, and every source is dated."""
    problems = []
    targets = registry.get("targets", [])
    ids = [item.get("id") for item in targets]
    if len(ids) != len(set(ids)):
        problems.append("target ids are not unique")
    alias_keys = {}
    for item in targets:
        label = item.get("id", "?")
        missing = [key for key in TARGET_KEYS if key not in item]
        if missing:
            problems.append(f"{label}: missing {', '.join(missing)}")
            continue
        if item["verification"] not in STATUSES:
            problems.append(f"{label}: verification must be one of {', '.join(STATUSES)}")
        urls = {source.get("url") for source in item["sources"]}
        for source in item["sources"]:
            if not str(source.get("url", "")).startswith("https://"):
                problems.append(f"{label}: source without an https URL")
            if not DATE.match(str(source.get("checked", ""))):
                problems.append(f"{label}: source {source.get('url')} has no check date (YYYY-MM-DD)")
        for claim in claims_of(item):
            name = claim.get("name")
            status = claim.get("status")
            if status not in STATUSES:
                problems.append(f"{label}: {name} has status {status!r}; use VERIFIED, PARTIAL or UNKNOWN")
            if status in ("VERIFIED", "PARTIAL") and not claim.get("source"):
                problems.append(f"{label}: {name} is {status} but names no source")
            if claim.get("source") and claim["source"] not in urls:
                problems.append(f"{label}: {name} cites {claim['source']}, which is not in its sources")
        neg = item["negative_prompt"]
        if neg.get("mechanism") not in MECHANISMS:
            problems.append(f"{label}: negative_prompt mechanism must be one of {', '.join(MECHANISMS)}")
        for alias in item["aliases"]:
            key = normalize(alias)
            if key in alias_keys:
                problems.append(f"{label}: alias {alias!r} repeats {alias_keys[key]!r} after normalization")
            alias_keys.setdefault(key, alias)
    return problems


def _alias_index(registry):
    index = {}
    for item in registry["targets"]:
        for alias in item["aliases"]:
            index.setdefault(normalize(alias), set()).add(item["id"])
    return index


def resolve(name, registry=None):
    """Map a user's name to one target.

    Returns {"status": "ok", "target": id}, {"status": "ambiguous", "candidates": [...]} when a bare family name
    could mean several targets (the caller should ask), or {"status": "unknown", "target": None}.
    """
    registry = registry or load_registry()
    key = normalize(name)
    if not key:
        return {"status": "unknown", "target": None, "reason": "empty name"}
    hits = _alias_index(registry).get(key)
    if not hits and key == "flux":
        candidates = sorted(item["id"] for item in registry["targets"]
                            if any("flux" in normalize(alias) for alias in item["aliases"]))
        return {"status": "ambiguous", "candidates": candidates, "reason": "name the FLUX version"}
    if not hits and key in ("sd", "stablediffusion"):
        return {"status": "ambiguous", "candidates": ["sd-3-5", "sdxl"], "reason": "name the version"}
    if not hits:
        return {"status": "unknown", "target": None}
    if len(hits) > 1:
        return {"status": "ambiguous", "candidates": sorted(hits)}
    return {"status": "ok", "target": next(iter(hits))}


MARKDOWN_PATH = os.path.join(ROOT, "references", "image-targets.md")
CLAIM_LABELS = {"prompt_style": "Prompt form", "negative_prompt": "Negative prompt", "text_in_image": "Text in image",
                "references": "Reference images", "edit": "Editing"}


def _cell(text):
    """One Markdown table cell: no line breaks, and pipes escaped."""
    return str(text if text not in (None, "") else "not stated").replace("|", "\\|").replace("\n", " ")


def render_markdown(registry):
    """The human-readable reference, generated from the registry. Same input, same text."""
    out = ["# Image targets: sources, status and native settings", "",
           "> Generated from `references/image-targets.json` by `python3 scripts/image_targets.py markdown`. "
           "Do not edit this file by hand; change the JSON and regenerate. Facts are as of "
           f"{registry['verified_on']}, from the pages named in each target's sources.", "",
           "**Status.** `VERIFIED`: read in a primary vendor page on the date shown. `PARTIAL`: from a secondary "
           "summary, a partly read page, or an older version of the page. `UNKNOWN`: not found in any page read; "
           "nothing is assumed.", "",
           "**Negative prompt mechanism.** `flag`: given as a parameter in the prompt text. `field`: a separate API "
           "or UI field. `none`: no negative field documented. `ui-only`: a negative field exists in the product, "
           "not in the API for that model. `unknown`: not documented in the pages read.", "",
           "## Index", "", "| Target | Vendor | Overall | Negative prompt | Route |", "|---|---|---|---|---|"]
    for item in registry["targets"]:
        out.append(f"| [{_cell(item['name'])}](#{_anchor(item['name'])}) | {_cell(item['vendor'])} | "
                   f"{item['verification']} | {item['negative_prompt']['mechanism']} | {item['route']} |")
    for item in registry["targets"]:
        out += ["", f"## {item['name']}", "", f"- **id:** `{item['id']}`",
                f"- **Vendor:** {item['vendor']}",
                f"- **Access:** API: {item['access'].get('api') or 'not stated'}; UI: {item['access'].get('ui') or 'not stated'}",
                f"- **Overall status:** {item['verification']}",
                f"- **Aliases:** " + ", ".join(f"`{alias}`" for alias in item["aliases"]), "",
                "| Topic | Status | Fact | Source |", "|---|---|---|---|"]
        for field, label in CLAIM_LABELS.items():
            claim = item[field]
            source = f"[link]({claim['source']})" if claim.get("source") else "none"
            out.append(f"| {label} | {claim['status']} | {_cell(claim['text'])} | {source} |")
        if item["native_settings"]:
            out += ["", "| Native setting | Values | Status | Source |", "|---|---|---|---|"]
            for setting in item["native_settings"]:
                source = f"[link]({setting['source']})" if setting.get("source") else "none"
                out.append(f"| `{_cell(setting['name'])}` | {_cell(setting['values'])} | {setting['status']} | {source} |")
        if item["limitations"]:
            out += ["", "**Limitations**", ""] + [f"- {_cell(text)}" for text in item["limitations"]]
        out += ["", "**Sources**", ""]
        for source in item["sources"]:
            out.append(f"- [{_cell(source['title'])}]({source['url']}), checked {source['checked']} ({source['kind']})")
    return "\n".join(out) + "\n"


def _anchor(title):
    """GitHub-style heading anchor: lower case, spaces to hyphens, most punctuation removed."""
    return re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")


def main(argv=None):
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    registry = load_registry()
    if args[:1] == ["markdown"]:
        sys.stdout.write(render_markdown(registry))
        return 0
    if args[:1] == ["check"]:
        problems = validate_registry(registry)
        for problem in problems:
            print(problem)
        return 1 if problems else 0
    print("usage: image_targets.py markdown | check")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
