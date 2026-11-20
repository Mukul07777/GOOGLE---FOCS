"""Dashboard analytics. Days are bucketed in the student's local timezone (tz_offset from the browser)."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api._common import close_idle_sessions, note_counts, session_minutes, session_out
from app.core.deps import get_current_user, get_db
from app.models._util import utcnow
from app.models.doubt import Doubt
from app.models.flashcard import Flashcard
from app.models.note import Note
from app.models.quiz_attempt import QuizAttempt
from app.models.session import StudySession
from app.models.study_day import StudyDay
from app.models.user import User
from app.services import calibration, streaks, syllabus

router = APIRouter(prefix="/analytics", tags=["analytics"])

HEATMAP_DAYS = 7 * 53  # a year, like GitHub's contribution graph
MAX_MINUTES_PER_DAY = 16 * 60
BEAT_EVERY = timedelta(seconds=50)  # one minute of focus per heartbeat, however many tabs are open


class Heartbeat(BaseModel):
    activity: Literal["lecture", "mock", "practice", "flashcards", "room", "revision"]
    tz_offset: int = Field(0, ge=-840, le=840)


@router.post("/heartbeat", status_code=204)
def heartbeat(body: Heartbeat, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Sent once a minute while the student is really studying; becomes their focus time."""
    now = utcnow()
    today = (now + timedelta(minutes=body.tz_offset)).date()
    row = db.scalar(select(StudyDay).where(StudyDay.user_id == user.id, StudyDay.day == today))
    if row is None:
        row = StudyDay(user_id=user.id, day=today, minutes=0, by_activity={})
        db.add(row)
    elif row.last_beat_at and now - row.last_beat_at < BEAT_EVERY or row.minutes >= MAX_MINUTES_PER_DAY:
        return  # a second tab, or an impossible day: no extra minute
    row.minutes += 1
    row.by_activity = {**(row.by_activity or {}), body.activity: (row.by_activity or {}).get(body.activity, 0) + 1}
    row.last_beat_at = now
    db.commit()


