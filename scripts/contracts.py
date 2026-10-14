"""Contracts shared by the validator, the repo checker and the studio.

references/gemini-image-models.json is the only source of model IDs, aliases, statuses,
sizes, prices, aspect ratios and reference limits. Code reads it through this module
instead of keeping its own copy.
"""

import json
import math
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(ROOT, "references", "gemini-image-models.json")
# Image model IDs only: the catalog lists image models, so text models such as gemini-2.5-pro do not match.
MODEL_ID = re.compile(r"gemini-(?:nano-banana|\d[a-z0-9.\-]*-image)[a-z0-9.\-]*")
# Built from two parts so that this file does not contain the forbidden text itself.
KEY_IN_URL = re.compile(r"[?&]" + "key=")


def load_catalog(path=CATALOG_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def find_model(catalog, model_id):
    return next((m for m in catalog["models"] if m["id"] == model_id), None)


def model_ratios(catalog, model):
    """Aspect ratios that one model accepts. A model without its own list gets the catalog's union."""
    return model.get("aspect_ratios", catalog["aspect_ratios"])


def reference_total(model):
    """Most reference images that one request may carry for this model (0 when the model takes none)."""
    return model.get("reference_total_max") or 0


def _normalize(name):
    return re.sub(r"[\s\-]+", " ", name.strip()).lower()


def _name_pattern(name):
    # Spaces and hyphens match each other, so 'Nano-Banana 2' and 'Nano Banana 2' name the same model.
    return r"[\s\-]+".join(re.escape(part) for part in re.split(r"[\s\-]+", name.strip()))


def alias_table(catalog):
    """(name, model ID) pairs for every model ID and alias, longest name first.

    The longest name comes first so that 'Nano Banana 2 Lite' and 'Nano Banana 2.1' are never read as 'Nano Banana 2'.
    """
    pairs = []
    for model in catalog["models"]:
        for name in [model["id"], *model.get("aliases", [])]:
            pairs.append((name, model["id"]))
    return sorted(pairs, key=lambda pair: -len(pair[0]))


def model_ids_named(text, catalog):
    """Sorted model IDs that `text` names, by ID or by alias. A name does not match when a letter, a digit or '.<digit>' follows it."""
    table = alias_table(catalog)
    if not table:
        return []
    lookup = {_normalize(name): model_id for name, model_id in table}
    pattern = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(_name_pattern(name) for name, _ in table)
                         + r")(?![A-Za-z0-9]|\.\d)", re.IGNORECASE)
    return sorted({lookup[_normalize(m.group(1))] for m in pattern.finditer(text)})


def is_family_name(text, catalog):
    """True when the whole text is a family name listed in the catalog ('Nano Banana', 'Gemini Image').

    Anything after the name, such as a version or a product word, makes it a different request.
    """
    names = "|".join(_name_pattern(name) for name in catalog["bare_family_name"]["names"])
    return re.fullmatch(r"\s*(?:" + names + r")\s*", text, re.IGNORECASE) is not None


def resolve_target(target, catalog):
    """The model a target string means, or None. A family name means the default model of the family."""
    named = model_ids_named(target, catalog)
    if len(named) == 1:
        return find_model(catalog, named[0])
    if not named and is_family_name(target, catalog):
        return find_model(catalog, catalog["bare_family_name"]["default_model"])
    return None


def nearest_ratio(value, ratios):
    """Official ratio closest to `value` (width / height), measured on a log scale.

    Ties keep the catalog order, so the answer is the same on every run.
    `value` must be greater than zero.
    """
    def distance(ratio):
        width, height = ratio.split(":")
        return abs(math.log(int(width) / int(height)) - math.log(value))

    return min(ratios, key=distance)
