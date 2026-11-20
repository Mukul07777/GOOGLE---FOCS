"""How a student's preparation is going, in a few numbers: what a teacher sees for a class, and a parent for a child.

Read for many students at once (one query per kind of record, not per student)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Integer, case, func, select
from sqlalchemy.orm import Session

from app.models._util import utcnow
from app.models.mock import MockTest
from app.models.prep import TopicProgress
from app.models.quiz_attempt import QuizAttempt
from app.models.study_day import StudyDay
from app.models.user import User
from app.models.weak import WeakTopic
from app.services import streaks, syllabus

STREAK_DAYS = 90
WEAK_SHOWN = 6


def summaries(db: Session, users: list[User], today: date | None = None) -> dict[int, dict[str, Any]]:
    """For each student: this week's study time day by day, their streak, how much of their syllabus is done, their
    open weak chapters, their last test and how they answered questions this week."""
    ids = [u.id for u in users]
    if not ids:
        return {}
    today = today or utcnow().date()
    week = [today - timedelta(days=n) for n in range(6, -1, -1)]
    week_ago = utcnow() - timedelta(days=7)

    minutes: dict[int, dict[date, int]] = defaultdict(dict)
    for uid, day, mins in db.execute(select(StudyDay.user_id, StudyDay.day, StudyDay.minutes).where(
            StudyDay.user_id.in_(ids), StudyDay.day >= today - timedelta(days=STREAK_DAYS))):
        minutes[uid][day] = int(mins or 0)

    done: dict[int, set[str]] = defaultdict(set)
    for uid, topic_id in db.execute(select(TopicProgress.user_id, TopicProgress.topic_id).where(TopicProgress.user_id.in_(ids))):
        done[uid].add(topic_id)

    weak: dict[int, dict[str, int]] = defaultdict(dict)
    for uid, chapter_id, misses in db.execute(select(WeakTopic.user_id, WeakTopic.chapter_id, WeakTopic.misses).where(
            WeakTopic.user_id.in_(ids), WeakTopic.status == "open")):
        weak[uid][chapter_id] = weak[uid].get(chapter_id, 0) + int(misses or 1)

    tests: dict[int, list[tuple]] = defaultdict(list)  # newest first
    for row in db.execute(select(MockTest.user_id, MockTest.title, MockTest.score, MockTest.max_score, MockTest.submitted_at).where(
            MockTest.user_id.in_(ids), MockTest.status == "submitted").order_by(MockTest.submitted_at.desc())):
        tests[row[0]].append(row)

    answered: dict[int, tuple[int, int]] = {}
    right = func.sum(case((QuizAttempt.correct.is_(True), 1), else_=0)).cast(Integer)
    for uid, tried, correct in db.execute(select(QuizAttempt.user_id, func.count(QuizAttempt.id), right).where(
            QuizAttempt.user_id.in_(ids), QuizAttempt.attempted_at >= week_ago).group_by(QuizAttempt.user_id)):
        answered[uid] = (int(tried or 0), int(correct or 0))

    out: dict[int, dict[str, Any]] = {}
    for u in users:
        syl, whole = syllabus.of(u), syllabus.of(u, whole=True)
        topics = {t.id for c in syl.by_id.values() for t in c.topics} if syl else set()
        finished = len(done[u.id] & topics)
        spots = []
        for chapter_id, misses in sorted(weak[u.id].items(), key=lambda kv: -kv[1]):
            chapter = whole.by_id.get(chapter_id) if whole else None
            if chapter:
                spots.append({"id": chapter.id, "chapter": chapter.name, "subject": chapter.subject})
        mine = tests[u.id]
        last = None
        if mine:
            _, title, score, top, at = mine[0]
            last = {"title": title or "Test", "score": round(float(score or 0), 1), "max": top or 0,
                    "percent": round(100 * float(score or 0) / top) if top else 0, "on": at.date().isoformat() if at else None}
        tried, correct = answered.get(u.id, (0, 0))
        days = [minutes[u.id].get(d, 0) for d in week]
        active = {d for d, m in minutes[u.id].items() if m > 0}
        out[u.id] = {
            "exam": syllabus.label(u.exam_target), "week_minutes": sum(days), "days": days, "today_minutes": days[-1],
            "goal_minutes": u.daily_goal_min or 60, "streak": streaks.current_streak(active, today)["streak"],
            "syllabus": {"done": finished, "total": len(topics), "percent": round(100 * finished / len(topics)) if topics else None},
            "weak": spots[:WEAK_SHOWN], "weak_count": len(spots), "last_test": last,
            "tests_week": sum(1 for t in mine if t[4] and t[4] >= week_ago),
            "questions_week": tried, "accuracy_week": round(100 * correct / tried) if tried else None,
            "last_active": u.last_seen_at.date().isoformat() if u.last_seen_at else None,
        }
    return out
