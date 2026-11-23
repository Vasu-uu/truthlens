"""Safe image decoding and small helpers (PNG/base64 encoding)."""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.main_errors import ApiError

try:  # HEIC/HEIF support is optional
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover
    pass

MAX_PIXELS = 100_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


@dataclass
class LoadedImage:
    """Decoded image plus the raw metadata needed by forensics."""

    rgb: Image.Image
    fmt: str
    width: int
    height: int
    info: dict[str, Any] = field(default_factory=dict)
    exif: Image.Exif | None = None
    raw: bytes = b""


def load_image(data: bytes) -> LoadedImage:
    """Decode bytes into an RGB image. Raises ApiError(400/413) on bad input."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            fmt = (im.format or "UNKNOWN").upper()
            info = {k: v for k, v in im.info.items() if isinstance(v, (str, int, float))}
            exif = im.getexif()
            w, h = im.size
            rgb = ImageOps.exif_transpose(im).convert("RGB")
    except Image.DecompressionBombError:
        raise ApiError(413, "image_too_large", "The image has too many pixels to process safely.") from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise ApiError(400, "invalid_image", "This file could not be read as an image (supported: JPG, PNG, WebP, HEIC).") from None
    if min(w, h) < 32:
        raise ApiError(400, "image_too_small", "The image is too small to analyse (minimum 32 px).")
    return LoadedImage(rgb=rgb, fmt=fmt, width=w, height=h, info=info, exif=exif, raw=data)


def limit_size(img: Image.Image, max_side: int) -> Image.Image:
    """Downscale so the longest side is at most max_side."""
    w, h = img.size
    s = max_side / max(w, h)
    if s >= 1:
        return img
    return img.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)


def png_b64(arr_or_img: Any) -> str:
    """Encode a PIL image or uint8 numpy array as a base64 PNG string."""
    img = Image.fromarray(arr_or_img) if isinstance(arr_or_img, np.ndarray) else arr_or_img
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")
