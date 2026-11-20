"""Line-image normalisation.

This exact logic is mirrored in ``backend/app/services/ocr/recognizer.py`` — the model only
works if training and inference feed it identically prepared pixels.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

HEIGHT = 48
MIN_WIDTH = 16
MAX_WIDTH = 1280
DOWNSAMPLE = 4  # horizontal stride of the CNN; one CTC frame per 4 px


def to_gray(img: Image.Image | np.ndarray) -> np.ndarray:
    if isinstance(img, Image.Image):
        return np.asarray(img.convert("L"), dtype=np.uint8)
    if img.ndim == 3:
        # ITU-R 601 luma, same as PIL "L"
        return (img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114).astype(np.uint8)
    return img


def normalize_polarity(gray: np.ndarray) -> np.ndarray:
    """Return dark-text-on-light-background regardless of the board colour.

    The border of a text crop is almost always background. Ink is whichever tail of the
    histogram sits further from that background level: if the bright tail is further away,
    the text is light (chalkboard, pen tablet, dark slide) and we invert.
    """
    h, w = gray.shape
    b = max(1, min(h, w) // 8)
    border = np.concatenate([gray[:b].ravel(), gray[-b:].ravel(), gray[:, :b].ravel(), gray[:, -b:].ravel()])
    bg = float(np.median(border))
    lo, hi = np.percentile(gray, (3, 97))
    if (hi - bg) > (bg - lo):
        gray = 255 - gray
    return gray


def stretch_contrast(gray: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(gray, (2, 98))
    if hi - lo < 8:
        return gray
    out = (gray.astype(np.float32) - lo) * (255.0 / (hi - lo))
    return np.clip(out, 0, 255).astype(np.uint8)


def prepare_line(img: Image.Image | np.ndarray) -> np.ndarray:
    """Any crop -> float32 array (HEIGHT, W) in [-1, 1], dark text on light background."""
    gray = stretch_contrast(normalize_polarity(to_gray(img)))
    h, w = gray.shape
    new_w = int(round(w * HEIGHT / max(h, 1)))
    new_w = max(MIN_WIDTH, min(MAX_WIDTH, new_w))
    resized = Image.fromarray(gray).resize((new_w, HEIGHT), Image.BILINEAR)
    arr = np.asarray(resized, dtype=np.float32) / 255.0
    return (arr - 0.5) / 0.5
