"""Deterministic checks on a generated image: format, dimensions, aspect ratio and a content hash.

Stdlib only, no network. These checks say what can be measured from the bytes. They do not judge
the picture: fidelity, text legibility and identity are rated by a person (see core.CRITERIA).
"""

import hashlib
import struct

ASPECT_TOLERANCE = 0.02  # local choice: the width/height ratio may differ from the requested one by 2 %


def _png_size(data):
    if len(data) >= 24 and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    return None


def _jpeg_size(data):
    """Walk the JPEG markers to the first start-of-frame segment (SOF0 to SOF15, without DHT, JPG and DAC)."""
    i = 2
    while i + 9 <= len(data):
        if data[i] != 0xFF:
            return None
        marker = data[i + 1]
        if marker == 0xFF:  # fill byte before a marker
            i += 1
            continue
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            return width, height
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:  # standalone markers carry no length
            i += 2
            continue
        (length,) = struct.unpack(">H", data[i + 2:i + 4])
        i += 2 + length
    return None


def _webp_size(data):
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    kind = data[12:16]
    if kind == b"VP8 ":  # lossy keyframe: 14-bit width and height, little-endian, after the start code
        if len(data) < 30 or data[23:26] != b"\x9d\x01\x2a":
            return None
        width, height = struct.unpack("<HH", data[26:30])
        return width & 0x3FFF, height & 0x3FFF
    if kind == b"VP8L":  # lossless: signature byte, then width-1 and height-1 packed into 4 bytes
        if len(data) < 25 or data[20] != 0x2F:
            return None
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if kind == b"VP8X":  # extended: canvas size, 24 bits each, minus one
        if len(data) < 30:
            return None
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    return None


_SIZE_READERS = {"image/png": _png_size, "image/jpeg": _jpeg_size, "image/webp": _webp_size}


def image_size(data, mime_type):
    """(width, height) read from the header, or None when the header cannot be read."""
    reader = _SIZE_READERS.get(mime_type)
    size = reader(data) if reader else None
    if size is None or size[0] <= 0 or size[1] <= 0:
        return None
    return size


def aspect_matches(width, height, aspect_ratio):
    """True when width/height is within ASPECT_TOLERANCE of the requested 'W:H' ratio.

    The comparison is in whole numbers, cross-multiplied, so the tolerance boundary is exact (no float drift).
    """
    wanted_w, wanted_h = (int(part) for part in aspect_ratio.split(":"))
    return abs(width * wanted_h - height * wanted_w) / (height * wanted_w) <= ASPECT_TOLERANCE


def check_output(data, mime_type, aspect_ratio):
    """Measurable facts about one generated image, stored with its run record."""
    size = image_size(data, mime_type)
    result = {
        "format": mime_type,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "width": None,
        "height": None,
        "aspect_ratio_ok": None,
        "aspect_tolerance": ASPECT_TOLERANCE,
    }
    if size is not None:
        result["width"], result["height"] = size
        result["aspect_ratio_ok"] = aspect_matches(size[0], size[1], aspect_ratio)
    return result
