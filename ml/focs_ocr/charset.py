"""Character set shared by training and inference.

The set covers printable ASCII plus the Greek letters, operators, super/subscripts and
fractions that show up on JEE / NEET / GATE boards. Anything outside the set is either
normalised to an equivalent (``−`` → ``-``) or dropped from training labels.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

ASCII = "".join(chr(c) for c in range(32, 127))
GREEK = "αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΦΨΩ"
MATH = "∞∫∑√≤≥≠≈±∓×÷→←↔⇒⇔∂∇°∝∈∀∃∴∵·•′″⊥∠∪∩⊂"
SUPSUB = "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ₀₁₂₃₄₅₆₇₈₉₊₋"
FRACTIONS = "½¼¾"

CHARS: str = ASCII + GREEK + MATH + SUPSUB + FRACTIONS
BLANK = 0  # CTC blank index; real characters start at 1

# Look-alike code points folded onto the canonical glyph the model predicts.
_FOLD = {
    "−": "-", "–": "-", "—": "-", "‐": "-", "‑": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"', "´": "'",
    "…": "...", " ": " ", " ": " ", " ": " ",
    "∆": "Δ", "µ": "μ", "Ω": "Ω", "℃": "°C", "⋅": "·",
    "∙": "·", "⟶": "→", "●": "•", "✕": "×",
}


def normalize_text(text: str) -> str:
    """Fold look-alike characters and collapse whitespace."""
    text = unicodedata.normalize("NFC", text)
    text = "".join(_FOLD.get(ch, ch) for ch in text)
    text = text.replace("\t", " ")
    return " ".join(text.split())


def in_charset(text: str) -> bool:
    return all(ch in _INDEX for ch in text)


def encode(text: str) -> list[int]:
    return [_INDEX[ch] for ch in text if ch in _INDEX]


def decode_greedy(indices, probs=None) -> tuple[str, float]:
    """Collapse repeats and drop blanks. Returns (text, mean confidence of emitted chars)."""
    out: list[str] = []
    confs: list[float] = []
    prev = BLANK
    for t, idx in enumerate(indices):
        idx = int(idx)
        if idx != BLANK and idx != prev:
            out.append(CHARS[idx - 1])
            if probs is not None:
                confs.append(float(probs[t]))
        prev = idx
    conf = sum(confs) / len(confs) if confs else 0.0
    return "".join(out), conf


def save(path: Path) -> None:
    path.write_text(json.dumps({"chars": CHARS, "blank": BLANK}, ensure_ascii=False), encoding="utf-8")


NUM_CLASSES = len(CHARS) + 1
_INDEX = {ch: i + 1 for i, ch in enumerate(CHARS)}
assert len(_INDEX) == len(CHARS), "duplicate characters in charset"
