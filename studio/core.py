"""Rules for the studio: frozen briefs, single-use approvals, reviews and evaluations.

Stdlib only, and nothing here touches the network. client.py and providers.py make the paid call,
and run_brief() calls it only after the approval has been consumed.

Data lives in one directory, outside the skill folder by default (see server.py):
    briefs/<sha256>.json   each brief in canonical JSON, named by its hash
    inputs/<sha256>        uploaded reference images, named by their hash
    outputs/<run_id>.ext   generated images
    runs/<run_id>.json     run record: status, review and evaluation history
    approvals.json         registry keyed by the SHA-256 of each token; the token is never stored
"""

import contextlib
import hashlib
import json
import os
import re
import secrets
import sys
import tempfile
import threading
import time
from datetime import date, datetime, timedelta, timezone

try:
    import fcntl
except ImportError:  # not POSIX; the store falls back to msvcrt, and refuses to run if neither exists
    fcntl = None
try:
    import msvcrt
except ImportError:  # not Windows
    msvcrt = None

from validate_prompt import validate  # noqa: E402
from contracts import model_ratios, reference_total  # noqa: E402
from .checks import check_output  # noqa: E402

APPROVAL_TTL = timedelta(minutes=30)  # approval window; the single-use design is credited in NOTICE
APPROVAL_RETENTION = timedelta(hours=24)  # finished approvals stay this long, so a reuse says "used"
STALE_RUN_AFTER = timedelta(minutes=30)  # longer than one provider call can take: no retry, 300 s socket timeout
INTERRUPTED_MESSAGE = "The studio stopped before this run finished. The approval stays used."
MAX_LIVE_APPROVALS = 64
MAX_PROMPT_CHARS = 8000  # local cap; no official limit was found
MAX_NOTE_CHARS = 2000  # local cap for review and evaluation notes
MAX_REFERENCE_BYTES = 10 * 1024 * 1024  # local cap per image; the official limit applies to the whole request
MAX_INLINE_REQUEST_BYTES = 20_000_000  # Gemini's official inline limit (image understanding page, read 2026-10-13); the studio applies it to every provider as its request cap
MAX_RUNS_LISTED = 50
REVIEW_VERDICTS = ("pass", "targeted_fix", "regenerate", "blocked")
NOTE_REQUIRED = ("targeted_fix", "blocked")
RATINGS = (1, 2, 3, 4, 5)
# Criteria a person rates on each image. The checks in checks.py measure format and size only; these are judgments.
CRITERIA = ("fidelity", "composition", "text", "identity", "preservation", "constraints")
EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
RUN_ID = re.compile(r"run_[0-9a-f]{16}")
CASE_ID = re.compile(r"[a-z0-9][a-z0-9_\-]{0,63}")
# Local rule for interaction ids we send or store. The format of the official id is not documented in the pages read.
INTERACTION_ID = re.compile(r"[A-Za-z0-9_.\-]{1,200}")


class StudioError(Exception):
    """A rule was broken. `code` is stable for the page; `status` is the HTTP status to use."""

    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def as_dict(self):
        return {"error": self.code, "message": self.message}


class ProviderError(StudioError):
    """The paid call failed or returned no usable image. The approval stays spent."""

    def __init__(self, code, message):
        super().__init__(code, message, status=502)


def utcnow():
    return datetime.now(timezone.utc)


def iso(moment):
    return moment.isoformat(timespec="seconds")


def parse_time(text):
    """ISO time as an aware datetime. A time without an offset is read as UTC, the clock the studio writes."""
    moment = datetime.fromisoformat(text)
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def is_sha256(value):
    return isinstance(value, str) and len(value) == 64 and set(value) <= set("0123456789abcdef")


def is_image_type(value):
    return isinstance(value, str) and value in EXTENSIONS


