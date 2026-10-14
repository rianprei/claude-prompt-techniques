# Studio: local page and command line, one approval per paid run

The studio generates Nano Banana images. It has two front ends over the same rules in `core.py`: a local page
(`serve`) and a command line (`plan`, `approve`, `run`, and the rest). An agent with a shell uses the command line, so the
person does not have to operate a separate interface. The paid API is called only after an approval for that exact
brief. Stdlib only. Nothing runs at import time.

## Command line

```
python3 -m studio cases                                              # the fixed cases; spends nothing
python3 -m studio plan --prompt "..." --model gemini-nano-banana-2.1 --aspect-ratio 1:1 --size 1K
python3 -m studio approve <brief_sha256> --confirm <first 8 characters>   # only after the person agrees
python3 -m studio run <brief_sha256> --approval <approval_id>        # spends that one approval
python3 -m studio show <run_id>                                      # brief, record, output_path
python3 -m studio plan --from <run_id> --edit "change the teapot to blue"   # a targeted edit; plan only
python3 -m studio rate <run_id> --rating 4 --criterion fidelity=4 --note "..."
python3 -m studio review <run_id> --verdict targeted_fix --note "the handle is missing"
python3 -m studio history --limit 20
python3 -m studio compare <case_id>
python3 -m studio library words --library /path/to/a/local/copy     # optional; no network
python3 -m studio serve --fake-provider                              # the page, with placeholder images
```

Every command prints one JSON object on stdout. A refused request prints `{"error", "message"}` on stderr and
exits 2; a provider or machine failure exits 1. `run --fake-provider` writes a grey placeholder with no network and
no cost. Every command except `library` takes `--data-dir` (default `~/.local/share/prompt-techniques-studio`,
created with mode 0700, outside the skill folder).

## Approval: who says yes

- `plan` builds and freezes the brief. It reports the brief hash, the nominal cost, the warnings, the reference
  hashes that would be uploaded, and the prompt. It spends nothing and writes no approval.
- `approve` issues a single-use approval for that brief, valid for 30 minutes. It asks for the first 8 characters of
  the hash. On a terminal it prompts for them; anywhere else they must come in as `--confirm`.
- **Limit.** The code cannot tell who typed the characters. An agent could pass `--confirm` on its own. The rule
  therefore lives in the skill (`SKILL.md`): the agent runs `approve` only after the person has written those
  characters in the conversation. The approval id is printed once, on stdout.
- `run` spends the approval before the provider is called. A failed call keeps the approval spent, and nothing
  retries on its own. Each paid run needs its own approval, and one approval pays for one run. The code does not
  stop a loop that asks for new approvals; the rule against loops lives in `SKILL.md`.

## Refinement: targeted edits

`plan --from RUN --edit TEXT` plans one edit of a generated image. The parent's output goes in as a reference, byte
for byte, and its hash is checked against the run record. Model, ratio and size default to the parent's. The prompt
is fixed: *Edit the attached image. Change only this: … Keep everything else exactly as it is: …*, which keeps the
parts that were not asked to change.

- `--chain` also sends `previous_interaction_id`, the `id` of the parent's response. It works only for the same model.
  The official multi-turn example uses this field. The pages read do not say whether the server keeps the earlier
  interaction for long or what the default of `store` is, so the image reference, which does not depend on server
  state, is the default.
- A parent output over 10 MB cannot be an edit reference (the local limit), so it cannot be edited here.
- `--ref` adds further references to the edit, up to the model's total.

## Thinking level

`--thinking-level` accepts the levels that the guide's per-model table lists: Nano Banana 2.1 takes minimal, medium
(default) and high; Flash Image and Lite take minimal (default) and high. The value is sent in lower case in
`generation_config.thinking_level`, as the guide's Interactions examples send it, although the API reference's enum
is written in upper case. Pro refuses any level: its thinking cannot be turned off and the guide lists no levels for it.

## Fixed cases and comparison

`evals/image_cases.json` holds eight fixed requests: six that generate an image and two edits (an edit needs `--from`).
Each case names the criteria a person rates: `fidelity`, `composition`, `text`, `identity`, `preservation`,
`constraints`.

- `plan --case ID` uses the case's parameters. A case fixes its own parameters: passing `--model` or a prompt with it
  is refused. A case with references needs `--ref` for each one it asks for.
- `rate RUN --rating N --criterion NAME=N ...` records a person's judgment, from 1 to 5, overall and per criterion.
  The latest rating counts.
- At generation the studio records deterministic checks: format, width, height, byte count, the file's sha256, and
  whether the aspect ratio is within 2 % of the requested one (a local tolerance). They measure the file. They do not
  judge the picture.
