"""Mentor calls: half an hour on video inside a mentorship.

A mentor sets the hours they're free each week (India time) and their own price; a student books one of the next two
weeks' open slots and pays that price (Focs keeps a share; a mentor who sets ₹0 gives free calls, booked at once).
The slot is held for a few minutes while the student pays. The call happens in a private video room that opens ten
minutes before. Afterwards the mentor writes notes and up to five action items, which the student ticks off, and the
student rates the call.

Cancelling: a mentor can always cancel (a paid call is then refunded); a student gets a refund up to 12 hours before.
"""
import re
import secrets
from datetime import datetime, time, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.mentors import _mentorship, _names, _short
from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_mentor
from app.core.ratelimit import limit
from app.models._util import utcnow
from app.models.mentor import MentorCall, MentorProfile
from app.models.payment import Payment
from app.models.user import User
from app.services import payments, progress
from app.services.mentors import call_price, mask_contacts, mentor_share, slot_taken

router = APIRouter(prefix="/mentors", tags=["mentors"])

IST = timedelta(hours=5, minutes=30)  # mentors' hours are India time (no daylight saving)
BOOK_AHEAD_DAYS = 14
MIN_NOTICE = timedelta(hours=3)
HOLD = timedelta(minutes=15)  # how long an unpaid booking keeps its slot
JOIN_EARLY = timedelta(minutes=10)
JOIN_LATE = timedelta(minutes=30)  # after the planned end
REFUND_NOTICE = timedelta(hours=12)
MAX_SLOTS = 40
MAX_ACTIONS = 5
_TIME = re.compile(r"^([01]\d|2[0-3]):(00|30)$")


class Slot(BaseModel):
    day: int = Field(ge=0, le=6)  # Monday = 0
    time: str

    @field_validator("time")
    @classmethod
    def _on_the_half_hour(cls, v: str) -> str:
        if not _TIME.match(v):
            raise ValueError("a time like 19:00 or 19:30")
        return v


class SlotsIn(BaseModel):
    slots: list[Slot] = Field(max_length=MAX_SLOTS)


class BookIn(BaseModel):
    starts_at: datetime
    agenda: str = Field(default="", max_length=1000)


class NotesIn(BaseModel):
    notes: str = Field(min_length=10, max_length=3000)
    actions: list[str] = Field(default_factory=list, max_length=MAX_ACTIONS)


class ActionIn(BaseModel):
    done: bool


class RateIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    review: str = Field(default="", max_length=600)


def _iso(dt) -> str | None:
    return dt.isoformat() + "Z" if dt else None


def _utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def open_slots(profile: MentorProfile, now: datetime) -> list[datetime]:
    """The mentor's weekly hours over the next two weeks, as UTC start times, from three hours ahead."""
    today = (now + IST).date()
    out = set()
    for n in range(BOOK_AHEAD_DAYS):
        day = today + timedelta(days=n)
        for s in profile.slots or []:
            if s.get("day") == day.weekday():
                h, m = map(int, s["time"].split(":"))
                start = datetime.combine(day, time(h, m)) - IST
                if start >= now + MIN_NOTICE:
                    out.add(start)
    return sorted(out)


def _lapse(db: Session, calls: list[MentorCall]) -> None:
    """Unpaid holds that ran out give their slot back."""
    now, changed = utcnow(), False
    for c in calls:
        if c.status == "held" and (c.held_until is None or c.held_until <= now):
            c.status, c.cancelled_by, changed = "cancelled", "unpaid", True
            p = db.get(Payment, c.payment_id) if c.payment_id else None
            if p is not None and p.status == "created":
                p.status = "failed"
    if changed:
        db.commit()


def _out(c: MentorCall, role: str, other: str) -> dict[str, Any]:
    now = utcnow()
    end = c.starts_at + timedelta(minutes=c.minutes)
    live = c.status == "booked" and c.starts_at - JOIN_EARLY <= now <= end + JOIN_LATE
    return {"id": c.id, "mentorship_id": c.mentorship_id, "role": role, "with": other, "starts_at": _iso(c.starts_at), "ends_at": _iso(end),
            "minutes": c.minutes, "status": c.status, "paid_via": c.paid_via, "price_inr": c.price_inr, "agenda": c.agenda,
            "snapshot": c.snapshot if role == "mentor" else None, "notes": c.notes, "actions": c.actions or [],
            "rating": c.rating, "review": c.review, "cancelled_by": c.cancelled_by,
            "join_url": f"{settings.CALL_ROOM_BASE.rstrip('/')}/{c.room}" if live else None, "can_join": live,
            "opens_at": _iso(c.starts_at - JOIN_EARLY), "over": now > end,
            "payment_id": c.payment_id if c.status == "held" else None,
            "needs_notes": role == "mentor" and c.status == "booked" and now >= c.starts_at,
            "can_rate": role == "student" and c.status in ("booked", "done") and now >= end and c.rating is None,
            "refundable": c.paid_via == "paid" and (role == "mentor" or c.starts_at - now >= REFUND_NOTICE)}