def sniff_image(data):
    """MIME type from the file signature, or None. Only PNG, JPEG and WebP are accepted."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def is_unpriced(model):
    """True when the catalog row says no official page gave its price. Such a model is offered with no estimate."""
    return model.get("cost") == "unverified"


def allowed_sizes(catalog, model):
    """Priced sizes the studio offers; an unpriced model offers all its sizes. 512 px stays hidden until the catalog confirms its JSON value."""
    confirmed = catalog["image_sizes"]["512_json_value_confirmed"]
    prices = model.get("prices_usd_per_image", {})
    return [s for s in model.get("sizes", [])
            if (is_unpriced(model) or s in prices) and (s != "512" or confirmed)]


def max_references(model):
    """Most reference images one request may carry: the guide's total for the model (14 for the current image models)."""
    return reference_total(model)


def thinking_levels(model):
    """Thinking levels the guide lists for the model, in the lower case the Interactions API uses. Empty when none."""
    levels = (model.get("thinking") or {}).get("levels") or []
    return [level.lower() for level in levels]


def offered_models(catalog):
    """Current or active models, never previews. Deprecated and shut-down models are not offered."""
    offers = []
    for model in catalog["models"]:
        if model["status"] not in ("current", "active") or model["id"].endswith("-preview"):
            continue
        sizes = allowed_sizes(catalog, model)
        prices = model.get("prices_usd_per_image", {})
        offers.append({
            "id": model["id"],
            "provider": model.get("provider", "gemini"),
            "name": model.get("display_name", model["id"]),
            "sizes": sizes,
            "size_ratio": model.get("size_ratio", {}),
            "aspect_ratios": model_ratios(catalog, model),
            "aspect_control": model.get("aspect_control", True),
            "cost": "unverified" if is_unpriced(model) else "verified",
            "prices_usd_per_image": {s: prices[s] for s in sizes if s in prices},
            "max_references": max_references(model),
            "thinking_levels": thinking_levels(model),
        })
    return offers


def provider_of(catalog, model_id):
    """The provider a model ID belongs to. Model IDs are unique across the catalog, so this has one answer."""
    for model in catalog["models"]:
        if model["id"] == model_id:
            return model.get("provider", "gemini")
    raise StudioError("model_not_offered", f"{model_id!r} is not in the catalog. Build a new plan.", 409)


def _check_thinking(offer, thinking_level):
    """A thinking level the model's row in the guide lists. A model with no level control refuses any value."""
    if not offer["thinking_levels"]:
        raise StudioError("thinking_not_supported",
                          f"{offer['id']} has no thinking level control in the guide. Leave the level out.")
    level = thinking_level.strip().lower() if isinstance(thinking_level, str) else ""
    if level not in offer["thinking_levels"]:
        raise StudioError("thinking_level_not_allowed",
                          f"{thinking_level!r} is not a thinking level of {offer['id']}; "
                          f"it accepts {', '.join(offer['thinking_levels'])}.")
    return level


def _check_interaction(value):
    if not isinstance(value, str) or not INTERACTION_ID.fullmatch(value):
        raise StudioError("bad_interaction_id", "The interaction id is not in the form the studio accepts.")
    return value


def _check_run_id(value):
    if not isinstance(value, str) or not RUN_ID.fullmatch(value):
        raise StudioError("run_unknown", "Unknown run.", 404)
    return value


def _check_case_id(value):
    if not isinstance(value, str) or not CASE_ID.fullmatch(value):
        raise StudioError("bad_case_id", "A case id is lower-case letters, digits, '-' or '_', up to 64 characters.")
    return value


