#!/usr/bin/env python3
"""Render one visual brief for an image target, keeping the prompt text apart from native settings.

    python3 scripts/image_prompt.py render --target midjourney --brief brief.json
    python3 scripts/image_prompt.py resolve "flux"

A brief is a JSON object (fields below). Each target gets the prompt form its own vendor documents, the native
parameters it accepts (only those in references/image-targets.json), and warnings for everything not verified.
Nothing here calls a network or a paid API. Gemini/Nano Banana is not rendered: it returns a redirect to Template N
and the Studio, so its path does not change.

Brief fields: subject, action, environment, composition, perspective, medium, lighting, color, materials,
aspect_ratio ("W:H", whole numbers, or "auto"), text ([{content, placement, typography, replaces}]),
constraints ([str]: "no watermark" style exclusions, or positive invariants), references ([{role, use}], role one of
style, subject, structure, background), edit ({change, preserve: [str]}), boxes ([{id, bbox: [top, left, bottom, right]
0-1000, desc}]; FLUX 3 only), options ({...}). A field a target does not send is named in a warning, not dropped.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `contracts` and `image_targets` import by name
from image_targets import load_registry, resolve, target  # noqa: E402

BRIEF_KEYS = {"subject", "action", "environment", "composition", "perspective", "medium", "lighting", "color",
              "materials", "aspect_ratio", "text", "constraints", "references", "edit", "boxes", "options"}
TEXT_KEYS = {"content", "placement", "typography", "replaces"}
NEGATION = re.compile(r"\b(no|not|without|don't|do not|never|avoid|nothing)\b", re.IGNORECASE)
LEADING_NEGATION = re.compile(r"^\s*(no|without|avoid|don't|do not)\s+(.+?)\s*$", re.IGNORECASE)
FLUX3_ASPECTS = ("21:9", "2:1", "16:9", "3:2", "7:5", "4:3", "5:4", "1:1", "4:5", "3:4", "5:7", "2:3", "9:16", "1:2", "9:21")
FLUX3_RESOLUTIONS = ("768sq", "1k", "1.5k", "2k", "4k")
GPT_QUALITIES = ("low", "medium", "high", "xhigh", "max", "auto")
GPT_BACKGROUNDS = ("transparent", "opaque", "auto")
GPT_FORMATS = ("png", "jpeg", "webp")
IDEOGRAM_QUALITIES = ("very_low", "low", "medium", "high")
IDEOGRAM_MAGIC = ("auto", "on", "off")
SEEDREAM_SIZES = ("1K", "1.5K", "2K")
SEEDREAM_FORMATS = ("png", "jpeg")
SEEDREAM_OPTIMIZE = ("standard", "fast")
SEEDREAM_SEQUENTIAL = ("disabled", "auto")
SEEDREAM_NO_FAST = ("seedream-5-0-flash", "seedream-5-0-lite", "seedream-4-5")
SEEDREAM_NO_SEQUENCE = ("seedream-5-0-pro", "seedream-5-0-flash")
GPT_MODELS = ("gpt-image-2.5-sunburst", "gpt-image-2.5-flare")
GPT_MODELS_OTHER_PAGES = ("gpt-image-2", "gpt-image-1.5")
REFERENCE_ROLES = ("style", "subject", "structure", "background")
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
VISUAL_FIELDS = ("subject", "action", "environment", "composition", "perspective", "medium", "lighting", "color",
                 "materials")
# Which brief fields each target's renderer actually sends. A field outside these sets is still used, if at all, as
# prompt text, and gets a warning saying so: nothing is dropped silently.
EDIT_TARGETS = {"midjourney", "gpt-image", "flux-3", "flux-kontext", "ideogram"}
REFERENCE_TARGETS = {"midjourney", "gpt-image", "flux-3", "firefly"}
BOX_TARGETS = {"flux-3"}
ASPECT_TARGETS = {"midjourney", "gpt-image", "flux-3", "flux-kontext"}

# Options each target accepts, from references/image-targets.json. Anything else gets a warning, not a silent drop.
OPTIONS = {
    "midjourney": {"raw"},
    "gpt-image": {"model", "quality", "background", "output_format"},
    "flux-3": {"resolution", "grounding", "safety_tolerance"},
    "flux-2": set(),
    "flux-kontext": set(),
    "ideogram": {"magic_prompt", "rendering_quality", "background", "num_images", "seed"},
    "recraft": {"style", "image_format"},
    "firefly": {"structure_strength"},
    "seedream": {"model", "size", "watermark", "output_format", "optimize_mode", "sequential"},
    "sd-3-5": set(),
    "sdxl": set(),
    "comfyui": {"checkpoint"},
}


class BriefError(ValueError):
    """The brief or an option is malformed, or a value is outside what the target documents."""


def _text(value, field):
    if value is None:
        return None
    if not isinstance(value, str):
        raise BriefError(f"{field} must be text")
    return value.strip() or None


def validate_brief(brief):
    """Check the brief's shape and return a cleaned copy. Unknown fields are refused, not ignored."""
    if not isinstance(brief, dict):
        raise BriefError("the brief must be a JSON object")
    unknown = sorted(set(brief) - BRIEF_KEYS)
    if unknown:
        raise BriefError("unknown brief fields: " + ", ".join(unknown))
    clean = {}
    for field in ("subject", "action", "environment", "composition", "perspective", "medium", "lighting", "color",
                  "materials", "aspect_ratio"):
        value = _text(brief.get(field), field)
        if value:
            clean[field] = value
    if "aspect_ratio" in clean and clean["aspect_ratio"] != "auto":
        ratio = re.fullmatch(r"(\d+):(\d+)", clean["aspect_ratio"])
        if not ratio or min(int(ratio.group(1)), int(ratio.group(2))) < 1:
            raise BriefError("aspect_ratio must be W:H with whole numbers above zero (for example 4:5), or auto; "
                             "decimals are refused")
    clean["text"] = []
    for entry in brief.get("text") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("content"), str) or not entry["content"].strip():
            raise BriefError("each text entry needs a non-empty content string")
        if set(entry) - TEXT_KEYS:
            raise BriefError("unknown text entry fields: " + ", ".join(sorted(set(entry) - TEXT_KEYS)))
        clean["text"].append({key: str(value).strip() for key, value in entry.items() if value})
    constraints = brief.get("constraints") or []
    if not isinstance(constraints, list) or not all(isinstance(item, str) and item.strip() for item in constraints):
        raise BriefError("constraints must be a list of non-empty strings")
    clean["constraints"] = [item.strip() for item in constraints]
    refs = brief.get("references") or []
    if not isinstance(refs, list) or not all(isinstance(item, dict) and isinstance(item.get("role"), str) for item in refs):
        raise BriefError("references must be a list of {role, use} objects")
    clean["references"] = [{"role": item["role"].strip(), "use": str(item.get("use", "")).strip()} for item in refs]
    for item in clean["references"]:
        if item["role"] not in REFERENCE_ROLES:
            raise BriefError("reference role must be one of " + ", ".join(REFERENCE_ROLES))
    edit = brief.get("edit")
    if edit is not None:
        if not isinstance(edit, dict) or not isinstance(edit.get("change"), str) or not edit["change"].strip():
            raise BriefError("edit needs a change: text")
        preserve = edit.get("preserve") or []
        if not isinstance(preserve, list) or not all(isinstance(item, str) for item in preserve):
            raise BriefError("edit.preserve must be a list of text")
        clean["edit"] = {"change": edit["change"].strip(), "preserve": [item.strip() for item in preserve]}
    clean["boxes"] = []
    for box in brief.get("boxes") or []:
        bbox = box.get("bbox") if isinstance(box, dict) else None
        if (not isinstance(box, dict) or not isinstance(box.get("id"), str) or not ID_PATTERN.fullmatch(box["id"])
                or not isinstance(box.get("desc"), str) or not isinstance(bbox, list) or len(bbox) != 4
                or not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 1000 for v in bbox)
                or bbox[0] > bbox[2] or bbox[1] > bbox[3]):
            raise BriefError("each box needs id, desc, and bbox = [top, left, bottom, right] integers 0-1000 "
                             "with top <= bottom and left <= right")
        clean["boxes"].append({"id": box["id"], "bbox": bbox, "desc": box["desc"]})
    options = brief.get("options") or {}
    if not isinstance(options, dict):
        raise BriefError("options must be an object")
    clean["options"] = options
    return clean


