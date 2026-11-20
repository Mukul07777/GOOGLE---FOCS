"""Master sessions: a mentor's live session for many students, like a class on Google Meet.

A mentor posts a session (once, or the same time for a few weeks): a title, what it covers, how long, how many seats
and a price per seat (₹0: free). Students preparing for that exam register: a free seat is booked at once; a paid seat
is held while the student pays. When PRO_GROUP_SESSIONS_PER_WEEK is set (0 at launch), that many paid sessions a week
cost a Pro student nothing and Focs pays the mentor their share instead. Each student writes the doubt they want answered, so the mentor walks in with a queue. Everyone
joins the same video room, which opens ten minutes before. Afterwards the mentor marks it held, with notes for those who
came, and earns their share of every paid or Pro seat.

Cancelling: a mentor can cancel before it starts (paid seats are refunded); a student can leave before it starts (a
paid seat is refunded up to 12 hours before).
"""
import secrets
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.mentors import _names, _short
from app.api.notifications import notify
from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_mentor, require_student
from app.core.ratelimit import limit
from app.models._util import utcnow
from app.models.mentor import GroupSeat, GroupSession, MentorProfile
from app.models.payment import Payment
from app.models.user import User
from app.services import payments
from app.services.mentors import EXAMS, exam_of, ist_week, mask_contacts, mentor_share, seat_booked, seat_holds

router = APIRouter(prefix="/mentors", tags=["mentors"])

AHEAD_DAYS = 30
MIN_NOTICE = timedelta(hours=1)
JOIN_EARLY = timedelta(minutes=10)
JOIN_LATE = timedelta(minutes=15)
HOLD = timedelta(minutes=15)  # how long an unpaid seat stays yours
REFUND_NOTICE = timedelta(hours=12)
MAX_REPEAT = 4
MAX_SEATS = 100


class ScheduleIn(BaseModel):
    starts_at: datetime
    topic: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=2000)
    minutes: int = Field(default=settings.GROUP_SESSION_MINUTES, ge=30, le=180)
    seats: int = Field(default=settings.GROUP_SESSION_SEATS, ge=1, le=MAX_SEATS)
    price_inr: int = Field(default=0, ge=0, le=settings.SESSION_PRICE_MAX_INR)
    repeat_weeks: int = Field(default=1, ge=1, le=MAX_REPEAT)


class SeatIn(BaseModel):
    doubt: str = Field(default="", max_length=600)


class AnsweredIn(BaseModel):
    answered: bool


class HeldIn(BaseModel):
    notes: str = Field(default="", max_length=3000)


def _iso(dt) -> str | None:
    return dt.isoformat() + "Z" if dt else None


def _utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def _mine(db: Session, user: User) -> MentorProfile:
    p = db.scalar(select(MentorProfile).where(MentorProfile.user_id == user.id))
    if p is None or p.status != "approved":
        raise HTTPException(status_code=403, detail="Only approved mentors host master sessions.")
    return p


def _session(db: Session, session_id: int) -> GroupSession:
    g = db.get(GroupSession, session_id)
    if g is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return g


def _live(g: GroupSession, now: datetime) -> bool:
    return g.status == "scheduled" and g.starts_at - JOIN_EARLY <= now <= g.starts_at + timedelta(minutes=g.minutes) + JOIN_LATE


def _lapse(db: Session, seats: list[GroupSeat]) -> None:
    """Unpaid seats whose time to pay ran out give their place back."""
    now, changed = utcnow(), False
    for s in seats:
        if s.status == "held" and (s.held_until is None or s.held_until <= now):
            s.status, changed = "cancelled", True
            p = db.get(Payment, s.payment_id) if s.payment_id else None
            if p is not None and p.status == "created":
                p.status = "failed"
    if changed:
        db.commit()


def _seats(db: Session, ids: list[int]) -> dict[int, list[GroupSeat]]:
    """The seats that count in each session (booked, or held and still inside their time to pay)."""
    rows = list(db.scalars(select(GroupSeat).where(GroupSeat.session_id.in_(ids)).order_by(GroupSeat.id))) if ids else []
    _lapse(db, rows)
    now, out = utcnow(), {}
    for s in rows:
        if seat_holds(s, now):
            out.setdefault(s.session_id, []).append(s)
    return out