def inline_request_bytes(prompt, sizes):
    """Size of the inline request body: the prompt bytes, plus each reference as base64 (4 characters per 3 bytes)."""
    return len(prompt.encode("utf-8")) + sum(4 * ((size + 2) // 3) for size in sizes)


def build_brief(catalog, store, *, prompt, model_id, aspect_ratio, image_size, references,
                thinking_level=None, previous_interaction_id=None, parent_run_id=None, case_id=None):
    """Check a request and freeze it as a brief. Returns the plan that the user approves.

    `references` is a list of {"sha256", "mime_type"} entries uploaded earlier. The optional fields are left out of
    the brief when they are None, so a request without them keeps the hash it had before they existed.
    `parent_run_id` and `case_id` only label the brief; the API never receives them.
    """
    offers = {offer["id"]: offer for offer in offered_models(catalog)}
    if not isinstance(model_id, str) or model_id not in offers:
        raise StudioError("model_not_offered",
                          f"{model_id!r} is not offered. Only current or active models without preview are.")
    offer = offers[model_id]
    if not isinstance(prompt, str) or not prompt.strip():
        raise StudioError("empty_prompt", "The prompt is empty.")
    prompt = prompt.strip()
    if len(prompt) > MAX_PROMPT_CHARS:
        raise StudioError("prompt_too_long", f"The prompt has more than {MAX_PROMPT_CHARS} characters.")
    if aspect_ratio not in offer["aspect_ratios"]:
        raise StudioError("aspect_ratio_not_official",
                          f"{aspect_ratio!r} is not an aspect ratio of {model_id}; it accepts {len(offer['aspect_ratios'])}.")
    if image_size not in offer["sizes"]:
        raise StudioError("image_size_not_allowed", f"{image_size!r} is not available for {model_id}.")
    tied_ratio = offer["size_ratio"].get(image_size)  # some models fix the ratio inside the size, so the two must agree
    if tied_ratio is not None and tied_ratio != aspect_ratio:
        raise StudioError("size_aspect_mismatch", f"{image_size} on {model_id} is {tied_ratio}; pass --aspect-ratio {tied_ratio}.")
    if not isinstance(references, list) or len(references) > offer["max_references"]:
        raise StudioError("too_many_references",
                          f"{model_id} takes at most {offer['max_references']} reference images here.")
    refs = [store.check_reference(ref) for ref in references]
    if inline_request_bytes(prompt, [store.reference_size(ref) for ref in refs]) > MAX_INLINE_REQUEST_BYTES:
        raise StudioError("request_too_large", "The prompt and the reference images together are over the studio's 20 MB request cap.", 413)
    findings = validate(prompt, model_id, catalog) + catalog_age_findings(catalog)
    blocking = [f for f in findings if f["level"] == "ERROR"]
    if blocking:
        raise StudioError("prompt_blocked", "; ".join(f"{f['code']}: {f['message']}" for f in blocking))
    brief = {
        "prompt": prompt,
        "model": model_id,
        "aspect_ratio": aspect_ratio,
        "image_size": image_size,
        "references": refs,
    }
    if thinking_level is not None:
        brief["thinking_level"] = _check_thinking(offer, thinking_level)
    if previous_interaction_id is not None:
        brief["previous_interaction_id"] = _check_interaction(previous_interaction_id)
    if parent_run_id is not None:
        brief["parent_run_id"] = _check_run_id(parent_run_id)
    if case_id is not None:
        brief["case_id"] = _check_case_id(case_id)
    return {
        "brief_sha256": store.save_brief(brief),
        "brief": brief,
        "estimated_cost_usd": offer["prices_usd_per_image"].get(image_size),  # None when no official price was read
        "warnings": findings,
    }


class Store:
    """Files under one directory. Writes are atomic and the approval registry is locked."""

    def __init__(self, root):
        self.root = root
        # Private by default: the briefs and images are the user's own prompts and pictures.
        os.makedirs(root, mode=0o700, exist_ok=True)
        for sub in ("briefs", "inputs", "outputs", "runs"):
            os.makedirs(os.path.join(root, sub), mode=0o700, exist_ok=True)
        self._runs_cache = {}  # run file name -> (file identity, record); see list_runs
        self._runs_lock = threading.Lock()
        # msvcrt locks belong to the process, not the thread: the threads of the server queue here before the file lock.
        self._msvcrt_mutex = threading.Lock()
        self._runs_warned = set()  # (file name, identity) of each unreadable run record already reported

    def _path(self, *parts):
        return os.path.join(self.root, *parts)

    @contextlib.contextmanager
    def _locked(self):
        if fcntl is None and msvcrt is None:
            raise StudioError("unsupported_platform",
                              "The studio needs file locks (fcntl on POSIX, msvcrt on Windows) and refuses to run without them.",
                              500)
        with open(self._path(".lock"), "a+b") as handle:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            else:
                with self._msvcrt_mutex:
                    _msvcrt_lock(handle, msvcrt)
                    try:
                        yield
                    finally:
                        _msvcrt_unlock(handle, msvcrt)

    # Briefs are content-addressed: a changed field makes a new brief with a new hash.
    def save_brief(self, brief):
        data = canonical_json(brief)
        digest = sha256_hex(data)
        path = self._path("briefs", digest + ".json")
        if not os.path.exists(path):
            _write_atomic(path, data)
        return digest

    def load_brief(self, digest):
        if not is_sha256(digest):
            raise StudioError("brief_unknown", "Unknown brief.", 404)
        try:
            with open(self._path("briefs", digest + ".json"), "rb") as handle:
                data = handle.read()
        except FileNotFoundError:
            raise StudioError("brief_unknown", "Unknown brief.", 404) from None
        if sha256_hex(data) != digest:
            raise StudioError("brief_tampered", "The stored brief does not match its hash. Nothing was run.", 500)
        return json.loads(data)

    def save_reference(self, mime_type, data):
        """Store an uploaded image under its hash after checking its type, size and signature."""
        if not is_image_type(mime_type):
            raise StudioError("unsupported_image", "Upload a PNG, JPEG or WebP image.")
        if not data:
            raise StudioError("empty_image", "The image is empty.")
        if len(data) > MAX_REFERENCE_BYTES:
            raise StudioError("image_too_large", "The image is larger than the local limit.", 413)
        if sniff_image(data) != mime_type:
            raise StudioError("image_signature_mismatch", "The file content does not match its image type.")
        digest = sha256_hex(data)
        path = self._path("inputs", digest)
        if not os.path.exists(path):
            _write_atomic(path, data)
        return {"sha256": digest, "mime_type": mime_type}

    def reference_size(self, ref):
        """Byte size of a reference that check_reference has accepted."""
        return os.path.getsize(self._path("inputs", ref["sha256"]))

    def check_reference(self, ref):
        """A brief may name only images that were uploaded to this studio."""
        if not isinstance(ref, dict) or not is_sha256(ref.get("sha256")) or not is_image_type(ref.get("mime_type")):
            raise StudioError("bad_reference", "Each reference must be an image uploaded to this studio.")
        if not os.path.exists(self._path("inputs", ref["sha256"])):
            raise StudioError("reference_unknown", "A reference image was not uploaded to this studio.", 404)
        return {"sha256": ref["sha256"], "mime_type": ref["mime_type"]}

    def read_references(self, brief):
        """Bytes of each reference, checked against its hash right before the call."""
        out = []
        for ref in brief["references"]:
            try:
                with open(self._path("inputs", ref["sha256"]), "rb") as handle:
                    data = handle.read()
            except FileNotFoundError:
                raise StudioError("reference_missing",
                                  "A reference image is missing from the studio data. Nothing was run.", 500) from None
            if sha256_hex(data) != ref["sha256"] or sniff_image(data) != ref["mime_type"]:
                raise StudioError("reference_tampered", "A reference image changed after upload. Nothing was run.", 500)
            out.append((ref["mime_type"], data))
        return out

    def issue_approval(self, brief_sha, now=None):
        """Create a single-use approval for one brief. Only the digest of the token is stored."""
        now = now or utcnow()
        self.load_brief(brief_sha)  # an approval must point at a stored brief
        # Hex, not urlsafe base64: a token that starts with "-" would be read as an option by `run --approval`.
        token = secrets.token_hex(24)
        with self._locked():
            registry = self._read_registry()
            _prune(registry, now)
            live = [r for r in registry.values()
                    if r["consumed_at"] is None and parse_time(r["expires_at"]) > now]
            if len(live) >= MAX_LIVE_APPROVALS:
                raise StudioError("approval_capacity",
                                  "Too many approvals are waiting. Run them or let them expire.", 409)
            expires = now + APPROVAL_TTL
            registry[sha256_hex(token.encode("utf-8"))] = {
                "brief_sha256": brief_sha,
                "issued_at": iso(now),
                "expires_at": iso(expires),
                "consumed_at": None,
            }
            self._write_registry(registry)
        return {"approval_id": token, "expires_at": iso(expires), "scope": "single_use"}

    def consume_approval(self, token, brief_sha, now=None):
        """Spend an approval. Raises unless it is unused, unexpired and bound to this brief."""
        now = now or utcnow()
        if not isinstance(token, str) or not token:
            raise StudioError("approval_unknown", "No approval was given. Approve the plan first.", 409)
        with self._locked():
            registry = self._read_registry()
            _prune(registry, now)
            record = registry.get(sha256_hex(token.encode("utf-8")))
            if record is None:
                raise StudioError("approval_unknown",
                                  "The approval is unknown or was pruned. Approve the plan again.", 409)
            if record["consumed_at"] is not None:
                raise StudioError("approval_used",
                                  "This approval was already used. Each paid run needs its own approval.", 409)
            if parse_time(record["expires_at"]) <= now:
                raise StudioError("approval_expired", "The approval expired. Approve the plan again.", 409)
            if record["brief_sha256"] != brief_sha:
                raise StudioError("approval_mismatch", "The brief changed after approval. Approve the new plan.", 409)
            record["consumed_at"] = iso(now)
            self._write_registry(registry)

    def _read_registry(self):
        try:
            with open(self._path("approvals.json"), encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            return {}
        except ValueError:
            # Unreadable state means no approval can be trusted, so nothing is spent.
            raise StudioError("registry_corrupt",
                              "The approval registry is not valid JSON. Nothing was run.", 500) from None

    def _write_registry(self, registry):
        _write_atomic(self._path("approvals.json"), json.dumps(registry, indent=2, sort_keys=True).encode("utf-8"))

    def write_output(self, name, data):
        _write_atomic(self._path("outputs", name), data)

    def write_run(self, record):
        data = json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
        _write_atomic(self._path("runs", record["run_id"] + ".json"), data)

    def update_run(self, run_id, change):
        """Read, change and write one run record under the store lock. Returns the new record."""
        with self._locked():
            record = self.load_run(run_id)
            change(record)
            self.write_run(record)
            return record

    def load_run(self, run_id):
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            raise StudioError("run_unknown", "Unknown run.", 404)
        try:
            with open(self._path("runs", run_id + ".json"), encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            raise StudioError("run_unknown", "Unknown run.", 404) from None

    def list_runs(self, limit=MAX_RUNS_LISTED):
        """Newest first. limit=None returns every run.

        A file whose identity (inode, mtime, size) has not changed since the last call is not parsed again.
        Every write adds keys or entries to a record, so its size changes on each write. A record that cannot be
        read is left out and named once on stderr, so one damaged file does not blank the listing. The returned
        records are shared with the cache, so callers must not change them.
        """
        with self._runs_lock:
            records, cache = [], {}
            for name in os.listdir(self._path("runs")):
                if not name.endswith(".json"):
                    continue
                path = self._path("runs", name)
                try:
                    info = os.stat(path)
                    identity = (info.st_ino, info.st_mtime_ns, info.st_size)
                    hit = self._runs_cache.get(name)
                    if hit is None or hit[0] != identity:
                        with open(path, encoding="utf-8") as handle:
                            hit = (identity, json.load(handle))
                except FileNotFoundError:  # removed since listdir
                    continue
                except ValueError:  # not valid JSON: named once per version of the file, then left out
                    if (name, identity) not in self._runs_warned:
                        self._runs_warned.add((name, identity))
                        sys.stderr.write(f"studio: run record {name} cannot be read and is left out of the listing\n")
                    continue
                cache[name] = hit
                records.append(hit[1])
            self._runs_cache = cache
        records.sort(key=lambda r: r["started_at"], reverse=True)
        return records if limit is None else records[:limit]

    def mark_stale_runs(self, now=None):
        """Mark runs that a stopped studio left as "running" as failed. Returns how many changed.

        Only runs started at least STALE_RUN_AFTER ago are touched. A live run should be younger than that:
        one provider call has no retry and a 300 s socket timeout. A record that cannot be read is skipped
        and left as it is, so a damaged file does not stop the studio from starting; the listing leaves it out
        and names it on stderr.
        """
        now = now or utcnow()
        changed = 0
        with self._locked():
            for name in os.listdir(self._path("runs")):
                if not name.endswith(".json"):
                    continue
                try:
                    with open(self._path("runs", name), encoding="utf-8") as handle:
                        record = json.load(handle)
                    started = parse_time(record["started_at"])
                except (OSError, ValueError, KeyError, TypeError):
                    continue
                if record.get("status") != "running" or started + STALE_RUN_AFTER > now:
                    continue
                record.update(status="failed", error="interrupted", error_message=INTERRUPTED_MESSAGE)
                record["finished_at"] = iso(now)
                self.write_run(record)
                changed += 1
        return changed

    def output_path(self, output_name):
        return self._path("outputs", output_name)

    def read_output(self, run_id):
        record = self.load_run(run_id)
        if record["status"] != "generated":
            raise StudioError("run_not_generated", "This run produced no image.", 404)
        try:
            with open(self._path("outputs", record["output"]), "rb") as handle:
                return handle.read(), record["mime_type"]
        except FileNotFoundError:
            raise StudioError("output_missing", "The generated image file is missing from the studio data.", 404) from None


LOCK_TIMEOUT_SECONDS = 30  # Windows only: how long an operation waits for the store lock before it gives up
CATALOG_STALE_DAYS = 90


def _msvcrt_lock(handle, module, timeout=LOCK_TIMEOUT_SECONDS):
    """msvcrt locks byte ranges from the current position. The lock file has at least one byte, so byte 0 is locked."""
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    limit = time.monotonic() + timeout
    while True:
        handle.seek(0)
        try:
            module.locking(handle.fileno(), module.LK_NBLCK, 1)
            return
        except OSError:
            if time.monotonic() >= limit:
                raise StudioError("store_busy", "Another studio operation holds the store lock. Try again in a moment.",
                                  503) from None
            time.sleep(0.05)


def _msvcrt_unlock(handle, module):
    handle.seek(0)
    module.locking(handle.fileno(), module.LK_UNLCK, 1)


def catalog_age_findings(catalog, today=None):
    """A warning, not an error, when the model catalog was verified long ago: its IDs, prices and limits may have changed."""
    today = today or date.today()
    verified = date.fromisoformat(catalog["verified_on"])
    age = (today - verified).days
    if age <= CATALOG_STALE_DAYS:
        return []
    return [{"level": "WARN", "code": "catalog_stale",
             "message": (f"The model catalog was verified {age} days ago (on {verified.isoformat()}). Check the Google "
                         "model pages before relying on its IDs, prices and limits.")}]


def _write_atomic(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _prune(registry, now):
    """Forget approvals whose last event is older than the retention window."""
    for digest in list(registry):
        record = registry[digest]
        last_event = parse_time(record["consumed_at"] or record["expires_at"])
        if last_event + APPROVAL_RETENTION <= now:
            del registry[digest]


def run_brief(catalog, store, client_factory, brief_sha, approval_id, now=None):
    """Spend one approval on one brief and record the outcome. Returns the run record.

    Order matters. The key is checked first, then the approval is consumed, and only
    then is the provider called. A failed call leaves the approval spent, so nothing
    retries on its own.
    """
    now = now or utcnow()
    brief = store.load_brief(brief_sha)
    if brief["model"] not in {offer["id"] for offer in offered_models(catalog)}:
        raise StudioError("model_not_offered", f"{brief['model']!r} is no longer offered. Build a new plan.", 409)
    client = client_factory(provider_of(catalog, brief["model"]))  # raises before anything is spent when the key is missing
    preflight = getattr(client, "preflight", None)  # config checks that need no call; also before anything is spent
    if preflight is not None:
        preflight(brief)
    store.consume_approval(approval_id, brief_sha, now)
    run_id = "run_" + secrets.token_hex(8)
    record = {
        "run_id": run_id,
        "brief_sha256": brief_sha,
        "model": brief["model"],
        "aspect_ratio": brief["aspect_ratio"],
        "image_size": brief["image_size"],
        "thinking_level": brief.get("thinking_level"),
        "status": "running",
        "started_at": iso(now),
        "reviews": [],
        "evaluations": [],
    }
    for key in ("parent_run_id", "case_id"):  # labels from the brief, so the history can show lineage and cases
        if key in brief:
            record[key] = brief[key]
    store.write_run(record)
    try:
        image = client.generate(brief, store.read_references(brief))
        mime_type = sniff_image(image["data"])
        if mime_type is None:
            raise ProviderError("unsupported_output", "The provider returned data that is not PNG, JPEG or WebP.")
        output = run_id + EXTENSIONS[mime_type]
        store.write_output(output, image["data"])
        record.update(status="generated", output=output, mime_type=mime_type,
                      checks=check_output(image["data"], mime_type, brief["aspect_ratio"]),
                      provider=image.get("provider", "unknown"))  # "fake" runs are placeholders, never compared
        if image.get("interaction_id"):  # the id a later edit can chain from, when the user asks for it
            record["interaction_id"] = image["interaction_id"]
    except StudioError as exc:
        record.update(status="failed", error=exc.code, error_message=exc.message)
    except Exception:
        record.update(status="failed", error="internal", error_message="Unexpected error. The approval stays used.")
        record["finished_at"] = iso(utcnow())
        store.write_run(record)
        raise
    except BaseException:  # Ctrl+C or a stop during the call: the run must not stay "running"
        record.update(status="failed", error="interrupted", error_message=INTERRUPTED_MESSAGE)
        record["finished_at"] = iso(utcnow())
        store.write_run(record)
        raise
    record["finished_at"] = iso(utcnow())
    store.write_run(record)
    return record


def _clean_note(note):
    if note is None:
        return ""
    if not isinstance(note, str):
        raise StudioError("bad_note", "The note must be text.")
    note = note.strip()
    if len(note) > MAX_NOTE_CHARS:
        raise StudioError("note_too_long", f"The note has more than {MAX_NOTE_CHARS} characters.")
    return note


def record_review(store, run_id, verdict, note=None, now=None):
    """Add a review verdict to a generated image. Reviews are appended, never overwritten."""
    now = now or utcnow()
    if not isinstance(verdict, str) or verdict not in REVIEW_VERDICTS:
        raise StudioError("invalid_verdict", "The verdict must be pass, targeted_fix, regenerate or blocked.")
    note = _clean_note(note)
    if verdict in NOTE_REQUIRED and not note:
        raise StudioError("note_required", f"'{verdict}' needs a note that says what is wrong.")
    def add_review(record):
        if record["status"] != "generated":
            raise StudioError("run_not_reviewable", "Only generated images can be reviewed.", 409)
        record["reviews"].append({"verdict": verdict, "note": note, "at": iso(now)})

    # Locked read-modify-write: two clicks cannot drop one review.
    return store.update_run(run_id, add_review)


def _clean_criteria(criteria):
    """Per-criterion ratings, each from 1 to 5. Only the names in CRITERIA are accepted."""
    if criteria is None:
        return {}
    if not isinstance(criteria, dict):
        raise StudioError("bad_criteria", "Criteria must map a criterion name to a rating.")
    for name, value in criteria.items():
        if name not in CRITERIA:
            raise StudioError("unknown_criterion", f"{name!r} is not a criterion. Use one of: {', '.join(CRITERIA)}.")
        if isinstance(value, bool) or not isinstance(value, int) or value not in RATINGS:
            raise StudioError("invalid_rating", f"The rating for {name} must be a whole number from 1 to 5.")
    return dict(criteria)


def record_evaluation(store, run_id, rating, note=None, now=None, criteria=None):
    """Add a 1-5 rating to a generated image. Ratings are appended; the latest one counts.

    `criteria` optionally rates each of CRITERIA on the same scale. Older entries have no criteria.
    """
    now = now or utcnow()
    if isinstance(rating, bool) or not isinstance(rating, int) or rating not in RATINGS:
        raise StudioError("invalid_rating", "The rating must be a whole number from 1 to 5.")
    note = _clean_note(note)
    scores = _clean_criteria(criteria)
    def add_evaluation(record):
        if record["status"] != "generated":
            raise StudioError("run_not_evaluable", "Only generated images can be rated.", 409)
        record["evaluations"].append({"rating": rating, "note": note, "at": iso(now), "criteria": scores})

    return store.update_run(run_id, add_evaluation)


REFINE_TEMPLATE = ("Edit the attached image. Change only this: {edit}. Keep everything else exactly as it is: "
                   "the subject, the composition, the framing, the colours, the lighting, and every element that "
                   "is not part of the change.")


def plan_refinement(catalog, store, parent_run_id, edit, *, references=(), model_id=None, aspect_ratio=None,
                    image_size=None, thinking_level=None, chain=False, case_id=None):
    """Plan one targeted edit of a generated image. Nothing is spent here.

    The parent's output goes in as a reference, byte for byte; its hash is checked against the run record when
    the record has one. Model, ratio and size default to the parent's. `chain` also sends the parent's interaction
    id, and only for the same model, because nothing documents a chain across models.
    """
    if not isinstance(edit, str) or not edit.strip():
        raise StudioError("empty_edit", "Say what to change.")
    parent = store.load_run(parent_run_id)
    if parent["status"] != "generated":
        raise StudioError("run_not_generated", "Only a generated image can be edited.", 409)
    data, mime_type = store.read_output(parent_run_id)
    if len(data) > MAX_REFERENCE_BYTES:
        raise StudioError("parent_too_large",
                          "The output is larger than the 10 MB reference limit, so it cannot be an edit reference.", 413)
    expected = (parent.get("checks") or {}).get("sha256")
    if expected and expected != sha256_hex(data):
        raise StudioError("output_tampered", "The output file does not match its record. Nothing was planned.", 500)
    target = model_id or parent["model"]
    previous = None
    if chain:
        if target != parent["model"]:
            raise StudioError("chain_model_mismatch", "A chained edit must use the same model as the run it chains from.")
        if not parent.get("interaction_id"):
            raise StudioError("chain_unavailable", "This run has no interaction id to chain from. Edit without chain.", 409)
        previous = parent["interaction_id"]
    parent_ref = store.save_reference(mime_type, data)
    return build_brief(catalog, store, prompt=REFINE_TEMPLATE.format(edit=edit.strip()), model_id=target,
                       aspect_ratio=aspect_ratio or parent["aspect_ratio"],
                       image_size=image_size or parent["image_size"],
                       references=[parent_ref, *references], thinking_level=thinking_level,
                       previous_interaction_id=previous, parent_run_id=parent_run_id, case_id=case_id)


def preferences(store):
    """Average of each run's latest rating, per model and per aspect ratio."""
    totals = {"model": {}, "aspect_ratio": {}}
    for record in store.list_runs(limit=None):
        if not record["evaluations"]:
            continue
        rating = record["evaluations"][-1]["rating"]
        for key in totals:
            count, total = totals[key].get(record[key], (0, 0))
            totals[key][record[key]] = (count + 1, total + rating)
    return {
        key: {label: {"count": count, "average": round(total / count, 2)}
              for label, (count, total) in values.items()}
        for key, values in totals.items()
    }


def summarize_run(record):
    reviews, evaluations = record["reviews"], record["evaluations"]
    return {
        "run_id": record["run_id"],
        "status": record["status"],
        "model": record["model"],
        "aspect_ratio": record["aspect_ratio"],
        "image_size": record["image_size"],
        "started_at": record["started_at"],
        "output": record.get("output"),
        "error": record.get("error"),
        "error_message": record.get("error_message"),
        "verdict": reviews[-1]["verdict"] if reviews else None,
        "rating": evaluations[-1]["rating"] if evaluations else None,
        "parent_run_id": record.get("parent_run_id"),
        "case_id": record.get("case_id"),
        "thinking_level": record.get("thinking_level"),
        "provider": record.get("provider"),
        "checks": record.get("checks"),
    }