def _split_constraints(constraints):
    """Exclusions ('no watermark' -> 'watermark') and the rest (kept as positive text)."""
    negatives, positives = [], []
    for item in constraints:
        match = LEADING_NEGATION.match(item)
        (negatives if match else positives).append(match.group(2) if match else item)
    return negatives, positives


def _exclusions(negatives):
    """For targets with no negative field: the exclusions stay in the prompt as one sentence."""
    return ("No " + ", no ".join(negatives) + ".") if negatives else ""


def _sentence(text):
    """One sentence: capital first letter, full stop at the end."""
    text = text.strip()
    return text[:1].upper() + text[1:] + ("" if text.endswith(".") else ".")


def _add(prompt, sentence):
    """Append a sentence to a prompt. When the prompt is still empty the sentence stands alone, with no leading '. '."""
    sentence = sentence.strip().lstrip(". ")
    if not prompt:
        return sentence
    stripped = prompt.rstrip()
    return stripped + ("" if stripped.endswith(".") else ".") + " " + sentence


def _flag(options, key):
    """A true/false option. The string "false" is refused, not read as true."""
    value = options[key]
    if not isinstance(value, bool):
        raise BriefError(f"{key} is true or false")
    return value


def _has_negation(text):
    return bool(NEGATION.search(text or ""))


