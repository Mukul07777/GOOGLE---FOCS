"""Confidence vs reality: what a student believes they understood, set against what they actually got right.

Every answer can be locked in as "sure" or "guessing". Four outcomes follow, and two of them matter most:

- blind spots: sure, and wrong. The student doesn't know they don't know; nothing else in their week will tell
  them. Memory research (the hypercorrection effect) finds these are also the mistakes corrected best once the
  answer is seen, so they lead: in the lecture's summary, in weak spots (counted double), and in the daily plan.
- hidden strengths: guessing, and right. Knowledge the student doesn't trust yet.

services/bridge.py does the same per chapter before and after a test; this is per question, everywhere.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models._util import utcnow
from app.models.quiz_attempt import QuizAttempt

CONFIDENCE = ("sure", "unsure")
SHOWN = 8


def _cell(a: QuizAttempt) -> str:
    return ("sure" if a.confidence == "sure" else "guess") + ("_right" if a.correct else "_wrong")


def report(db: Session, user_id: int, *, session_id: int | None = None, days: int = 30) -> dict[str, Any]:
    """The 2x2 (sure/guessing x right/wrong), accuracy when sure vs when guessing, per topic, and the blind spots
    and hidden strengths themselves (newest first). Only answers locked in with a confidence count."""
    stmt = select(QuizAttempt).where(QuizAttempt.user_id == user_id, QuizAttempt.confidence.in_(CONFIDENCE))
    stmt = stmt.where(QuizAttempt.session_id == session_id) if session_id else stmt.where(QuizAttempt.attempted_at >= utcnow() - timedelta(days=days))
    rows = db.scalars(stmt.order_by(QuizAttempt.attempted_at.desc())).all()
    grid = {"sure_right": 0, "sure_wrong": 0, "guess_right": 0, "guess_wrong": 0}
    topics: dict[str, dict[str, Any]] = {}
    for a in rows:
        cell = _cell(a)
        grid[cell] += 1
        t = topics.setdefault(a.topic or "General", {"topic": a.topic or "General", "subject": a.subject or "", **{k: 0 for k in grid}})
        t[cell] += 1
    sure = grid["sure_right"] + grid["sure_wrong"]
    guess = grid["guess_right"] + grid["guess_wrong"]

    def item(a: QuizAttempt) -> dict[str, Any]:
        return {"id": a.id, "topic": a.topic, "subject": a.subject, "question": (a.question or "")[:300], "q_type": a.q_type,
                "at": a.attempted_at.isoformat() + "Z" if a.attempted_at else None}

    by_topic = sorted(topics.values(), key=lambda t: (-t["sure_wrong"], -(t["sure_wrong"] + t["guess_wrong"]), t["topic"]))
    return {"answers": len(rows), "grid": grid,
            "sure_accuracy": round(100 * grid["sure_right"] / sure) if sure else None,
            "guess_accuracy": round(100 * grid["guess_right"] / guess) if guess else None,
            "blind_spots": [item(a) for a in rows if a.confidence == "sure" and not a.correct][:SHOWN],
            "hidden_strengths": [item(a) for a in rows if a.confidence == "unsure" and a.correct][:SHOWN],
            "topics": by_topic[:12]}


def headline(rep: dict[str, Any]) -> str | None:
    """One line to start from, e.g. after a lecture: the first blind spot."""
    if rep["blind_spots"]:
        b = rep["blind_spots"][0]
        more = len(rep["blind_spots"]) - 1
        return (f"You were sure about {b['topic'] or 'a question'} and got it wrong: start there."
                + (f" {more} more like it below." if more else ""))
    if rep["hidden_strengths"]:
        return "No blind spots: every answer you were sure of was right. Some guesses were right too, so you know more than you think."
    return None
