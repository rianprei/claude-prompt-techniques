"""Adapters for the image providers. Each one builds the request, reads the reply, and returns the image bytes.

A key is read from its environment variable when a run starts. It goes only in a header or a form field the provider
documents, never in a URL, a log line or an error message. A refused or failed call raises ProviderError; run_brief keeps
the approval spent.

Gemini is not here: its client lives in client.py and stays as it was. Each adapter follows the official pages named in its
catalog entry (references/studio-models.json). Where those pages did not show a field, the entry or studio/README.md
marks it PARTIAL or UNKNOWN. A field that a page did not show is sent only where the entry marks it that way (for example
the ComfyUI upload).
"""

import base64
import copy
import json
import os
import secrets
import time
from urllib.parse import quote, urlencode, urlsplit

from .core import EXTENSIONS, ProviderError, StudioError
from .transport import IMAGE_LIMIT_BYTES, JSON_LIMIT_BYTES, fetch_image, http_request, multipart

POLL_INTERVAL_SECONDS = 1.0
COMFYUI_URL_ENV = "COMFYUI_URL"
COMFYUI_DEFAULT_URL = "http://127.0.0.1:8188"  # the ComfyUI server's default address
COMFYUI_WORKFLOW_ENV = "COMFYUI_WORKFLOW"
WORKFLOW_LIMIT_BYTES = 1024 * 1024
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
RATE_LIMIT_HINT = (" Limits are set by the provider's account and tier. The approval is spent: plan again to retry.")


def _provider_message(payload):
    """The message a provider puts in an error body, if it sends JSON. Short, and without its request echo."""
    try:
        data = json.loads(payload.decode("utf-8", "replace"))
    except ValueError:
        return ""
    if not isinstance(data, dict):
        return ""
    error = data.get("error", data.get("message", ""))
    if isinstance(error, dict):
        error = error.get("message", "")
    return str(error)[:200]


def _decode_image(text):
    try:
        return base64.b64decode(text, validate=True)
    except (ValueError, TypeError):
        raise ProviderError("bad_response", "The image data is not valid base64.") from None


def _first(reply, key):
    """The first object of a list field, or None."""
    items = reply.get(key)
    if isinstance(items, list) and items and isinstance(items[0], dict):
        return items[0]
    return None


class Adapter:
    """Shared plumbing: the key check, the redacted error, JSON replies and the injected transport."""

    key = ""
    name = ""
    env = ()  # every variable must be set, or the run is refused before the approval is spent
    secret_env = ()  # the values of these are removed from every message

    def __init__(self, env, timeout, transport=http_request, sleep=time.sleep, clock=time.monotonic):
        missing = [name for name in self.env if not env.get(name, "").strip()]
        if missing:
            raise StudioError("missing_api_key", f"{', '.join(missing)} is not set where the studio runs.", 412)
        self._env = {name: env.get(name, "").strip() for name in self.env}
        self._secrets = [env[name].strip() for name in self.secret_env if env.get(name, "").strip()]
        self._timeout = timeout
        self._transport = transport
        self._sleep = sleep
        self._clock = clock

    def preflight(self, brief):
        """Checks that need no network and no key use. run_brief calls it before the approval is spent."""

    def _no_references(self, refs):
        """Refuse references for a provider used here for generation only."""
        if refs:
            raise StudioError("references_not_supported", f"{self.name} is used here for generation only; take the references out.")

    def _redact(self, text):
        for value in self._secrets:
            text = text.replace(value, "[redacted]")
        return text

    def _send(self, method, url, headers, body=None, limit=JSON_LIMIT_BYTES):
        status, payload = self._transport(method, url, headers, body, self._timeout, limit)
        if not 200 <= status < 300:
            message = f"{self.name} returned HTTP {status}. {_provider_message(payload)}".strip()
            if status == 429:
                message += RATE_LIMIT_HINT
            raise ProviderError(f"http_{status}", self._redact(message))
        return payload

    def _json(self, payload):
        try:
            data = json.loads(payload.decode("utf-8", "replace"))
        except ValueError:
            raise ProviderError("bad_response", f"{self.name} returned something that is not JSON.") from None
        if not isinstance(data, dict):
            raise ProviderError("bad_response", f"{self.name} returned JSON that is not an object.")
        return data

    def _result(self, data):
        return {"data": data, "mime_type": None, "provider": self.key, "interaction_id": None}

    def _b64_result(self, reply):
        item = _first(reply, "data")
        text = item.get("b64_json") if item else None
        if not isinstance(text, str):
            raise ProviderError("no_image", f"The {self.name} response has no image.")
        return self._result(_decode_image(text))

    def _url_result(self, reply):
        item = _first(reply, "data")
        url = item.get("url") if item else None
        if not isinstance(url, str):
            raise ProviderError("no_image", f"The {self.name} response has no image.")
        return self._result(fetch_image(url, self._timeout, self._transport))


