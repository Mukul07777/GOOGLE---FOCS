"""Classroom mode: a phone on a desk sees the board at an angle. The student marks its four corners once; every frame
is straightened to a flat, front-on board before OCR, so the reader sees what it was trained on."""
from __future__ import annotations

import json

import cv2
import numpy as np

MAX_SIDE = 1600


def parse_corners(raw: str | None) -> np.ndarray | None:
    """Four [x, y] points in 0..1 of the frame (any order), or None when absent or not a usable quadrilateral."""
    if not raw:
        return None
    try:
        pts = np.array(json.loads(raw), dtype=np.float32)
    except (ValueError, TypeError):
        return None
    if pts.shape != (4, 2) or not np.isfinite(pts).all() or (pts < -0.01).any() or (pts > 1.01).any():
        return None
    ordered = order(np.clip(pts, 0, 1))
    if cv2.contourArea(ordered) < 0.02:  # a sliver: nothing to read
        return None
    return ordered


def order(pts: np.ndarray) -> np.ndarray:
    """Top-left, top-right, bottom-right, bottom-left, whatever order the four points came in."""
    s, d = pts.sum(axis=1), np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32)


def warp(img: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """The board inside `corners` (ordered, 0..1) as a front-on rectangle, its sides as long as the board's own."""
    h, w = img.shape[:2]
    src = corners * np.array([w, h], dtype=np.float32)
    tl, tr, br, bl = src
    width = max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))
    height = max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))
    scale = min(1.0, MAX_SIDE / max(width, height, 1.0))
    out_w, out_h = max(16, int(round(width * scale))), max(16, int(round(height * scale)))
    dst = np.array([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, matrix, (out_w, out_h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
