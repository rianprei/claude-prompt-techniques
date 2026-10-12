"""Contracts shared by the validator, the repo checker and the studio.

references/gemini-image-models.json is the only source of model IDs, statuses,
sizes, prices and aspect ratios. Code reads it through this module instead of
keeping its own copy.
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


def nearest_ratio(value, ratios):
    """Official ratio closest to `value` (width / height), measured on a log scale.

    Ties keep the catalog order, so the answer is the same on every run.
    `value` must be greater than zero.
    """
    def distance(ratio):
        width, height = ratio.split(":")
        return abs(math.log(int(width) / int(height)) - math.log(value))

    return min(ratios, key=distance)
