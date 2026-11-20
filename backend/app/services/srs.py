"""SM-2 spaced repetition (the SuperMemo-2 algorithm used by Anki), with 4 friendly grades."""
from __future__ import annotations

from datetime import timedelta

from app.models._util import utcnow
from app.models.flashcard import Flashcard

GRADES = {"again": 1, "hard": 3, "good": 4, "easy": 5}


def review(card: Flashcard, grade: str) -> Flashcard:
    q = GRADES[grade]
    now = utcnow()
    if q < 3:
        card.repetitions = 0
        card.lapses = (card.lapses or 0) + 1
        card.interval_days = 0
        card.due_at = now + timedelta(minutes=10)  # relearn in the same sitting
    else:
        reps = card.repetitions or 0
        if reps == 0:
            interval = 1.0
        elif reps == 1:
            interval = 3.0 if q == 5 else 2.0
        else:
            interval = (card.interval_days or 1.0) * (card.ease or 2.5)
        if q == 3:
            interval = max(1.0, interval * 0.8)
        elif q == 5:
            interval *= 1.3
        card.repetitions = reps + 1
        card.interval_days = round(min(interval, 365.0), 2)
        card.due_at = now + timedelta(days=card.interval_days)
    ease = (card.ease or 2.5) + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    card.ease = round(max(1.3, min(ease, 3.0)), 3)
    card.last_reviewed_at = now
    return card


def preview_intervals(card: Flashcard) -> dict[str, str]:
    """Human-readable next interval for each button, like Anki shows."""
    out = {}
    for grade in GRADES:
        clone = Flashcard(ease=card.ease, interval_days=card.interval_days, repetitions=card.repetitions, lapses=card.lapses)
        review(clone, grade)
        d = clone.interval_days
        out[grade] = "10m" if d == 0 else f"{d:.0f}d" if d < 30 else f"{d / 30:.1f}mo"
    return out