def _text_lines(text_items):
    lines = []
    for item in text_items:
        line = f'"{item["content"]}"'
        if item.get("placement"):
            line += f" {item['placement']}"
        if item.get("typography"):
            line += f", {item['typography']}"
        lines.append(line)
    return lines


def _subject(b):
    return " ".join(part for part in (b.get("subject"), b.get("action")) if part)


def _reference_phrase(index, ref):
    """'image 2 is the style: the palette'. The position is how a prompt names an input image."""
    return f"image {index} is the {ref['role']}" + (f": {ref['use']}" if ref["use"] else "")


def _edit_sentence(edit):
    sentence = _sentence(edit["change"])
    if edit["preserve"]:
        sentence += " Keep " + ", ".join(edit["preserve"]) + "."
    return sentence


def _check_options(b, item, out):
    allowed = OPTIONS.get(item["id"], set())
    for key in b["options"]:
        if key not in allowed:
            out["warnings"].append(f"option {key!r} is not documented for {item['name']}; it was not sent")


def _check_fields(b, item, out):
    """Brief fields this target's renderer does not send. Each becomes prompt text or a warning, never a silent drop."""
    name = item["name"]
    if b.get("edit") and item["id"] not in EDIT_TARGETS:
        out["prompt"] = (_edit_sentence(b["edit"]) + " " + out["prompt"]).strip()
        out["warnings"].append(f"no image-edit call is made for {name} here: the change is a sentence in the prompt, "
                               "and the image itself is not sent")
    if b["boxes"] and item["id"] not in BOX_TARGETS:
        out["warnings"].append(f"boxes are FLUX 3 only; they were not sent to {name}")
    if b["references"] and item["id"] not in REFERENCE_TARGETS:
        out["warnings"].append(f"references are not sent to {name}: attach them in the tool and name each one in the prompt")
    if b.get("aspect_ratio") not in (None, "auto") and item["id"] not in ASPECT_TARGETS:
        out["warnings"].append(f"aspect_ratio is not sent to {name}: set the size in the tool")


def _midjourney(b, out):
    parts = [_subject(b), b.get("environment"), b.get("medium"), b.get("lighting"), b.get("color"), b.get("materials"),
             b.get("composition"), b.get("perspective")]
    negatives, positives = _split_constraints(b["constraints"])
    prompt_parts = [p for p in parts if p] + positives
    text_lines = _text_lines(b["text"])
    if text_lines:
        prompt_parts.extend(text_lines)
    out["prompt"] = ", ".join(prompt_parts)
    params = []
    if "aspect_ratio" in b:
        params.append(f"--ar {b['aspect_ratio']}" if b["aspect_ratio"] != "auto" else "")
    if negatives:
        params.append("--no " + ", ".join(negatives))
        out["negative_prompt"] = ", ".join(negatives)
        out["negative_mechanism"] = "flag"
        out["limitations"].append("Midjourney reads each word after --no separately (the moderation system); "
                                  "name what you want instead of 'no' plus a word that could read badly alone")
    style_refs = [r for r in b["references"] if r["role"] == "style"]
    if style_refs:
        params.append("--sref <image URL or style code>")
    if b.get("edit") or [r for r in b["references"] if r["role"] != "style"]:
        params.append("--edit <image URLs, up to four>")
        if len([r for r in b["references"] if r["role"] != "style"]) > 4:
            raise BriefError("--edit takes up to four reference images")
        out["warnings"].append("attach each image to --edit by its public URL; Midjourney cannot take a file path")
    if "raw" in b["options"] and _flag(b["options"], "raw"):
        params.append("--raw")
    if b.get("edit"):
        out["prompt"] = (_edit_sentence(b["edit"]) + " " + out["prompt"]).strip()
    words = len(out["prompt"].split())
    if words > 40:
        out["warnings"].append(f"Midjourney's Prompt Basics say short and simple phrases work best and to avoid long lists; "
                               f"this prompt has {words} words (40 is this renderer's heuristic, not a vendor limit)")
    out["native_parameters"] = " ".join(p for p in params if p)
    out["paste"] = (out["prompt"] + " " + out["native_parameters"]).strip()
    out["limitations"].append("Parameters go at the end of the prompt, after a space, with no punctuation inside them.")