class OpenAIImages(Adapter):
    """GPT Image models. Generation without references; the edit endpoint takes the references as image[] parts."""

    key, name, env, secret_env = "openai", "OpenAI", ("OPENAI_API_KEY",), ("OPENAI_API_KEY",)
    BASE = "https://api.openai.com/v1/images"

    def generate(self, brief, refs):
        auth = {"Authorization": f"Bearer {self._env['OPENAI_API_KEY']}"}
        if refs:
            fields = [("model", brief["model"]), ("prompt", brief["prompt"]), ("size", brief["image_size"]), ("n", "1")]
            files = [("image[]", f"reference-{index}{EXTENSIONS[mime]}", mime, data)
                     for index, (mime, data) in enumerate(refs, 1)]
            content_type, body = multipart(fields, files)
            reply = self._json(self._send("POST", f"{self.BASE}/edits", {**auth, "Content-Type": content_type}, body))
        else:
            body = json.dumps({"model": brief["model"], "prompt": brief["prompt"], "size": brief["image_size"], "n": 1},
                              ensure_ascii=False).encode("utf-8")
            reply = self._json(self._send("POST", f"{self.BASE}/generations",
                                          {**auth, "Content-Type": "application/json"}, body))
        return self._b64_result(reply)


class BlackForestLabs(Adapter):
    """FLUX 3 Image: submit, then poll the polling_url the submit returns until the job is Ready."""

    key, name, env, secret_env = "bfl", "Black Forest Labs", ("BFL_API_KEY",), ("BFL_API_KEY",)
    BASE = "https://api.bfl.ai/v1"
    PENDING = ("Pending", "Reasoning", "Generating")  # the guide: in progress, keep polling
    MODERATED = ("Request Moderated", "Content Moderated")  # the guide: blocked input, or blocked output
    FAILED = ("Error", "Failed", "Task not found")  # the guide's Error and Task not found; Failed is checked by its examples

    def generate(self, brief, refs):
        key = self._env["BFL_API_KEY"]
        payload = {"prompt": brief["prompt"], "aspect_ratio": brief["aspect_ratio"]}
        if refs:
            payload["images"] = [base64.b64encode(data).decode("ascii") for _mime, data in refs]
        headers = {"x-key": key, "Content-Type": "application/json"}
        job = self._json(self._send("POST", f"{self.BASE}/{brief['model']}", headers,
                                    json.dumps(payload, ensure_ascii=False).encode("utf-8")))
        polling = job.get("polling_url")
        if not _is_bfl_host(polling):
            raise ProviderError("bad_polling_url", "The Black Forest Labs reply named a polling address outside bfl.ai. "
                                                   "The key was not sent there.")
        deadline = self._clock() + self._timeout
        while True:
            info = self._poll_once(polling, key)
            state = info.get("status")
            if state == "Ready":
                sample = (info.get("result") or {}).get("sample")
                if not isinstance(sample, str):
                    raise ProviderError("no_image", "The Black Forest Labs reply is Ready but names no image.")
                return self._result(fetch_image(sample, self._timeout, self._transport))  # the guide: download within 1 hour
            if state in self.PENDING:
                if self._clock() >= deadline:
                    raise ProviderError("timeout", "The image did not finish before the studio's time limit. "
                                                   "The approval stays spent.")
                self._sleep(POLL_INTERVAL_SECONDS)
                continue
            if state in self.MODERATED:
                raise ProviderError("safety_block", f"Black Forest Labs moderated this request ({state}). Change the brief "
                                                    "yourself; the studio does not rephrase it.")
            if state in self.FAILED:
                raise ProviderError("provider_error", f"Black Forest Labs reported {state}. Nothing was saved.")
            # A state the guide does not list is not polled again: it stops the run at once.
            raise ProviderError("unexpected_status", f"Black Forest Labs returned a status the studio does not know "
                                                     f"({str(state)[:40]!r}). Nothing was saved.")

    def _poll_once(self, url, key):
        """One poll. A failed task can come back as HTTP 503 with a JSON body whose status the guide lists; any other
        non-2xx reply is an HTTP error, even when its body happens to carry a status field."""
        status, payload = self._transport("GET", url, {"x-key": key}, None, self._timeout, JSON_LIMIT_BYTES)
        if 200 <= status < 300:
            return self._json(payload)
        try:
            info = json.loads(payload.decode("utf-8", "replace"))
        except ValueError:
            info = None
        listed = self.PENDING + self.MODERATED + self.FAILED + ("Ready",)
        if isinstance(info, dict) and info.get("status") in listed:
            return info
        raise ProviderError(f"http_{status}", self._redact(f"{self.name} returned HTTP {status}. {_provider_message(payload)}".strip()))


