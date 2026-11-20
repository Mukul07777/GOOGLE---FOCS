"""Admin panel: its own sign-in, then growth, revenue, AI cost and usage. Student accounts can't open it."""
import hmac
import logging
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.rooms import hub
from app.core import ratelimit
from app.core.config import settings
from app.core.deps import get_db, require_admin
from app.core.ratelimit import limit
from app.core.security import create_admin_token, verify_password
from app.models._util import utcnow
from app.models.doubt import Doubt
from app.models.llm_call import LlmCall
from app.models.mock import MockTest
from app.models.note import Note
from app.models.quiz_attempt import QuizAttempt
from app.models.session import StudySession
from app.models.user import User
from app.services import gaps, ledger, pricing

log = logging.getLogger("focs.admin")
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])
public = APIRouter(prefix="/admin", tags=["admin"])  # just the sign-in

# checked when the ID is wrong too, so a wrong ID takes exactly as long as a wrong password
_DUMMY_HASH = "$2b$12$WMvzeczD/pq.n.vDXkcLpeh9Gbm8ZBqeMt2uABl0BwP8zvf4WIkXm"


class AdminLogin(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=200)


@public.post("/login", dependencies=[Depends(limit("admin-login", 5))])
def login(body: AdminLogin, request: Request) -> dict[str, Any]:
    ip = ratelimit.client_ip(request)  # the visitor, not the hosting proxy every visitor comes through
    failures = f"admin-login-failed:{ip}"
    ratelimit.guard(failures, 10, 15 * 60)  # locked out after 10 wrong tries: checked before the password is
    if not settings.ADMIN_PASSWORD_HASH:
        raise HTTPException(status_code=503, detail="The admin login isn't set up yet. Run set_admin.bat on the server "
                                                    "to choose the admin ID and password, then restart Focs.")
    same_id = hmac.compare_digest(body.username.strip().lower().encode(), settings.ADMIN_USERNAME.strip().lower().encode())
    right_pw = verify_password(body.password, settings.ADMIN_PASSWORD_HASH if same_id else _DUMMY_HASH)
    if not (same_id and right_pw):
        ratelimit.record(failures)
        log.warning("admin sign-in failed from %s", ip)
        raise HTTPException(status_code=401, detail="Wrong admin ID or password.")
    log.info("admin signed in from %s", ip)
    hours = settings.ADMIN_SESSION_HOURS
    return {"token": create_admin_token(settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD_HASH, hours),
            "username": settings.ADMIN_USERNAME, "expires_in": hours * 3600}


@router.get("/me")
def me(username: str = Depends(require_admin)) -> dict[str, str]:
    return {"username": username}

PAYING = ("pro", "team")


def _count(db: Session, stmt) -> int:
    return int(db.scalar(stmt) or 0)


def _tally(db: Session, column, missing: str) -> dict[str, int]:
    """Users per value of `column`, empty ones counted as `missing`. Grouped on the bare column: Postgres
    rejects grouping on coalesce(column, :param) because the select and the group by get separate parameters."""
    out: dict[str, int] = {}
    for value, n in db.execute(select(column, func.count()).group_by(column)).all():
        out[value or missing] = out.get(value or missing, 0) + n
    return out


def _day(value) -> str:
    return str(value)[:10]


