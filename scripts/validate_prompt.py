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
import re
import sys

# Models that always reason internally (references/tool-routing.md).
REASONING_NATIVE = ("o3", "o4-mini", "deepseek-r1", "gpt-6", "fable-5", "mythos-5", "opus-5-5")
CLAUDE_5 = re.compile(r"claude-(fable|mythos|opus|sonnet|haiku)-5")

COT_PHRASE = re.compile(
    r"\b(step[- ]by[- ]step|passo a passo|chain[- ]of[- ]thought|cadeia de pensamento"
    r"|show (your|the) (reasoning|work)|(reason|think) (it )?through)\b",
    re.IGNORECASE,
)
NEGATION = re.compile(
    r"\b(not|no|never|don't|do not|avoid|without|skip|não|nunca|sem|evite|evitar)\b",
    re.IGNORECASE,
)
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


def finding(level, code, message):
    return {"level": level, "code": code, "message": message}


def split_sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def requests_cot(sentence):
    """True when the sentence asks for step-by-step reasoning, False when it forbids it."""
    match = COT_PHRASE.search(sentence)
    if match is None:
        return False
    # TODO(human): decide how double negatives are read. "Don't skip the
    # step-by-step check" asks for reasoning but contains a negation word, so
    # the line below returns False for it. Write the rule here.
    return NEGATION.search(sentence[: match.start()]) is None


def check_cot(sentences, target):
    if not any(key in target for key in REASONING_NATIVE):
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


def validate(text, target=""):
    """Return the findings for one prompt. An empty list means nothing was flagged."""
    if not text.strip():
        return [finding("ERROR", "E-EMPTY", "prompt is empty")]
    target = (target or "").lower()
    sentences = split_sentences(text)
    return (
        check_cot(sentences, target)
        + check_thinking_tag(text, target)
        + check_prefill(text)
        + check_caps(text)
        + check_format(text)
        + check_agent_stop(text)
        + check_vague(text)
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
                        help="model or tool, for example gpt-6-astra or claude-opus-5-5")
    parser.add_argument("--strict", action="store_true", help="treat warnings as blocking")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    args = parser.parse_args(argv)
    try:
        text = read_input(args.path)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    findings = validate(text, args.target)
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
