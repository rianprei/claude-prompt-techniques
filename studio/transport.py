"""HTTP for the image providers: one request function, multipart bodies, and a guarded download. Stdlib only.

Redirects are refused, so a key header is never replayed to a new address. A reply is read up to a byte limit. A failure
names only the host, never the path, the query or a header, so no key can reach an error message from here.
"""

import re
import secrets
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from .core import ProviderError

JSON_LIMIT_BYTES = 8 * 1024 * 1024  # a JSON reply, or a provider error body
IMAGE_LIMIT_BYTES = 25 * 1024 * 1024  # one image, from a response body or a URL; the studio's own cap
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects. urllib would replay the key headers on the new location."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _read_limited(stream, limit):
    data = stream.read(limit + 1)
    if len(data) > limit:
        raise ProviderError("response_too_large", "The provider's reply is larger than the studio's local limit.")
    return data


def http_request(method, url, headers, body, timeout, limit=JSON_LIMIT_BYTES):
    """Return (status, payload). Raises ProviderError when the host cannot be reached or the reply is too large."""
    host = urlsplit(url).hostname or "unknown host"
    request = urllib.request.Request(url, data=body, headers=dict(headers or {}), method=method)
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return response.status, _read_limited(response, limit)
    except urllib.error.HTTPError as exc:  # before OSError: HTTPError is a subclass of it
        with exc:  # the status and body are all that is needed
            return exc.code, _read_limited(exc, limit)
    except OSError as exc:  # URLError and timeouts
        raise ProviderError("network_error", f"Could not reach {host} ({type(exc).__name__}).") from None


def multipart(fields=(), files=()):
    """(content type, body) for multipart/form-data.

    fields: (name, text) pairs. files: (name, filename, mime type, bytes) tuples. Filenames are reduced to a safe set.
    """
    boundary = "studio" + secrets.token_hex(12)
    chunks = []
    for name, value in fields:
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8"))
    for name, filename, mime_type, data in files:
        safe = _SAFE_FILENAME.sub("_", filename) or "file"
        head = (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{safe}"\r\n'
                f"Content-Type: {mime_type}\r\n\r\n")
        chunks.append(head.encode("utf-8") + data + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    return f"multipart/form-data; boundary={boundary}", b"".join(chunks)


def fetch_image(url, timeout, transport=http_request):
    """Bytes of an image that a provider names by URL. Only HTTPS, and no credential: the link is all it needs.

    Some providers return a temporary link (Ideogram and Recraft say their links expire), so the caller downloads
    the image at once.
    """
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ProviderError("bad_image_url", "The provider named an image address that is not a plain HTTPS link. "
                                             "Nothing was saved.")
    status, payload = transport("GET", url, {}, None, timeout, IMAGE_LIMIT_BYTES)
    if not 200 <= status < 300:
        raise ProviderError(f"image_download_http_{status}", f"Could not download the generated image (HTTP {status}).")
    return payload
