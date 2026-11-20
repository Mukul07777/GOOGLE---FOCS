"""AI allowance, metered like Claude's usage limits.

Every AI action costs a few units. A study day's allowance opens with the first AI action and resets
USAGE_WINDOW_HOURS later (24: a day); a 7-day cap sits on top. A live lecture's board notes are counted in lecture
time instead: hours a study day (LECTURE_HOURS_*: Pro 7, Starter 1), however many boards the teacher fills. Under
both, what a student's AI really costs over 30 days is capped (AI_CEILING_*_INR), so a pass always pays for the AI it
includes. Actions answered by the offline fallback cost nothing.

Two ways to spend:
* ``require`` + ``charge`` — features that stop when the allowance is used up (doubts, practice sets…):
  the API answers 402 with when it resets.
* ``can_spend`` + ``charge`` — the live lecture never stops: past the limit, boards get basic
  (offline) notes until the window resets.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models._util import utcnow
from app.models.user import User
from app.services import ledger, pricing

COSTS: dict[str, int] = {
    "board_note": 0,       # AI notes for a captured board: counted in lecture time (see lecture_time_left), not units
    "checkpoint": 1,       # topic-change question
    "pop_quiz": 1,
    "doubt": 2,
    "room_ask": 2,
    "room_quiz": 1,
    "regenerate_note": 1,
    "flashcards": 2,
    "grade_answer": 2,
    "revision_sheet": 3,
    "practice_set": 5,
    "test_analysis": 5,    # reading an uploaded test result (marking weak topics by hand is free)
    "dictation": 1,        # a spoken answer transcribed on the server (browser dictation is free)
    "detailed_notes": 2,   # only when a note has to be written; notes already in the library are free
    "lecture_audio": 1,    # every few pieces of the lecture's sound turned into text (see services/voice)
    "talk_summary": 1,     # a summary of what the teacher said; written again only after more speech came in
    "gap_trace": 2,        # tracing a topic back to the earlier chapters it rests on (shared: only the first student pays)
    "gap_lesson": 2,       # the short lesson that fixes a root gap
    "working_check": 2,    # rough work read and checked step by step (the image model)
}

LABELS: dict[str, str] = {
    "board_note": "AI board notes", "checkpoint": "Checkpoint questions", "pop_quiz": "Pop quizzes",
    "doubt": "Doubts", "room_ask": "Ask AI in rooms", "room_quiz": "Room quizzes", "regenerate_note": "Regenerated notes",
    "flashcards": "Flashcard sets", "grade_answer": "Answer grading", "revision_sheet": "Revision sheets",
    "practice_set": "Practice sets", "detailed_notes": "Detailed notes", "dictation": "Spoken answers", "test_analysis": "Test results read", "lecture_audio": "Lecture captions",
    "talk_summary": "Summaries of what the teacher said",
    "gap_trace": "Root-cause traces", "gap_lesson": "Root-gap lessons", "working_check": "Working checked",
}

WEEK = timedelta(days=7)


def _window() -> timedelta:
    return timedelta(hours=settings.USAGE_WINDOW_HOURS)


def limits(plan: str | None) -> tuple[int, int]:
    """(per-window, per-week) units for a plan; 0 means unlimited."""
    plan = plan or "free"
    if plan == "team":
        return settings.USAGE_TEAM_WINDOW, settings.USAGE_TEAM_WEEKLY
    if plan == "pro":
        return settings.USAGE_PRO_WINDOW, settings.USAGE_PRO_WEEKLY
    return settings.USAGE_FREE_WINDOW, settings.USAGE_FREE_WEEKLY


def _roll(user: User, now: datetime) -> None:
    """Expire finished windows (lazily, on read)."""
    if user.usage_window_start and now >= user.usage_window_start + _window():
        user.usage_window_start, user.usage_window_used = None, 0
    if user.usage_week_start and now >= user.usage_week_start + WEEK:
        user.usage_week_start, user.usage_week_used = None, 0


def _room(user: User) -> tuple[int | None, int | None]:
    """Units left in the window and in the week (None = unlimited)."""
    per_window, per_week = limits(user.plan)
    left_window = None if not per_window else max(0, per_window - (user.usage_window_used or 0))
    left_week = None if not per_week else max(0, per_week - (user.usage_week_used or 0))
    return left_window, left_week


def ceiling_inr(user: User) -> float:
    """What this student's AI may cost in any 30 days, in rupees (0: no ceiling). On Pro it is what the pass they are
    on brings in over 30 days, so a student never costs more than they paid."""
    plan = user.plan or "free"
    if plan == "team":
        return 0.0
    if plan == "pro":
        running = pricing.pass_ceiling_inr(user.id)
        return settings.AI_CEILING_PRO_INR if running is None else running
    return settings.AI_CEILING_FREE_INR


def over_ceiling(user: User) -> bool:
    ceiling = ceiling_inr(user)
    return bool(ceiling) and ledger.user_spend_inr(user.id) >= ceiling


def can_spend(db: Session, user: User, action: str) -> bool:
    _roll(user, utcnow())
    cost = COSTS[action]
    left_window, left_week = _room(user)
    return (left_window is None or left_window >= cost) and (left_week is None or left_week >= cost) and not over_ceiling(user)


def _span() -> str:
    hours = settings.USAGE_WINDOW_HOURS
    return "daily" if hours == 24 else f"{hours:g}-hour"


def _upsell() -> str:
    if not (settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET):
        return ""  # Pro can't be bought on this server yet: don't point at it
    free, pro = limits("free")[0], limits("pro")[0]
    return f" — or upgrade to Pro for {pro // free}× more a day" if free and pro and pro >= 2 * free else " — or upgrade to Pro"


def _human(delta: timedelta) -> str:
    minutes = max(1, int(delta.total_seconds() // 60))
    if minutes < 60:
        return f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"{days} d {hours} h" if hours else f"{days} d"
    return f"{hours} h {minutes} min" if minutes else f"{hours} h"


def require(db: Session, user: User, action: str) -> None:
    """Refuse with 402 when this action no longer fits in the user's allowance."""
    if can_spend(db, user, action):
        return
    now = utcnow()
    cost = COSTS[action]
    free = (user.plan or "free") == "free"
    left_window, left_week = _room(user)
    if (left_window is None or left_window >= cost) and (left_week is None or left_week >= cost):  # the 30-day ceiling
        raise HTTPException(status_code=402, detail=(
            "You've used this month's fair-use AI for your plan. It comes back day by day, as your use from 30 days ago "
            "drops off" + (_upsell() if free else ". Live lectures still get basic notes.") + "."))
    weekly = left_window is None or left_window >= cost
    left = left_week if weekly else left_window
    start = user.usage_week_start if weekly else user.usage_window_start
    resets = (start + (WEEK if weekly else _window())) if start else now
    span = "weekly" if weekly else _span()
    upsell = _upsell() if free else ""
    if left:  # a little is left, just not enough for this (practice sets cost the most)
        where = "this week" if weekly else f"in this {span} window"
        head = f"{LABELS[action]} need {cost} units of AI allowance and you have {left} left {where}."
    else:
        head = f"You've used {'your free' if free else 'this'} {span} AI allowance."
    raise HTTPException(
        status_code=402,
        detail=f"{head} It resets in {_human(resets - now)}{upsell}.",
        headers={"X-Usage-Resets-At": resets.isoformat() + "Z"},
    )