def _gpt_image(b, out):
    negatives, positives = _split_constraints(b["constraints"])
    sections = []
    style = [b.get("medium")]
    if any(style):
        sections.append("Style: " + "; ".join(p for p in style if p))
    scene = [b.get("environment"), b.get("perspective"), b.get("composition"), b.get("lighting"), b.get("color")]
    if any(scene):
        sections.append("Scene: " + "; ".join(p for p in scene if p))
    if _subject(b):
        sections.append("Subject: " + _subject(b) + (f" ({b['materials']})" if b.get("materials") else ""))
    if b["references"]:
        sections.append("Inputs: " + "; ".join(_reference_phrase(i, r) for i, r in enumerate(b["references"], 1)) + ".")
    if b["text"]:
        sections.append("Text: " + "; ".join(_text_lines(b["text"])))
    constraints = b["constraints"]
    if constraints:
        sections.append("Constraints: " + "; ".join(constraints) + ".")
    if b.get("edit"):
        sections.insert(0, "Change only: " + b["edit"]["change"].rstrip(".") + ".")
        keep = b["edit"]["preserve"]
        sections.append("Keep everything else the same" + (": " + ", ".join(keep) + "." if keep else "."))
    out["prompt"] = "\n".join(sections)
    options = b["options"]
    model = options.get("model", "gpt-image-2.5-sunburst")
    if model not in GPT_MODELS + GPT_MODELS_OTHER_PAGES:
        raise BriefError("gpt-image model must be one of " + ", ".join(GPT_MODELS + GPT_MODELS_OTHER_PAGES))
    if model in GPT_MODELS_OTHER_PAGES:
        out["warnings"].append(f"{model} appears on an OpenAI page other than the generation guide, which lists the 2.5 "
                               "models; confirm it is available to your account")
    quality = options.get("quality", "auto")
    if quality not in GPT_QUALITIES:
        raise BriefError("quality must be one of " + ", ".join(GPT_QUALITIES))
    if quality in ("xhigh", "max") and model not in GPT_MODELS:
        raise BriefError("quality xhigh and max exist only on gpt-image-2.5-sunburst and gpt-image-2.5-flare")
    background = options.get("background")
    if background is not None and background not in GPT_BACKGROUNDS:
        raise BriefError("background must be transparent, opaque or auto")
    output_format = options.get("output_format", "png")
    if output_format not in GPT_FORMATS:
        raise BriefError("output_format must be png, jpeg or webp")
    if background == "transparent" and output_format not in ("png", "webp"):
        raise BriefError("a transparent background needs output_format png or webp")
    size = {"1:1": "1024x1024", "3:2": "1536x1024", "2:3": "1024x1536"}.get(b.get("aspect_ratio", ""))
    if b.get("aspect_ratio") and size is None:
        out["warnings"].append("this ratio is not one of the recommended sizes; use a custom WIDTHxHEIGHT: multiples "
                               "of 16, aspect between 1:3 and 3:1, edges up to 3840, 655,360 to 8,294,400 pixels")
    out["native_settings"] = {"model": model, "endpoint": "images.edit" if b.get("edit") else "images.generate",
                              "size": size, "quality": quality, "output_format": output_format}
    if background:
        out["native_settings"]["background"] = background
    if negatives:
        out["limitations"].append("No negative field: the exclusions are sentences in the prompt, as the guide does.")
    out["limitations"].append("Text rendering and precise placement are listed as limitations by the vendor.")


def _flux3(b, out):
    negatives, positives = _split_constraints(b["constraints"])
    scene = ", ".join(p for p in (_subject(b), b.get("environment")) if p)
    sentences = [_sentence(p) for p in (b.get("medium"), scene, b.get("lighting"), b.get("color"), b.get("materials"),
                                        b.get("composition"), b.get("perspective"), *positives) if p]
    sentences += [_sentence(_reference_phrase(i, r)) for i, r in enumerate(b["references"], 1)]
    sentence = " ".join(sentences)
    if negatives:
        sentence += " " + _exclusions(negatives)
    for item in b["text"]:
        line = f'The text reads "{item["content"]}"'
        if item.get("placement"):
            line += f" {item['placement']}"
        if item.get("typography"):
            line += f", set in {item['typography']}"
        sentence += " " + line + "."
    for box in b["boxes"]:
        # The boxes page: the caption names each element with <id>, then a space, then the JSON array.
        sentence += " " + _sentence(f"Element <{box['id']}>: {box['desc']}")
    if b.get("edit"):
        sentence = _edit_sentence(b["edit"]) + " " + sentence
    out["prompt"] = sentence.strip()
    if negatives:
        out["warnings"].append("FLUX 3 Image has no negative field: the exclusions are written as a sentence; "
                               "a positive description of what should be there controls better")
    if b["boxes"]:
        rows = [{"id": box["id"], "bbox": box["bbox"], "desc": box["desc"]} for box in b["boxes"]]
        out["prompt"] = out["prompt"] + " " + json.dumps(rows)
    aspect = b.get("aspect_ratio")
    native = {}
    if aspect is not None:
        if aspect in FLUX3_ASPECTS:
            native["aspect_ratio"] = aspect
        else:
            native["aspect_ratio"] = "auto"
            out["warnings"].append(f"{aspect} is not in the FLUX 3 aspect_ratio list; auto was used")
    if b["references"] and len(b["references"]) > 10:
        raise BriefError("FLUX 3 Image takes at most 10 references")
    options = b["options"]
    if "resolution" in options:
        if options["resolution"] not in FLUX3_RESOLUTIONS:
            raise BriefError("resolution must be one of " + ", ".join(FLUX3_RESOLUTIONS))
        native["resolution"] = options["resolution"]
    if "grounding" in options:
        native["grounding"] = _flag(options, "grounding")
    if "safety_tolerance" in options:
        tolerance = options["safety_tolerance"]
        if not (isinstance(tolerance, int) and not isinstance(tolerance, bool) and 0 <= tolerance <= 4):
            raise BriefError("safety_tolerance is an integer from 0 (strictest) to 4")
        native["safety_tolerance"] = options["safety_tolerance"]
    out["native_settings"] = native
    out["limitations"].append("The endpoint rejects unknown fields with HTTP 422: seed, width and input_image from "
                              "other endpoints are not accepted here.")


