"""Command line for the studio, so that an agent with a shell can plan, approve, run, inspect and rate images.

Every command prints one JSON object on stdout. A refused request prints {"error", "message"} on stderr and exits 2;
a provider or machine failure exits 1. Only `run` calls the paid API, and only with an unspent approval issued for
that exact brief. plan, approve, show, history, review, rate, compare, cases, library and models spend nothing.

The approval is the person's step. `approve` names the first 8 characters of the brief hash, which the plan shows.
On a terminal it asks for them; elsewhere they must come in as --confirm. The code cannot tell who typed them, so
the rule lives in SKILL.md: pass --confirm only after the user has written those characters in the conversation.
"""

import argparse
import json
import os
import sys
from types import SimpleNamespace

from contracts import load_studio_catalog  # studio/__init__.py put scripts/ on sys.path
from .client import FakeClient, TIMEOUT_SECONDS, real_client
from .core import (CRITERIA, MAX_REFERENCE_BYTES, Store, StudioError, build_brief, offered_models,
                   plan_refinement, record_evaluation, record_review, run_brief, sniff_image, summarize_run)
from .evalset import compare_case, find_case, load_cases, validate_cases
from .library import search as search_library
from .server import DEFAULT_DATA_DIR, main as serve_main, provider_states

CONFIRM_LENGTH = 8  # characters of the brief hash the person must type to approve; short enough to type, long enough to check
MAX_PROMPT_FILE_BYTES = 64 * 1024  # local cap on a prompt read from a file
CASE_FIELDS = ("id", "kind", "title", "model", "aspect_ratio", "image_size", "thinking_level",
               "references_needed", "criteria")


def _emit(payload):
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _fail(code, message, status):
    print(json.dumps({"error": code, "message": message}, ensure_ascii=False), file=sys.stderr)
    return 1 if status >= 500 else 2


def _is_tty():
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):  # stdin closed or replaced
        return False


def _price(catalog, model_id, image_size):
    for offer in offered_models(catalog):
        if offer["id"] == model_id:
            return offer["prices_usd_per_image"].get(image_size)
    return None


def _cost_text(price):
    """The cost line of a plan. No estimate is shown unless an official page gave the price."""
    if price is None:
        return "cost not verified in an official page: no estimate (approval still needed for each run)"
    return f"about {price} USD per image"


def _prompt_text(args):
    if args.prompt is not None and args.prompt_file is not None:
        raise StudioError("two_prompts", "Give --prompt or --prompt-file, not both.")
    if args.prompt_file is None:
        return args.prompt
    if not os.path.isfile(args.prompt_file):
        raise StudioError("prompt_file_not_found", f"No file at {args.prompt_file}.")
    if os.path.getsize(args.prompt_file) > MAX_PROMPT_FILE_BYTES:
        raise StudioError("prompt_too_long", f"The prompt file is larger than {MAX_PROMPT_FILE_BYTES} bytes.")
    with open(args.prompt_file, encoding="utf-8") as handle:
        return handle.read()


def _read_reference(store, path):
    """Upload one image file given on the command line, with the same type and size checks as the page."""
    if not os.path.isfile(path):
        raise StudioError("reference_not_found", f"No file at {path}.")
    if os.path.getsize(path) > MAX_REFERENCE_BYTES:
        raise StudioError("image_too_large", "The image is larger than the local limit.", 413)
    with open(path, "rb") as handle:
        data = handle.read(MAX_REFERENCE_BYTES + 1)
    mime_type = sniff_image(data)
    if mime_type is None:
        raise StudioError("unsupported_image", "Upload a PNG, JPEG or WebP image.")
    return store.save_reference(mime_type, data)


def _parse_criteria(items):
    scores = {}
    for item in items or []:
        name, separator, value = item.partition("=")
        if not separator or not value.strip().isdigit():
            raise StudioError("bad_criteria", f"Write each criterion as NAME=N, N from 1 to 5. Names: {', '.join(CRITERIA)}.")
        scores[name.strip()] = int(value)
    return scores


def _case_or_none(case_id):
    if case_id is None:
        return None
    case = find_case(load_cases(), case_id)
    if case is None:
        raise StudioError("unknown_case", f"No case {case_id!r} in evals/image_cases.json.", 404)
    return case


