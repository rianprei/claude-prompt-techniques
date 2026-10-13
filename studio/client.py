"""Client for the Gemini Interactions endpoint, the one the official image guide uses.

The key is read from GEMINI_API_KEY when a run starts. It goes only in the
x-goog-api-key header, and it never appears in a URL, a log line or an error message.
"""

import base64
import json
import os
import struct
import urllib.error
import urllib.request
import zlib

from .core import ProviderError, StudioError
from contracts import load_catalog  # studio/__init__.py put scripts/ on sys.path

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
KEY_ENV = "GEMINI_API_KEY"
TIMEOUT_SECONDS = 300  # our value; the upstream timeout is UNKNOWN (audit I9)
SAFETY_REASONS = tuple(load_catalog()["safety_finish_reasons"])


def api_key_from_env():
    return os.environ.get(KEY_ENV, "").strip() or None


def build_request(brief, references):
    """Endpoint, headers without the key, and the JSON body for one generation call."""
    parts = [{"type": "text", "text": brief["prompt"]}]
    for mime_type, data in references:
        parts.append({"type": "image", "data": base64.b64encode(data).decode("ascii"), "mime_type": mime_type})
    body = {
        "model": brief["model"],
        "input": parts,
        "response_format": {
            "type": "image",
            "aspect_ratio": brief["aspect_ratio"],
            "image_size": brief["image_size"],
        },
    }
    return ENDPOINT, {"Content-Type": "application/json"}, json.dumps(body, ensure_ascii=False).encode("utf-8")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects. urllib would replay the key header on the new location."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def urllib_transport(url, headers, body, timeout):
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:  # before OSError: HTTPError is a subclass of it
        with exc:  # close the response; only the status and body are needed
            return exc.code, exc.read()
    except OSError as exc:  # URLError and timeouts
        raise ProviderError("network_error", f"Could not reach the Gemini API ({type(exc).__name__}).") from None


def find_image(data):
    """The image block of an Interactions response: output_image, else the first image in the model steps."""
    output = data.get("output_image")
    if isinstance(output, dict) and output.get("data"):
        return output
    steps = data.get("steps")
    for step in steps if isinstance(steps, list) else []:
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        content = step.get("content")
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict) and block.get("type") == "image" and block.get("data"):
                return block
    return None


def _provider_message(text):
    try:
        message = json.loads(text).get("error", {}).get("message", "")
    except (ValueError, AttributeError):
        return ""
    return str(message)[:200]


def parse_response(status, payload, api_key=""):
    text = payload.decode("utf-8", "replace") if isinstance(payload, bytes) else str(payload)
    if status != 200:
        message = f"Gemini API returned HTTP {status}. {_provider_message(text)}".strip()
        if api_key:
            message = message.replace(api_key, "[redacted]")
        raise ProviderError(f"http_{status}", message)
    try:
        data = json.loads(text)
    except ValueError:
        raise ProviderError("bad_response", "The Gemini API returned something that is not JSON.") from None
    image = find_image(data) if isinstance(data, dict) else None
    if image is None:
        reason = next((r for r in SAFETY_REASONS if r in text), None)
        if reason:
            raise ProviderError("safety_block",
                                f"The provider blocked this output ({reason}). Change the brief yourself; "
                                "the studio does not rephrase it.")
        raise ProviderError("no_image", "The response has no image.")
    try:
        data_bytes = base64.b64decode(image["data"], validate=True)
    except (ValueError, TypeError):
        raise ProviderError("bad_response", "The image data is not valid base64.") from None
    return {"data": data_bytes, "mime_type": image.get("mime_type")}


class GeminiClient:
    def __init__(self, api_key, transport=urllib_transport):
        if not api_key:
            raise StudioError("missing_api_key", f"{KEY_ENV} is not set where the studio runs.", 412)
        self._api_key = api_key
        self._transport = transport

    def generate(self, brief, references):
        url, headers, body = build_request(brief, references)
        headers["x-goog-api-key"] = self._api_key
        status, payload = self._transport(url, headers, body, TIMEOUT_SECONDS)
        return parse_response(status, payload, self._api_key)


class FakeClient:
    """Stand-in for demos and tests: no network call, no cost, and a plain grey placeholder."""

    def generate(self, brief, references):
        return {"data": placeholder_png(), "mime_type": "image/png"}


def placeholder_png(width=64, height=64):
    """A flat grey PNG built with zlib and struct, so no imaging library is needed."""
    row = b"\x00" + b"\x80\x80\x80" * width  # filter byte 0, then RGB pixels
    raw = row * height

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def real_client():
    """Client for the live API, built from the environment at run time and never from a file."""
    return GeminiClient(api_key_from_env())
