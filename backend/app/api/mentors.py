"""Mentors: people who cleared an exam guiding those preparing for it, week after week.

A mentor has a mentor account of their own (a student account can't mentor, and a mentor account can't study). They
apply with their qualifications and proof; an admin reviews it before they are listed. A student asks a mentor for
mentorship; once the mentor accepts, the two have a conversation that carries on, and the student sends a check-in
every week with their Focs progress (time studied, tests, weak chapters), so the advice is about what is actually
happening. Each mentor sets their own price for a private call (calls.py) and for their master sessions
(group_sessions.py)."""
import re
import secrets
from datetime import timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.notifications import notify
from app.core.deps import get_current_user, get_db, require_admin, require_mentor, require_student
from app.core.ratelimit import limit
from app.models._util import utcnow
from app.models.mentor import MentorMessage, MentorProfile, Mentorship
from app.models.user import User
from app.core.config import settings
from app.services import images, payments, progress, storage
from app.services.mentors import (CHECKIN_EVERY_DAYS, EXAMS, LANGUAGES, MAX_CAPACITY, MAX_MENTORS_PER_STUDENT, TOPICS, call_price, earnings,
                                  exam_of, mask_contacts, mentor_share, stats)

router = APIRouter(prefix="/mentors", tags=["mentors"])
admin = APIRouter(prefix="/admin/mentors", tags=["admin"], dependencies=[Depends(require_admin)])

PROOF_TYPES = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
PROOF_MAX = 8 * 1024 * 1024
PHOTO_TYPES = ("image/jpeg", "image/png", "image/webp")
PHOTO_MAX = 8 * 1024 * 1024
PHOTO_SIDE = 480  # pixels, square: sharp on a card at twice its size, about 40 KB
PHOTO_DIR = "mentor-photo/"
PHOTO_NAME = re.compile(r"\d+-[A-Za-z0-9_-]{16,40}\.jpg")
OPEN = ("requested", "active")


class ProfileEdit(BaseModel):
    headline: str | None = Field(default=None, max_length=120)
    about: str | None = Field(default=None, max_length=2000)
    topics: list[str] | None = Field(default=None, max_length=8)
    languages: list[str] | None = Field(default=None, max_length=4)
    capacity: int | None = Field(default=None, ge=1, le=MAX_CAPACITY)
    accepting: bool | None = None
    call_price_inr: int | None = Field(default=None, ge=0, le=settings.MENTOR_CALL_PRICE_MAX_INR)


class RequestIn(BaseModel):
    goal: str = Field(min_length=20, max_length=1000)
    share_progress: bool = True


class MessageIn(BaseModel):
    body: str = Field(default="", max_length=2000)
    checkin: bool = False


class ShareIn(BaseModel):
    share_progress: bool


class ReportIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ReviewIn(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=300)


def _iso(dt) -> str | None:
    return dt.isoformat() + "Z" if dt else None


def _photo_url(path: str | None) -> str | None:
    return f"/api/mentors/photos/{path.removeprefix(PHOTO_DIR)}" if path else None


def _active_count(db: Session, mentor_id: int) -> int:
    return db.scalar(select(func.count(Mentorship.id)).where(Mentorship.mentor_id == mentor_id, Mentorship.status == "active")) or 0


def _profile_out(db: Session, p: MentorProfile, name: str, private: bool = False) -> dict[str, Any]:
    taken = _active_count(db, p.id)
    out = {"id": p.id, "name": name, "exam": p.exam, "exam_label": EXAMS[p.exam]["label"], "credential": p.credential,
           "institution": p.institution, "headline": p.headline, "about": p.about, "topics": [t for t in p.topics or [] if t in TOPICS],
           "languages": p.languages or [], "capacity": p.capacity, "active": taken, "open_spots": max(0, p.capacity - taken),
           "accepting": p.accepting, "verified": p.status == "approved", "has_hours": bool(p.slots),
           "qualification": p.qualification or "", "experience": p.experience or "", "call_price_inr": call_price(p),
           "photo": _photo_url(p.photo_path), **stats(db, [p.id])[p.id]}
    if private:
        out.update(status=p.status, review_note=p.review_note, created_at=_iso(p.created_at), slots=p.slots or [],
                   phone=p.phone or "", submitted_at=_iso(p.submitted_at or p.created_at), reviewed_at=_iso(p.reviewed_at),
                   has_proof=bool(p.proof_path), price_set=p.call_price_inr is not None, photo_pending=_photo_url(p.photo_pending))
    return out


