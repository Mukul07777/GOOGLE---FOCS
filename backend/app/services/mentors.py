"""Mentors: who mentors for which exam, what they help with, and keeping a conversation on Focs.

Many students preparing for JEE or NEET are minors talking to young adults, so a mentor is listed only after Focs
has seen proof of what they cleared, phone numbers and emails are hidden in messages (a conversation that moves to
WhatsApp is one nobody can look at when it is reported), and either side can report a conversation."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models._util import utcnow
from app.core.config import settings
from app.models.mentor import GroupSeat, GroupSession, MentorCall, MentorPayout, MentorProfile

EXAMS = {
    "jee": {"label": "JEE", "who": "IIT and NIT students who cleared JEE"},
    "neet": {"label": "NEET", "who": "medical students who cleared NEET"},
    "upsc": {"label": "UPSC", "who": "candidates who reached the UPSC interview or made the list"},
    "gate": {"label": "GATE", "who": "students with a good GATE rank, now at IITs, IISc or PSUs"},
    "cbse": {"label": "School (Class 1 to 12)", "who": "students who did well in their boards and entrance exams"},
    "ca": {"label": "CA", "who": "qualified chartered accountants and final-level students"},
    "college": {"label": "B.Tech", "who": "seniors who did well in the same courses"},
    "placement": {"label": "Placements", "who": "students placed at good companies"},
    "ssc_cgl": {"label": "SSC CGL", "who": "officers selected through SSC CGL and candidates who cleared Tier-II"},
}

TOPICS = {
    "plan": "Study plan and timetable",
    "mocks": "Mock tests and analysis",
    "subjects": "Weak subjects",
    "revision": "Revision",
    "mindset": "Stress and motivation",
    "choices": "Colleges, branches and careers",
    "writing": "Answer writing",
    "interview": "Interview",
}

LANGUAGES = {"en": "English", "hi": "Hindi"}
CHECKIN_EVERY_DAYS = 7
MAX_MENTORS_PER_STUDENT = 3
MAX_CAPACITY = 20


def exam_of(exam_target: str | None) -> str | None:
    """The mentoring exam for what a student is preparing for (a GATE paper is GATE, a B.Tech branch is B.Tech)."""
    t = exam_target or ""
    if t in ("jee", "neet", "upsc", "ca", "ssc_cgl"):
        return t
    if t == "coding":
        return "placement"
    for prefix in ("gate", "cbse", "college"):
        if t.startswith(prefix):
            return prefix
    return None


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)")
_HANDLES = re.compile(r"\b(?:wa\.me|t\.me|chat\.whatsapp\.com|instagram\.com|telegram\.me)/\S+", re.I)
HIDDEN = "[contact hidden: keep the conversation on Focs]"


def mask_contacts(text: str) -> str:
    """Phone numbers, emails and chat links swapped for a note. Short numbers (a rank, a year, marks) are kept."""
    text = _HANDLES.sub(HIDDEN, _EMAIL.sub(HIDDEN, text))
    return _PHONE.sub(lambda m: HIDDEN if len(re.sub(r"\D", "", m.group())) >= 10 else m.group(), text)


# ---------------------------------------------------------------- prices
def call_price(profile: MentorProfile) -> int:
    """What this mentor charges for a private call: their own price, or Focs's default until they set one."""
    return settings.MENTOR_CALL_PRICE_INR if profile.call_price_inr is None else profile.call_price_inr


# ---------------------------------------------------------------- master-session seats
def seat_holds(s: GroupSeat, now: datetime) -> bool:
    """Whether a seat counts: booked, or held and still inside its time to pay. (Older rows have no status: booked.)"""
    status = s.status or "booked"
    return status == "booked" or (status == "held" and s.held_until is not None and s.held_until > now)


def seat_booked(s: GroupSeat) -> bool:
    return (s.status or "booked") == "booked"


# ---------------------------------------------------------------- calls
IST = timedelta(hours=5, minutes=30)  # mentors' times are India time (no daylight saving)


def ist_week(start: datetime) -> date:
    """The Monday (India time) of the week a UTC time falls in."""
    local = (start + IST).date()
    return local - timedelta(days=local.weekday())


def holds(c: MentorCall, now: datetime) -> bool:
    """Whether a call keeps its slot: booked or done, or held and still inside its time to pay."""
    return c.status in ("booked", "done") or (c.status == "held" and c.held_until is not None and c.held_until > now)