def _is_bfl_host(url):
    """True for an HTTPS address on bfl.ai or one of its subdomains. The key goes only to such an address."""
    if not isinstance(url, str):
        return False
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (host == "bfl.ai" or host.endswith(".bfl.ai")) and not parts.username


class Ideogram(Adapter):
    """Ideogram generation from a prompt; the precise edit (one image and a prompt) is documented for 4.5 only."""

    key, name, env, secret_env = "ideogram", "Ideogram", ("IDEOGRAM_API_KEY",), ("IDEOGRAM_API_KEY",)
    BASE = "https://api.ideogram.ai/v2/image"
    EDIT_MODELS = ("ideogram-4-5",)

    def preflight(self, brief):
        if brief.get("references") and brief["model"] not in self.EDIT_MODELS:
            raise StudioError("references_not_supported", f"{brief['model']} takes no reference image here; the precise edit "
                                                          "is documented for ideogram-4-5 only.")

    def generate(self, brief, refs):
        headers = {"Api-Key": self._env["IDEOGRAM_API_KEY"]}
        model = brief["model"]
        if refs:
            mime, data = refs[0]
            content_type, body = multipart([("prompt", brief["prompt"])], [("image", f"source{EXTENSIONS[mime]}", mime, data)])
            reply = self._json(self._send("POST", f"{self.BASE}/precise-edit/{model}",
                                          {**headers, "Content-Type": content_type}, body))
        else:
            body = json.dumps({"prompt": brief["prompt"]}, ensure_ascii=False).encode("utf-8")
            reply = self._json(self._send("POST", f"{self.BASE}/generate/{model}",
                                          {**headers, "Content-Type": "application/json"}, body))
        return self._url_result(reply)


class Recraft(Adapter):
    """Recraft raster generation. The studio asks for base64, so no link has to be downloaded."""

    key, name, env, secret_env = "recraft", "Recraft", ("RECRAFT_API_KEY",), ("RECRAFT_API_KEY",)
    BASE = "https://external.api.recraft.ai/v1"

    def preflight(self, brief):
        self._no_references(brief.get("references"))

    def generate(self, brief, refs):
        self._no_references(refs)
        body = json.dumps({"prompt": brief["prompt"], "model": brief["model"], "size": brief["image_size"], "n": 1,
                           "response_format": "b64_json"}, ensure_ascii=False).encode("utf-8")
        headers = {"Authorization": f"Bearer {self._env['RECRAFT_API_KEY']}", "Content-Type": "application/json"}
        return self._b64_result(self._json(self._send("POST", f"{self.BASE}/images/generations", headers, body)))