- `compare CASE` groups the runs of one case by variant (model, ratio, size, thinking level, and generate or edit) and
  reports counts and the means of the latest ratings. It names no winner. With a few runs per variant, check `n`
  before reading any difference. Placeholder (fake-provider) runs are never compared.

## Library (optional)

`library WORDS` searches the headings (lines that start with `#`) of this skill's `references/`. With
`--library DIR` it also searches the Markdown files of a folder the person already has. Each result gives the file,
the line and the heading, and nothing else: no body text is returned or copied. Symbolic links are not followed.
The YouMind-OpenLab prompt library has no licence file, so the studio never downloads it and does not bundle it.

## Rules enforced in code (`core.py`)

- **Models.** Only current or active IDs without preview are offered. Deprecated and shut-down IDs are not. On
  2026-10-13 that means `gemini-nano-banana-2.1`, `gemini-3.1-flash-lite-image` and `gemini-3-pro-image`.
  `gemini-3.1-flash-image` is deprecated (release notes, 2026-10-06), so it is refused for new briefs.
  The source is `references/gemini-image-models.json`.
- **Sizes.** Only sizes with a catalog price. 512 px is documented only for `gemini-3.1-flash-image`, which is
  deprecated, so no offer lists 512 px. Its JSON value (`512`) is in the Interactions API reference; no live call was made.
- **Aspect ratios.** Each offer lists the ratios its model accepts (`aspect_ratios` in the catalog). A ratio the model
  does not accept is refused at planning time. For example, `gemini-3-pro-image` takes 10 ratios and has no 1:4, and
  Nano Banana 2.1 takes all 14.
- **References.** Uploaded through the page or `--ref`, checked by file signature (PNG, JPEG or WebP), stored by hash.
  The count is capped at `reference_total_max`, which is 14 for each current image model: the guide's total ("Mix up
  to 14 reference images"). The per-type limits are not enforced, because the request does not say which type each
  image is. The 10 MB size cap per image and the 8000-character prompt cap are local choices. The whole request is
  capped at 20 MB inline, the prompt plus each reference as base64, from the image understanding page. A brief over
  that limit is refused at planning time, before any approval is spent.
- **Prompt.** `scripts/validate_prompt.py` checks it. An ERROR blocks the plan. A WARN is shown with the plan.
  For image models only the checks that apply to them run: key in URL, model status (also through the catalog's
  aliases), aspect ratios of the model, vague wording, an edit with no preservation clause, numbered references with
  no roles, text without quotation marks, and long lists of negations. The last four are heuristics that flag a
  prompt for review as WARN; they do not block it.
- **Approval.** 30 minutes, single use, bound to the brief hash. The registry keeps only the SHA-256 of each token,
  and the token is 48 hex characters. (A URL-safe token starts with `-` about 1.6 % of the time, and the command line
  then reads it as an option and refuses the run. The intermittent failure of the CLI tests showed this, and a
  regression test now fixes the format.) A refused approval (unknown, used, expired or mismatched) is never spent.
- **Failure.** A failed provider call keeps its approval spent. Nothing retries on its own, and nothing rephrases a
  blocked prompt, as the catalog's safety section asks.
- **Missing key.** Refused before any approval is spent.
- **Runs cut off by a stop.** When the studio starts, a run still `running` that began 30 minutes or more earlier is
  marked `failed` with error `interrupted`. Younger runs are left alone, because a live run from another studio process
  looks the same in the record. A run record that cannot be read is skipped by the start-up reconciliation, and the
  listing leaves it out with a line on stderr that names it.

## Security

- The page listens on 127.0.0.1 only. Any Host header other than 127.0.0.1 or localhost is refused (DNS rebinding).
- Every POST to the page needs the per-process token in `X-Studio-Token` and a JSON body. No CORS headers are sent,
  so other websites cannot read the page that carries the token or send the header.
- The page's token is not a secret from this machine. `GET /` serves the page with the token in it, and `GET /api/state`
  and the generated images (`/api/runs/<id>/image`) need only the Host check. Any process or user that reaches
  127.0.0.1 can therefore read the token, issue an approval (`POST /api/approvals`), and spend the API key. Use the
  studio on a single-user machine only.
- The command line runs as the person who runs it. Its `--prompt-file` and `--ref` options read any file that person
  can read. A reference is copied into the local store at plan time, but nothing is sent to Google before the
  approval, and the plan shows each reference by hash and the prompt in full.
  The approval id is printed on stdout, so the agent sees it; it is single use and bound to one brief.
- The API key is read from `GEMINI_API_KEY` on each run. It goes only in the `x-goog-api-key` header. It is never in a
  URL, never stored, never printed, and redacted from provider error messages. Redirects are refused, so the header
  never reaches a second address. The CLI tests check that the key appears in no file of the data directory and in no
  output of the flows they cover (a live run, a failed run, a missing key).
- The server sends a strict Content-Security-Policy. The page uses no inline scripts and builds no HTML from data.

