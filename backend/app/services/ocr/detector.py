"""Text-line detection.

Primary: PP-OCRv4 DBNet (bundled with rapidocr-onnxruntime, Apache-2.0).
Fallback: a morphology-based line finder that needs nothing but OpenCV.
"""
from __future__ import annotations

import logging

import cv2
import numpy as np

log = logging.getLogger("focs.ocr")


def order_boxes(boxes: list[np.ndarray]) -> list[np.ndarray]:
    """Reading order: top-to-bottom rows, left-to-right within a row."""
    if not boxes:
        return []
    items = sorted(boxes, key=lambda b: (b[:, 1].min(), b[:, 0].min()))
    heights = [b[:, 1].max() - b[:, 1].min() for b in items]
    tol = max(6.0, float(np.median(heights)) * 0.5)
    rows: list[list[np.ndarray]] = []
    for b in items:
        cy = b[:, 1].mean()
        if rows and abs(np.mean([r[:, 1].mean() for r in rows[-1]]) - cy) < tol:
            rows[-1].append(b)
        else:
            rows.append([b])
    return [b for row in rows for b in sorted(row, key=lambda x: x[:, 0].min())]


def crop_quad(img: np.ndarray, quad: np.ndarray) -> np.ndarray:
    pts = quad.astype(np.float32)
    w = int(max(np.linalg.norm(pts[0] - pts[1]), np.linalg.norm(pts[2] - pts[3])))
    h = int(max(np.linalg.norm(pts[0] - pts[3]), np.linalg.norm(pts[1] - pts[2])))
    w, h = max(w, 2), max(h, 2)
    dst = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(pts, dst)
    crop = cv2.warpPerspective(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE, flags=cv2.INTER_CUBIC)
    if h / max(w, 1) >= 1.5:  # vertical text
        crop = np.rot90(crop)
    return crop


class DBNetDetector:
    name = "dbnet-ppocrv4"
    DETECT_SIDE = 1024  # detect on a smaller copy (≈2.5x faster); lines are still read at full resolution
    MAX_LINES = 40      # a busy frame can yield 100+ boxes; the biggest ones carry the board content

    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR

        from app.core.config import settings

        # its default is every core, which stalled a lecture video playing on the same laptop
        self._engine = RapidOCR(intra_op_num_threads=max(1, settings.OCR_THREADS), inter_op_num_threads=1)
        self.det = self._engine.text_det
        self.det.limit_type = "max"  # never upscale lecture frames before detection
        self.rec = self._engine.text_rec  # exposed so the engine can ensemble recognisers

    def detect(self, img: np.ndarray) -> list[np.ndarray]:
        h, w = img.shape[:2]
        scale = min(1.0, self.DETECT_SIDE / max(h, w))
        small = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else img
        boxes, _ = self.det(np.ascontiguousarray(small[..., ::-1]) if small.ndim == 3 else small)  # PP-OCR wants BGR
        if boxes is None or len(boxes) == 0:
            return []
        out = [np.asarray(b, dtype=np.float32) / scale for b in boxes]
        if len(out) > self.MAX_LINES:
            out = sorted(out, key=lambda b: cv2.contourArea(b), reverse=True)[: self.MAX_LINES]
        return out


class MorphDetector:
    """Classical fallback: binarise, smear characters into line blobs, take bounding boxes."""

    name = "morphology"

    def detect(self, img: np.ndarray) -> list[np.ndarray]:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
        h, w = gray.shape
        border = np.concatenate([gray[:5].ravel(), gray[-5:].ravel(), gray[:, :5].ravel(), gray[:, -5:].ravel()])
        if np.median(border) < 128:
            gray = 255 - gray
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15)
        k = max(9, w // 60)
        smear = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, 3)))
        smear = cv2.dilate(smear, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
        contours, _ = cv2.findContours(smear, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for c in contours:
            x, y, bw, bh = cv2.boundingRect(c)
            if bh < 8 or bw < 12 or bh > h * 0.4 or bw * bh < 150:
                continue
            pad = int(bh * 0.15)
            x0, y0 = max(0, x - pad), max(0, y - pad)
            x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)
            boxes.append(np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float32))
        return boxes