class BytePlus(Adapter):
    """Seedream on BytePlus ModelArk. References go as data URLs; the reply is base64 because the studio asks for it."""

    key, name, env, secret_env = "byteplus", "BytePlus ModelArk", ("ARK_API_KEY",), ("ARK_API_KEY",)
    URL = "https://ark.ap-southeast.bytepluses.com/api/v3/images/generations"

    def generate(self, brief, refs):
        body = {"model": brief["model"], "prompt": brief["prompt"], "size": brief["image_size"],
                "response_format": "b64_json", "sequential_image_generation": "disabled"}
        if refs:
            body["image"] = [f"data:{mime};base64," + base64.b64encode(data).decode("ascii") for mime, data in refs]
        headers = {"Authorization": f"Bearer {self._env['ARK_API_KEY']}", "Content-Type": "application/json"}
        reply = self._json(self._send("POST", self.URL, headers, json.dumps(body, ensure_ascii=False).encode("utf-8")))
        return self._b64_result(reply)


class Stability(Adapter):
    """Stable Image Core and Ultra, and the SD3.5 models. The reply is the image itself, because the request asks for image/*."""

    key, name, env, secret_env = "stability", "Stability AI", ("STABILITY_API_KEY",), ("STABILITY_API_KEY",)
    BASE = "https://api.stability.ai/v2beta/stable-image/generate"
    CORE_ULTRA = {"stable-image-core": "core", "stable-image-ultra": "ultra"}  # no model field
    SD3_MODELS = ("sd3.5-large", "sd3.5-large-turbo", "sd3.5-medium")  # the model enum of /generate/sd3 in the API reference

    def _call(self, model):
        """(endpoint path, extra form fields) for a model, or None when the studio has no endpoint for it."""
        if model in self.CORE_ULTRA:
            return f"{self.BASE}/{self.CORE_ULTRA[model]}", []
        if model in self.SD3_MODELS:
            return f"{self.BASE}/sd3", [("model", model)]
        return None

    def preflight(self, brief):
        self._no_references(brief.get("references"))
        if self._call(brief["model"]) is None:
            raise StudioError("model_not_offered", f"{brief['model']!r} has no Stability endpoint in the studio.", 409)

    def generate(self, brief, refs):
        self._no_references(refs)
        call = self._call(brief["model"])
        if call is None:
            raise StudioError("model_not_offered", f"{brief['model']!r} has no Stability endpoint in the studio.", 409)
        url, extra = call
        content_type, body = multipart([("prompt", brief["prompt"]), ("aspect_ratio", brief["aspect_ratio"]),
                                        ("output_format", "png")] + extra)
        headers = {"authorization": f"Bearer {self._env['STABILITY_API_KEY']}", "accept": "image/*",
                   "Content-Type": content_type}
        return self._result(self._send("POST", url, headers, body, IMAGE_LIMIT_BYTES))


