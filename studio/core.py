"""Rules for the studio: frozen briefs, single-use approvals, reviews and evaluations.

Stdlib only, and nothing here touches the network. client.py makes the paid call,
and run_brief() calls it only after the approval has been consumed.

Data lives in one directory (studio/data by default; git ignores it):
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
from datetime import datetime, timedelta, timezone

try:
    import fcntl
except ImportError:  # not POSIX: the store refuses to run instead of running unlocked
    fcntl = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from validate_prompt import validate  # noqa: E402

APPROVAL_TTL = timedelta(minutes=30)  # window taken from banana-claude's approval design (audit I1)
APPROVAL_RETENTION = timedelta(hours=24)  # finished approvals stay this long, so a reuse says "used"
MAX_LIVE_APPROVALS = 64
MAX_PROMPT_CHARS = 8000  # local cap; no official limit was found
MAX_NOTE_CHARS = 2000  # local cap for review and evaluation notes
MAX_REFERENCE_BYTES = 10 * 1024 * 1024  # local cap; no official limit was found
MAX_RUNS_LISTED = 50
REVIEW_VERDICTS = ("pass", "targeted_fix", "regenerate", "blocked")
NOTE_REQUIRED = ("targeted_fix", "blocked")
RATINGS = (1, 2, 3, 4, 5)
EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
RUN_ID = re.compile(r"run_[0-9a-f]{16}")


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
    return datetime.fromisoformat(text)


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


def allowed_sizes(catalog, model):
    """Priced sizes the studio offers. 512 px stays hidden until the catalog confirms its JSON value."""
    confirmed = catalog["image_sizes"]["512_json_value_confirmed"]
    prices = model.get("prices_usd_per_image", {})
    return [s for s in model.get("sizes", []) if s in prices and (s != "512" or confirmed)]


def max_references(model):
    """Smallest documented reference limit. The catalog does not map limits to models, so this is conservative."""
    limits = [v for v in model.get("reference_limits", {}).values() if v]
    return min(limits) if limits else 0


def offered_models(catalog):
    """Current or active models, never previews. Deprecated and shut-down models are not offered."""
    offers = []
    for model in catalog["models"]:
        if model["status"] not in ("current", "active") or model["id"].endswith("-preview"):
            continue
        sizes = allowed_sizes(catalog, model)
        offers.append({
            "id": model["id"],
            "name": model.get("display_name", model["id"]),
            "sizes": sizes,
            "prices_usd_per_image": {s: model["prices_usd_per_image"][s] for s in sizes},
            "max_references": max_references(model),
        })
    return offers


def build_brief(catalog, store, *, prompt, model_id, aspect_ratio, image_size, references):
    """Check a request and freeze it as a brief. Returns the plan that the user approves.

    `references` is a list of {"sha256", "mime_type"} entries uploaded earlier.
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
    if aspect_ratio not in catalog["aspect_ratios"]:
        raise StudioError("aspect_ratio_not_official",
                          f"{aspect_ratio!r} is not one of the {len(catalog['aspect_ratios'])} official aspect ratios.")
    if image_size not in offer["sizes"]:
        raise StudioError("image_size_not_allowed", f"{image_size!r} is not available for {model_id}.")
    if not isinstance(references, list) or len(references) > offer["max_references"]:
        raise StudioError("too_many_references",
                          f"{model_id} takes at most {offer['max_references']} reference images here.")
    refs = [store.check_reference(ref) for ref in references]
    findings = validate(prompt, model_id, catalog)
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
    return {
        "brief_sha256": store.save_brief(brief),
        "brief": brief,
        "estimated_cost_usd": offer["prices_usd_per_image"][image_size],
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

    def _path(self, *parts):
        return os.path.join(self.root, *parts)

    @contextlib.contextmanager
    def _locked(self):
        if fcntl is None:
            raise StudioError("unsupported_platform",
                              "The studio needs POSIX file locks and refuses to run without them.", 500)
        with open(self._path(".lock"), "a") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

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
        token = secrets.token_urlsafe(24)
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
        """Newest first. limit=None returns every run."""
        records = []
        for name in os.listdir(self._path("runs")):
            if name.endswith(".json"):
                with open(self._path("runs", name), encoding="utf-8") as handle:
                    records.append(json.load(handle))
        records.sort(key=lambda r: r["started_at"], reverse=True)
        return records if limit is None else records[:limit]

    def read_output(self, run_id):
        record = self.load_run(run_id)
        if record["status"] != "generated":
            raise StudioError("run_not_generated", "This run produced no image.", 404)
        try:
            with open(self._path("outputs", record["output"]), "rb") as handle:
                return handle.read(), record["mime_type"]
        except FileNotFoundError:
            raise StudioError("output_missing", "The generated image file is missing from the studio data.", 404) from None


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
    client = client_factory()  # raises before anything is spent when the key is missing
    store.consume_approval(approval_id, brief_sha, now)
    run_id = "run_" + secrets.token_hex(8)
    record = {
        "run_id": run_id,
        "brief_sha256": brief_sha,
        "model": brief["model"],
        "aspect_ratio": brief["aspect_ratio"],
        "image_size": brief["image_size"],
        "status": "running",
        "started_at": iso(now),
        "reviews": [],
        "evaluations": [],
    }
    store.write_run(record)
    try:
        image = client.generate(brief, store.read_references(brief))
        mime_type = sniff_image(image["data"])
        if mime_type is None:
            raise ProviderError("unsupported_output", "The provider returned data that is not PNG, JPEG or WebP.")
        output = run_id + EXTENSIONS[mime_type]
        store.write_output(output, image["data"])
        record.update(status="generated", output=output, mime_type=mime_type)
    except StudioError as exc:
        record.update(status="failed", error=exc.code, error_message=exc.message)
    except Exception:
        record.update(status="failed", error="internal", error_message="Unexpected error. The approval stays used.")
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


def record_evaluation(store, run_id, rating, note=None, now=None):
    """Add a 1-5 rating to a generated image. Ratings are appended; the latest one counts."""
    now = now or utcnow()
    if isinstance(rating, bool) or not isinstance(rating, int) or rating not in RATINGS:
        raise StudioError("invalid_rating", "The rating must be a whole number from 1 to 5.")
    note = _clean_note(note)
    def add_evaluation(record):
        if record["status"] != "generated":
            raise StudioError("run_not_evaluable", "Only generated images can be rated.", 409)
        record["evaluations"].append({"rating": rating, "note": note, "at": iso(now)})

    return store.update_run(run_id, add_evaluation)


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
    }
