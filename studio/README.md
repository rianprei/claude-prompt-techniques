# Studio: local page with one approval per paid run

The studio is a local page for Nano Banana image generation. It builds a brief,
shows the plan and its nominal price, and calls the paid API only after the user
approves that exact brief. It is part of the P1 GUI plan in the curation audit
(ideas I1, I2, I3, I7 and I15). Stdlib only. Nothing runs at import time.

## Run it

    python3 -m studio serve --fake-provider      # placeholder images, no network, no cost
    GEMINI_API_KEY=... python3 -m studio serve   # live provider; the key is read on each run

The page opens at http://127.0.0.1:8765/. Options: `--port` and `--data-dir`
(default `studio/data`, which git ignores).

## Flow

1. **Brief.** Prompt, model, aspect ratio, image size and optional reference images.
   The brief is frozen as canonical JSON and named by its SHA-256 hash. A changed field is a new brief.
2. **Plan.** The page shows the prompt, the model, the size, the nominal price and the checker's warnings.
3. **Approval.** One click issues a single-use approval for that brief hash, valid for 30 minutes.
4. **Run.** The approval is spent first, and only then is the provider called. The result is a generated image or a recorded failure.
5. **Review.** Each generated image gets one of four verdicts: pass, targeted fix, regenerate or blocked.
   Targeted fix and blocked need a note.
6. **Evaluation.** Each generated image can get a rating from 1 to 5 with a note. The history shows the
   average rating per model and per aspect ratio, using each run's latest rating.

## Rules enforced in code (`core.py`)

- **Models.** Only current or active IDs without preview are offered. Deprecated and shut-down IDs are not.
  The source is `references/gemini-image-models.json`.
- **Sizes.** Only sizes with a catalog price. 512 px stays hidden until the catalog confirms its JSON value.
- **Aspect ratios.** Only the 14 official values.
- **References.** Uploaded through the page, checked by file signature (PNG, JPEG or WebP), stored by hash.
  The count is capped at the smallest documented reference limit for the model, which is conservative because
  the catalog does not map limits to models. The 10 MB size cap and the 8000-character prompt cap are local
  choices, not official limits.
- **Prompt.** `scripts/validate_prompt.py` checks it. An ERROR blocks the plan. A WARN is shown with the plan.
  For image models only the checks that apply to them run: key in URL, model status, aspect ratios and vague wording.
- **Approval.** 30 minutes, single use, bound to the brief hash. The registry keeps only the SHA-256 of
  each token. A refused approval (unknown, used, expired or mismatched) is never spent.
- **Failure.** A failed provider call keeps its approval spent. Nothing retries on its own, and nothing rephrases
  a blocked prompt, as the catalog's safety section asks.
- **Missing key.** Refused before any approval is spent.

## Security

- The server listens on 127.0.0.1 only. Any Host header other than 127.0.0.1 or localhost is refused (DNS rebinding).
- Every POST needs the per-process token in `X-Studio-Token` and a JSON body. No CORS headers are sent.
- Only POST needs the token. `GET /api/state` and the generated images (`/api/runs/<id>/image`) need only the Host check, so any process on this machine can connect to 127.0.0.1 and read run history and images. Browsers on other sites cannot read them: no CORS headers are sent, and the Host check blocks DNS rebinding.
- The API key is read from `GEMINI_API_KEY` on each run. It goes only in the `x-goog-api-key` header. It is never in a URL,
  never stored, never shown in the page or the state, and redacted from provider error messages. Redirects are refused, so the header never reaches a second address.
- The server sends a strict Content-Security-Policy. The page uses no inline scripts and builds no HTML from data.

## API

The client calls the Interactions endpoint shown in the official image guide (local copy read on 2026-10-12):
`POST /v1beta/interactions`, with text and image parts in `input` and `response_format` set to
`{type: image, aspect_ratio, image_size}`. The image is read from `output_image.data`, or from the first image
block in `steps[].content`.

UNKNOWN until a live call is made: the response field names beyond the guide's examples, and the upstream
timeout (the client uses 300 s, our own choice). No live call was made while this was built.

## Data (`studio/data`, ignored by git, created with mode 0700)

- `briefs/<sha256>.json`: canonical JSON, named by its hash.
- `inputs/<sha256>`: uploaded reference images, named by their hash.
- `outputs/<run_id>.<ext>`: generated images.
- `runs/<run_id>.json`: status, review history and evaluation history.
- `approvals.json`: SHA-256 of each token, with its brief hash, issue time, expiry and consumption time.

## Platform and catalog

- The store locks files with `fcntl`, which exists only on POSIX systems (Linux, macOS). On Windows the store refuses to run and raises `unsupported_platform`.
- The studio does not check the age of the catalog. Its date is `verified_on` in `references/gemini-image-models.json`. `scripts/check_repo.py` warns when that date is more than 90 days old, but only for whoever runs that check.

## Tests

    python3 -m unittest discover -s tests

- `test_studio_core.py`: the rules above.
- `test_studio_client.py`: the request and response shapes, with a fake transport.
- `test_studio_server.py`: the HTTP server end to end with the fake provider, plus the missing-key case.
- `test_studio_page.py`: runs `tests/studio_page_check.mjs` against the real server, through a small DOM stub,
  when Node is installed. It is skipped otherwise. Set `STUDIO_REQUIRE_NODE=1` (for example in CI) to make a missing Node a failure instead.

No test calls Google's API. The tests use localhost only.

## Not covered

- Live API calls. None were made.
- Real browser rendering. `tests/studio_page_check.mjs` drives the page script against the real server through a
  small DOM stub (22 checks). No real browser was used, so layout and styling were not checked.
- Official rate and text limits. The catalog has none, so the studio sets none.
- Content policy. It is not enforced by code: no real brands and no real people in prompts, and no sexualized
  depictions of real people.

## Origins

Concepts only, no code copied: approval design, brief hashing and review verdicts from
AgriciDaniel/banana-claude (MIT); per-variant ratings and preference totals from juliandickie/creators-studio
(MIT). The attribution is in `NOTICE`.