def charge(db: Session, user: User, action: str, source: str | None = "ai") -> None:
    """Record an AI action. Offline answers are free, and so are actions counted another way (board notes). Commits."""
    if source != "ai" or not COSTS[action]:
        return
    now = utcnow()
    if db.get_bind().dialect.name != "sqlite":
        # lock and re-read the row: live capture and doubts can charge the same user at the same time
        db.execute(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    _roll(user, now)
    cost = COSTS[action]
    if not user.usage_window_start:
        user.usage_window_start = now
    if not user.usage_week_start:
        user.usage_week_start = now
    user.usage_window_used = (user.usage_window_used or 0) + cost
    user.usage_week_used = (user.usage_week_used or 0) + cost
    db.commit()


def lecture_limit_s(plan: str | None) -> int:
    """Seconds of lecture a study day gets AI board notes, for a plan; 0 means unlimited."""
    plan = plan or "free"
    hours = settings.LECTURE_HOURS_TEAM if plan == "team" else settings.LECTURE_HOURS_PRO if plan == "pro" else settings.LECTURE_HOURS_FREE
    return round(3600 * hours)


def _roll_lecture(user: User, now: datetime) -> None:
    if user.lecture_day_start and now >= user.lecture_day_start + _window():
        user.lecture_day_start, user.lecture_day_seconds = None, 0


def lecture_time_left(user: User) -> bool:
    """Whether today's lecture time still gets AI board notes."""
    _roll_lecture(user, utcnow())
    limit = lecture_limit_s(user.plan)
    return not limit or (user.lecture_day_seconds or 0) < limit


def count_lecture(user: User, seconds: float) -> None:
    """Add captured lecture time to the study day (the caller commits, with the frame)."""
    now = utcnow()
    _roll_lecture(user, now)
    if not user.lecture_day_start:
        user.lecture_day_start = now
    user.lecture_day_seconds = (user.lecture_day_seconds or 0) + max(0, round(seconds))


def caption_limit_s(plan: str | None) -> int:
    """Seconds of lecture captions a week for a plan; 0 means unlimited."""
    plan = plan or "free"
    if plan == "team":
        return 0
    return 60 * (settings.CAPTION_MINUTES_PRO_WEEK if plan == "pro" else settings.CAPTION_MINUTES_FREE_WEEK)


def _roll_captions(user: User, now: datetime) -> None:
    if user.caption_week_start and now >= user.caption_week_start + WEEK:
        user.caption_week_start, user.caption_week_seconds = None, 0


def captions_left(user: User) -> bool:
    """Whether this week's lecture captions still have time left (speech to text is the one cost paid by the minute)."""
    _roll_captions(user, utcnow())
    limit = caption_limit_s(user.plan)
    return not limit or (user.caption_week_seconds or 0) < limit


def charge_captions(db: Session, user: User, seconds: float) -> None:
    """Count transcribed lecture sound against the week, silence included (it is billed all the same). Commits."""
    now = utcnow()
    _roll_captions(user, now)
    if not user.caption_week_start:
        user.caption_week_start = now
    user.caption_week_seconds = (user.caption_week_seconds or 0) + max(0, round(seconds))
    db.commit()


def _meter(used: int, limit: int, start: datetime | None, span: timedelta) -> dict:
    return {
        "used": used, "limit": limit or None, "unlimited": not limit,
        "pct": 0 if not limit else min(100, round(100 * used / limit)),
        "resets_at": (start + span).isoformat() + "Z" if start else None,
    }


def status(db: Session, user: User) -> dict:
    _roll(user, utcnow())
    _roll_captions(user, utcnow())
    _roll_lecture(user, utcnow())
    per_window, per_week = limits(user.plan)
    return {
        "plan": user.plan or "free",
        "window_hours": settings.USAGE_WINDOW_HOURS,
        "window": _meter(user.usage_window_used or 0, per_window, user.usage_window_start, _window()),
        "week": _meter(user.usage_week_used or 0, per_week, user.usage_week_start, WEEK),
        # in minutes
        "lecture": _meter((user.lecture_day_seconds or 0) // 60, lecture_limit_s(user.plan) // 60, user.lecture_day_start, _window()),
        "lecture_limits": {p: lecture_limit_s(p) // 60 for p in ("free", "pro", "team")},
        "captions": _meter((user.caption_week_seconds or 0) // 60, caption_limit_s(user.plan) // 60, user.caption_week_start, WEEK),
        # the 30-day fair-use ceiling, as a share only (what the AI costs is Focs's business, not the student's worry)
        "fair_use_pct": min(100, round(100 * ledger.user_spend_inr(user.id) / ceiling)) if (ceiling := ceiling_inr(user)) else None,
        "costs": [{"action": k, "label": LABELS[k], "cost": v} for k, v in COSTS.items() if v],
        "limits": {p: dict(zip(("window", "week"), limits(p), strict=True)) for p in ("free", "pro", "team")},
    }
