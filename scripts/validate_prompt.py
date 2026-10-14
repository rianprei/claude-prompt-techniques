#!/usr/bin/env python3
"""Static checks for a generated prompt, using this skill's own rules.

The checks read the text only. They cannot tell whether a prompt produces a
good answer; that is measured by hand with evals/protocol.md.

Usage:
    python3 scripts/validate_prompt.py [--target MODEL] [--strict] [--json] [PATH]

PATH is a file, or "-" (the default) to read stdin.
Exit status: 0 when nothing blocks, 1 when a finding blocks, 2 on a read error.
Most signals are in English; a few Portuguese forms are included.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contracts import (KEY_IN_URL, MODEL_ID, find_model, load_catalog,  # noqa: E402
                       model_ids_named, model_ratios, nearest_ratio, resolve_target)

# Models that always reason internally (references/tool-routing.md).
REASONING_NATIVE = ("o3", "o4-mini", "deepseek-r1", "gpt-6", "fable-5", "mythos-5", "opus-5-5")
VENDOR_PREFIX = re.compile(r"^(?:claude|anthropic|openai|google|xai)-")
CLAUDE_5 = re.compile(r"claude-(fable|mythos|opus|sonnet|haiku)-5")
# Image models only: Gemini image IDs and the Nano Banana names. Text models such as gemini-2.5-pro do not match.
IMAGE_TARGET = re.compile(r"gemini-.*-image|nano[- ]?banana")

COT_PHRASE = re.compile(
    r"\b(step[- ]by[- ]step|passo a passo|chain[- ]of[- ]thought|cadeia de pensamento"
    r"|show(?:ing)? (?:your|the) (?:reasoning|work)|(?:reason|think)(?:ing)? (?:it )?through)\b",
    re.IGNORECASE,
)
# Words that negate what follows them in the same clause. English verbs that mean
# "do not do X" (skip, omit, avoid...) count as negations too.
NEGATOR = re.compile(
    r"\b(?:\w+n['’]t|not|no|never|neither|nor|none|nothing|without|cannot"
    r"|avoid(?:s|ed|ing)?|skip(?:s|ped|ping)?|omit(?:s|ted|ting)?|forget(?:s|ting)?|forgot|forgotten"
    r"|stop(?:s|ped|ping)?|drop(?:s|ped|ping)?|ignore(?:s|d)?|ignoring|bypass(?:es|ed|ing)?"
    r"|neglect(?:s|ed|ing)?|refrain(?:s|ed|ing)?"
    r"|não|nunca|sem|nem|evite|evitar|pule|pular|omita|omitir|esqueça|esquecer)\b",
    re.IGNORECASE,
)
# A negation reaches only to the end of its clause, so these punctuation marks and
# conjunctions end its reach.
CLAUSE_BREAK = re.compile(r"[,;:()–—]|\b(?:but|and|or|mas|e|ou)\b", re.IGNORECASE)
THINKING_TAG = re.compile(r"<\s*thinking\s*>|\bthinking tags?\b", re.IGNORECASE)
CAPS_DIRECTIVE = re.compile(r"\b(MUST|NEVER|ALWAYS|CRITICAL|MANDATORY|REQUIRED|DO NOT)\b")
FORMAT_SIGNAL = re.compile(
    r"\b(return|respond|output|answer|format|json|markdown|table|list|schema|xml|yaml|csv"
    r"|bullets?|retorne|responda|formato|lista|tabela|saída)\b",
    re.IGNORECASE,
)
AGENT_SIGNAL = re.compile(
    r"\b(tools?|run|execute|commit|edit|refactor|deploy|install|shell|terminal|agents?|loop|iterate)\b",
    re.IGNORECASE,
)
STOP_SIGNAL = re.compile(
    r"\b(stop|done when|until|at most|max(imum)?|limit|retry|retries|escalate|ask before"
    r"|approval|confirm|halt|abort)\b",
    re.IGNORECASE,
)
VAGUE = re.compile(
    r"\b(whatever is needed|whatever it takes|as needed|if necessary|and so on|etc)\b",
    re.IGNORECASE,
)
# An aspect ratio written after its keyword ("aspect ratio 16:9") or before it ("16:9 aspect ratio").
ASPECT_AFTER_KEYWORD = re.compile(
    r"(?:aspect ratio|aspect|ratio|proporção|proporcao|--ar)\b[^\n\d]{0,20}?"
    r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
ASPECT_BEFORE_KEYWORD = re.compile(
    r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*(?:aspect ratio|ratio|proporção|proporcao)\b",
    re.IGNORECASE,
)
# Image checks, run only for image targets. They read the text and flag it for review; they never judge the picture.
NEGATIVE_LIST_MIN = 4  # negations in one image prompt before the prompt is flagged
EDIT_VERB = re.compile(
    r"\b(change|modify|remove|replace|edit|alter|adjust|swap|erase|add|recolou?r|transform|troque|troca|altere"
    r"|modifique|remova|substitua|edite|adicione|apague|ajuste|mude|transforme)\b",
    re.IGNORECASE,
)
EXISTING_IMAGE = re.compile(
    r"\b(provided|attached|uploaded|original|reference|this|first|second|third|previous|generated"
    r"|anexad[oa]s?|enviad[oa]s?|esta|este|primeir[oa]|segund[oa]|terceir[oa]|anterior|gerad[oa]s?)\b",
    re.IGNORECASE,
)
IMAGE_NOUN = re.compile(r"\b(image|photo|picture|photograph|imagem|foto|figura|referência)s?\b", re.IGNORECASE)
PRESERVE = re.compile(
    r"\b(keep|kept|preserv\w*|unchanged|exactly the same|remain\w*|stay\w* the same|maintain\w*|everything else"
    r"|nothing else|mantenh\w*|inalterad\w*|exatamente igual|permanec\w*|sem alterar|continu\w* igual|tudo o resto)\b",
    re.IGNORECASE,
)
REF_ORDINAL = re.compile(
    r"\b(?:(?:image|photo|picture|imagem|foto|reference|referência)\s*#?\s*([123])"
    r"|(first|second|third|primeir[oa]|segund[oa]|terceir[oa])\s+(?:image|photo|picture|imagem|foto|reference|referência))\b",
    re.IGNORECASE,
)
ORDINAL_VALUE = {"first": 1, "second": 2, "third": 3, "primeiro": 1, "primeira": 1,
                 "segundo": 2, "segunda": 2, "terceiro": 3, "terceira": 3}
ROLE_WORD = re.compile(
    r"\b(identity|identidade|face|rosto|character|personagem|product|produto|style|estilo|composition|composição"
    r"|layout|palette|paleta|colou?r|cor|background|fundo|lighting|iluminação|texture|textura|logo|pose|outfit|roupa)\b",
    re.IGNORECASE,
)
# Words that ask for text to be drawn. Layout nouns such as 'title' or 'caption' are left out: "space for the title" asks for no text.
TEXT_CUE = re.compile(
    r"\b(text|texto|words?|palavras?|says|reads|diz|lê-se|escrit[oa]|lettering|letras)\b",
    re.IGNORECASE,
)
NO_TEXT = re.compile(
    r"\b(no text|without text|no words|no lettering|no labels?|sem texto|sem palavras|sem letras|sem rótulos"
    r"|sem legenda)\b",
    re.IGNORECASE,
)
QUOTE = re.compile(r"[\"'“”‘’«»]")


def finding(level, code, message):
    return {"level": level, "code": code, "message": message}


def split_sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def requests_cot(sentence):
    """True when the sentence asks for step-by-step reasoning, False when it forbids it.

    Only the clause before the phrase is read. Each negator in that clause counts,
    and an even count cancels out: "Don't skip the step-by-step check" has two
    (don't, skip), so it asks for reasoning. A negation placed after the phrase is
    not read.
    """
    match = COT_PHRASE.search(sentence)
    if match is None:
        return False
    clause = CLAUSE_BREAK.split(sentence[: match.start()])[-1]
    return len(NEGATOR.findall(clause)) % 2 == 0


# A target counts when one of these families starts its model name and is followed by "-", "." or ":" (version,
# size or Ollama tag). A substring test would also match names such as "my-gpt-6-wrapper" or "gpt-60".
def reasoning_native(target):
    # Gateways write "provider/model" and "provider/vendor/model", so the model is the part after the last slash.
    model = target.rsplit("/", 1)[-1]
    # "deepseek-r1" is itself a family name, so the model is also tried without a vendor prefix such as "claude-".
    names = (model, VENDOR_PREFIX.sub("", model, count=1))
    return any(name == key or any(name.startswith(key + sep) for sep in "-.:")
               for name in names for key in REASONING_NATIVE)


def check_cot(sentences, target):
    if not reasoning_native(target):
        return []
    if any(requests_cot(s) for s in sentences):
        return [finding("ERROR", "E-COT-REASONING",
                        f"asks for step-by-step reasoning on {target}, which reasons "
                        "internally (tool-routing.md)")]
    return []


def check_thinking_tag(text, target):
    if CLAUDE_5.search(target) and THINKING_TAG.search(text):
        return [finding("ERROR", "E-THINKING-TAG",
                        "asks for visible thinking tags on a Claude 5.x model; "
                        "the request can be refused (tool-routing.md)")]
    return []


def check_prefill(text):
    if re.search(r"\bprefill", text, re.IGNORECASE):
        return [finding("WARN", "W-PREFILL",
                        "prefill is API-only and returns 400 on Claude 4.6+; "
                        "use Structured Outputs or a direct format instruction")]
    return []


def check_caps(text):
    hits = CAPS_DIRECTIVE.findall(text)
    if len(hits) >= 3:
        return [finding("WARN", "W-CAPS",
                        f"{len(hits)} stacked CAPS directives; recent Claude models can "
                        "overtrigger (references/persuasion.md)")]
    return []


def check_format(text):
    if FORMAT_SIGNAL.search(text) is None:
        return [finding("WARN", "W-OUTPUT-FORMAT",
                        "no output format declared (SKILL.md fast-path check)")]
    return []


def check_agent_stop(text):
    if AGENT_SIGNAL.search(text) and STOP_SIGNAL.search(text) is None:
        return [finding("ERROR", "E-AGENT-NO-STOP",
                        "agentic prompt has no stop condition (SKILL.md self-check)")]
    return []


def check_vague(text):
    match = VAGUE.search(text)
    if match:
        return [finding("WARN", "W-VAGUE",
                        f"vague phrase '{match.group(0)}': name the condition or the output")]
    return []


def check_key_in_url(text):
    if KEY_IN_URL.search(text):
        return [finding("ERROR", "E-KEY-IN-URL",
                        "API key in a URL query string; send it in the x-goog-api-key header")]
    return []


def check_models(text, target, catalog):
    """Block preview IDs and shut-down image models; warn on deprecated or unlisted image IDs.

    Names in the catalog's aliases count as model references too, so 'Nano Banana 2 preview' is read as its ID.
    """
    problems, seen = [], set()
    candidates = [match.group(0).rstrip(".") for source in (text.lower(), target)
                  for match in MODEL_ID.finditer(source)]
    candidates += model_ids_named(text + " " + target, catalog)
    for model_id in candidates:
        if model_id in seen:
            continue
        seen.add(model_id)
        model = find_model(catalog, model_id)
        if model_id.endswith("-preview"):
            problems.append(finding("ERROR", "E-MODEL-PREVIEW",
                                    f"{model_id} is a preview ID; use the current ID "
                                    "from references/gemini-image-models.json"))
        elif model is None:
            problems.append(finding("WARN", "W-MODEL-UNKNOWN",
                                    f"{model_id} is not in references/gemini-image-models.json; "
                                    "check the official model list"))
        elif model["status"] == "shut_down":
            problems.append(finding("ERROR", "E-MODEL-SHUT-DOWN",
                                    f"{model_id} is shut down (shutdown: {model['shutdown']})"))
        elif model["status"] == "deprecated":
            problems.append(finding("WARN", "W-MODEL-DEPRECATED",
                                    f"{model_id} is deprecated; see references/gemini-image-models.md"))
    return problems


def check_aspect_ratios(text, catalog, model=None):
    """Only the ratios the target model accepts pass; any other is reported with the nearest one it accepts.

    Without a known model, the check uses the union of all the catalog's ratios.
    """
    ratios = model_ratios(catalog, model) if model else catalog["aspect_ratios"]
    scope = model["id"] if model else "the catalog's official set"
    mentions = ASPECT_AFTER_KEYWORD.findall(text) + ASPECT_BEFORE_KEYWORD.findall(text)
    problems, seen = [], set()
    for width, height in mentions:
        label = f"{width}:{height}"
        if label in seen or label in ratios:
            continue
        seen.add(label)
        if float(width) == 0 or float(height) == 0:
            problems.append(finding("WARN", "W-ASPECT-RATIO", f"{label} is not a valid aspect ratio"))
            continue
        nearest = nearest_ratio(float(width) / float(height), ratios)
        problems.append(finding("WARN", "W-ASPECT-RATIO",
                                f"{label} is not one of the {len(ratios)} aspect ratios of {scope}; "
                                f"nearest is {nearest}, so state the mapping in the prompt"))
    return problems


def check_edit_preservation(text):
    """An edit of an existing image must say what stays the same (Google's inpainting pattern)."""
    if (EDIT_VERB.search(text) and IMAGE_NOUN.search(text) and EXISTING_IMAGE.search(text)
            and PRESERVE.search(text) is None):
        return [finding("WARN", "W-EDIT-NO-PRESERVATION",
                        "edit of an existing image with no preservation clause; say what stays exactly the same")]
    return []


def check_reference_roles(text):
    """Two or more numbered references need a role each: identity, style, composition, palette or product."""
    refs = set()
    for match in REF_ORDINAL.finditer(text):
        refs.add(int(match.group(1)) if match.group(1) else ORDINAL_VALUE[match.group(2).lower()])
    if len(refs) < 2:
        return []
    roles = {match.group(0).lower() for match in ROLE_WORD.finditer(text)}
    if len(roles) < len(refs):
        return [finding("WARN", "W-REF-ROLE",
                        f"{len(refs)} references are numbered but {len(roles)} role(s) are named; "
                        "say what each one contributes")]
    return []


def check_text_quotes(text):
    """Words that must appear in the picture go in quotation marks, so they are rendered literally."""
    if TEXT_CUE.search(text) and NO_TEXT.search(text) is None and QUOTE.search(text) is None:
        return [finding("WARN", "W-TEXT-UNQUOTED",
                        "text for the image is named without quotation marks; put the exact words in quotes")]
    return []


def check_negative_list(text):
    """Long lists of 'no X' describe what is absent. Name what should be there instead."""
    count = len(NEGATOR.findall(text))
    if count >= NEGATIVE_LIST_MIN:
        return [finding("WARN", "W-NEGATIVE-LIST",
                        f"{count} negations; describe the wanted scene positively, e.g. 'an empty street' "
                        "instead of 'no cars'")]
    return []


def validate(text, target="", catalog=None):
    """Return the findings for one prompt. An empty list means nothing was flagged."""
    if not text.strip():
        return [finding("ERROR", "E-EMPTY", "prompt is empty")]
    target = (target or "").lower()
    catalog = load_catalog() if catalog is None else catalog
    model = resolve_target(target, catalog) if target else None
    if IMAGE_TARGET.search(target) or model is not None:
        # An image model's output is the picture itself, so the text-answer and agent checks do not apply.
        return (check_key_in_url(text)
                + check_models(text, target, catalog)
                + check_aspect_ratios(text, catalog, model)
                + check_vague(text)
                + check_edit_preservation(text)
                + check_reference_roles(text)
                + check_text_quotes(text)
                + check_negative_list(text))
    sentences = split_sentences(text)
    return (
        check_cot(sentences, target)
        + check_thinking_tag(text, target)
        + check_prefill(text)
        + check_caps(text)
        + check_agent_stop(text)
        + check_vague(text)
        + check_key_in_url(text)
        + check_models(text, target, catalog)
        + check_format(text)
    )


def exit_status(findings, strict=False):
    blocking = {"ERROR", "WARN"} if strict else {"ERROR"}
    return 1 if any(f["level"] in blocking for f in findings) else 0


def read_input(path):
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Static checks for a generated prompt.")
    parser.add_argument("path", nargs="?", default="-", help="prompt file, or - for stdin")
    parser.add_argument("--target", default="",
                        help="model or tool, for example gpt-6-astra, claude-opus-5-5 "
                             "or gemini-nano-banana-2.1")
    parser.add_argument("--strict", action="store_true", help="treat warnings as blocking")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    args = parser.parse_args(argv)
    try:
        catalog = load_catalog()
    except (OSError, ValueError) as exc:
        print(f"error: cannot read the model catalog: {exc}", file=sys.stderr)
        return 2
    try:
        text = read_input(args.path)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    findings = validate(text, args.target, catalog)
    if args.json:
        print(json.dumps(findings, indent=2, ensure_ascii=False))
    elif findings:
        for f in findings:
            print(f"{f['level']} {f['code']}: {f['message']}")
    else:
        print("OK: no findings")
    return exit_status(findings, args.strict)


if __name__ == "__main__":
    sys.exit(main())
