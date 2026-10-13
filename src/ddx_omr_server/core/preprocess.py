"""Page decoding and checkbox crops, matching the classifier's training input.

Crop the box plus ``pad`` of its size on every side, optionally binarise with
Otsu, resize to 64x64, normalise to [-1, 1]. Behaviour ported from
ddx-rnd/grid-omr/omr_server.py; no decision is taken here — the caller owns
confidence.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass

import cv2
import numpy as np
import numpy.typing as npt

CROP_SIZE = 64


class ImageError(ValueError):
    """The page image cannot be decoded."""


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float


def decode_page(image_b64: str, max_bytes: int) -> npt.NDArray[np.uint8]:
    """Decode a base64 PNG/JPEG page to a greyscale array, or raise ImageError."""
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageError("image_png_b64 is not valid base64.") from exc
    if not raw:
        raise ImageError("image_png_b64 is empty.")
    if len(raw) > max_bytes:
        raise ImageError(f"the image is {len(raw)} bytes; the limit is {max_bytes}.")
    page = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_GRAYSCALE)
    if page is None or page.size == 0:
        raise ImageError("the image bytes do not decode as a raster image.")
    return np.asarray(page, dtype=np.uint8)


def crop_box(
    page: npt.NDArray[np.uint8], box: Box, pad: float, otsu: bool
) -> npt.NDArray[np.float32] | None:
    """One normalised 64x64 crop, or None when the box lies outside the page."""
    height, width = page.shape[:2]
    px, py = box.w * pad, box.h * pad
    x0, y0 = max(int(box.x - px), 0), max(int(box.y - py), 0)
    x1, y1 = min(int(box.x + box.w + px), width), min(int(box.y + box.h + py), height)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    crop = page[y0:y1, x0:x1]
    if otsu:
        _, crop = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    crop = cv2.resize(crop, (CROP_SIZE, CROP_SIZE), interpolation=cv2.INTER_LINEAR)
    return ((crop.astype(np.float32) / 255.0) - 0.5) / 0.5