def cmd_plan(args, ctx):
    """Build and freeze one brief. Nothing is spent; the plan is shown to the person before any approval."""
    catalog, store = ctx.catalog, ctx.store
    case = _case_or_none(args.case)
    prompt = _prompt_text(args) if case is None else None
    if case is not None:
        fixed = [flag for flag, value in (("--model", args.model), ("--aspect-ratio", args.aspect_ratio),
                 ("--size", args.size), ("--thinking-level", args.thinking_level), ("--prompt", args.prompt),
                 ("--prompt-file", args.prompt_file), ("--edit", args.edit)) if value is not None]
        if fixed:
            raise StudioError("case_fixes_parameters", f"A case fixes its own parameters; drop {', '.join(fixed)}.")
        if (case["kind"] == "edit") != bool(args.from_run):
            raise StudioError("case_kind_mismatch", "An edit case needs --from RUN_ID; a generate case must not have it.")
        if len(args.ref) < case["references_needed"]:
            raise StudioError("case_needs_references",
                              f"This case needs {case['references_needed']} reference image(s); pass --ref.")
        model, aspect, size, level = case["model"], case["aspect_ratio"], case["image_size"], case.get("thinking_level")
        prompt, edit = case.get("prompt"), case.get("edit")
    else:
        model, aspect, size, level = args.model, args.aspect_ratio, args.size, args.thinking_level
        edit = args.edit
    refs = [_read_reference(store, path) for path in args.ref]

    if args.from_run:
        if prompt is not None:
            raise StudioError("prompt_with_from", "With --from, the change is --edit, not a new prompt.")
        if not edit:
            raise StudioError("empty_edit", "Say what to change with --edit.")
        brief = plan_refinement(catalog, store, args.from_run, edit, references=refs, model_id=model,
                                aspect_ratio=aspect, image_size=size, thinking_level=level,
                                chain=args.chain, case_id=args.case)
    else:
        if args.chain:
            raise StudioError("chain_needs_from", "--chain applies only to an edit (--from RUN_ID).")
        for flag, value in (("--model", model), ("--aspect-ratio", aspect), ("--size", size)):
            if value is None:
                raise StudioError("missing_parameter", f"{flag} is required for a new image.")
        brief = build_brief(catalog, store, prompt=prompt, model_id=model, aspect_ratio=aspect, image_size=size,
                            references=refs, thinking_level=level, case_id=args.case)

    digest, fields = brief["brief_sha256"], brief["brief"]
    _emit({
        "brief_sha256": digest,
        "spent": False,
        "model": fields["model"],
        "aspect_ratio": fields["aspect_ratio"],
        "image_size": fields["image_size"],
        "thinking_level": fields.get("thinking_level"),
        "previous_interaction_id": fields.get("previous_interaction_id"),
        "parent_run_id": fields.get("parent_run_id"),
        "case_id": fields.get("case_id"),
        "references": len(fields["references"]),
        "reference_sha256": [ref["sha256"] for ref in fields["references"]],  # what the approval uploads, by hash
        "prompt": fields["prompt"],
        "estimated_cost_usd": brief["estimated_cost_usd"],
        "cost_note": None if brief["estimated_cost_usd"] is not None else _cost_text(None),
        "warnings": brief["warnings"],
        "next": (f"Show this plan to the user. Only after the user approves it in the conversation, run: "
                 f"approve {digest} --confirm {digest[:CONFIRM_LENGTH]}"),
    })
    return 0


def cmd_approve(args, ctx):
    """Issue the single-use approval for one brief, after the person confirms its hash prefix."""
    store, catalog = ctx.store, ctx.catalog
    brief = store.load_brief(args.brief)
    prefix = args.brief[:CONFIRM_LENGTH]
    typed = args.confirm
    if typed is None:
        if not ctx.stdin_isatty():
            raise StudioError("confirmation_required",
                              f"Approval needs the person to confirm. Show the plan, then pass --confirm {prefix} "
                              "only after the user has typed it.", 409)
        sys.stderr.write(f"Plan: {brief['model']}, {brief['aspect_ratio']}, {brief['image_size']}, "
                         f"{_cost_text(_price(catalog, brief['model'], brief['image_size']))}\n")
        try:
            typed = ctx.input_func(f"Type {prefix} to approve this one paid run: ")
        except EOFError:  # Ctrl-D at the prompt is a refusal, not a crash
            typed = ""
    if not isinstance(typed, str) or typed.strip().lower() != prefix:
        raise StudioError("confirmation_mismatch", "The characters do not match the start of the brief hash. "
                                                   "Nothing was approved.", 409)
    approval = store.issue_approval(args.brief)
    _emit({
        "brief_sha256": args.brief,
        "approval_id": approval["approval_id"],
        "expires_at": approval["expires_at"],
        "scope": approval["scope"],
        "estimated_cost_usd": _price(catalog, brief["model"], brief["image_size"]),
        "next": "Run it once with: run <brief_sha256> --approval <approval_id>. That run spends the approval.",
    })
    return 0