def _workspace_constants() -> dict[str, Any]:
    """What a mentor's forms need: the exams, topics and languages, and the price limits."""
    return {"exams": {k: v["label"] for k, v in EXAMS.items()}, "topics": TOPICS, "languages": LANGUAGES, "max_capacity": MAX_CAPACITY,
            "default_call_price_inr": settings.MENTOR_CALL_PRICE_INR, "max_call_price_inr": settings.MENTOR_CALL_PRICE_MAX_INR,
            "max_session_price_inr": settings.SESSION_PRICE_MAX_INR, "commission_pct": settings.MENTOR_COMMISSION_PCT,
            "call_minutes": settings.MENTOR_CALL_MINUTES, "pro_sessions_per_week": settings.PRO_GROUP_SESSIONS_PER_WEEK}


def _names(db: Session, ids: set[int]) -> dict[int, str]:
    return dict(db.execute(select(User.id, User.full_name).where(User.id.in_(ids))).all()) if ids else {}


def _short(name: str | None) -> str:
    """A student's first name and initial: a mentor doesn't need more."""
    parts = (name or "A student").split()
    return parts[0] + (f" {parts[-1][0]}." if len(parts) > 1 else "")


def _checkin_due(m: Mentorship) -> bool:
    if m.status != "active":
        return False
    # the first one is due at once: it shows the mentor where the student starts from
    return m.last_checkin_at is None or utcnow() - m.last_checkin_at >= timedelta(days=CHECKIN_EVERY_DAYS)


def _role(m: Mentorship, profile: MentorProfile, user: User) -> str:
    if profile.user_id == user.id:
        return "mentor"
    if m.student_id == user.id:
        return "student"
    raise HTTPException(status_code=404, detail="Mentorship not found")


