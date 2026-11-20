"""Who counts as a real student, and which chapters real students actually work on. Shared by the number scripts
(scripts/evidence.py, scripts/warm_chains.py). Read-only: nothing here writes."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.models._util import utcnow
from app.models.gap import GapTrace
from app.models.user import User
from app.models.weak import WeakTopic
from app.models.working import WorkingCheck

NOT_REAL = ("demo.focs.%", "%@example.com", "%.invalid")


def real_students(db: Session) -> list[User]:
    """Active students only: no demo (demo.focs.*), test (@example.com, .invalid), mentor or switched-off accounts."""
    q = select(User).where(func.coalesce(User.role, "student") == "student", User.is_active.is_not(False))
    for pattern in NOT_REAL:
        q = q.where(User.email.not_ilike(pattern))
    return list(db.scalars(q))


def _tagged(db: Session, user_ids: set[int], days: int) -> list[tuple[int, str, int]]:
    """(student, chapter id, attempts) for every chapter-tagged attempt in the last ``days`` days.

    Counted: a weak chapter a test showed (WeakTopic, one per question lost), a root-cause trace (GapTrace) and a
    checked solution (WorkingCheck). Left out on purpose: QuizAttempt (its topic is free text, not a chapter id)
    and TopicProgress (it says what was finished, not what was attempted)."""
    if not user_ids:
        return []
    since = utcnow() - timedelta(days=days)
    tables = set(inspect(db.get_bind()).get_table_names())
    rows: list[tuple[int, str, int]] = []
    if "weak_topics" in tables:
        rows += [(uid, cid, n or 1) for uid, cid, n in db.execute(select(WeakTopic.user_id, WeakTopic.chapter_id, WeakTopic.misses).where(
            WeakTopic.user_id.in_(user_ids), WeakTopic.created_at >= since))]
    if "gap_traces" in tables:
        rows += [(uid, cid, 1) for uid, cid in db.execute(select(GapTrace.user_id, GapTrace.chapter_id).where(
            GapTrace.user_id.in_(user_ids), GapTrace.created_at >= since))]
    if "working_checks" in tables:
        rows += [(uid, cid, 1) for uid, cid in db.execute(select(WorkingCheck.user_id, WorkingCheck.chapter_id).where(
            WorkingCheck.user_id.in_(user_ids), WorkingCheck.created_at >= since, WorkingCheck.chapter_id.is_not(None)))]
    return rows


def chapter_activity(db: Session, user_ids: set[int], days: int = 60) -> Counter[str]:
    """Chapter id -> how many chapter-tagged attempts real students made in the last ``days`` days (see _tagged)."""
    counts: Counter[str] = Counter()
    for _, cid, n in _tagged(db, user_ids, days):
        counts[cid] += n
    return counts


def active_students(db: Session, user_ids: set[int], days: int = 60) -> int:
    """How many of these students made a chapter-tagged attempt in the last ``days`` days (for the privacy floor)."""
    return len({uid for uid, _, _ in _tagged(db, user_ids, days)})