def _out(g: GroupSession, taken: int, now: datetime) -> dict[str, Any]:
    live = _live(g, now)
    return {"id": g.id, "starts_at": _iso(g.starts_at), "minutes": g.minutes, "topic": g.topic, "description": g.description or "",
            "price_inr": g.price_inr or 0, "seats": g.seats, "taken": taken, "status": g.status, "notes": g.notes,
            "over": now > g.starts_at + timedelta(minutes=g.minutes),
            "can_join": live, "join_url": f"{settings.CALL_ROOM_BASE.rstrip('/')}/{g.room}" if live else None,
            "opens_at": _iso(g.starts_at - JOIN_EARLY)}


def _week_seats(db: Session, user: User) -> Counter:
    """Pro-included seats this student holds in sessions still on, by week (India time): the Pro quota counts these."""
    rows = db.execute(select(GroupSession.starts_at).join(GroupSeat, GroupSeat.session_id == GroupSession.id)
                      .where(GroupSeat.user_id == user.id, GroupSession.status != "cancelled", GroupSeat.paid_via == "pro",
                             or_(GroupSeat.status.is_(None), GroupSeat.status == "booked"))).all()
    return Counter(ist_week(r[0]) for r in rows)


def _refund(db: Session, seat: GroupSeat) -> bool:
    """A paid seat given back: its payment is marked for the admin to refund. True if there was money to return."""
    p = db.get(Payment, seat.payment_id) if seat.payment_id else None
    if p is None:
        return False
    if p.status == "paid":
        p.status = "refund_due"
        return True
    if p.status == "created":
        p.status = "failed"
    return False


# ---------------------------------------------------------------- the mentor's side
@router.post("/me/sessions", status_code=201, dependencies=[Depends(limit("group-schedule", 10))])
def schedule(body: ScheduleIn, db: Session = Depends(get_db), user: User = Depends(require_mentor)) -> list[dict[str, Any]]:
    """Post a master session, or the same time for up to four weeks."""
    p = _mine(db, user)
    start = _utc(body.starts_at).replace(second=0, microsecond=0)
    if start < utcnow() + MIN_NOTICE or start > utcnow() + timedelta(days=AHEAD_DAYS):
        raise HTTPException(status_code=422, detail="Pick a time from an hour to a month from now.")
    made = []
    for n in range(body.repeat_weeks):
        at = start + timedelta(weeks=n)
        clash = db.scalar(select(GroupSession).where(GroupSession.mentor_id == p.id, GroupSession.starts_at == at, GroupSession.status == "scheduled"))
        if clash:
            continue
        g = GroupSession(mentor_id=p.id, starts_at=at, minutes=body.minutes, topic=mask_contacts(body.topic.strip()),
                         description=mask_contacts(body.description.strip()) or None, price_inr=body.price_inr, seats=body.seats,
                         room=f"Focs-group-{secrets.token_urlsafe(12).replace('_', '').replace('-', '')}", pay_inr=0)
        db.add(g)
        made.append(g)
    db.commit()
    return [_out(g, 0, utcnow()) for g in made]


@router.get("/me/sessions")
def hosting(db: Session = Depends(get_db), user: User = Depends(require_mentor)) -> dict[str, Any]:
    """The mentor's sessions: coming up (with each registration's doubt, the queue, and what they'll earn) and the last
    month's."""
    p = _mine(db, user)
    now = utcnow()
    rows = db.scalars(select(GroupSession).where(GroupSession.mentor_id == p.id, GroupSession.status != "cancelled",
                                                 GroupSession.starts_at >= now - timedelta(days=30)).order_by(GroupSession.starts_at)).all()
    by = _seats(db, [g.id for g in rows])
    names = _names(db, {s.user_id for seats in by.values() for s in seats})
    out = []
    for g in rows:
        seats = by.get(g.id, [])
        booked = [s for s in seats if seat_booked(s)]
        earning = sum(s.mentor_share_inr if s.mentor_share_inr is not None else mentor_share(s.price_inr or 0)
                      for s in booked if s.paid_via in ("paid", "pro") and (s.price_inr or 0) > 0)
        out.append({**_out(g, len(seats), now), "needs_marking": g.status == "scheduled" and now >= g.starts_at,
                    "registered": len(booked), "earning_inr": earning + (g.pay_inr or 0),
                    "queue": [{"id": s.id, "student": _short(names.get(s.user_id)), "doubt": s.doubt, "answered": s.answered,
                               "paid_via": s.paid_via or "pro"} for s in booked]})
    return {"sessions": out, "minutes": settings.GROUP_SESSION_MINUTES, "seats": settings.GROUP_SESSION_SEATS, "max_seats": MAX_SEATS,
            "max_price_inr": settings.SESSION_PRICE_MAX_INR, "commission_pct": settings.MENTOR_COMMISSION_PCT,
            "pay_inr": settings.GROUP_SESSION_PAY_INR}