def _mentorship(db: Session, user: User, mentorship_id: int) -> tuple[Mentorship, MentorProfile, str]:
    m = db.get(Mentorship, mentorship_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Mentorship not found")
    profile = db.get(MentorProfile, m.mentor_id)
    return m, profile, _role(m, profile, user)


def _unread(db: Session, m: Mentorship, role: str, me: int) -> int:
    seen = m.mentor_seen_at if role == "mentor" else m.student_seen_at
    stmt = select(func.count(MentorMessage.id)).where(MentorMessage.mentorship_id == m.id, MentorMessage.sender_id != me)
    if seen:
        stmt = stmt.where(MentorMessage.created_at > seen)
    return db.scalar(stmt) or 0


def _row(db: Session, m: Mentorship, profile: MentorProfile, role: str, user: User, names: dict[int, str]) -> dict[str, Any]:
    last = db.scalar(select(MentorMessage).where(MentorMessage.mentorship_id == m.id).order_by(MentorMessage.id.desc()).limit(1))
    other = names.get(profile.user_id, "Mentor") if role == "student" else _short(names.get(m.student_id))
    return {"id": m.id, "role": role, "status": m.status, "with": other, "mentor_id": profile.id, "exam_label": EXAMS[profile.exam]["label"],
            "credential": profile.credential, "institution": profile.institution, "goal": m.goal, "share_progress": m.share_progress,
            "created_at": _iso(m.created_at), "accepted_at": _iso(m.accepted_at), "last_message_at": _iso(m.last_message_at),
            "last_checkin_at": _iso(m.last_checkin_at), "checkin_due": _checkin_due(m) and role == "student",
            "unread": _unread(db, m, role, user.id), "photo": _photo_url(profile.photo_path) if role == "student" else None,
            "preview": (("Check-in · " if last.kind == "checkin" else "") + (last.body or ""))[:140] if last else None}


# ---------------------------------------------------------------- finding a mentor
@router.get("")
def browse(exam: str | None = Query(None, max_length=10), db: Session = Depends(get_db), user: User = Depends(require_student)) -> dict[str, Any]:
    """Verified mentors for the student's exam (or another one), with what they help with, their price and whether they
    have room."""
    mine = exam_of(user.exam_target)
    exam = exam if exam in EXAMS else mine
    profiles = db.scalars(select(MentorProfile).where(MentorProfile.exam == exam, MentorProfile.status == "approved",
                                                      MentorProfile.user_id != user.id)).all() if exam else []
    names = _names(db, {p.user_id for p in profiles})
    taken = {mid: status for mid, status in db.execute(select(Mentorship.mentor_id, Mentorship.status).where(
        Mentorship.student_id == user.id, Mentorship.status.in_(OPEN)))}
    mentors = [{**_profile_out(db, p, names.get(p.user_id, "Mentor")), "with_me": taken.get(p.id)} for p in profiles]
    mentors.sort(key=lambda m: (m["with_me"] is None, not (m["accepting"] and m["open_spots"]), -(m["rating"] or 0), -m["calls_done"]))
    return {"exam": exam, "my_exam": mine, "exams": {k: v["label"] for k, v in EXAMS.items()},
            "who": EXAMS[exam]["who"] if exam else None, "topics": TOPICS, "languages": LANGUAGES, "mentors": mentors,
            "call_minutes": settings.MENTOR_CALL_MINUTES, "group_per_week": settings.PRO_GROUP_SESSIONS_PER_WEEK,
            "pro": payments.is_pro(user)}


# ---------------------------------------------------------------- the mentor's own account
@router.get("/me")
def workspace(db: Session = Depends(get_db), user: User = Depends(require_mentor)) -> dict[str, Any]:
    """The mentor dashboard's starting point: their application or profile (None before they apply) and the limits."""
    profile = db.scalar(select(MentorProfile).where(MentorProfile.user_id == user.id))
    return {"profile": _profile_out(db, profile, user.full_name, private=True) if profile else None, **_workspace_constants()}


@router.post("/apply", status_code=201, dependencies=[Depends(limit("mentor-apply", 5))])
def apply(exam: str = Form(...), credential: str = Form(..., min_length=6, max_length=160), institution: str = Form(..., min_length=2, max_length=80),
          qualification: str = Form(..., min_length=2, max_length=160), experience: str = Form("", max_length=2000),
          phone: str = Form(..., min_length=10, max_length=20), call_price_inr: int = Form(..., ge=0, le=settings.MENTOR_CALL_PRICE_MAX_INR),
          headline: str = Form("", max_length=120), about: str = Form("", max_length=2000), topics: str = Form(""), languages: str = Form("en"),
          capacity: int = Form(5, ge=1, le=MAX_CAPACITY), proof: UploadFile | None = File(None),
          db: Session = Depends(get_db), user: User = Depends(require_mentor)) -> dict[str, Any]:
    """A mentor account's application: what they cleared, their education, where they are now, their price, and proof
    (a rank card, a scorecard, a degree or college ID). Only Focs staff see the proof and the phone number, and the proof
    is deleted once reviewed. While it waits it can be sent again with changes; after a rejection, with new proof."""
    if exam not in EXAMS:
        raise HTTPException(status_code=422, detail="Choose the exam you'll mentor for.")
    if sum(c.isdigit() for c in phone) < 10:
        raise HTTPException(status_code=422, detail="Give a phone number Focs can reach you on (it is never shown to students).")
    profile = db.scalar(select(MentorProfile).where(MentorProfile.user_id == user.id))
    if profile is not None and profile.status == "approved":
        raise HTTPException(status_code=409, detail="You're already approved. Edit your profile instead.")
    data = None
    if proof is not None and proof.filename:
        if proof.content_type not in PROOF_TYPES:
            raise HTTPException(status_code=415, detail="Upload the proof as a PDF or a photo (JPEG, PNG, WebP).")
        data = proof.file.read(PROOF_MAX + 1)
        if len(data) > PROOF_MAX:
            raise HTTPException(status_code=413, detail="The proof can be up to 8 MB.")
    elif profile is None or not profile.proof_path:
        raise HTTPException(status_code=422, detail="Add proof of what you cleared: a rank card, scorecard, degree or college ID.")
    if profile is None:
        profile = MentorProfile(user_id=user.id)
        db.add(profile)
    profile.exam, profile.credential, profile.institution = exam, " ".join(credential.split()), " ".join(institution.split())
    profile.qualification, profile.experience = " ".join(qualification.split()), experience.strip() or None
    profile.phone, profile.call_price_inr = " ".join(phone.split()), call_price_inr
    profile.headline, profile.about = headline.strip(), about.strip()
    profile.topics = [t for t in dict.fromkeys(topics.split(",")) if t in TOPICS]
    profile.languages = [x for x in dict.fromkeys(languages.split(",")) if x in LANGUAGES] or ["en"]
    profile.capacity, profile.accepting, profile.status, profile.review_note = capacity, True, "pending", None
    profile.submitted_at = utcnow()
    db.flush()
    if data is not None:
        storage.delete(profile.proof_path)
        profile.proof_path = f"mentor-proof/{profile.id}-{int(utcnow().timestamp())}.{PROOF_TYPES[proof.content_type]}"
        storage._put(profile.proof_path, data)
    db.commit()
    return _profile_out(db, profile, user.full_name, private=True)


@router.patch("/me")
def edit_profile(body: ProfileEdit, db: Session = Depends(get_db), user: User = Depends(require_mentor)) -> dict[str, Any]:
    """What a mentor can change any time: how they describe themselves, what they help with, how many students and
    their call price. (What they cleared and their education were reviewed, so those change only by applying again.)"""
    profile = db.scalar(select(MentorProfile).where(MentorProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(status_code=404, detail="You haven't applied to mentor.")
    changes = body.model_dump(exclude_unset=True)
    if "topics" in changes:
        changes["topics"] = [t for t in dict.fromkeys(changes["topics"] or []) if t in TOPICS]
    if "languages" in changes:
        changes["languages"] = [x for x in dict.fromkeys(changes["languages"] or []) if x in LANGUAGES] or ["en"]
    for key, value in changes.items():
        setattr(profile, key, value.strip() if isinstance(value, str) else value)
    db.commit()
    return _profile_out(db, profile, user.full_name, private=True)


def _own_profile(db: Session, user: User) -> MentorProfile:
    profile = db.scalar(select(MentorProfile).where(MentorProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Apply to mentor first: your photo goes on the card students see.")
    return profile


@router.post("/me/photo", dependencies=[Depends(limit("mentor-photo", 10))])
def upload_photo(photo: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require_mentor)) -> dict[str, Any]:
    """A photo for the mentor's card, cropped square. Students see it once Focs has checked it (many of them are
    under 18): with the application, or on its own for a mentor already listed, whose old photo stays up meanwhile."""
    profile = _own_profile(db, user)
    if photo.content_type not in PHOTO_TYPES:
        raise HTTPException(status_code=415, detail="Choose a photo (JPEG, PNG or WebP).")
    data = photo.file.read(PHOTO_MAX + 1)
    if len(data) > PHOTO_MAX:
        raise HTTPException(status_code=413, detail="The photo can be up to 8 MB.")
    try:
        picture = images.square_jpeg(data, PHOTO_SIDE)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="That photo couldn't be opened. Try another one.") from exc
    storage.delete(profile.photo_pending)  # a photo sent before this one and not checked yet
    profile.photo_pending = f"{PHOTO_DIR}{profile.id}-{secrets.token_urlsafe(16)}.jpg"  # a new name each time
    storage._put(profile.photo_pending, picture)
    db.commit()
    return _profile_out(db, profile, user.full_name, private=True)


@router.delete("/me/photo")
def remove_photo(db: Session = Depends(get_db), user: User = Depends(require_mentor)) -> dict[str, Any]:
    """Take the photo down (and any waiting to be checked). No check needed: the card shows initials again."""
    profile = _own_profile(db, user)
    for path in (profile.photo_path, profile.photo_pending):
        storage.delete(path)
    profile.photo_path = profile.photo_pending = None
    db.commit()
    return _profile_out(db, profile, user.full_name, private=True)


@router.get("/photos/{name}")
def photo_file(name: str, db: Session = Depends(get_db)) -> Response:
    """A mentor's photo. No sign-in, so a plain <img> can show it: its name has a random part that only the people who
    may see it are given, and a new photo gets a new name. Only a current photo is served."""
    path = PHOTO_DIR + name
    current = PHOTO_NAME.fullmatch(name) and db.scalar(select(MentorProfile.id).where(
        (MentorProfile.photo_path == path) | (MentorProfile.photo_pending == path)))
    data = storage.read(path) if current else None
    if data is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.get("/me/earnings")
def my_earnings(db: Session = Depends(get_db), user: User = Depends(require_mentor)) -> dict[str, Any]:
    """This month's and all-time earnings, what Focs has paid out and still owes (paid by Focs, outside the app)."""
    from app.models.mentor import MentorPayout

    profile = db.scalar(select(MentorProfile).where(MentorProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(status_code=404, detail="You haven't applied to mentor.")
    now = utcnow()
    month = earnings(db, [profile.id], since=now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))[profile.id]
    total = earnings(db, [profile.id])[profile.id]
    price = call_price(profile)
    payouts = db.scalars(select(MentorPayout).where(MentorPayout.mentor_id == profile.id).order_by(MentorPayout.created_at.desc()).limit(20)).all()
    return {"month": month, "total": total, "call_price_inr": price, "commission_pct": settings.MENTOR_COMMISSION_PCT,
            "call_share_inr": mentor_share(price), "session_pay_inr": settings.GROUP_SESSION_PAY_INR,
            "payouts": [{"amount_inr": p.amount_inr, "note": p.note, "created_at": _iso(p.created_at)} for p in payouts]}


@router.post("/{profile_id}/request", status_code=201, dependencies=[Depends(limit("mentor-request", 10))])
def ask_for_mentorship(profile_id: int, body: RequestIn, db: Session = Depends(get_db), user: User = Depends(require_student)) -> dict[str, Any]:
    profile = db.get(MentorProfile, profile_id)
    if profile is None or profile.status != "approved" or profile.user_id == user.id:
        raise HTTPException(status_code=404, detail="Mentor not found")
    mine = db.scalars(select(Mentorship).where(Mentorship.student_id == user.id, Mentorship.status.in_(OPEN))).all()
    if any(m.mentor_id == profile.id for m in mine):
        raise HTTPException(status_code=409, detail="You've already asked this mentor.")
    if len(mine) >= MAX_MENTORS_PER_STUDENT:
        raise HTTPException(status_code=409, detail=f"You can have up to {MAX_MENTORS_PER_STUDENT} mentors at a time. End one to ask another.")
    if not profile.accepting or _active_count(db, profile.id) >= profile.capacity:
        raise HTTPException(status_code=409, detail="This mentor has no free spots right now.")
    m = Mentorship(mentor_id=profile.id, student_id=user.id, goal=mask_contacts(body.goal.strip()), share_progress=body.share_progress,
                   status="requested", reports=[], student_seen_at=utcnow())
    db.add(m)
    db.flush()
    notify(db, [profile.user_id], "mentor_request", f"{_short(user.full_name)} asked you to mentor them: “{m.goal[:120]}”", f"/mentor/seekers/{m.id}")
    db.commit()
    return _row(db, m, profile, "student", user, _names(db, {profile.user_id}))


# ---------------------------------------------------------------- the conversation
@router.get("/mentorships")
def mentorships(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Every mentorship: the ones where you are the student, and (for a mentor) the ones where you guide."""
    me = db.scalar(select(MentorProfile).where(MentorProfile.user_id == user.id))
    rows = db.scalars(select(Mentorship).where((Mentorship.student_id == user.id) | (Mentorship.mentor_id == (me.id if me else -1)))
                      .order_by(Mentorship.created_at.desc())).all()
    profiles = {p.id: p for p in db.scalars(select(MentorProfile).where(MentorProfile.id.in_({m.mentor_id for m in rows})))} if rows else {}
    names = _names(db, {p.user_id for p in profiles.values()} | {m.student_id for m in rows})
    out = [_row(db, m, profiles[m.mentor_id], "mentor" if me and m.mentor_id == me.id else "student", user, names) for m in rows]
    return {"as_student": [r for r in out if r["role"] == "student"], "as_mentor": [r for r in out if r["role"] == "mentor"],
            "checkins_due": sum(r["checkin_due"] for r in out), "requests": sum(r["role"] == "mentor" and r["status"] == "requested" for r in out),
            "unread": sum(r["unread"] for r in out)}


def _message_out(msg: MentorMessage, user: User) -> dict[str, Any]:
    return {"id": msg.id, "kind": msg.kind, "body": msg.body, "snapshot": msg.snapshot, "mine": msg.sender_id == user.id,
            "created_at": _iso(msg.created_at)}


@router.get("/mentorships/{mentorship_id}")
def conversation(mentorship_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    m, profile, role = _mentorship(db, user, mentorship_id)
    names = _names(db, {profile.user_id, m.student_id})
    out = _row(db, m, profile, role, user, names)
    msgs = db.scalars(select(MentorMessage).where(MentorMessage.mentorship_id == m.id).order_by(MentorMessage.id.desc()).limit(200)).all()
    out["messages"] = [_message_out(x, user) for x in reversed(msgs)]
    out["mentor"] = _profile_out(db, profile, names.get(profile.user_id, "Mentor"))
    # the mentor sees how the student is doing now, if the student shares it
    student = db.get(User, m.student_id)
    out["progress"] = progress.summaries(db, [student])[student.id] if role == "mentor" and m.share_progress and m.status == "active" else None
    setattr(m, "mentor_seen_at" if role == "mentor" else "student_seen_at", utcnow())
    db.commit()
    return out


@router.post("/mentorships/{mentorship_id}/messages", status_code=201, dependencies=[Depends(limit("mentor-message", 60))])
def send(mentorship_id: int, body: MessageIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """A message, or (from the student) the week's check-in: a few lines plus their progress as Focs sees it."""
    m, _, role = _mentorship(db, user, mentorship_id)
    if m.status != "active":
        raise HTTPException(status_code=409, detail="This mentorship isn't active.")
    text = mask_contacts(body.body.strip())
    if body.checkin and role != "student":
        raise HTTPException(status_code=422, detail="Check-ins come from the student.")
    if not text and not body.checkin:
        raise HTTPException(status_code=422, detail="Write a message first.")
    snapshot = None
    if body.checkin:
        snapshot = progress.summaries(db, [user])[user.id] if m.share_progress else {"shared": False}
        m.last_checkin_at = utcnow()
    msg = MentorMessage(mentorship_id=m.id, sender_id=user.id, kind="checkin" if body.checkin else "text", body=text, snapshot=snapshot)
    db.add(msg)
    m.last_message_at = utcnow()
    setattr(m, "mentor_seen_at" if role == "mentor" else "student_seen_at", m.last_message_at)
    db.commit()
    return _message_out(msg, user)


def _decide(db: Session, user: User, mentorship_id: int, to: str) -> dict[str, Any]:
    m, profile, role = _mentorship(db, user, mentorship_id)
    if to in ("active", "declined"):
        if role != "mentor" or m.status != "requested":
            raise HTTPException(status_code=409, detail="Only a waiting request can be accepted or declined, by the mentor.")
        if to == "active" and _active_count(db, profile.id) >= profile.capacity:
            raise HTTPException(status_code=409, detail="You're at your limit of students. Raise it in your profile, or end a mentorship.")
        m.accepted_at = utcnow() if to == "active" else None
    elif m.status not in OPEN:
        raise HTTPException(status_code=409, detail="This mentorship has already ended.")
    else:
        m.ended_at = utcnow()
    m.status = to
    if to in ("active", "declined"):
        first = (_names(db, {profile.user_id}).get(profile.user_id) or "Your mentor").split()[0]
        notify(db, [m.student_id], f"mentor_{'accepted' if to == 'active' else 'declined'}",
               f"{first} accepted your mentorship request. Say hello and send your first check-in." if to == "active"
               else f"{first} can't take you on right now. Try another mentor.", f"/app/mentors/{m.id}" if to == "active" else "/app/mentors")
    db.commit()
    return _row(db, m, profile, role, user, _names(db, {profile.user_id, m.student_id}))


@router.post("/mentorships/{mentorship_id}/accept")
def accept(mentorship_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _decide(db, user, mentorship_id, "active")


@router.post("/mentorships/{mentorship_id}/decline")
def decline(mentorship_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _decide(db, user, mentorship_id, "declined")


@router.post("/mentorships/{mentorship_id}/end")
def end(mentorship_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Either side can end it (a student withdrawing a request ends it too)."""
    return _decide(db, user, mentorship_id, "ended")


@router.patch("/mentorships/{mentorship_id}")
def set_sharing(mentorship_id: int, body: ShareIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m, profile, role = _mentorship(db, user, mentorship_id)
    if role != "student":
        raise HTTPException(status_code=403, detail="Only the student decides what their mentor sees.")
    m.share_progress = body.share_progress
    db.commit()
    return _row(db, m, profile, role, user, _names(db, {profile.user_id}))


@router.post("/mentorships/{mentorship_id}/report", status_code=204, dependencies=[Depends(limit("mentor-report", 10))])
def report(mentorship_id: int, body: ReportIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    """Something wrong in a conversation. Focs reads it; the mentor is paused from new students meanwhile."""
    m, profile, role = _mentorship(db, user, mentorship_id)
    m.reports = [*(m.reports or []), {"by": role, "reason": body.reason.strip(), "at": _iso(utcnow())}]
    if role == "student":
        profile.accepting = False
    db.commit()


# ---------------------------------------------------------------- admin: reviewing mentors and reports
@admin.get("")
def applications(status: Literal["pending", "approved", "rejected", "photo"] = "pending", db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Applications by status; "photo": listed mentors with a new photo to check."""
    where = ((MentorProfile.status == "approved") & MentorProfile.photo_pending.is_not(None) if status == "photo"
             else MentorProfile.status == status)
    profiles = db.scalars(select(MentorProfile).where(where).order_by(MentorProfile.created_at)).all()
    people = {u.id: u for u in db.scalars(select(User).where(User.id.in_({p.user_id for p in profiles})))} if profiles else {}
    return [{**_profile_out(db, p, people[p.user_id].full_name, private=True), "email": people[p.user_id].email,
             "has_proof": bool(p.proof_path)} for p in profiles]


@admin.get("/{profile_id}/proof")
def proof(profile_id: int, db: Session = Depends(get_db)) -> Response:
    p = db.get(MentorProfile, profile_id)
    data = storage.read(p.proof_path) if p and p.proof_path else None
    if data is None:
        raise HTTPException(status_code=404, detail="No proof on file (it is deleted after review).")
    kind = next(k for k, ext in PROOF_TYPES.items() if p.proof_path.endswith("." + ext))
    return Response(data, media_type=kind, headers={"Cache-Control": "no-store"})


@admin.post("/{profile_id}/review")
def review(profile_id: int, body: ReviewIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    p = db.get(MentorProfile, profile_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Mentor not found")
    p.status, p.review_note, p.reviewed_at = ("approved" if body.approve else "rejected"), body.note.strip() or None, utcnow()
    storage.delete(p.proof_path)  # an ID or a rank card is kept no longer than the review needs
    p.proof_path = None
    if body.approve and p.photo_pending:  # the photo sent with the application was checked with it
        storage.delete(p.photo_path)
        p.photo_path, p.photo_pending = p.photo_pending, None
    notify(db, [p.user_id], "mentor_review",
           "Your mentor application was approved. Students can find you now: set your call hours and post a master session."
           if body.approve else f"Your mentor application wasn't approved{': ' + p.review_note if p.review_note else '.'} You can apply again.",
           "/mentor")
    db.commit()
    return {"id": p.id, "status": p.status}


@admin.post("/{profile_id}/photo")
def review_photo(profile_id: int, body: ReviewIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    """A new photo checked on its own: up on the card, or deleted with a reason the mentor is told."""
    p = db.get(MentorProfile, profile_id)
    if p is None or not p.photo_pending:
        raise HTTPException(status_code=404, detail="No new photo to check.")
    note = body.note.strip()
    if body.approve:
        storage.delete(p.photo_path)
        p.photo_path, p.photo_pending = p.photo_pending, None
        if p.status == "approved":
            notify(db, [p.user_id], "mentor_photo", "Your new photo was approved: students see it on your card now.", "/mentor/profile")
    else:
        storage.delete(p.photo_pending)
        p.photo_pending = None
        notify(db, [p.user_id], "mentor_photo", f"Your photo wasn't approved{': ' + note if note else '.'} "
               "Add a clear photo of your face, just you, with no contact details on it.", "/mentor/profile")
    db.commit()
    return {"id": p.id, "photo": _photo_url(p.photo_path), "photo_pending": None}


@admin.get("/reports")
def reports(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Reported conversations, newest report first, with the last messages to read."""
    rows = [m for m in db.scalars(select(Mentorship)) if m.reports]
    out = []
    for m in rows:
        profile = db.get(MentorProfile, m.mentor_id)
        names = _names(db, {profile.user_id, m.student_id})
        msgs = db.scalars(select(MentorMessage).where(MentorMessage.mentorship_id == m.id).order_by(MentorMessage.id.desc()).limit(30)).all()
        out.append({"id": m.id, "mentor": names.get(profile.user_id), "mentor_profile": profile.id, "student": names.get(m.student_id),
                    "status": m.status, "reports": m.reports, "goal": m.goal,
                    "messages": [{"from": "mentor" if x.sender_id == profile.user_id else "student", "body": x.body, "kind": x.kind,
                                  "at": _iso(x.created_at)} for x in reversed(msgs)]})
    out.sort(key=lambda r: r["reports"][-1]["at"] or "", reverse=True)
    return out


@admin.get("/calls")
def call_money(db: Session = Depends(get_db)) -> dict[str, Any]:
    """What calls and Pro bring in and what Focs keeps, refunds owed (send them from the Razorpay dashboard, then mark
    them here), and each mentor's earnings: calls, group sessions, paid out and still owed."""
    from app.models.payment import Payment

    paid = db.scalars(select(Payment).where(Payment.status.in_(("paid", "refund_due", "refunded")))).all()
    owed = [p for p in paid if p.status == "refund_due"]
    people = _names(db, {p.user_id for p in owed})
    profiles = db.scalars(select(MentorProfile).where(MentorProfile.status == "approved")).all()
    names = _names(db, {p.user_id for p in profiles})
    money = earnings(db, [p.id for p in profiles])
    by_mentor = [{"id": p.id, "mentor": names.get(p.user_id), **money[p.id]} for p in profiles if money[p.id]["owed_inr"] or money[p.id]["earned_inr"]]
    return {"calls_revenue_inr": sum(p.amount_inr for p in paid if p.purpose == "mentor_call" and p.status == "paid"),
            "sessions_revenue_inr": sum(p.amount_inr for p in paid if p.purpose == "session_seat" and p.status == "paid"),
            "pro_revenue_inr": sum(p.amount_inr for p in paid if p.purpose in payments.PRO_PASSES and p.status == "paid"),
            "mocks_revenue_inr": sum(p.amount_inr for p in paid if p.purpose == "mocks" and p.status == "paid"),
            "focs_share_inr": sum(m["focs_inr"] for m in money.values()), "commission_pct": settings.MENTOR_COMMISSION_PCT,
            "owed_to_mentors_inr": sum(max(0, m["owed_inr"]) for m in money.values()),
            "refunds_due": [{"id": p.id, "student": people.get(p.user_id), "amount_inr": p.amount_inr, "purpose": p.purpose,
                             "provider_payment_id": p.provider_payment_id, "paid_at": _iso(p.paid_at)} for p in owed],
            "by_mentor": sorted(by_mentor, key=lambda r: -r["owed_inr"])}


class PayoutIn(BaseModel):
    amount_inr: int = Field(ge=1, le=10_00_000)
    note: str = Field(default="", max_length=200)


@admin.post("/{profile_id}/payouts", status_code=201)
def record_payout(profile_id: int, body: PayoutIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Money sent to a mentor outside Focs (UPI, bank): recorded so their "owed" goes down."""
    from app.models.mentor import MentorPayout

    if db.get(MentorProfile, profile_id) is None:
        raise HTTPException(status_code=404, detail="Mentor not found")
    db.add(MentorPayout(mentor_id=profile_id, amount_inr=body.amount_inr, note=body.note.strip()))
    db.commit()
    return earnings(db, [profile_id])[profile_id]


@admin.post("/payments/{payment_id}/refunded", status_code=204)
def mark_refunded(payment_id: int, db: Session = Depends(get_db)) -> None:
    from app.models.payment import Payment

    p = db.get(Payment, payment_id)
    if p is None or p.status != "refund_due":
        raise HTTPException(status_code=404, detail="No refund owed on that payment.")
    p.status = "refunded"
    db.commit()