def cmd_run(args, ctx):
    """Spend the approval on the brief. The paid call happens only after the approval is consumed."""
    record = run_brief(ctx.catalog, ctx.store, ctx.client_factory, args.brief, args.approval)
    result = summarize_run(record)
    result["provider"] = record.get("provider")
    if record["status"] != "generated":
        _emit(result)
        return 1
    result["output_path"] = ctx.store.output_path(record["output"])
    result["checks"] = record.get("checks")
    _emit(result)
    return 0


def cmd_show(args, ctx):
    record = ctx.store.load_run(args.run)
    result = dict(record)
    result["brief"] = ctx.store.load_brief(record["brief_sha256"])
    if record["status"] == "generated":
        result["output_path"] = ctx.store.output_path(record["output"])
    _emit(result)
    return 0


def cmd_history(args, ctx):
    _emit({"runs": [summarize_run(record) for record in ctx.store.list_runs(limit=args.limit)]})
    return 0


def cmd_review(args, ctx):
    _emit(summarize_run(record_review(ctx.store, args.run, args.verdict, args.note)))
    return 0


def cmd_rate(args, ctx):
    scores = _parse_criteria(args.criterion)
    _emit(summarize_run(record_evaluation(ctx.store, args.run, args.rating, args.note, criteria=scores)))
    return 0


def cmd_compare(args, ctx):
    _case_or_none(args.case)  # raises unknown_case for an id that is not in the cases file
    _emit(compare_case(ctx.store.list_runs(limit=None), args.case))
    return 0


def cmd_cases(args, ctx):
    cases = load_cases()
    problems = validate_cases(cases, ctx.catalog)
    _emit({"cases": [{field: case.get(field) for field in CASE_FIELDS} for case in cases], "problems": problems})
    return 0 if not problems else 1


def cmd_library(args, ctx):
    _emit(search_library(" ".join(args.query), library=args.library))
    return 0


def cmd_models(args, ctx):
    """Every model the studio can plan, with its provider, sizes, ratios and cost, and which providers have variables set."""
    _emit({"models": offered_models(ctx.catalog),
           "providers": provider_states(ctx.catalog, fake=False)})
    return 0


HANDLERS = {"plan": cmd_plan, "approve": cmd_approve, "run": cmd_run, "show": cmd_show, "history": cmd_history,
            "review": cmd_review, "rate": cmd_rate, "compare": cmd_compare, "cases": cmd_cases,
            "library": cmd_library, "models": cmd_models}