def _flux2(b, out):
    parts = [_subject(b), b.get("medium"), b.get("environment"), b.get("lighting"), b.get("color"), b.get("materials"),
             b.get("composition"), b.get("perspective")]
    negatives, positives = _split_constraints(b["constraints"])
    out["prompt"] = ". ".join(p for p in [*parts, *positives] if p)
    out["prompt"] += "." if out["prompt"] else ""
    for item in _text_lines(b["text"]):
        out["prompt"] = _add(out["prompt"], "The text " + item + ".")
    if negatives:
        out["prompt"] = _add(out["prompt"], _exclusions(negatives))
        out["warnings"].append("FLUX.2 has no negative prompts: the exclusions are written as a sentence; a positive "
                               "description of the wanted state works better")
    words = len(out["prompt"].split())
    if words < 10:
        out["warnings"].append(f"{words} words: below the 10-word band for quick exploration; add detail for most projects")
    elif words > 80:
        out["warnings"].append(f"{words} words: the 80-plus band is for complex scenes; keep the length only if each added "
                               "detail is needed")
    out["warnings"].append("FLUX.2 API field names were not read; no native settings are emitted")


def _kontext(b, out):
    negatives, positives = _split_constraints(b["constraints"])
    sentences = []
    if b.get("edit"):
        sentences.append(_edit_sentence(b["edit"]))
        if any(b.get(field) for field in VISUAL_FIELDS):
            out["warnings"].append("for an edit only the change, what to keep and the text replacements are sent; "
                                   "the other visual fields were not used")
        out["warnings"].append("send the image to edit as input_image (base64 or URL, up to 20 MB or 20 megapixels)")
    else:
        parts = [_subject(b), b.get("environment"), b.get("medium"), b.get("lighting"), b.get("color"),
                 b.get("materials"), b.get("composition"), b.get("perspective")]
        if any(parts):
            sentences.append(". ".join(p for p in parts if p) + ".")
        out["warnings"].append("FLUX.1 Kontext is a previous-generation model here; FLUX.2 is recommended for generation")
        out["warnings"].append("this brief has no edit, and the Kontext endpoint edits an input image: nothing is sent as "
                               "input_image, so the endpoint cannot run from this prompt alone")
    sentences += [_sentence(p) for p in positives]
    for item in b["text"]:
        if item.get("replaces"):
            sentences.append(f"'{item['replaces']}' changed to '{item['content']}'.")
        else:
            sentences.append(_sentence(f"The text reads {_text_lines([item])[0]}"))
    for item in negatives:
        out["warnings"].append(f"Kontext has no negative field: describe the wanted result instead of 'no {item}'")
    out["prompt"] = " ".join(sentence.strip() for sentence in sentences if sentence.strip())
    native = {"endpoint": "/v1/flux-kontext-pro"}
    if b.get("aspect_ratio") not in (None, "auto"):
        width, height = (int(v) for v in b["aspect_ratio"].split(":"))
        if not (3 / 7 <= width / height <= 7 / 3):
            raise BriefError("Kontext aspect_ratio must be between 3:7 and 7:3")
        native["aspect_ratio"] = b["aspect_ratio"]
    out["native_settings"] = native