@router.put("/sessions/{session_id}/queue/{seat_id}")
def answered(session_id: int, seat_id: int, body: AnsweredIn, db: Session = Depends(get_db), user: User = Depends(require_mentor)) -> dict[str, Any]:
    p = _mine(db, user)
    g = _session(db, session_id)
    seat = db.get(GroupSeat, seat_id)
    if g.mentor_id != p.id or seat is None or seat.session_id != g.id:
        raise HTTPException(status_code=404, detail="Not in your session")
    seat.answered = body.answered
    db.commit()
    return {"id": seat.id, "answered": seat.answered}


@router.post("/sessions/{session_id}/held")
def held(session_id: int, body: HeldIn, db: Session = Depends(get_db), user: User = Depends(require_mentor)) -> dict[str, Any]:
    """The session happened: notes for the students who came (and it counts towards the mentor's earnings)."""
    p = _mine(db, user)
    g = _session(db, session_id)
    if g.mentor_id != p.id or g.status == "cancelled" or g.starts_at > utcnow():
        raise HTTPException(status_code=409, detail="A session is marked held once it has started.")
    g.status, g.notes = "done", mask_contacts(body.notes.strip()) or None
    db.commit()
    return _out(g, len(_seats(db, [g.id]).get(g.id, [])), utcnow())


@router.post("/sessions/{session_id}/cancel")
def cancel(session_id: int, db: Session = Depends(get_db), user: User = Depends(require_mentor)) -> dict[str, Any]:
    """Called off before it starts: every paid seat is refunded and everyone registered is told."""
    p = _mine(db, user)
    g = _session(db, session_id)
    if g.mentor_id != p.id or g.status != "scheduled" or g.starts_at <= utcnow():
        raise HTTPException(status_code=409, detail="Only a session that hasn't started can be cancelled.")
    g.status = "cancelled"  # (Pro seats stop counting towards the students' week)
    seats = _seats(db, [g.id]).get(g.id, [])
    for s in seats:
        _refund(db, s)
        if s.status == "held":
            s.status = "cancelled"
    first = (_names(db, {p.user_id}).get(p.user_id) or "Your mentor").split()[0]
    notify(db, [s.user_id for s in seats if seat_booked(s)], "session_cancelled",
           f"{first} cancelled the master session “{g.topic or 'Open doubts'}”." + (" Paid seats are refunded." if (g.price_inr or 0) else ""),
           "/app/mentors?tab=sessions")
    db.commit()
    return _out(g, 0, utcnow())


# ---------------------------------------------------------------- the student's side
@router.get("/sessions")
def sessions(db: Session = Depends(get_db), user: User = Depends(require_student)) -> dict[str, Any]:
    """Master sessions coming up with approved mentors for the student's exam, and the ones they've registered for."""
    exam = exam_of(user.exam_target)
    now = utcnow()
    mentors = {p.id: p for p in db.scalars(select(MentorProfile).where(MentorProfile.exam == exam, MentorProfile.status == "approved",
                                                                        MentorProfile.user_id != user.id))} if exam else {}
    mine_rows = list(db.scalars(select(GroupSeat).where(GroupSeat.user_id == user.id)))
    _lapse(db, mine_rows)
    mine = {s.session_id: s for s in mine_rows if s.status != "cancelled"}
    rows = db.scalars(select(GroupSession).where(
        ((GroupSession.mentor_id.in_(list(mentors))) & (GroupSession.status == "scheduled") & (GroupSession.starts_at >= now - timedelta(hours=2)))
        | (GroupSession.id.in_(list(mine)))).order_by(GroupSession.starts_at)).all()
    extra = {g.mentor_id for g in rows} - set(mentors)
    if extra:
        mentors.update({p.id: p for p in db.scalars(select(MentorProfile).where(MentorProfile.id.in_(extra)))})
    names = _names(db, {p.user_id for p in mentors.values()})
    counts = {k: len(v) for k, v in _seats(db, [g.id for g in rows]).items()}
    used = _week_seats(db, user)
    pro = payments.is_pro(user)
    out = []
    for g in rows:
        seat = mine.get(g.id)
        if g.status == "cancelled" and seat is None:
            continue
        p = mentors[g.mentor_id]
        info = _out(g, counts.get(g.id, 0), now)
        booked = seat is not None and seat_booked(seat)
        if not booked:
            info.update(can_join=False, join_url=None)  # the room is for those registered
        out.append({**info, "mentor": names.get(p.user_id, "Mentor"), "mentor_id": p.id, "credential": p.credential, "institution": p.institution,
                    "seated": booked, "seat_status": seat.status if seat else None, "paid_via": seat.paid_via if seat else None,
                    "my_doubt": seat.doubt if seat else None, "answered": seat.answered if seat else None,
                    "pro_free": pro and (g.price_inr or 0) > 0 and used[ist_week(g.starts_at)] < settings.PRO_GROUP_SESSIONS_PER_WEEK,
                    "week_free": pro and used[ist_week(g.starts_at)] < settings.PRO_GROUP_SESSIONS_PER_WEEK})
    return {"sessions": out, "pro": pro, "per_week": settings.PRO_GROUP_SESSIONS_PER_WEEK, "exam_label": EXAMS[exam]["label"] if exam else None}


