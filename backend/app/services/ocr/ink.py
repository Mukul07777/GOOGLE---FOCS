"""Where a frame has writing, and whether two frames show the same board.

The live pipeline used to tell boards apart by their OCR text. On a real PW lecture (2026-10-20) the teacher's
handwriting came back as 20-110 characters of junk that changed with every frame ("2 x7- 3 x+2 | p x x m="), and Hindi
handwriting not at all, so one question worked over nine minutes became fifteen "new boards", each with its own paid
write-up. The strokes themselves barely change. A top-hat filter keeps marks thinner than about 15 px (pen, chalk,
print) and drops large shapes, so the teacher standing in front of the board counts for little. Then, in three steps:
a coarse grid finds how far the page has scrolled (a pen tablet scrolls up and down); a 2 px grid, give or take a
cell, refines that and turns away a frame so busy it would match anything; and the strokes themselves, pixel for
pixel give or take one, decide. Two slides made from one template, or two boards written in one hand at the same
places, share a layout; only the last step tells them apart.

Measured on three recorded lectures (PW physics and maths on a pen tablet, a Hindi NEET zoology board with slides), the
share of a board's strokes found again, pixel for pixel, in a later frame of it: 0.47-0.98, the teacher standing in
front of part of it 20 frames later included (frames 5 s apart score higher); of one board in a frame of another,
0.21-0.34 (two slides of one template the most), and up to 0.39 for typed boards in one font with lines in the same
places.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

WIDTH = 1280                    # frames are compared at this width
COARSE, FINE = 10, 2            # cell sizes in px (and the strokes themselves, at 1 px)
EDGE_TOP, EDGE_SIDE = 60, 30    # px left out at the top and bottom, and at the sides: logos and the toolbars, on every
                                # board alike
MAX_SCROLL = 40                 # coarse rows (of 72 on a 16:9 frame) a page may scroll between two frames of it
ROUGH_GUESSES = 6               # coarse scrolls looked at closely
SAME_BOARD = 0.43               # share of a board's strokes found again, pixel for pixel, for a frame to be that board
OVER_CHANCE = 0.3               # and on the 2 px grid, that much more than a frame that busy would match by luck
_KERNEL = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
_NEAR = np.ones((3, 3), np.uint8)


def _pack(m: np.ndarray) -> tuple[np.ndarray, tuple[int, int]]:
    return np.packbits(m), m.shape


def _unpack(bits: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    return np.unpackbits(bits, count=shape[0] * shape[1]).reshape(shape).astype(bool)


@dataclass(eq=False)
class Ink:
    """A frame's strokes, on the grids and as they are (bit-packed: about 150 KB, and a lecture keeps a dozen)."""
    coarse: np.ndarray
    fine_bits: np.ndarray
    fine_shape: tuple[int, int]
    exact_bits: np.ndarray
    exact_shape: tuple[int, int]
    amount: int  # coarse cells with writing

    def fine(self) -> np.ndarray:
        return _unpack(self.fine_bits, self.fine_shape)

    def exact(self) -> np.ndarray:
        return _unpack(self.exact_bits, self.exact_shape)