@router.get("/calibration")
def calibration_report(session_id: int | None = None, days: int = 30, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Confidence vs reality: answers locked in as sure or guessing, set against right or wrong."""
    rep = calibration.report(db, user.id, session_id=session_id, days=max(1, min(days, 365)))
    return {**rep, "headline": calibration.headline(rep)}


@router.get("/overview")
def overview(
    tz_offset: int = Query(0, ge=-840, le=840, description="minutes east of UTC, e.g. 330 for IST"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    shift = timedelta(minutes=tz_offset)
    local = lambda dt: (dt + shift).date() if dt else None  # noqa: E731
    today = local(utcnow())

    close_idle_sessions(db, user.id)
    sessions = db.scalars(select(StudySession).where(StudySession.user_id == user.id)).all()
    attempts = db.scalars(select(QuizAttempt).where(QuizAttempt.user_id == user.id)).all()
    note_times = db.scalars(select(Note.captured_at).join(StudySession).where(StudySession.user_id == user.id)).all()
    review_times = db.scalars(select(Flashcard.last_reviewed_at).where(Flashcard.user_id == user.id,
                                                                      Flashcard.last_reviewed_at.is_not(None))).all()
    doubt_times = db.scalars(select(Doubt.created_at).where(Doubt.user_id == user.id)).all()

    minutes_by_day: dict[date, float] = defaultdict(float)
    for s in sessions:
        if s.started_at:
            minutes_by_day[local(s.started_at)] += session_minutes(s)
    # Focus heartbeats (lecture, mock, practice, flashcards, rooms, revision) count only minutes the student was
    # really there, so on any day that has them they are the number, and the activity breakdown adds up to it.
    # Only days from before heartbeats existed fall back to lecture start-to-end time.
    focus_days = {r.day: r for r in db.scalars(select(StudyDay).where(StudyDay.user_id == user.id))}
    for d, r in focus_days.items():
        minutes_by_day[d] = float(r.minutes)
    active_days: set[date] = {d for d, m in minutes_by_day.items() if m >= 1}
    for t in [*note_times, *review_times, *doubt_times, *(a.attempted_at for a in attempts)]:
        if t:
            active_days.add(local(t))

    streak = streaks.current_streak(active_days, today)
    best_streak = max(streaks.best_streak(active_days), streak["streak"])

    heat_start = today - timedelta(days=HEATMAP_DAYS - 1)
    activity_by_day: dict[date, int] = defaultdict(int)
    for t in [*note_times, *review_times, *doubt_times, *(a.attempted_at for a in attempts)]:
        if t and local(t) >= heat_start:
            activity_by_day[local(t)] += 1
    heatmap = [
        {"date": (heat_start + timedelta(days=i)).isoformat(),
         "minutes": round(minutes_by_day.get(heat_start + timedelta(days=i), 0)),
         "actions": activity_by_day.get(heat_start + timedelta(days=i), 0),
         "active": (heat_start + timedelta(days=i)) in active_days}
        for i in range(HEATMAP_DAYS)
    ]

    week = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        day_attempts = [a for a in attempts if local(a.attempted_at) == d]
        correct = sum(1 for a in day_attempts if a.correct)
        week.append({"date": d.isoformat(), "label": d.strftime("%a"), "minutes": round(minutes_by_day.get(d, 0)),
                     "questions": len(day_attempts), "correct": correct,
                     "accuracy": round(100 * correct / len(day_attempts)) if day_attempts else None})

    by_subject: dict[str, dict] = defaultdict(lambda: {"notes": 0, "questions": 0, "correct": 0})
    for subject, count in db.execute(select(Note.subject, func.count(Note.id)).join(StudySession)
                                     .where(StudySession.user_id == user.id).group_by(Note.subject)).all():
        by_subject[subject or "General"]["notes"] += count
    # a student's own subjects, then anything else of their field they have work in. Work from an exam they used to
    # prepare for stays in the Library, but isn't what they are studying now.
    mine = syllabus.of(user)
    field = set(syllabus.of(user, whole=True).subjects) if mine else None
    topic_stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for a in attempts:
        s = by_subject[a.subject or "General"]
        s["questions"] += 1
        s["correct"] += int(bool(a.correct))
        if a.topic and (field is None or not a.subject or a.subject in field):
            topic_stats[a.topic][0] += 1
            topic_stats[a.topic][1] += int(bool(a.correct))
    shown = list(by_subject) if field is None else [*mine.subjects, *(s for s in by_subject if s in field and s not in mine.subjects)]
    subjects = sorted(
        ({"subject": k, **(v := by_subject[k]), "accuracy": round(100 * v["correct"] / v["questions"]) if v["questions"] else None}
         for k in shown),
        key=lambda x: -(x["notes"] + x["questions"]),
    )
    weak_topics = sorted(
        ({"topic": t, "attempts": n, "accuracy": round(100 * c / n)} for t, (n, c) in topic_stats.items() if n >= 2),
        key=lambda x: (x["accuracy"], -x["attempts"]),
    )[:5]

    total_q = len(attempts)
    total_correct = sum(1 for a in attempts if a.correct)
    now = utcnow()
    recent = sorted(sessions, key=lambda s: s.started_at or datetime.min, reverse=True)[:5]
    counts = note_counts(db, [s.id for s in recent])
    return {
        "streak": streak["streak"],
        "best_streak": best_streak,
        "streak_at_risk": streak["at_risk"],
        "active_today": streak["active_today"],
        "freezes_left": streak["freezes_left"],
        "frozen_days": streak["frozen_days"],
        "study_days_year": sum(1 for d in active_days if d >= heat_start),
        "today_minutes": round(minutes_by_day.get(today, 0)),
        "today_by_activity": (focus_days[today].by_activity or {}) if today in focus_days else {},
        "daily_goal_min": user.daily_goal_min or 60,
        "week_minutes": round(sum(minutes_by_day.get(today - timedelta(days=i), 0) for i in range(7))),
        "totals": {
            "sessions": len(sessions),
            "notes": len(note_times),
            "questions": total_q,
            "doubts": len(doubt_times),
            "flashcards": db.scalar(select(func.count(Flashcard.id)).where(Flashcard.user_id == user.id)) or 0,
        },
        "accuracy": round(100 * total_correct / total_q, 1) if total_q else None,
        "due_cards": db.scalar(select(func.count(Flashcard.id)).where(Flashcard.user_id == user.id,
                                                                      Flashcard.due_at <= now)) or 0,
        "redo_count": sum(1 for a in attempts if a.needs_redo),
        "week": week,
        "heatmap": heatmap,
        "subjects": subjects,
        "weak_topics": weak_topics,
        "recent_sessions": [session_out(s, counts.get(s.id, 0)).model_dump(mode="json") for s in recent],
    }
