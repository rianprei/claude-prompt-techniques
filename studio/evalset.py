"""Fixed image cases, their validation, and the comparison of the runs made from them.

Cases live in evals/image_cases.json. A case is a request, not a result: running it plans a brief, and the paid
call happens only after an approval, like any other run. compare_case() groups the runs of one case by variant
(model, ratio, size, thinking level, and whether it was an edit) and reports counts and means. It names no winner:
with a few runs per variant, a difference is not evidence, and the ratings are a person's judgment.
"""

import json
import os

from validate_prompt import validate  # noqa: E402  (studio/__init__.py puts scripts/ on sys.path)
from .core import CASE_ID, CRITERIA, StudioError, offered_models

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_PATH = os.path.join(HERE, "evals", "image_cases.json")
CASE_KINDS = ("generate", "edit")
CASE_FIELDS = ("id", "kind", "title", "model", "aspect_ratio", "image_size", "references_needed", "criteria")


def load_cases(path=CASES_PATH):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)["cases"]
    except (OSError, ValueError, KeyError, TypeError):
        raise StudioError("cases_unreadable", f"{os.path.basename(path)} is missing, not JSON, or has no 'cases' list.", 500) from None


def find_case(cases, case_id):
    for case in cases:
        if case["id"] == case_id:
            return case
    return None


def validate_cases(cases, catalog):
    """Problems found in the case list, as readable strings. An empty list means the cases are usable."""
    problems = []
    offers = {offer["id"]: offer for offer in offered_models(catalog)}
    seen = set()
    for case in cases:
        label = str(case.get("id", "?"))
        missing = [field for field in CASE_FIELDS if field not in case]
        if missing:
            problems.append(f"{label}: missing {', '.join(missing)}")
            continue
        if not CASE_ID.fullmatch(case["id"]) or case["id"] in seen:
            problems.append(f"{label}: id is malformed or repeated")
        seen.add(case["id"])
        if case["kind"] not in CASE_KINDS:
            problems.append(f"{label}: kind must be generate or edit")
        if case["model"] not in offers:
            problems.append(f"{label}: model {case['model']!r} is not offered")
            continue
        offer = offers[case["model"]]
        if case["aspect_ratio"] not in offer["aspect_ratios"]:
            problems.append(f"{label}: {case['aspect_ratio']!r} is not a ratio of {case['model']}")
        if case["image_size"] not in offer["sizes"]:
            problems.append(f"{label}: {case['image_size']!r} is not a size of {case['model']}")
        level = case.get("thinking_level")
        if level is not None and level not in offer["thinking_levels"]:
            problems.append(f"{label}: thinking level {level!r} is not one of {case['model']}'s levels")
        if not isinstance(case["references_needed"], int) or case["references_needed"] < 0:
            problems.append(f"{label}: references_needed must be a whole number, 0 or more")
        criteria = case["criteria"]
        if not isinstance(criteria, list) or not criteria or any(name not in CRITERIA for name in criteria):
            problems.append(f"{label}: criteria must be a non-empty list of {', '.join(CRITERIA)}")
        if case["kind"] == "generate":
            text = case.get("prompt", "")
            if not isinstance(text, str) or not text:
                problems.append(f"{label}: a generate case needs a prompt, as text")
            else:
                findings = validate(text, case["model"], catalog)
                problems.extend(f"{label}: {f['code']}: {f['message']}" for f in findings if f["level"] == "ERROR")
        elif not case.get("edit"):
            problems.append(f"{label}: an edit case needs the edit text")
    return problems


def _mean(values):
    return round(sum(values) / len(values), 2) if values else None


def compare_case(runs, case_id):
    """Group the runs made from one case by variant, and report counts and means for each.

    `runs` is a list of run records (store.list_runs(limit=None)). The output has no ranking.
    """
    groups = {}
    for run in runs:
        if run.get("case_id") != case_id or run.get("provider") == "fake":  # placeholders are never compared
            continue
        kind = "edit" if run.get("parent_run_id") else "generate"
        thinking = run.get("thinking_level") or "default"
        key = f"{run['model']} | {run['aspect_ratio']} | {run['image_size']} | thinking={thinking} | {kind}"
        group = groups.setdefault(key, {"runs": 0, "generated": 0, "failed": 0, "aspect_ok": 0, "rated": 0,
                                        "overall": [], "criteria": {name: [] for name in CRITERIA}})
        group["runs"] += 1
        if run["status"] == "generated":
            group["generated"] += 1
            if (run.get("checks") or {}).get("aspect_ratio_ok") is True:
                group["aspect_ok"] += 1
        elif run["status"] == "failed":
            group["failed"] += 1
        if run["evaluations"]:
            group["rated"] += 1
            latest = run["evaluations"][-1]
            group["overall"].append(latest["rating"])
            for name, score in (latest.get("criteria") or {}).items():
                if name in group["criteria"]:
                    group["criteria"][name].append(score)
    variants = []
    for key in sorted(groups):
        group = groups[key]
        variants.append({
            "variant": key,
            "runs": group["runs"],
            "generated": group["generated"],
            "failed": group["failed"],
            "aspect_ratio_ok": group["aspect_ok"],
            "rated": group["rated"],
            "overall_mean": _mean(group["overall"]),
            "criteria_mean": {name: _mean(values) for name, values in group["criteria"].items() if values},
        })
    return {"case": case_id, "variants": variants,
            "note": "Means of the latest ratings only. No variant is ranked: check n before reading a difference."}