class ComfyUI(Adapter):
    """A workflow that the user runs on their own ComfyUI server, in API format.

    The workflow file names the nodes the studio fills in: a CLIPTextEncode node titled 'Prompt' takes the prompt, a
    LoadImage node titled 'Reference' takes the reference image, and every EmptyLatentImage node takes the size.
    """

    key, name, env, secret_env = "comfyui", "ComfyUI", (COMFYUI_WORKFLOW_ENV,), ()

    def __init__(self, env, timeout, transport=http_request, sleep=time.sleep, clock=time.monotonic):
        super().__init__(env, timeout, transport, sleep, clock)
        self._base = (env.get(COMFYUI_URL_ENV, "").strip() or COMFYUI_DEFAULT_URL).rstrip("/")
        host = (urlsplit(self._base).hostname or "").lower()
        if urlsplit(self._base).scheme not in ("http", "https") or host not in LOOPBACK_HOSTS:
            raise StudioError("comfyui_not_local", "COMFYUI_URL must point at this machine (127.0.0.1, localhost or ::1). "
                                                   "The studio does not send prompts or images to another host.", 412)
        # Read and checked now, so a broken workflow is refused before any approval is spent.
        self._doc = self._load_workflow()
        self._titled(self._doc, "CLIPTextEncode", "Prompt")

    def preflight(self, brief):
        if brief.get("references"):
            self._titled(self._doc, "LoadImage", "Reference")

    def _load_workflow(self):
        path = self._env[COMFYUI_WORKFLOW_ENV]
        if not os.path.isfile(path):
            raise StudioError("comfyui_workflow", f"No workflow file at {path}.", 412)
        if os.path.getsize(path) > WORKFLOW_LIMIT_BYTES:
            raise StudioError("comfyui_workflow", "The workflow file is larger than the studio's limit.", 412)
        try:
            with open(path, encoding="utf-8") as handle:
                workflow = json.load(handle)
        except ValueError:
            raise StudioError("comfyui_workflow", "The workflow file is not valid JSON.", 412) from None
        if not isinstance(workflow, dict):
            raise StudioError("comfyui_workflow", "The workflow must be a JSON object of nodes (API format).", 412)
        return workflow

    @staticmethod
    def _titled(workflow, class_type, title, required=True):
        nodes = [node for node in workflow.values() if isinstance(node, dict) and node.get("class_type") == class_type
                 and isinstance(node.get("_meta"), dict) and node["_meta"].get("title") == title]
        if len(nodes) != 1 and required:
            raise StudioError("comfyui_workflow",
                              f"The workflow needs exactly one {class_type} node titled '{title}'; it has {len(nodes)}.", 412)
        return nodes[0] if len(nodes) == 1 else None

    def _prepare(self, brief, refs, workflow, client_id):
        self._titled(workflow, "CLIPTextEncode", "Prompt")["inputs"]["text"] = brief["prompt"]
        if refs:
            node = self._titled(workflow, "LoadImage", "Reference")
            node["inputs"]["image"] = self._upload(refs[0], client_id)
        width, height = brief["image_size"].split("x") if "x" in brief["image_size"] else (None, None)
        for node in workflow.values():
            if isinstance(node, dict) and node.get("class_type") == "EmptyLatentImage" and width:
                node["inputs"]["width"], node["inputs"]["height"] = int(width), int(height)
        return workflow

    def _upload(self, ref, client_id):
        mime, data = ref
        content_type, body = multipart([], [("image", f"reference{EXTENSIONS[mime]}", mime, data)])
        reply = self._json(self._send("POST", f"{self._base}/upload/image", {"Content-Type": content_type}, body))
        name = reply.get("name")
        if not isinstance(name, str) or not name:
            raise ProviderError("bad_response", "The ComfyUI upload reply names no file.")
        return name

    def generate(self, brief, refs):
        client_id = secrets.token_hex(8)
        workflow = self._prepare(brief, refs, copy.deepcopy(self._doc), client_id)
        body = json.dumps({"prompt": workflow, "client_id": client_id}, ensure_ascii=False).encode("utf-8")
        submitted = self._json(self._send("POST", f"{self._base}/prompt", {"Content-Type": "application/json"}, body))
        prompt_id = submitted.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ProviderError("bad_response", "ComfyUI returned no prompt_id.")
        deadline = self._clock() + self._timeout
        while True:
            history = self._json(self._send("GET", f"{self._base}/history/{quote(prompt_id, safe='')}", {}))
            entry = history.get(prompt_id)
            if isinstance(entry, dict) and entry.get("outputs"):  # the official example's completion test
                return self._result(self._fetch_output(entry["outputs"]))
            if self._clock() >= deadline:
                raise ProviderError("timeout", "The ComfyUI workflow did not finish before the studio's time limit. "
                                               "The approval stays spent.")
            self._sleep(POLL_INTERVAL_SECONDS)

    def _fetch_output(self, outputs):
        for node_output in outputs.values():
            for image in (node_output.get("images") or []) if isinstance(node_output, dict) else []:
                if isinstance(image, dict) and image.get("type") == "output" and isinstance(image.get("filename"), str):
                    query = urlencode({"filename": image["filename"], "subfolder": image.get("subfolder", ""),
                                       "type": "output"})
                    status, payload = self._transport("GET", f"{self._base}/view?{query}", {}, None, self._timeout,
                                                      IMAGE_LIMIT_BYTES)
                    if not 200 <= status < 300:
                        raise ProviderError(f"view_http_{status}", f"ComfyUI would not return its output (HTTP {status}).")
                    return payload
        raise ProviderError("no_image", "The ComfyUI workflow finished with no output image.")


