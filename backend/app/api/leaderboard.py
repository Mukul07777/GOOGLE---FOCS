"""Weekly / all-time leaderboard built from every question a student answers (practice, pop quizzes,
room quizzes, mocks) and every junior's question their answer settled in Ask a senior. Names are shown as
"Asha V." and students can opt out in Settings."""
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import Integer, case, func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models._util import utcnow
from app.models.campus import CampusPost
from app.models.quiz_attempt import QuizAttempt
from app.models.user import User

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

XP_CORRECT, XP_TRIED = 10, 2
XP_HELPED = 25  # an answer the asker marked as the one that settled their question


def display_name(full_name: str) -> str:
    parts = full_name.split()
    if not parts:
        return "Student"
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0].upper()}."


@router.get("")
def leaderboard(period: Literal["week", "all"] = "week", scope: Literal["exam", "everyone"] = "exam",
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    correct = func.sum(case((QuizAttempt.correct.is_(True), 1), else_=0)).cast(Integer)
    tried = func.count(QuizAttempt.id)
    q = (select(User.id, User.full_name, User.exam_target, correct.label("correct"), tried.label("tried"))
         .join(QuizAttempt, QuizAttempt.user_id == User.id)
         .where(func.coalesce(User.show_on_leaderboard, True).is_(True))
         .group_by(User.id, User.full_name, User.exam_target))
    if period == "week":
        q = q.where(QuizAttempt.attempted_at >= utcnow() - timedelta(days=7))
    if scope == "exam" and user.exam_target:
        q = q.where(User.exam_target == user.exam_target)

    h = (select(User.id, User.full_name, User.exam_target, func.count(CampusPost.id).label("helped"))
         .join(CampusPost, CampusPost.user_id == User.id)
         .where(CampusPost.accepted.is_(True), CampusPost.ai.isnot(True), func.coalesce(User.show_on_leaderboard, True).is_(True))
         .group_by(User.id, User.full_name, User.exam_target))
    if period == "week":
        h = h.where(CampusPost.created_at >= utcnow() - timedelta(days=7))
    if scope == "exam" and user.exam_target:
        h = h.where(User.exam_target == user.exam_target)
    helped = {uid: (name, exam, int(n)) for uid, name, exam, n in db.execute(h).all()}

    rows = []
    for uid, name, exam, right, total in db.execute(q).all():
        right, total = int(right or 0), int(total or 0)
        n = helped.pop(uid, (None, None, 0))[2]
        rows.append({"user_id": uid, "name": display_name(name), "exam": exam, "correct": right, "answered": total,
                     "accuracy": round(100 * right / total) if total else 0, "helped": n,
                     "xp": right * XP_CORRECT + (total - right) * XP_TRIED + n * XP_HELPED})
    for uid, (name, exam, n) in helped.items():  # students who only helped this period
        rows.append({"user_id": uid, "name": display_name(name), "exam": exam, "correct": 0, "answered": 0, "accuracy": 0,
                     "helped": n, "xp": n * XP_HELPED})
    rows.sort(key=lambda r: (-r["xp"], -r["accuracy"], r["name"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    me = next((r for r in rows if r["user_id"] == user.id), None)
    return {"period": period, "scope": scope, "exam": user.exam_target, "total": len(rows),
            "top": rows[:50], "me": me, "hidden": user.show_on_leaderboard is False,
            "xp_rule": f"{XP_CORRECT} XP for each correct answer, {XP_TRIED} XP for each attempt that missed, "
                       f"{XP_HELPED} XP for each junior's question your answer settled"}