def _money(usd: float) -> dict[str, float]:
    return {"usd": round(usd, 4), "inr": round(usd * settings.USD_INR, 2)}


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict[str, Any]:
    ledger.flush()  # include calls still queued
    now = utcnow()
    day, week, month = now - timedelta(days=1), now - timedelta(days=7), now - timedelta(days=30)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ---- users
    total = _count(db, select(func.count(User.id)))
    by_plan = _tally(db, User.plan, "free")
    by_exam = _tally(db, User.exam_target, "other")
    signups = {_day(d): n for d, n in db.execute(
        select(func.date(User.created_at), func.count()).where(User.created_at >= month).group_by(func.date(User.created_at))).all()}
    active = {label: _count(db, select(func.count(User.id)).where(User.last_seen_at >= since))
              for label, since in (("day", day), ("week", week), ("month", month))}
    paying = sum(n for plan, n in by_plan.items() if plan in PAYING)

    # ---- AI cost (list prices)
    def cost_since(since=None) -> float:
        stmt = select(func.coalesce(func.sum(LlmCall.cost_usd), 0.0))
        return float(db.scalar(stmt.where(LlmCall.created_at >= since) if since else stmt) or 0.0)

    cost_by_day = {_day(d): float(c) for d, c in db.execute(
        select(func.date(LlmCall.created_at), func.sum(LlmCall.cost_usd)).where(LlmCall.created_at >= month)
        .group_by(func.date(LlmCall.created_at))).all()}
    by_feature = [{"feature": f, "calls": n, **_money(float(c))} for f, n, c in db.execute(
        select(LlmCall.feature, func.count(), func.sum(LlmCall.cost_usd)).group_by(LlmCall.feature)
        .order_by(func.sum(LlmCall.cost_usd).desc())).all()]
    by_model = [{"model": m, "calls": n, "prompt_tokens": int(pt or 0), "completion_tokens": int(ct or 0), **_money(float(c))}
                for m, n, pt, ct, c in db.execute(
                    select(LlmCall.model, func.count(), func.sum(LlmCall.prompt_tokens), func.sum(LlmCall.completion_tokens),
                           func.sum(LlmCall.cost_usd)).group_by(LlmCall.model).order_by(func.sum(LlmCall.cost_usd).desc())).all()]
    top = db.execute(select(LlmCall.user_id, func.sum(LlmCall.cost_usd), func.count()).where(LlmCall.user_id.is_not(None))
                     .group_by(LlmCall.user_id).order_by(func.sum(LlmCall.cost_usd).desc()).limit(10)).all()
    names = {u.id: u for u in db.scalars(select(User).where(User.id.in_([uid for uid, _, _ in top])))}
    top_users = [{"user_id": uid, "name": names[uid].full_name if uid in names else "deleted account",
                  "email": names[uid].email if uid in names else None, "plan": names[uid].plan if uid in names else None,
                  "calls": n, **_money(float(c))} for uid, c, n in top]
    calls_total = _count(db, select(func.count(LlmCall.id)))
    month_cost = cost_since(month)
    active_month = max(1, active["month"])

    # ---- revenue (payments are not connected yet: expected monthly revenue from paying plans)
    month_price = pricing.price("exam", "month")[0]
    mrr = by_plan.get("pro", 0) * month_price

    # ---- usage
    usage = {
        "lectures": _count(db, select(func.count(StudySession.id))),
        "boards": _count(db, select(func.count(Note.id))),
        "questions_answered": _count(db, select(func.count(QuizAttempt.id))),
        "doubts": _count(db, select(func.count(Doubt.id))),
        "mocks_taken": _count(db, select(func.count(MockTest.id)).where(MockTest.status == "submitted")),
        "lectures_30d": _count(db, select(func.count(StudySession.id)).where(StudySession.started_at >= month)),
        "rooms_live": sum(1 for s in hub.rooms.values() if s.members),
        "people_in_rooms": sum(len({m.user_id for m in s.members}) for s in hub.rooms.values()),
    }

    days = [(now - timedelta(days=i)).date().isoformat() for i in range(29, -1, -1)]
    return {
        "generated_at": now.isoformat() + "Z",
        "goal": {"target": settings.GOAL_CUSTOMERS, "paying": paying, "signups": total},
        "users": {"total": total, "new_today": sum(v for k, v in signups.items() if k == days[-1]),
                  "new_7d": _count(db, select(func.count(User.id)).where(User.created_at >= week)),
                  "new_30d": _count(db, select(func.count(User.id)).where(User.created_at >= month)),
                  "active": active, "by_plan": by_plan, "by_exam": by_exam, "paying": paying},
        "revenue": {"price_inr": month_price, "offer": pricing.offer(), "pro_users": by_plan.get("pro", 0), "team_users": by_plan.get("team", 0),
                    "mrr_inr": mrr, "collected_inr": 0, "payments_connected": False},
        "ai_cost": {"total": _money(cost_since()), "today": _money(cost_since(day)), "week": _money(cost_since(week)),
                    "this_month": _money(cost_since(start_of_month)), "last_30d": _money(month_cost),
                    "per_active_user_30d": _money(month_cost / active_month), "calls": calls_total,
                    "by_feature": by_feature, "by_model": by_model, "top_users": top_users, "usd_inr": settings.USD_INR,
                    "budget": {"daily_inr": round(ledger.free_budget_inr(), 2), "spent_inr": round(ledger.spent_today_inr(), 2),
                               "reached": ledger.over_budget()},
                    "note": "List prices for every recorded AI call. While on free tiers, the actual bill is ₹0."},
        "margin_30d_inr": round(mrr - month_cost * settings.USD_INR, 2),
        "series": [{"day": d, "signups": signups.get(d, 0), "cost_inr": round(cost_by_day.get(d, 0.0) * settings.USD_INR, 2)}
                   for d in days],
        "usage": usage,
        "roots": gaps.proof(db),
    }


@router.get("/users")
def users(q: str = Query("", max_length=80), limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    ledger.flush()
    stmt = select(User)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.email.ilike(like), User.full_name.ilike(like)))
    rows = db.scalars(stmt.order_by(User.created_at.desc()).limit(limit)).all()
    costs = dict(db.execute(select(LlmCall.user_id, func.sum(LlmCall.cost_usd))
                            .where(LlmCall.user_id.in_([u.id for u in rows])).group_by(LlmCall.user_id)).all())
    lectures = dict(db.execute(select(StudySession.user_id, func.count()).where(StudySession.user_id.in_([u.id for u in rows]))
                               .group_by(StudySession.user_id)).all())
    return [{"id": u.id, "name": u.full_name, "email": u.email, "plan": u.plan or "free", "exam": u.exam_target,
             "joined": u.created_at.isoformat() + "Z" if u.created_at else None,
             "last_seen": u.last_seen_at.isoformat() + "Z" if u.last_seen_at else None,
             "lectures": lectures.get(u.id, 0), **_money(float(costs.get(u.id) or 0.0))} for u in rows]
