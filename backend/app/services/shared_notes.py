"""Board notes shared across students.

Thousands of students watch the same popular lectures, so the same board reaches Focs again and again. The
first capture pays for the AI notes; every later capture of that board (exact, or the same board read with a
little OCR noise in its words) reuses them for free. Near matches are found with a 64-bit simhash split into four
bands: boards whose hashes differ in at most three bits always share a band, and the candidates are then confirmed
by comparing the text itself, whose numbers and signs must be identical.
"""
from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models._util import utcnow
from app.models.shared_note import SharedNote

MIN_CHARS = 16          # shorter boards are too ambiguous to share at all
NEAR_MIN_CHARS = 60     # below this only an exact match counts: a few changed characters could be a different board
MIN_SIMILARITY = 0.93   # a near match must be this close to count as the same board
MAX_CANDIDATES = 25


# Signs and relations are part of the board: "x^2 - 5x + 6 = 0" and "x^2 - 5x - 6 = 0", or "x > 2" and "x < 2", are
# different problems with different notes. (Until 2026-10-19 only letters and digits were kept, and such boards
# shared one set of notes.) The spellings OCR and students use for one sign are made one.
_SAME_SIGN = (("−", "-"), ("–", "-"), ("—", "-"), (">=", "≥"), ("=>", "≥"), ("<=", "≤"), ("=<", "≤"), ("!=", "≠"))
_TOKENS = re.compile(r"[a-z0-9]+|[-+=<>≤≥≠±×÷/^*()\[\]{}√∞∪∩∈]")
_MATH = re.compile(r"[0-9]+|[-+=<>≤≥≠±×÷/^*√∞∪∩∈]")


def normalize(text: str) -> str:
    t = text.lower()
    for a, b in _SAME_SIGN:
        t = t.replace(a, b)
    return " ".join(_TOKENS.findall(t))


def _words(norm: str) -> str:
    """The words and numbers alone, for finding candidates: single-sign tokens make the simhash jumpy (two OCR slips
    in a sentence moved 10 of its 64 bits), and the signs are checked exactly afterwards anyway."""
    return " ".join(t for t in norm.split() if t[0].isalnum())


def _maths(norm: str) -> str:
    """The board's numbers and signs, in order: a near match may differ in words (OCR noise), never in these."""
    return "".join(_MATH.findall(norm))


def _h64(token: str) -> int:
    return int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "big")


def simhash(norm: str) -> int:
    words = norm.split()
    grams = [" ".join(words[i:i + 2]) for i in range(max(1, len(words) - 1))]
    weights = [0] * 64
    for g in grams:
        h = _h64(g)
        for bit in range(64):
            weights[bit] += 1 if h >> bit & 1 else -1
    return sum(1 << bit for bit in range(64) if weights[bit] > 0)


def _bands(h: int) -> tuple[int, int, int, int]:
    return tuple((h >> (16 * i)) & 0xFFFF for i in range(4))  # type: ignore[return-value]


def _exam(exam: str | None) -> str:
    return (exam or "other")[:20]


def find(db: Session, text: str, exam: str | None) -> SharedNote | None:
    """The shared notes of this board (or of the same board read with a little OCR noise), or None."""
    norm = normalize(text)
    if len(norm) < MIN_CHARS:
        return None
    exam = _exam(exam)
    row = db.scalar(select(SharedNote).where(SharedNote.exam == exam,
                                             SharedNote.text_hash == hashlib.sha1(norm.encode()).hexdigest()).limit(1))
    if row is None and len(norm) >= NEAR_MIN_CHARS:
        b = _bands(simhash(_words(norm)))
        bands = (SharedNote.band0, SharedNote.band1, SharedNote.band2, SharedNote.band3)
        candidates = db.scalars(select(SharedNote).where(SharedNote.exam == exam, or_(*(col == v for col, v in zip(bands, b, strict=True))))
                                .order_by(SharedNote.id.desc()).limit(MAX_CANDIDATES)).all()
        best, best_score, maths = None, MIN_SIMILARITY, _maths(norm)
        for c in candidates:
            if not 0.85 <= len(c.text) / len(norm) <= 1.18 or _maths(c.text) != maths:
                continue
            m = SequenceMatcher(None, norm, c.text, autojunk=False)
            if m.quick_ratio() >= best_score and (score := m.ratio()) >= best_score:
                best, best_score = c, score
        row = best
    return row


def lookup(db: Session, text: str, exam: str | None) -> dict[str, Any] | None:
    """Notes another student's capture of this board already paid for, or None."""
    row = find(db, text, exam)
    if row is None:
        return None
    row.hits = (row.hits or 0) + 1
    row.last_hit_at = utcnow()
    db.flush()
    if not row.is_lecture:
        return {"is_lecture": False, "source": "shared"}
    return {"is_lecture": True, "topic": row.topic or "Untitled board", "subject": row.subject or "General",
            "notes_md": row.notes_md, "source": "shared", **({"board": row.board} if row.board else {})}


def translation(db: Session, text: str, exam: str | None, language: str) -> str | None:
    row = find(db, text, exam)
    return (row.translations or {}).get(language) if row else None


def keep_translation(db: Session, text: str, exam: str | None, language: str, md: str) -> None:
    row = find(db, text, exam)
    if row is not None:
        row.translations = {**(row.translations or {}), language: md}  # (a new dict: JSON columns notice reassignment)


def store(db: Session, text: str, exam: str | None, notes: dict[str, Any]) -> None:
    """Keep freshly written AI notes for the next student who captures this board. Caller commits."""
    norm = normalize(text)
    if len(norm) < MIN_CHARS or notes.get("source") != "ai":
        return
    b = _bands(simhash(_words(norm)))
    db.add(SharedNote(exam=_exam(exam), text_hash=hashlib.sha1(norm.encode()).hexdigest(), band0=b[0], band1=b[1],
                      band2=b[2], band3=b[3], text=norm, is_lecture=bool(notes.get("is_lecture")),
                      topic=notes.get("topic"), subject=notes.get("subject"), notes_md=notes.get("notes_md") or "",
                      board=notes.get("board")))
    db.flush()  # (the session doesn't autoflush: its translation is looked up right after)