def _grid(stroke: np.ndarray, cell: int) -> np.ndarray:
    h, w = stroke.shape
    m = stroke > 0 if cell == 1 else (
        cv2.resize(stroke, (w // cell, h // cell), interpolation=cv2.INTER_AREA) > (0.04 if cell == COARSE else 0.2))
    top, side = EDGE_TOP // cell, EDGE_SIDE // cell
    m[:top] = m[-top:] = False
    m[:, :side] = m[:, -side:] = False
    return m


def ink_map(img: np.ndarray) -> Ink:
    """The strokes on a frame (RGB or gray)."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
    h, w = gray.shape
    gray = cv2.resize(gray, (WIDTH, max(EDGE_TOP * 3, round(h * WIDTH / w) // COARSE * COARSE)), interpolation=cv2.INTER_AREA)
    dark = np.median(gray[::4, ::4]) < 128  # chalkboard or pen tablet: light marks; whiteboard or slide: dark ones
    hat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT if dark else cv2.MORPH_BLACKHAT, _KERNEL)
    stroke = (hat > 60).astype(np.float32)
    coarse = _grid(stroke, COARSE)
    return Ink(coarse, *_pack(_grid(stroke, FINE)), *_pack(_grid(stroke, 1)), int(coarse.sum()))


def _overlap(a: np.ndarray, b: np.ndarray, s: int) -> int:
    """Cells of ``a`` that ``b`` has too, the page scrolled down by ``s`` rows (``a``'s row r is ``b``'s row r - s)."""
    h = a.shape[0]
    if abs(s) >= h:
        return 0
    x, y = (a[s:], b[:h - s]) if s >= 0 else (a[:h + s], b[-s:])
    return int(np.count_nonzero(x & y))


def _near(m: np.ndarray) -> np.ndarray:
    return cv2.dilate(m.astype(np.uint8), _NEAR).astype(bool)


def _scrolls(old: Ink, new: Ink) -> list[tuple[float, int]]:
    """The likeliest scrolls of ``new`` against ``old``, best first, as (share of ``old``'s strokes found on the 2 px grid
    give or take a cell, scroll in 2 px rows). Lines of writing a fixed distance apart line up with other lines at
    the wrong scroll too, so the coarse grid's few best guesses are each refined."""
    near = _near(new.coarse)
    if max(_overlap(old.coarse, near, s) for s in range(-MAX_SCROLL, MAX_SCROLL + 1)) < 0.4 * old.amount:
        return []  # not even the layout matches
    # ranked cell for cell: give or take a cell, every line half overlaps the one above it at the wrong scroll
    rough = sorted(((_overlap(old.coarse, new.coarse, s), s) for s in range(-MAX_SCROLL, MAX_SCROLL + 1)), reverse=True)
    a, b = old.fine(), _near(new.fine())
    total, step = max(1, int(a.sum())), COARSE // FINE
    found = {}
    for _, r in rough[:ROUGH_GUESSES]:
        for s in range(r * step - step, r * step + step + 1):
            if s not in found:
                found[s] = _overlap(a, b, s) / total
    return sorted(((k, s) for s, k in found.items()), reverse=True)


def compare(old: Ink, new: Ink) -> tuple[float, float, list[int]]:
    """(share of ``old``'s strokes found again in ``new`` on the 2 px grid, give or take a cell, at the scroll that
    matches best; what a frame as busy as ``new`` would get there by luck; the best scrolls, in 2 px rows). (0, 1, [])
    when either frame has almost nothing on it, they differ in shape (a phone's photo against a screen), or not even
    the layout matches."""
    if old.amount < 10 or new.amount < 10 or old.coarse.shape != new.coarse.shape:
        return 0.0, 1.0, []
    scrolls = _scrolls(old, new)
    if not scrolls:
        return 0.0, 1.0, []
    return scrolls[0][0], float(_near(new.fine()).mean()), [s for _, s in scrolls[:2]]


def _exact(old: Ink, new: Ink, scrolls: list[int]) -> float:
    """Share of ``old``'s strokes that are strokes in ``new`` too, pixel for pixel give or take one, near these scrolls."""
    a, b = old.exact(), new.exact()
    total = max(1, int(a.sum()))
    shifted = [np.roll(b, dx, axis=1) for dx in (-1, 0, 1)]
    return max(_overlap(a, bb, s) for at in scrolls for s in range(at * FINE - 1, at * FINE + 2) for bb in shifted) / total


def match(old: Ink, new: Ink) -> float:
    """How surely ``new`` shows the board ``old`` showed: the share of its strokes found again, or 0 if it doesn't."""
    k, luck, scrolls = compare(old, new)
    if k < SAME_BOARD or k - luck < OVER_CHANCE:
        return 0.0
    exact = _exact(old, new, scrolls)
    return exact if exact >= SAME_BOARD else 0.0


def same_board(old: Ink, new: Ink) -> bool:
    return match(old, new) > 0


def new_writing(written: Ink, now: Ink) -> float:
    """Share of what is on the board ``now`` that wasn't there when it was ``written`` up."""
    return 1.0 - compare(now, written)[0]