def slot_taken(db: Session, mentor_id: int, starts_at: datetime, ignore: int | None = None) -> bool:
    now = utcnow()
    rows = db.scalars(select(MentorCall).where(MentorCall.mentor_id == mentor_id, MentorCall.starts_at == starts_at,
                                               MentorCall.status.in_(("held", "booked", "done"))))
    return any(c.id != ignore and holds(c, now) for c in rows)


def stats(db: Session, mentor_ids: list[int]) -> dict[int, dict[str, Any]]:
    """Calls done and the average rating, for mentor cards."""
    out: dict[int, dict[str, Any]] = {i: {"calls_done": 0, "rating": None, "ratings": 0} for i in mentor_ids}
    ratings: dict[int, list[int]] = {}
    for mid, rating in db.execute(select(MentorCall.mentor_id, MentorCall.rating).where(
            MentorCall.mentor_id.in_(mentor_ids), MentorCall.status == "done")) if mentor_ids else []:
        out[mid]["calls_done"] += 1
        if rating:
            ratings.setdefault(mid, []).append(rating)
    for mid, rs in ratings.items():
        out[mid].update(rating=round(sum(rs) / len(rs), 1), ratings=len(rs))
    return out


# ---------------------------------------------------------------- money
def mentor_share(price_inr: int) -> int:
    """What the mentor earns from a paid call: the price less Focs's share."""
    return price_inr - round(price_inr * settings.MENTOR_COMMISSION_PCT / 100)


def earnings(db: Session, mentor_ids: list[int], since: datetime | None = None) -> dict[int, dict[str, int]]:
    """Per mentor: paid calls done and what they earned, master sessions held and their share of every paid or Pro seat
    (older sessions: a fixed pay, if anyone came), what Focs kept, what was paid out, and what's owed. ``since`` limits
    the earned figures (not payouts or owed)."""
    out = {i: {"calls": 0, "calls_inr": 0, "focs_inr": 0, "sessions": 0, "sessions_inr": 0, "earned_inr": 0, "paid_out_inr": 0, "owed_inr": 0}
           for i in mentor_ids}
    if not mentor_ids:
        return out
    total = {i: 0 for i in mentor_ids}
    for c in db.scalars(select(MentorCall).where(MentorCall.mentor_id.in_(mentor_ids), MentorCall.status == "done", MentorCall.paid_via == "paid")):
        share = c.mentor_share_inr if c.mentor_share_inr is not None else mentor_share(c.price_inr)
        total[c.mentor_id] += share
        if since is None or c.starts_at >= since:
            o = out[c.mentor_id]
            o["calls"] += 1
            o["calls_inr"] += share
            o["focs_inr"] += c.price_inr - share
    held = db.scalars(select(GroupSession).where(GroupSession.mentor_id.in_(mentor_ids), GroupSession.status == "done")).all()
    seats: dict[int, list[GroupSeat]] = {}
    for s in db.scalars(select(GroupSeat).where(GroupSeat.session_id.in_([g.id for g in held]))) if held else []:
        if seat_booked(s):
            seats.setdefault(s.session_id, []).append(s)
    for g in held:
        came = seats.get(g.id, [])
        if not came:
            continue  # nobody came: nothing to pay
        paid = [s for s in came if s.paid_via in ("paid", "pro") and (s.price_inr or 0) > 0]
        share = sum(s.mentor_share_inr if s.mentor_share_inr is not None else mentor_share(s.price_inr or 0) for s in paid)
        pay = (g.pay_inr or 0) + share
        total[g.mentor_id] += pay
        if since is None or g.starts_at >= since:
            o = out[g.mentor_id]
            o["sessions"] += 1
            o["sessions_inr"] += pay
            o["focs_inr"] += sum(s.price_inr or 0 for s in paid) - share
    paid = {i: 0 for i in mentor_ids}
    for p in db.scalars(select(MentorPayout).where(MentorPayout.mentor_id.in_(mentor_ids))):
        paid[p.mentor_id] += p.amount_inr
    for i, o in out.items():
        o["earned_inr"] = o["calls_inr"] + o["sessions_inr"]
        o["paid_out_inr"] = paid[i]
        o["owed_inr"] = total[i] - paid[i]
    return out