def build_parser():
    parser = argparse.ArgumentParser(prog="python3 -m studio",
                                     description="Local studio for image models (Gemini, GPT Image, FLUX, Ideogram, "
                                                 "Recraft, Seedream, Stability, ComfyUI): plan and approve paid image "
                                                 "calls, then inspect, refine and rate the results.")
    commands = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir", default=DEFAULT_DATA_DIR,
                        help="where briefs, images and approvals are kept (default ~/.local/share/prompt-techniques-studio)")

    commands.add_parser("serve", help="start the local page; its flags are --port, --data-dir, --timeout, --fake-provider")

    plan = commands.add_parser("plan", parents=[common], help="build one brief; nothing is spent")
    plan.add_argument("--prompt", help="the prompt text")
    plan.add_argument("--prompt-file", help="read the prompt from this file")
    plan.add_argument("--case", help="use a fixed case from evals/image_cases.json")
    plan.add_argument("--model", help="model id from the models command, for example gemini-nano-banana-2.1 or gpt-image-2")
    plan.add_argument("--aspect-ratio", help="W:H, one the model accepts ('auto' where the model chooses)")
    plan.add_argument("--size", help="a size the model offers, for example 1K, 2K, 4K, 1024x1024 or default")
    plan.add_argument("--thinking-level", help="minimal, low, medium or high, where the model lists it")
    plan.add_argument("--ref", action="append", default=[], help="reference image (PNG, JPEG or WebP); repeatable")
    plan.add_argument("--from", dest="from_run", help="edit this run's output (run_...)")
    plan.add_argument("--edit", help="what to change in the --from image; everything else is kept")
    plan.add_argument("--chain", action="store_true",
                      help="with --from: also send the parent's interaction id (same model only)")

    approve = commands.add_parser("approve", parents=[common], help="issue the approval for one brief")
    approve.add_argument("brief", help="brief_sha256 from plan")
    approve.add_argument("--confirm", help="the first 8 characters of the brief hash, typed by the person")

    run = commands.add_parser("run", parents=[common], help="spend one approval on one brief")
    run.add_argument("brief", help="brief_sha256 from plan")
    run.add_argument("--approval", required=True, help="approval_id from approve; single use")
    run.add_argument("--fake-provider", action="store_true", help="placeholder image, no network and no cost")
    run.add_argument("--timeout", type=int, default=TIMEOUT_SECONDS,
                     help=f"seconds to wait for the live provider (default {TIMEOUT_SECONDS})")

    show = commands.add_parser("show", parents=[common], help="one run: its brief, record and output path")
    show.add_argument("run", help="run_id")

    history = commands.add_parser("history", parents=[common], help="the newest runs, with their verdicts and ratings")
    history.add_argument("--limit", type=int, default=20, help="how many runs to list (default 20)")

    review = commands.add_parser("review", parents=[common], help="record a review verdict on a generated image")
    review.add_argument("run", help="run_id")
    review.add_argument("--verdict", required=True, choices=("pass", "targeted_fix", "regenerate", "blocked"))
    review.add_argument("--note", help="what is wrong; required for targeted_fix and blocked")

    rate = commands.add_parser("rate", parents=[common], help="record a 1-5 rating, optionally per criterion")
    rate.add_argument("run", help="run_id")
    rate.add_argument("--rating", type=int, required=True, help="overall rating, 1 to 5")
    rate.add_argument("--criterion", action="append", default=[],
                      help=f"NAME=N with N from 1 to 5; names: {', '.join(CRITERIA)}")
    rate.add_argument("--note", help="short note")

    compare = commands.add_parser("compare", parents=[common], help="runs of one case, grouped by variant")
    compare.add_argument("case", help="case id from evals/image_cases.json")

    commands.add_parser("cases", parents=[common], help="list the fixed cases and any problem in the file")

    library = commands.add_parser("library", help="search style and example headings; no network")
    library.add_argument("query", nargs="+", help="words that the heading must contain")
    library.add_argument("--library", help="a local folder of Markdown files you already have (optional)")

    commands.add_parser("models", parents=[common],
                        help="every model you can plan, its provider, sizes, ratios, cost and which keys are set")
    return parser


def main(argv=None, *, client_factory=None, stdin_isatty=None, input_func=None):
    """Entry point for `python3 -m studio`. The keyword arguments let the tests replace the provider and the terminal."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["serve"]:
        return serve_main(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run" and args.timeout <= 0:
        parser.error("--timeout must be a positive number of seconds")
    if args.command == "history" and args.limit <= 0:
        parser.error("--limit must be a positive number")
    try:
        store = None if args.command == "library" else Store(args.data_dir)
        if store is not None:
            store.mark_stale_runs()  # the same start-up rule as the page: a stopped run is marked failed
        if args.command == "run" and client_factory is None:
            client_factory = FakeClient if args.fake_provider else (
                lambda provider: real_client(provider, timeout=args.timeout))
        ctx = SimpleNamespace(catalog=load_studio_catalog(), store=store, client_factory=client_factory,
                              stdin_isatty=stdin_isatty or _is_tty, input_func=input_func or input)
        return HANDLERS[args.command](args, ctx)
    except StudioError as exc:
        return _fail(exc.code, exc.message, exc.status)
    except OSError as exc:
        return _fail("io_error", f"{type(exc).__name__}: {exc.strerror or 'file or folder problem'}", 500)
    except KeyboardInterrupt:
        return 130