@router.post("/sessions/{session_id}/seat", status_code=201, dependencies=[Depends(limit("group-seat", 20))])
def take_seat(session_id: int, body: SeatIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_student)) -> dict[str, Any]:
    """Register for a session: free seats are booked at once, a Pro student's included one a week too; otherwise the seat
    is held while they pay (the reply has the checkout)."""
    g = _session(db, session_id)
    p = db.get(MentorProfile, g.mentor_id)
    if g.status != "scheduled" or g.starts_at + timedelta(minutes=g.minutes) <= utcnow() or p.user_id == user.id:
        raise HTTPException(status_code=409, detail="This session isn't open for registration.")
    mine = list(db.scalars(select(GroupSeat).where(GroupSeat.session_id == g.id, GroupSeat.user_id == user.id)))
    _lapse(db, mine)
    if any(seat_booked(s) for s in mine):
        raise HTTPException(status_code=409, detail="You're already registered.")
    for s in mine:  # an earlier checkout left unpaid: start again
        if s.status == "held":
            _refund(db, s)
            s.status = "cancelled"
    if len(_seats(db, [g.id]).get(g.id, [])) >= g.seats:
        raise HTTPException(status_code=409, detail="This session is full.")
    price = g.price_inr or 0
    pro_free = price > 0 and payments.is_pro(user) and _week_seats(db, user)[ist_week(g.starts_at)] < settings.PRO_GROUP_SESSIONS_PER_WEEK
    via = "free" if price == 0 else "pro" if pro_free else "paid"
    seat = GroupSeat(session_id=g.id, user_id=user.id, doubt=mask_contacts(body.doubt.strip()), paid_via=via, price_inr=price,
                     mentor_share_inr=mentor_share(price) if price else None,
                     status="held" if via == "paid" else "booked", held_until=utcnow() + HOLD if via == "paid" else None)
    db.add(seat)
    db.flush()
    checkout = None
    if via == "paid":
        first = (_names(db, {p.user_id}).get(p.user_id) or "your mentor").split()[0]
        checkout = payments.start(db, user, "session_seat", price, f"Master session with {first}: {g.topic or 'Open doubts'}", ref_id=seat.id,
                                  local=payments.is_local(request))
        seat = db.get(GroupSeat, seat.id)
        seat.payment_id = checkout["payment_id"]
    db.commit()
    return {"session_id": g.id, "seated": via != "paid", "seat_status": seat.status, "paid_via": via, "my_doubt": seat.doubt, "checkout": checkout}


@router.delete("/sessions/{session_id}/seat", status_code=204)
def leave(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    """Give up a seat before the session starts (a paid seat is refunded up to 12 hours before)."""
    g = _session(db, session_id)
    seats = [s for s in db.scalars(select(GroupSeat).where(GroupSeat.session_id == g.id, GroupSeat.user_id == user.id)) if s.status != "cancelled"]
    if not seats or g.starts_at <= utcnow():
        raise HTTPException(status_code=409, detail="You can leave a session before it starts.")
    for s in seats:
        if s.paid_via == "paid":
            if s.status == "held" or g.starts_at - utcnow() >= REFUND_NOTICE:
                _refund(db, s)
            s.status = "cancelled"
        else:
            db.delete(s)
    db.commit()