## API

The client calls the Interactions endpoint shown in the official image guide (local copy read on 2026-10-12):
`POST /v1beta/interactions`, with text and image parts in `input` and `response_format` set to
`{type: image, aspect_ratio, image_size}`. Two optional fields come from the same guide: a top-level
`previous_interaction_id` (for `--chain`) and `generation_config.thinking_level` (for `--thinking-level`). The image is
read from the first image block in a `model_output` step (`steps[].content[]`, with `data` and `mime_type`), the shape
the Interactions API reference documents (read 2026-10-13). The response's `id` is kept as `interaction_id` when it fits
a local rule (letters, digits, `_`, `.` and `-`, up to 200 characters); the official format of that id is not documented
in the pages read.

Not confirmed by a live call: that the API returns this shape for an image request (the reference documents it), that
a chained edit behaves as the example suggests, the upstream timeout (the client waits 300 s by default, our own choice;
`--timeout` changes it), and the default of `store`. No live call was made while this was built.

## Data (`~/.local/share/prompt-techniques-studio`, created with mode 0700)

- `briefs/<sha256>.json`: canonical JSON, named by its hash. A brief can carry `thinking_level`,
  `previous_interaction_id`, `parent_run_id` and `case_id`; each is left out when unused, so an old request keeps its hash.
- `inputs/<sha256>`: uploaded and edit reference images, named by their hash.
- `outputs/<run_id>.<ext>`: generated images.
- `runs/<run_id>.json`: status, `checks`, `interaction_id`, `provider`, review history and evaluation history (each
  evaluation may carry `criteria`).
- `approvals.json`: SHA-256 of each token, with its brief hash, issue time, expiry and consumption time.

## Platform and catalog

- The store locks files with `fcntl` on POSIX systems (Linux, macOS) and with `msvcrt` on Windows. A lock that stays busy
  for 30 seconds ends the operation with `store_busy` (503). The Windows path is tested with a stand-in module
  (`tests/test_studio_platform.py`), not on a Windows machine. Without either module the store refuses to run.
- A plan warns (`catalog_stale`) when the catalog's `verified_on` date is more than 90 days old. The warning does not
  block the plan and is not part of the brief's hash. `scripts/check_repo.py` warns on the same date and on the routing
  and image-target dates.

## Tests

    python3 -W error::ResourceWarning -m unittest discover -s tests

- `test_studio_core.py`: the rules above.
- `test_studio_client.py`: the request and response shapes, with a fake transport.
- `test_studio_server.py`: the HTTP server end to end with the fake provider, plus the missing-key case.
- `test_studio_page.py`: runs `tests/studio_page_check.mjs` against the real server, through a small DOM stub, when Node
  is installed. Set `STUDIO_REQUIRE_NODE=1` (for example in CI) to make a missing Node a failure instead.
- `test_studio_cli.py`: plan, approval (terminal and `--confirm`), run, the live path through a simulated transport,
  edits and chaining, cases, ratings, history, and the refusals.
- `test_studio_checks.py`: image headers (PNG, JPEG, WebP), the aspect tolerance, the library search, the fixed cases,
  and the comparison.
- `test_studio_platform.py`: the Windows lock path (against a stand-in module), the catalog age warning and the 429 hint.
- `test_studio_browser.py`: the page rendered in headless Chrome or Chromium, skipped when no browser is installed.

No test calls Google's API. The tests use localhost and simulated transports.

## Not covered

- Live API calls. None were made: `GEMINI_API_KEY` was not set where this was built, so the paid path is tested only
  with a simulated transport.
- Clicking through the page. `tests/test_studio_browser.py` renders the page in headless Chrome or Chromium and checks
  that its script ran; it is skipped when no browser is on PATH. Plan, approve and run are not clicked in a browser by
  the tests. `tests/studio_page_check.mjs` drives those steps through a small DOM stub.
- Server behaviour of a chained edit, the default of `store`, the format of the response `id`, and the 512 px option:
  not verified by a live call.
- Rate limits. The API documents how they work (per project, per usage tier, images per minute for image models, and
  429 RESOURCE_EXHAUSTED), but not the numbers for each model: those are shown in Google AI Studio (page read 2026-10-14).
  The studio sets none beyond the 20 MB inline limit. A 429 comes back with a hint: the approval is already spent, so
  plan again.
- Content policy. It is not enforced by code: no real brands and no real people in prompts, and no sexualized
  depictions of real people.

## Origins

Concepts only, no code copied: approval design, brief hashing and review verdicts from AgriciDaniel/banana-claude
(MIT); per-variant ratings and preference totals from juliandickie/creators-studio (MIT). The optional library search
reads only the headings of a folder the person names; it copies nothing from YouMind-OpenLab. The attribution is in
`NOTICE`.