def _ideogram(b, out):
    negatives, positives = _split_constraints(b["constraints"])
    parts = [_subject(b), b.get("environment"), b.get("medium"), b.get("lighting"), b.get("color"), b.get("materials"),
             b.get("composition"), b.get("perspective"), *positives]
    prompt = ", ".join(p for p in parts if p)
    for item in _text_lines(b["text"]):
        prompt = _add(prompt, f"The text reads {item}")
    if b.get("edit"):
        prompt = _edit_sentence(b["edit"]) + (" " + prompt if prompt else "")
    if negatives:
        prompt = _add(prompt, _exclusions(negatives))
        out["warnings"].append("Ideogram has no negative field: the exclusions are written as a sentence; a positive "
                               "description of the wanted state works better")
    out["prompt"] = prompt
    if b["text"]:
        out["warnings"].append("quoted text follows the Image app docs (Ideogram 4.5 and 4.0); the API developer pages do "
                               "not state its rendering behaviour")
    if len(prompt) > 10000:
        out["warnings"].append(f"Ideogram accepts 1 to 10000 characters; this prompt has {len(prompt)}")
    options = b["options"]
    native = {}
    if b.get("edit"):
        native = {"endpoint": "/v2/image/precise-edit/ideogram-4-5", "context_window": "none"}
    else:
        native = {"endpoint": "/v2/image/generate/ideogram-4-5"}
    if "magic_prompt" in options:
        if options["magic_prompt"] not in IDEOGRAM_MAGIC:
            raise BriefError("magic_prompt must be auto, on or off")
        native["magic_prompt"] = options["magic_prompt"]
    quality = options.get("rendering_quality")
    if quality is not None and quality not in IDEOGRAM_QUALITIES:
        raise BriefError("rendering_quality must be very_low, low, medium or high")
    has_source = bool(b.get("edit") or b["references"])
    native["rendering_quality"] = quality or ("medium" if has_source else "high")
    if "background" in options:
        if options["background"] not in ("auto", "transparent", "opaque"):
            raise BriefError("background must be auto, transparent or opaque")
        native["background"] = options["background"]
    if "num_images" in options:
        count = options["num_images"]
        if not (isinstance(count, int) and not isinstance(count, bool) and count >= 1):
            raise BriefError("num_images is a whole number of at least 1")
        if count > 8:
            out["warnings"].append("the Image app allows 1 to 8 images per run; the API reference gives no upper limit")
        native["num_images"] = count
    if "seed" in options:
        seed = options["seed"]
        if not (isinstance(seed, int) and not isinstance(seed, bool) and seed >= 0):
            raise BriefError("seed is a whole number from 0 up")
        if seed > 2147483647:
            out["warnings"].append("the Image app's Seed field stops at 2147483647; the API range is not stated")
        native["seed"] = seed
    out["native_settings"] = native


def _recraft(b, out):
    negatives, positives = _split_constraints(b["constraints"])
    parts = [_subject(b), b.get("environment"), b.get("medium"), b.get("lighting"), b.get("color"), b.get("materials"),
             b.get("composition"), b.get("perspective"), *positives]
    out["prompt"] = ", ".join(p for p in parts if p)
    for line in _text_lines(b["text"]):
        out["prompt"] = _add(out["prompt"], "The text reads " + line)
    if negatives:
        out["prompt"] = _add(out["prompt"], _exclusions(negatives))
        out["negative_prompt"] = ", ".join(negatives)
        out["warnings"].append("Recraft V4.1 has no API negative field (negative_prompt is for V2 and V3 only): the "
                               "exclusions are a sentence in the prompt; in the Studio, paste the plain items into the "
                               "negative prompt field")
    for field in ("subject", "environment", "composition", "lighting", "color", "materials", "action"):
        if _has_negation(b.get(field)):
            out["warnings"].append(f"negation in {field}: the Studio page says 'no' can confuse the model; write the "
                                   "wanted state instead")
    if b["text"]:
        out["warnings"].append("text_layout exists for V3 models only; the Studio 'Avoid text in image' switch is the "
                               "UI control, and its API equivalent is not confirmed")
    native = {"model": "recraftv4_1"}
    if "image_format" in b["options"]:
        native["image_format"] = options_value(b, "image_format", None, ("webp", "png"))
    if "style" in b["options"]:
        out["warnings"].append("style is not sent: the V4.1 model page lists curated styles as not supported by V4.1 "
                               "(the endpoint reference says all models except V4.1 Flash); check the model before sending it")
    out["native_settings"] = native


def options_value(b, key, default, allowed):
    value = b["options"].get(key, default)
    if value not in allowed:
        raise BriefError(f"{key} must be one of " + ", ".join(allowed))
    return value


def _firefly(b, out):
    negatives, positives = _split_constraints(b["constraints"])
    parts = [_subject(b), b.get("environment"), b.get("medium"), b.get("lighting"), b.get("color"), *positives]
    out["prompt"] = ", ".join(p for p in parts if p)
    if negatives:
        out["prompt"] = _add(out["prompt"], _exclusions(negatives))
        out["warnings"].append("negativePrompt is reported in a secondary summary only, not in a page read; "
                               "the exclusions are written as a sentence and no negative field is sent")
    native = {}
    if any(r["role"] != "structure" for r in b["references"]):
        out["warnings"].append("only structure references are sent to Firefly here; the other references were not used")
    structure = [r for r in b["references"] if r["role"] == "structure"]
    if structure:
        strength = b["options"].get("structure_strength", 50)
        if not (isinstance(strength, int) and not isinstance(strength, bool) and 1 <= strength <= 100):
            raise BriefError("structure_strength is an integer from 1 to 100 (default 50)")
        native["structure"] = {"strength": strength, "imageReference": {"source": {"uploadId": "<upload id>"}}}
    out["native_settings"] = native


