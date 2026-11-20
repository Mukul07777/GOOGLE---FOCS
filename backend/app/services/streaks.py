"""Study streaks with weekly freezes (like Duolingo): one missed day per calendar week doesn't break a streak."""
from __future__ import annotations

from datetime import date, timedelta

FREEZES_PER_WEEK = 1


def _week(d: date) -> tuple[int, int]:
    return d.isocalendar()[:2]


def current_streak(active: set[date], today: date) -> dict:
    """Streak ending today (or yesterday, if today isn't done yet).

    A single missed day is bridged by that week's freeze; two missed days in a row always break it.
    """
    cursor = today if today in active else today - timedelta(days=1)
    used: dict[tuple[int, int], int] = {}
    streak = 0
    while True:
        if cursor in active:
            streak += 1
        elif (cursor - timedelta(days=1)) in active and used.get(_week(cursor), 0) < FREEZES_PER_WEEK:
            used[_week(cursor)] = used.get(_week(cursor), 0) + 1  # frozen: kept the streak, doesn't add to it
        else:
            break
        cursor -= timedelta(days=1)
    return {
        "streak": streak,
        "active_today": today in active,
        "at_risk": streak > 0 and today not in active,
        "freezes_left": max(0, FREEZES_PER_WEEK - used.get(_week(today), 0)),
        "frozen_days": sum(used.values()),
    }


def best_streak(active: set[date]) -> int:
    best = run = 0
    used: dict[tuple[int, int], int] = {}
    prev: date | None = None
    for d in sorted(active):
        gap = (d - prev).days if prev else None
        if gap == 1:
            run += 1
        elif gap == 2 and used.get(_week(d - timedelta(days=1)), 0) < FREEZES_PER_WEEK:
            used[_week(d - timedelta(days=1))] = used.get(_week(d - timedelta(days=1)), 0) + 1
            run += 1
        else:
            run = 1
        best, prev = max(best, run), d
    return best
