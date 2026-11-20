"""FocsOCR line recogniser (ONNX Runtime, CPU).

The preprocessing here must stay byte-for-byte equivalent to ``ml/focs_ocr/imaging.py``.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.config import settings

log = logging.getLogger("focs.ocr")

HEIGHT = 48
MIN_WIDTH = 16
MAX_WIDTH = 1280
DOWNSAMPLE = 4
BLANK = 0


def _to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        return (img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114).astype(np.uint8)
    return img


def _normalize_polarity(gray: np.ndarray) -> np.ndarray:
    h, w = gray.shape
    b = max(1, min(h, w) // 8)
    border = np.concatenate([gray[:b].ravel(), gray[-b:].ravel(), gray[:, :b].ravel(), gray[:, -b:].ravel()])
    bg = float(np.median(border))
    lo, hi = np.percentile(gray, (3, 97))
    if (hi - bg) > (bg - lo):
        gray = 255 - gray
    return gray


def _stretch(gray: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(gray, (2, 98))
    if hi - lo < 8:
        return gray
    out = (gray.astype(np.float32) - lo) * (255.0 / (hi - lo))
    return np.clip(out, 0, 255).astype(np.uint8)


def prepare_line(img: np.ndarray) -> np.ndarray:
    gray = _stretch(_normalize_polarity(_to_gray(img)))
    h, w = gray.shape
    new_w = max(MIN_WIDTH, min(MAX_WIDTH, int(round(w * HEIGHT / max(h, 1)))))
    resized = Image.fromarray(gray).resize((new_w, HEIGHT), Image.BILINEAR)
    arr = np.asarray(resized, dtype=np.float32) / 255.0
    return (arr - 0.5) / 0.5


class FocsRecognizer:
    name = "focs"

    def __init__(self, model_dir: Path):
        import onnxruntime as ort

        self.model_path = model_dir / "focsocr.onnx"
        charset = json.loads((model_dir / "charset.json").read_text(encoding="utf-8"))
        self.chars: str = charset["chars"]
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.intra_op_num_threads = max(1, settings.OCR_THREADS)  # never every core: a lecture video plays beside it
        opts.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(self.model_path), sess_options=opts, providers=["CPUExecutionProvider"])
        self._lock = threading.Lock()
        log.info("FocsOCR loaded (%s, %d chars)", self.model_path.name, len(self.chars))

    def _decode(self, probs: np.ndarray, frames: int) -> tuple[str, float]:
        idx = probs[:frames].argmax(-1)
        conf = probs[:frames].max(-1)
        out, confs, prev = [], [], BLANK
        for t, k in enumerate(idx):
            k = int(k)
            if k != BLANK and k != prev:
                out.append(self.chars[k - 1])
                confs.append(float(conf[t]))
            prev = k
        text = "".join(out).strip()
        return text, (float(np.mean(confs)) if confs else 0.0)

    def recognize(self, crops: list[np.ndarray], batch_size: int = 16) -> list[tuple[str, float]]:
        if not crops:
            return []
        prepared = [prepare_line(c) for c in crops]
        order = sorted(range(len(prepared)), key=lambda i: prepared[i].shape[1])  # batch similar widths
        results: list[tuple[str, float]] = [("", 0.0)] * len(prepared)
        for start in range(0, len(order), batch_size):
            ids = order[start:start + batch_size]
            max_w = int(np.ceil(max(prepared[i].shape[1] for i in ids) / DOWNSAMPLE) * DOWNSAMPLE)
            batch = np.ones((len(ids), 1, HEIGHT, max_w), dtype=np.float32)
            for j, i in enumerate(ids):
                batch[j, 0, :, : prepared[i].shape[1]] = prepared[i]
            with self._lock:
                probs = self.session.run(None, {"image": batch})[0]
            for j, i in enumerate(ids):
                results[i] = self._decode(probs[j], prepared[i].shape[1] // DOWNSAMPLE)
        return results
