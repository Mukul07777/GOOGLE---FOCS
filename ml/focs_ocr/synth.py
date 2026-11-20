"""Synthetic text-line renderer.

Each sample imitates one crop of a real lecture frame:
  chalk    — green/black chalkboard, chalk grain, smudges
  white    — whiteboard with glare and ghost marks
  tablet   — pen-tablet lectures (PW / Unacademy style): vivid ink on black or white
  slide    — PPT/PDF slides, solid or gradient backgrounds
  paper    — ruled notebook, pen ink
  screen   — code editor / terminal

…then degraded the way a screen-captured video frame is: down-scaling, JPEG/H.264 blur,
noise, small rotations, imperfect detector crops and intrusions from neighbouring lines.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_ROOT = Path(__file__).resolve().parents[1] / "data" / "fonts"

# Windows system fonts that are worth using (skipped silently when absent, e.g. on Linux).
_WIN = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
SYSTEM_FONTS: list[tuple[str, str, int]] = [
    ("slide", "arial.ttf", 0), ("slide", "arialbd.ttf", 0), ("slide", "ariali.ttf", 0),
    ("slide", "calibri.ttf", 0), ("slide", "calibrib.ttf", 0), ("slide", "cambria.ttc", 0),
    ("slide", "cambria.ttc", 1), ("slide", "cambriab.ttf", 0), ("slide", "segoeui.ttf", 0),
    ("slide", "segoeuib.ttf", 0), ("slide", "seguisym.ttf", 0), ("slide", "times.ttf", 0),
    ("slide", "timesbd.ttf", 0), ("slide", "timesi.ttf", 0), ("slide", "verdana.ttf", 0),
    ("slide", "tahoma.ttf", 0), ("slide", "georgia.ttf", 0), ("slide", "trebuc.ttf", 0),
    ("slide", "pala.ttf", 0), ("slide", "framd.ttf", 0), ("slide", "micross.ttf", 0),
    ("hand", "comic.ttf", 0), ("hand", "comicbd.ttf", 0), ("hand", "Inkfree.ttf", 0),
    ("hand", "segoepr.ttf", 0), ("hand", "segoeprb.ttf", 0), ("hand", "segoesc.ttf", 0),
    ("mono", "consola.ttf", 0), ("mono", "consolab.ttf", 0), ("mono", "cour.ttf", 0),
    ("mono", "lucon.ttf", 0),
]


# Fonts whose lowercase glyphs are drawn as capitals — only safe for all-caps labels.
CAPS_ONLY_FONTS = {"PermanentMarker-Regular.ttf"}


@dataclass(frozen=True)
class FontSpec:
    path: str
    index: int
    category: str
    cmap: frozenset


def _read_cmap(path: Path, index: int) -> frozenset | None:
    from fontTools.ttLib import TTCollection, TTFont

    try:
        if path.suffix.lower() == ".ttc":
            font = TTCollection(str(path)).fonts[index]
        else:
            font = TTFont(str(path), lazy=True)
        cmap = font.getBestCmap() or {}
        return frozenset(cmap.keys())
    except Exception:
        return None


def discover_fonts(include_system: bool = True) -> list[FontSpec]:
    specs: list[FontSpec] = []
    for category in ("hand", "slide", "mono"):
        for p in sorted((FONT_ROOT / category).glob("*.tt[fc]")):
            cmap = _read_cmap(p, 0)
            if cmap:
                cat = "mono" if "Code" in p.name else category
                specs.append(FontSpec(str(p), 0, cat, cmap))
    if include_system and _WIN.exists():
        for category, name, index in SYSTEM_FONTS:
            p = _WIN / name
            if p.exists():
                cmap = _read_cmap(p, index)
                if cmap:
                    specs.append(FontSpec(str(p), index, category, cmap))
    # Only keep fonts PIL can actually rasterise.
    ok = []
    for s in specs:
        try:
            ImageFont.truetype(s.path, 24, index=s.index)
            ok.append(s)
        except Exception:
            pass
    return ok


@lru_cache(maxsize=512)
def _font(path: str, index: int, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size, index=index)


def _luma(rgb) -> float:
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def _jitter(rgb, rng, amount=18):
    return tuple(int(np.clip(c + rng.integers(-amount, amount + 1), 0, 255)) for c in rgb)


def _smooth_noise(h: int, w: int, rng: np.random.Generator, scale: int, amp: float) -> np.ndarray:
    sh, sw = max(2, h // scale), max(2, w // scale)
    small = rng.standard_normal((sh, sw)).astype(np.float32)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC) * amp


# ---------------------------------------------------------------------------
# Style palettes: (background RGB, list of ink RGBs, preferred font categories)
# ---------------------------------------------------------------------------
STYLES = ("chalk", "white", "tablet", "slide", "paper", "screen")
STYLE_WEIGHTS = np.array([0.17, 0.17, 0.22, 0.22, 0.12, 0.10])

CHALK_BG = [(38, 64, 52), (30, 52, 44), (45, 75, 60), (34, 38, 42), (22, 26, 30), (50, 55, 50)]
CHALK_INK = [(235, 235, 230), (245, 245, 245), (245, 230, 120), (240, 160, 190), (160, 210, 245), (180, 240, 170), (245, 190, 120)]
MARKER_INK = [(25, 25, 30), (30, 50, 170), (190, 35, 40), (25, 120, 60), (60, 30, 120)]
TABLET_DARK_INK = [(255, 235, 60), (80, 230, 255), (140, 255, 90), (255, 110, 200), (255, 255, 255), (255, 160, 60), (255, 80, 80), (170, 140, 255)]
TABLET_LIGHT_INK = [(10, 10, 10), (20, 60, 200), (210, 30, 30), (0, 140, 70), (120, 40, 160)]
PEN_INK = [(25, 45, 140), (20, 20, 30), (170, 30, 40), (30, 30, 90)]
CODE_DARK_BG = [(30, 30, 30), (40, 44, 52), (13, 17, 23), (39, 40, 34), (0, 43, 54)]
CODE_DARK_INK = [(212, 212, 212), (86, 156, 214), (206, 145, 120), (78, 201, 176), (220, 220, 170), (197, 134, 192), (152, 195, 121)]


def _pick(seq, rng):
    return seq[int(rng.integers(len(seq)))]


def _background(style: str, h: int, w: int, rng: np.random.Generator, text_h: int) -> np.ndarray:
    if style == "chalk":
        base = np.array(_jitter(_pick(CHALK_BG, rng), rng, 10), np.float32)
        img = np.ones((h, w, 3), np.float32) * base
        img += _smooth_noise(h, w, rng, max(4, text_h), rng.uniform(4, 14))[..., None]
        img += rng.standard_normal((h, w, 1)).astype(np.float32) * rng.uniform(2, 7)
        # faint smears of erased chalk
        smear = np.zeros((h, w), np.float32)
        for _ in range(int(rng.integers(0, 4))):
            y = int(rng.integers(0, h))
            cv2.line(smear, (0, y), (w, int(y + rng.integers(-h, h + 1))), 1.0, int(rng.integers(2, max(3, h // 3))))
        smear = cv2.GaussianBlur(smear, (0, 0), max(1.0, text_h / 4))
        img += (smear * rng.uniform(5, 25))[..., None]
        blotch = _smooth_noise(h, w, rng, max(3, text_h // 2), 1.0)
        img += (np.clip(blotch, 0, None) * rng.uniform(0, 18))[..., None]
    elif style == "white":
        v = rng.uniform(210, 252)
        tint = np.array([v, v + rng.uniform(-4, 4), v + rng.uniform(-3, 6)], np.float32)
        img = np.ones((h, w, 3), np.float32) * tint
        gx = np.linspace(0, 1, w, dtype=np.float32)[None, :] * rng.uniform(-25, 25)
        gy = np.linspace(0, 1, h, dtype=np.float32)[:, None] * rng.uniform(-12, 12)
        img += (gx + gy)[..., None]
        img += _smooth_noise(h, w, rng, max(6, text_h), rng.uniform(1, 6))[..., None]
    elif style == "tablet":
        if rng.random() < 0.72:
            base = _jitter(_pick([(0, 0, 0), (8, 8, 12), (12, 16, 32), (20, 20, 20), (5, 25, 20)], rng), rng, 6)
        else:
            base = _jitter((250, 250, 250), rng, 6)
        img = np.ones((h, w, 3), np.float32) * np.array(base, np.float32)
        if rng.random() < 0.15:  # faint grid
            step = int(rng.integers(12, 40))
            grid_col = 30 if _luma(base) < 128 else -30
            img[::step, :, :] += grid_col
            img[:, ::step, :] += grid_col
    elif style == "slide":
        c1 = tuple(int(x) for x in rng.integers(0, 256, 3))
        if rng.random() < 0.55:  # most slides are light
            c1 = _jitter(_pick([(255, 255, 255), (245, 245, 240), (235, 240, 250), (250, 245, 230)], rng), rng, 8)
        img = np.ones((h, w, 3), np.float32) * np.array(c1, np.float32)
        if rng.random() < 0.35:
            c2 = np.array(_jitter(c1, rng, 50), np.float32)
            t = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
            img = img * (1 - t) + c2 * t
    elif style == "paper":
        base = np.array([rng.uniform(232, 252), rng.uniform(228, 248), rng.uniform(210, 236)], np.float32)
        img = np.ones((h, w, 3), np.float32) * base
        img += rng.standard_normal((h, w, 1)).astype(np.float32) * rng.uniform(1, 4)
        if rng.random() < 0.7:
            step = int(text_h * rng.uniform(1.1, 1.6))
            off = int(rng.integers(0, max(1, step)))
            for y in range(off, h, max(step, 6)):
                img[y:y + 1] = img[y:y + 1] * 0.55 + np.array([150, 180, 220], np.float32) * 0.45
        if rng.random() < 0.15:
            x = int(rng.integers(0, max(1, w // 6)))
            img[:, x:x + 2] = (210, 90, 90)
    else:  # screen
        base = _pick(CODE_DARK_BG, rng) if rng.random() < 0.7 else (255, 255, 255)
        img = np.ones((h, w, 3), np.float32) * np.array(base, np.float32)
    return np.clip(img, 0, 255)


def _ink(style: str, bg_luma: float, rng: np.random.Generator) -> tuple[int, int, int]:
    if style == "chalk":
        return _jitter(_pick(CHALK_INK, rng), rng, 12)
    if style == "white":
        return _jitter(_pick(MARKER_INK, rng), rng, 15)
    if style == "tablet":
        return _jitter(_pick(TABLET_DARK_INK if bg_luma < 128 else TABLET_LIGHT_INK, rng), rng, 10)
    if style == "paper":
        return _jitter(_pick(PEN_INK, rng), rng, 12)
    if style == "screen":
        if bg_luma < 128:
            return _jitter(_pick(CODE_DARK_INK, rng), rng, 8)
        return _jitter(_pick([(0, 0, 0), (0, 0, 255), (163, 21, 21), (0, 128, 0)], rng), rng, 8)
    # slide: pick any colour with enough contrast
    for _ in range(10):
        c = tuple(int(x) for x in rng.integers(0, 256, 3))
        if abs(_luma(c) - bg_luma) > 90:
            return c
    return (0, 0, 0) if bg_luma > 128 else (255, 255, 255)


class LineRenderer:
    def __init__(self, fonts: list[FontSpec]):
        if not fonts:
            raise RuntimeError("No fonts found. Run: python ml/scripts/download_assets.py")
        self.fonts = fonts
        self.by_cat: dict[str, list[FontSpec]] = {}
        for f in fonts:
            self.by_cat.setdefault(f.category, []).append(f)

    def _choose_font(self, text: str, style: str, rng: np.random.Generator) -> FontSpec | None:
        need = {ord(c) for c in text if c != " "}
        prefs = {
            "chalk": ["hand", "slide"], "white": ["hand", "slide"], "tablet": ["hand", "slide"],
            "paper": ["hand"], "slide": ["slide"], "screen": ["mono", "slide"],
        }[style]
        order = prefs if rng.random() < 0.85 else list(reversed(prefs))
        upper_only = text == text.upper()
        for cat in order + ["slide", "hand", "mono"]:
            pool = [f for f in self.by_cat.get(cat, [])
                    if need <= f.cmap and (upper_only or Path(f.path).name not in CAPS_ONLY_FONTS)]
            if pool:
                return pool[int(rng.integers(len(pool)))]
        return None

    def _draw_mask(self, text: str, spec: FontSpec, size: int, rng: np.random.Generator, handwriting: bool):
        font = _font(spec.path, spec.index, size)
        ascent, descent = font.getmetrics()
        stroke = 0
        if handwriting and rng.random() < 0.25:
            stroke = int(rng.integers(1, max(2, size // 22) + 1))
        spacing = rng.uniform(-0.03, 0.12) * size if rng.random() < 0.3 else 0.0
        jitter_y = size * rng.uniform(0.0, 0.05) if handwriting and rng.random() < 0.5 else 0.0

        width = int(font.getlength(text) + abs(spacing) * len(text) + size * 2 + stroke * 2)
        height = int((ascent + descent) * 1.6 + stroke * 2 + size)
        mask = Image.new("L", (max(width, 8), max(height, 8)), 0)
        draw = ImageDraw.Draw(mask)
        x0, y0 = size, int(size * 0.5)
        if spacing == 0.0 and jitter_y == 0.0:
            draw.text((x0, y0), text, font=font, fill=255, stroke_width=stroke, stroke_fill=255)
        else:
            x = float(x0)
            for ch in text:
                dy = rng.normal(0, jitter_y) if jitter_y else 0.0
                draw.text((x, y0 + dy), ch, font=font, fill=255, stroke_width=stroke, stroke_fill=255)
                x += font.getlength(ch) + spacing
        arr = np.asarray(mask)
        line_top, line_bottom = y0, y0 + ascent + descent
        return arr, line_top, line_bottom

    def render(self, text: str, rng: np.random.Generator, difficulty: float = 1.0) -> np.ndarray | None:
        """Render ``text`` and return a degraded grayscale crop (uint8), or None if no font fits."""
        style = STYLES[int(rng.choice(len(STYLES), p=STYLE_WEIGHTS))]
        spec = self._choose_font(text, style, rng)
        if spec is None:
            return None
        handwriting = spec.category == "hand"
        size = int(rng.integers(28, 64))
        mask, line_top, line_bottom = self._draw_mask(text, spec, size, rng, handwriting)

        ys, xs = np.nonzero(mask > 40)
        if len(xs) == 0:
            return None
        ink_top, ink_bottom, ink_left, ink_right = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        ink_h = ink_bottom - ink_top

        # Vertical extent: sometimes font line-height (like a detector box on a full line),
        # sometimes the ink box expanded by a DBNet-like unclip ratio.
        if rng.random() < 0.5:
            top, bottom = min(line_top, ink_top), max(line_bottom, ink_bottom)
            pad_v = (bottom - top) * rng.uniform(0.02, 0.2)
        else:
            top, bottom = ink_top, ink_bottom
            pad_v = max(ink_h, size * 0.5) * rng.uniform(0.08, 0.45)
        pad_l = size * rng.uniform(0.05, 0.6)
        pad_r = size * rng.uniform(0.05, 0.6)
        if rng.random() < 0.08 * difficulty:  # detector clipped the line a little
            pad_v = -ink_h * rng.uniform(0.0, 0.08)
        y1 = int(max(0, top - pad_v)); y2 = int(min(mask.shape[0], bottom + pad_v))
        x1 = int(max(0, ink_left - pad_l)); x2 = int(min(mask.shape[1], ink_right + pad_r))
        if y2 - y1 < 6 or x2 - x1 < 6:
            return None

        # Paint only the crop (rotation later uses border replication, so no margin is needed).
        m = mask[y1:y2, x1:x2].astype(np.float32) / 255.0
        ink_top, ink_bottom, ink_left, ink_right = ink_top - y1, ink_bottom - y1, ink_left - x1, ink_right - x1
        h, w = m.shape
        y1, y2, x1, x2 = 0, h, 0, w
        bg = _background(style, h, w, rng, int(ink_h))
        bg_luma = float(np.median(_luma(bg[[0, -1], :].reshape(-1, 3).T)))
        ink = np.array(_ink(style, bg_luma, rng), np.float32)
        if abs(_luma(ink) - bg_luma) < 40 + 40 * (1 - difficulty):
            ink = np.array((255, 255, 255) if bg_luma < 128 else (15, 15, 15), np.float32)

        alpha = m * rng.uniform(0.75, 1.0)
        if style == "chalk":  # chalk grain: strokes break up where the board is rough
            grain = rng.random(m.shape).astype(np.float32)
            alpha *= np.clip(0.55 + grain * 0.7 + _smooth_noise(h, w, rng, 3, 0.25), 0, 1)
        elif style in ("white", "paper") and rng.random() < 0.4:  # marker/pen pressure variation
            alpha *= np.clip(0.8 + _smooth_noise(h, w, rng, max(4, size // 3), 0.2), 0.4, 1)
        ink_img = np.ones_like(bg) * ink
        if rng.random() < 0.15:  # two-tone / gradient ink
            ink2 = np.array(_ink(style, bg_luma, rng), np.float32)
            t = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
            ink_img = ink_img * (1 - t) + ink2 * t
        img = bg * (1 - alpha[..., None]) + ink_img * alpha[..., None]

        # Descenders/ascenders poking in from neighbouring lines (imperfect detection crops)
        if rng.random() < 0.12 * difficulty:
            thick = max(1, size // 12)
            reach = max(2, int((y2 - y1) * rng.uniform(0.05, 0.18)))
            from_top = rng.random() < 0.5
            for _ in range(int(rng.integers(1, 6))):
                x = int(rng.integers(x1, max(x1 + 1, x2)))
                ya, yb = (y1 - reach, y1 + reach) if from_top else (y2 - reach, y2 + reach)
                cv2.line(img, (x, ya), (x + int(rng.integers(-6, 7)), yb), tuple(float(c) for c in ink), thick)
        if rng.random() < 0.06:  # underline
            uy = min(h - 2, int(ink_bottom + rng.uniform(1, 6)))
            cv2.line(img, (int(ink_left), uy), (int(ink_right), uy), tuple(float(c) for c in ink), int(rng.integers(1, 4)))

        crop = self._degrade(img, rng, difficulty)
        return cv2.cvtColor(crop.astype(np.uint8), cv2.COLOR_RGB2GRAY)

    def _degrade(self, img: np.ndarray, rng: np.random.Generator, d: float) -> np.ndarray:
        p = lambda base: rng.random() < base * (0.35 + 0.65 * d)
        img = np.clip(img, 0, 255).astype(np.uint8)
        h, w = img.shape[:2]

        if p(0.5):  # small rotation / shear
            angle = float(np.clip(rng.normal(0, 1.2), -3.5, 3.5))
            shear = float(rng.uniform(-0.18, 0.18)) if rng.random() < 0.35 else 0.0
            M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
            M[0, 1] += shear
            M[0, 2] -= shear * h / 2
            img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)

        if p(0.3):  # uneven lighting / shadow
            g = np.linspace(rng.uniform(0.7, 1.0), rng.uniform(0.9, 1.15), w, dtype=np.float32)
            img = np.clip(img.astype(np.float32) * g[None, :, None], 0, 255).astype(np.uint8)

        # simulate capture resolution: text line ends up 14..56 px tall in the frame
        target_h = int(rng.uniform(14, 56)) if p(0.85) else h
        if target_h < h:
            scale = target_h / h
            img = cv2.resize(img, (max(8, int(w * scale)), target_h), interpolation=cv2.INTER_AREA)
            if rng.random() < 0.3:  # nearest-neighbour upscale artefacts from video players
                img = cv2.resize(img, (w, h), interpolation=cv2.INTER_NEAREST)
                img = cv2.resize(img, (max(8, int(w * scale)), target_h), interpolation=cv2.INTER_AREA)

        if p(0.45):  # blur, capped so tiny low-res lines stay legible (to a human)
            k = float(rng.uniform(0.3, 1.1)) * min(1.0, target_h / 32)
            if k > 0.25:
                img = cv2.GaussianBlur(img, (0, 0), k)
        if p(0.08):
            k = int(rng.integers(3, 6))
            kernel = np.zeros((k, k), np.float32)
            kernel[k // 2, :] = 1.0 / k
            img = cv2.filter2D(img, -1, kernel)
        if p(0.4):
            noise = rng.standard_normal(img.shape).astype(np.float32) * rng.uniform(2, 11)
            img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        if p(0.25):  # contrast / brightness / gamma
            a = rng.uniform(0.6, 1.2)
            b = rng.uniform(-30, 30)
            img = np.clip(img.astype(np.float32) * a + b, 0, 255)
            gamma = rng.uniform(0.7, 1.4)
            img = (255 * (img / 255) ** gamma).astype(np.uint8)
        if p(0.55):  # JPEG / video compression
            buf = io.BytesIO()
            Image.fromarray(img).save(buf, format="JPEG", quality=int(rng.integers(18, 92)))
            img = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"))
        return img