class Firefly(Adapter):
    """Adobe Firefly Services, synchronous Generate Image. It signs in with the project's client credentials.

    The reply's outputs[0].image.url is a pre-signed link, so the studio downloads it at once. The shape comes from the
    official tutorial examples; the reference schema was not readable, and the async variant (a different reply) is not used.
    """

    key, name = "firefly", "Adobe Firefly"
    env = ("FIREFLY_SERVICES_CLIENT_ID", "FIREFLY_SERVICES_CLIENT_SECRET")
    secret_env = env
    TOKEN_URL = "https://ims-na1.adobelogin.com/ims/token/v3"
    SCOPE = "openid,AdobeID,session,additional_info,read_organizations,firefly_api,ff_apis"
    GENERATE = "https://firefly-api.adobe.io/v3/images/generate"

    def preflight(self, brief):
        self._no_references(brief.get("references"))

    def _token(self):
        form = urlencode({"client_id": self._env["FIREFLY_SERVICES_CLIENT_ID"],
                          "client_secret": self._env["FIREFLY_SERVICES_CLIENT_SECRET"],
                          "grant_type": "client_credentials", "scope": self.SCOPE}).encode("ascii")
        reply = self._json(self._send("POST", self.TOKEN_URL, {"Content-Type": "application/x-www-form-urlencoded"}, form))
        token = reply.get("access_token")
        if not isinstance(token, str) or not token:
            raise ProviderError("bad_response", "Adobe did not return an access token.")
        self._secrets.append(token)  # removed from every later message, as the key is
        return token

    def generate(self, brief, refs):
        self._no_references(refs)
        token = self._token()
        body = json.dumps({"prompt": brief["prompt"], "aspectRatio": brief["aspect_ratio"], "numVariations": 1,
                           "modelId": brief["model"]}, ensure_ascii=False).encode("utf-8")
        headers = {"Accept": "application/json", "Content-Type": "application/json",
                   "x-api-key": self._env["FIREFLY_SERVICES_CLIENT_ID"], "Authorization": f"Bearer {token}"}
        reply = self._json(self._send("POST", self.GENERATE, headers, body))
        first = _first(reply, "outputs")
        url = (first.get("image") or {}).get("url") if first else None
        if not isinstance(url, str):
            raise ProviderError("no_image", "The Adobe Firefly response has no image.")
        return self._result(fetch_image(url, self._timeout, self._transport))


ADAPTERS = {cls.key: cls for cls in (OpenAIImages, BlackForestLabs, Ideogram, Recraft, BytePlus, Stability, ComfyUI,
                                     Firefly)}


def make_client(provider, timeout, env=None, transport=None):
    """A client for one non-Gemini provider. Raises missing_api_key before anything is spent."""
    cls = ADAPTERS.get(provider)
    if cls is None:
        raise StudioError("unknown_provider", f"{provider!r} is not a provider of the studio.", 409)
    return cls(os.environ if env is None else env, timeout, transport or http_request)


def configured(provider, env=None):
    """True when the provider's variables are set. Says nothing about whether the key is valid."""
    env = os.environ if env is None else env
    cls = ADAPTERS.get(provider)
    if cls is None:
        return False
    return all(env.get(name, "").strip() for name in cls.env)
