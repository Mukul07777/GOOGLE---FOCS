"""Render full lecture-frame scenes for the end-to-end OCR benchmark.

    python -m focs_ocr.scenes --n 240          (writes ml/data/bench)

Writes PNG frames plus labels.json (ground-truth lines in reading order). Scenes use a seed
disjoint from training, and whole-frame degradation (down-scaling, video JPEG) instead of the
per-line augmentations the recogniser was trained on.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .charset import in_charset, normalize_text
from .corpus import FORMULAS, Corpus
from .synth import CAPS_ONLY_FONTS, STYLES, _background, _font, _ink, _luma, discover_fonts

W, H = 1280, 720
PREFS = {"chalk": "hand", "white": "hand", "tablet": "hand", "paper": "hand", "slide": "slide", "screen": "mono"}
STYLE_NAMES = {"chalk": "chalkboard", "white": "whiteboard", "tablet": "pen tablet", "slide": "slide", "paper": "notebook", "screen": "code screen"}


def _line_text(corpus: Corpus, rng) -> str:
    for _ in range(50):
        r = rng.random()
        if r < 0.35:
            t = FORMULAS[int(rng.integers(len(FORMULAS)))]
        elif r < 0.55:
            t = corpus.terms[int(rng.integers(len(corpus.terms)))]
        elif r < 0.8:
            t = corpus._phrase(rng)
        else:
            t = corpus._words(rng)
        t = normalize_text(t)
        if 3 <= len(t) <= 34 and in_charset(t):
            return t
    return "F = ma"


def render_scene(corpus: Corpus, fonts, rng) -> tuple[np.ndarray, list[str], str]:
    style = STYLES[int(rng.integers(len(STYLES)))]
    bg = _background(style, H, W, rng, 40).astype(np.uint8)
    img = Image.fromarray(bg)
    draw = ImageDraw.Draw(img)
    bg_luma = float(_luma(bg[H // 2, W // 2]))
    want = PREFS[style]
    lines: list[str] = []
    y = int(rng.integers(40, 90))
    n = int(rng.integers(3, 7))
    for i in range(n):
        text = _line_text(corpus, rng)
        need = {ord(c) for c in text if c != " "}
        pool = [f for f in fonts if f.category == want and need <= f.cmap and (text == text.upper() or Path(f.path).name not in CAPS_ONLY_FONTS)]
        pool = pool or [f for f in fonts if need <= f.cmap]
        if not pool:
            continue
        spec = pool[int(rng.integers(len(pool)))]
        size = int(rng.integers(34, 58)) + (8 if i == 0 else 0)
        font = _font(spec.path, spec.index, size)
        x = int(rng.integers(50, 160))
        if x + font.getlength(text) > W - 30 or y + size * 1.3 > H - 20:
            break
        ink = _ink(style, bg_luma, rng)
        if abs(_luma(ink) - bg_luma) < 70:
            ink = (250, 250, 250) if bg_luma < 128 else (15, 15, 15)
        draw.text((x, y), text, font=font, fill=tuple(int(c) for c in ink))
        lines.append(text)
        y += int(size * rng.uniform(1.45, 1.9))

    frame = np.asarray(img)
    # whole-frame capture degradation: 720p/480p stream, mild blur, video compression
    scale = float(rng.choice([1.0, 0.75, 0.6]))
    if scale < 1:
        small = cv2.resize(frame, (int(W * scale), int(H * scale)), interpolation=cv2.INTER_AREA)
        frame = cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR)
    buf = io.BytesIO()
    Image.fromarray(frame).save(buf, format="JPEG", quality=int(rng.integers(45, 90)))
    frame = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"))
    return frame, lines, STYLE_NAMES[style]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=240)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "bench"))
    ap.add_argument("--seed", type=int, default=424242)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fonts = discover_fonts()
    corpus = Corpus(None)
    labels = []
    for i in range(args.n):
        rng = np.random.default_rng((args.seed, i))
        frame, lines, style = render_scene(corpus, fonts, rng)
        if not lines:
            continue
        name = f"scene_{i:04d}.jpg"
        Image.fromarray(frame).save(out / name, quality=92)
        labels.append({"file": name, "style": style, "lines": lines})
    (out / "labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(labels)} scenes to {out}")


if __name__ == "__main__":
    main()