def _plain(b, out, note):
    """Portable prose for a target whose syntax is not verified: no parameter syntax, no weights, no invented fields."""
    negatives, positives = _split_constraints(b["constraints"])
    parts = [_subject(b), b.get("environment"), b.get("medium"), b.get("lighting"), b.get("color"), b.get("materials"),
             b.get("composition"), b.get("perspective"), *positives]
    out["prompt"] = ", ".join(p for p in parts if p)
    for item in _text_lines(b["text"]):
        out["prompt"] = _add(out["prompt"], f"The text reads {item}")
    if negatives:
        out["warnings"].append("no negative field is assumed for this target; the exclusions are written as a sentence: "
                               + _exclusions(negatives))
        out["prompt"] = _add(out["prompt"], _exclusions(negatives))
    out["native_settings"] = {}
    out["warnings"].append(note)


def _seedream(b, out):
    """Seedream: documented request fields only. A field is sent only when the brief sets it; no default is invented."""
    _plain(b, out, "Seedream: negative handling is not documented in the API reference read; nothing is sent for it")
    options = b["options"]
    native = {}
    model = options.get("model")
    if model is not None:
        if not isinstance(model, str) or not model.strip():
            raise BriefError("model must be the model ID text from your console")
        native["model"] = model.strip()
    else:
        out["warnings"].append("set options.model to the model ID from your console; the BytePlus examples use "
                               "dola-seedream-5-0-pro-260628")
    text_model = (model or "").lower()
    if "size" in options:
        size = options["size"]
        if size not in SEEDREAM_SIZES:
            exact = re.fullmatch(r"(\d+)x(\d+)", str(size))
            if not exact:
                raise BriefError("size is 1K, 1.5K or 2K (put the aspect ratio in the prompt), or an exact WIDTHxHEIGHT")
            width, height = int(exact.group(1)), int(exact.group(2))
            if not (921600 <= width * height <= 4624220) or not (width <= 16 * height and height <= 16 * width):
                raise BriefError("an exact Seedream size must have 921,600 to 4,624,220 pixels "
                                 "and an aspect ratio between 1:16 and 16:1")
        native["size"] = size
    if "watermark" in options:
        if not isinstance(options["watermark"], bool):
            raise BriefError("watermark is true or false")
        native["watermark"] = options["watermark"]
    else:
        out["warnings"].append("watermark is on by default (an AI-generated mark in the lower-right corner); set "
                               "options.watermark to false to turn it off")
    if "output_format" in options:
        if options["output_format"] not in SEEDREAM_FORMATS:
            raise BriefError("output_format is png or jpeg")
        native["output_format"] = options["output_format"]
    if "optimize_mode" in options:
        if options["optimize_mode"] not in SEEDREAM_OPTIMIZE:
            raise BriefError("optimize_mode is standard or fast")
        if options["optimize_mode"] == "fast" and any(name in text_model for name in SEEDREAM_NO_FAST):
            raise BriefError("fast prompt optimization is not supported on Seedream 5.0 flash, 5.0 lite or 4.5")
        native["optimize_prompt_options"] = {"mode": options["optimize_mode"]}
    if "sequential" in options:
        if options["sequential"] not in SEEDREAM_SEQUENTIAL:
            raise BriefError("sequential is disabled or auto")
        if options["sequential"] == "auto" and any(name in text_model for name in SEEDREAM_NO_SEQUENCE):
            raise BriefError("sequential image generation is not supported on Seedream 5.0 pro or flash")
        native["sequential_image_generation"] = options["sequential"]
    if len(b["references"]) > 14:
        raise BriefError("Seedream takes at most 14 reference images")
    if len(b["references"]) > 10 and any(name in text_model for name in SEEDREAM_NO_SEQUENCE):
        raise BriefError("Seedream 5.0 pro and flash take at most 10 reference images")
    out["native_settings"] = native


def _sd35(b, out):
    _plain(b, out, "SD 3.5 syntax, weights, CFG and negative handling are not verified; nothing is assumed")
    out["prompt"] = re.sub(r"\(([^()]*):\d[\d.]*\)", r"\1", out["prompt"])  # no weight syntax is emitted


def _sdxl(b, out):
    _plain(b, out, "SDXL syntax and settings were not verified; nothing is assumed")