def _call(db: Session, user: User, call_id: int) -> tuple[MentorCall, str, str]:
    c = db.get(MentorCall, call_id)
    profile = db.get(MentorProfile, c.mentor_id) if c else None
    if c is None or user.id not in (c.student_id, profile.user_id):
        raise HTTPException(status_code=404, detail="Call not found")
    role = "mentor" if profile.user_id == user.id else "student"
    names = _names(db, {profile.user_id, c.student_id})
    return c, role, names.get(profile.user_id, "Mentor") if role == "student" else _short(names.get(c.student_id))


# ---------------------------------------------------------------- the mentor's hours
@router.put("/me/slots")
def set_slots(body: SlotsIn, db: Session = Depends(get_db), user: User = Depends(require_mentor)) -> dict[str, Any]:
    profile = db.scalar(select(MentorProfile).where(MentorProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(status_code=404, detail="You haven't applied to mentor.")
    profile.slots = sorted({(s.day, s.time) for s in body.slots})
    profile.slots = [{"day": d, "time": t} for d, t in profile.slots]
    db.commit()
    return {"slots": profile.slots}


# ---------------------------------------------------------------- booking
@router.get("/mentorships/{mentorship_id}/calls")
def calls_of(mentorship_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """A mentorship's calls, and (for the student) the open slots."""
    m, profile, role = _mentorship(db, user, mentorship_id)
    calls = db.scalars(select(MentorCall).where(MentorCall.mentorship_id == m.id).order_by(MentorCall.starts_at.desc())).all()
    _lapse(db, list(calls))
    names = _names(db, {profile.user_id, m.student_id})
    other = names.get(profile.user_id, "Mentor") if role == "student" else _short(names.get(m.student_id))
    slots = []
    if role == "student" and m.status == "active":
        slots = [{"starts_at": _iso(s)} for s in open_slots(profile, utcnow()) if not slot_taken(db, profile.id, s)]
    return {"calls": [c for c in (_out(c, role, other) for c in calls) if c["status"] != "cancelled" or c["cancelled_by"] != "unpaid"],
            "slots": slots, "has_hours": bool(profile.slots), "price_inr": call_price(profile),
            "minutes": settings.MENTOR_CALL_MINUTES, "pro": payments.is_pro(user), "payments": payments.provider(payments.is_local(request)),
            "mentor_share_inr": mentor_share(call_price(profile))}


@router.post("/mentorships/{mentorship_id}/calls", status_code=201, dependencies=[Depends(limit("mentor-book", 10))])
def book(mentorship_id: int, body: BookIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Book a slot at the mentor's price: held while the student pays (the reply has the checkout), or booked at once
    when the mentor's calls are free."""
    m, profile, role = _mentorship(db, user, mentorship_id)
    if role != "student":
        raise HTTPException(status_code=403, detail="The student books the call.")
    if m.status != "active":
        raise HTTPException(status_code=409, detail="Calls are booked inside an active mentorship.")
    start = _utc(body.starts_at).replace(second=0, microsecond=0)
    if start not in open_slots(profile, utcnow()):
        raise HTTPException(status_code=422, detail="That time isn't one of your mentor's open slots.")
    if slot_taken(db, profile.id, start):
        raise HTTPException(status_code=409, detail="Someone just took that slot. Pick another.")
    price = call_price(profile)
    free = price == 0
    call = MentorCall(mentorship_id=m.id, mentor_id=profile.id, student_id=user.id, starts_at=start, minutes=settings.MENTOR_CALL_MINUTES,
                      status="booked" if free else "held", held_until=None if free else utcnow() + HOLD, paid_via="free" if free else "paid",
                      price_inr=price, mentor_share_inr=mentor_share(price),
                      room=f"Focs-{secrets.token_urlsafe(12).replace('_', '').replace('-', '')}", agenda=mask_contacts(body.agenda.strip()),
                      snapshot=progress.summaries(db, [user])[user.id] if m.share_progress else None)
    db.add(call)
    db.flush()
    if free:
        db.commit()
        return {"call": _out(call, "student", ""), "checkout": None}
    first = (_names(db, {profile.user_id}).get(profile.user_id) or "your mentor").split()[0]
    checkout = payments.start(db, user, "mentor_call", call.price_inr, f"{call.minutes}-minute call with {first}", ref_id=call.id,
                              local=payments.is_local(request))
    call = db.get(MentorCall, call.id)
    call.payment_id = checkout["payment_id"]
    db.commit()
    return {"call": _out(call, "student", ""), "checkout": checkout}


@router.get("/calls")
def my_calls(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Every call you're in, as a student or a mentor: what's coming, what to rate, notes to write, and open action items."""
    me = db.scalar(select(MentorProfile).where(MentorProfile.user_id == user.id))
    calls = db.scalars(select(MentorCall).where((MentorCall.student_id == user.id) | (MentorCall.mentor_id == (me.id if me else -1)))
                       .order_by(MentorCall.starts_at)).all()
    _lapse(db, list(calls))
    profiles = {p.id: p for p in db.scalars(select(MentorProfile).where(MentorProfile.id.in_({c.mentor_id for c in calls})))} if calls else {}
    names = _names(db, {p.user_id for p in profiles.values()} | {c.student_id for c in calls})
    rows = []
    for c in calls:
        role = "mentor" if me and c.mentor_id == me.id else "student"
        other = names.get(profiles[c.mentor_id].user_id, "Mentor") if role == "student" else _short(names.get(c.student_id))
        rows.append(_out(c, role, other))
    upcoming = [r for r in rows if r["status"] in ("booked", "held") and not r["over"]]
    return {"upcoming": upcoming, "to_rate": [r for r in rows if r["can_rate"]], "to_note": [r for r in rows if r["needs_notes"]],
            "actions": [{"call_id": r["id"], "index": i, "text": a["text"], "with": r["with"]}
                        for r in rows if r["role"] == "student" for i, a in enumerate(r["actions"]) if not a.get("done")]}


@router.post("/calls/{call_id}/cancel")
def cancel(call_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    c, role, other = _call(db, user, call_id)
    if c.status not in ("held", "booked") or c.starts_at <= utcnow():
        raise HTTPException(status_code=409, detail="Only a call that hasn't started can be cancelled.")
    p = db.get(Payment, c.payment_id) if c.payment_id else None
    if p is not None:
        if p.status == "paid" and (role == "mentor" or c.starts_at - utcnow() >= REFUND_NOTICE):
            p.status = "refund_due"
        elif p.status == "created":
            p.status = "failed"
    c.status, c.cancelled_by = "cancelled", role
    db.commit()
    return _out(c, role, other)


# ---------------------------------------------------------------- after the call
@router.post("/calls/{call_id}/notes")
def notes(call_id: int, body: NotesIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """The mentor's notes and the student's action items: what to do before the next call."""
    c, role, other = _call(db, user, call_id)
    if role != "mentor":
        raise HTTPException(status_code=403, detail="The mentor writes the call notes.")
    if c.status not in ("booked", "done") or c.starts_at > utcnow():
        raise HTTPException(status_code=409, detail="Notes are written after the call.")
    c.notes = mask_contacts(body.notes.strip())
    c.actions = [{"text": mask_contacts(a.strip())[:200], "done": False} for a in body.actions if a.strip()][:MAX_ACTIONS]
    c.status = "done"
    db.commit()
    return _out(c, role, other)


@router.put("/calls/{call_id}/actions/{index}")
def tick(call_id: int, index: int, body: ActionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    c, role, other = _call(db, user, call_id)
    actions = [dict(a) for a in c.actions or []]
    if role != "student" or not 0 <= index < len(actions):
        raise HTTPException(status_code=404, detail="Action item not found")
    actions[index]["done"] = body.done
    c.actions = actions
    db.commit()
    return _out(c, role, other)


@router.post("/calls/{call_id}/rate")
def rate(call_id: int, body: RateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    c, role, other = _call(db, user, call_id)
    if role != "student" or c.status not in ("booked", "done") or utcnow() < c.starts_at + timedelta(minutes=c.minutes):
        raise HTTPException(status_code=409, detail="A call is rated by the student, once it's over.")
    c.rating, c.review, c.status = body.rating, mask_contacts(body.review.strip()) or None, "done"
    db.commit()
    return _out(c, role, other)