def _comfy(b, out):
    negatives, positives = _split_constraints(b["constraints"])
    parts = [_subject(b), b.get("environment"), b.get("medium"), b.get("lighting"), b.get("color"), b.get("materials"),
             b.get("composition"), b.get("perspective"), *positives]
    positive = ", ".join(p for p in parts if p)
    for item in _text_lines(b["text"]):
        positive = _add(positive, f"The text reads {item}")
    # The negative block lists what to avoid, without 'no': the page says negative prompts are unwanted elements.
    negative = ", ".join(negatives)
    out["blocks"] = {"Positive Prompt": positive, "Negative Prompt": negative}
    out["prompt"] = positive
    out["negative_prompt"] = negative or None
    out["negative_mechanism"] = "field"
    out["native_settings"] = {"node_inputs": "Positive Prompt -> KSampler positive; Negative Prompt -> KSampler negative",
                              "cfg": "set on the sampler node; the value depends on the checkpoint and is not given here"}
    if not b["options"].get("checkpoint"):
        out["warnings"].append("name the checkpoint: the node values depend on the model file loaded")
    else:
        out["native_settings"]["checkpoint"] = b["options"]["checkpoint"]


RENDERERS = {"midjourney": _midjourney, "gpt-image": _gpt_image, "flux-3": _flux3, "flux-2": _flux2,
             "flux-kontext": _kontext, "ideogram": _ideogram, "recraft": _recraft, "firefly": _firefly,
             "seedream": _seedream, "sd-3-5": _sd35, "sdxl": _sdxl, "comfyui": _comfy}


def _empty(status, **extra):
    result = {"status": status, "target": None, "name": None, "verification": None,
              "negative_prompt": None, "negative_mechanism": None, "native_parameters": "", "native_settings": {},
              "paste": None, "warnings": [], "limitations": [], "sources": []}
    result.update(extra)
    return result


def render(brief, target_name, registry=None):
    """Render the brief for one target. Returns a dict; raises BriefError for a malformed brief or a refused value."""
    registry = registry or load_registry()
    found = resolve(target_name, registry)
    if found["status"] == "ambiguous":
        return _empty("ambiguous", candidates=found["candidates"], reason=found.get("reason"))
    if found["status"] == "unknown":
        cleaned = validate_brief(brief)
        result = _empty("unknown")
        note = ("No target was named; generic portable prompt" if not str(target_name or "").strip()
                else "Target is not in the registry; no syntax, parameter or negative field was assumed")
        _plain(cleaned, result, note)
        result["paste"] = result["prompt"]
        result["limitations"].append("Name a target from references/image-targets.json for target-specific form.")
        return result
    item = target(registry, found["target"])
    if item["route"] == "gemini":
        return _empty("redirect", target=item["id"], name=item["name"], verification=item["verification"],
                      use=("Use Template N (Nano Banana Brief) in references/templates.md for the prompt, and "
                           "references/gemini-image-models.md for IDs and limits. For generation with the paid API, use "
                           "the Studio: python3 -m studio (see studio/README.md)."),
                      sources=[source["url"] for source in item["sources"]])
    cleaned = validate_brief(brief)
    result = _empty("ok", target=item["id"], name=item["name"], verification=item["verification"],
                    sources=[source["url"] for source in item["sources"]])
    RENDERERS[item["id"]](cleaned, result)
    _check_fields(cleaned, item, result)
    result["paste"] = result["paste"] or result["prompt"]
    _check_options(cleaned, item, result)
    labels = {"prompt_style": "prompt form", "negative_prompt": "negative prompt", "text_in_image": "text in image",
              "references": "reference images", "edit": "editing"}
    for claim, label in labels.items():
        if item[claim]["status"] == "UNKNOWN":
            result["warnings"].append(f"not verified for {item['name']}: {label}")
    if result["negative_mechanism"] is None:
        result["negative_mechanism"] = item["negative_prompt"]["mechanism"]
    result["warnings"] = list(dict.fromkeys(result["warnings"]))
    result["limitations"] = list(dict.fromkeys(result["limitations"] + item["limitations"]))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render an image brief for one target, or resolve a target name.")
    commands = parser.add_subparsers(dest="command", required=True)
    rendering = commands.add_parser("render", help="render a brief (JSON file) for a target")
    rendering.add_argument("--target", required=True)
    rendering.add_argument("--brief", required=True, help="path to a JSON file with the brief")
    resolving = commands.add_parser("resolve", help="map a model or platform name to a target")
    resolving.add_argument("name")
    args = parser.parse_args(argv)
    try:
        if args.command == "resolve":
            result = resolve(args.name)
        else:
            with open(args.brief, encoding="utf-8") as handle:
                result = render(json.load(handle), args.target)
    except (BriefError, OSError, ValueError) as exc:  # ValueError covers malformed JSON in the brief file
        kind = "brief_refused" if isinstance(exc, BriefError) else "bad_input"
        print(json.dumps({"error": kind, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
