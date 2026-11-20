"""Who can speak as a senior in "Ask a senior", and how a student proves it.

- A B.Tech student is a senior for a course their semester plan put before the semester they're in, once they've
  confirmed a college email with a one-time code. The semester they were in when they confirmed, plus one for every
  six months since, caps the seniority they can claim: setting "Semester 8" later doesn't make anyone a senior.
- A verified B.Tech student is also a senior for JEE and NEET Physics, Chemistry and Maths: they did Class 12 and
  the entrance exam. That links aspirants to the students who made it.
- GATE and placement students are seniors only for courses they have really worked through on Focs.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models._util import utcnow
from app.models.prep import TopicProgress
from app.models.user import User
from app.services import syllabus

# the college's own email domains (subdomains count: cs1200123@cse.iitd.ac.in)
DOMAINS = {"iitd": ("iitd.ac.in", "iitd.ernet.in"), "iiitd": ("iiitd.ac.in",), "dtu": ("dtu.ac.in",), "nsut": ("nsut.ac.in", "nsit.net.in")}
ACADEMIC = (".ac.in", ".edu.in", ".edu")  # "another college": any academic address
CODE_MINUTES, CODE_TRIES = 10, 5
SCHOOL_SUBJECTS = ("Physics", "Chemistry", "Mathematics")  # what a B.Tech student can speak to for JEE/NEET
MIN_TOPICS = 3  # GATE / placements: topics finished in a course before they count as a senior for it


def domain_ok(college: str | None, email: str) -> bool:
    domain = email.rsplit("@", 1)[-1].strip().lower()
    own = DOMAINS.get(syllabus.college_of(college))
    if own:
        return any(domain == d or domain.endswith("." + d) for d in own)
    return domain.endswith(ACADEMIC)


def _hash(code: str, user_id: int) -> str:
    return hashlib.sha256(f"{user_id}:{code}".encode()).hexdigest()


def start(user: User, email: str) -> str:
    """A fresh 6-digit code for this email, kept only as a hash; returns the code to send."""
    code = f"{secrets.randbelow(10**6):06d}"
    user.verify_pending = {"email": email.strip().lower(), "code_hash": _hash(code, user.id),
                           "expires": (utcnow() + timedelta(minutes=CODE_MINUTES)).isoformat(), "tries": 0}
    return code


def confirm(user: User, code: str) -> str | None:
    """None when confirmed, else why not."""
    p = user.verify_pending or {}
    if not p:
        return "Ask for a code first."
    if datetime.fromisoformat(p["expires"]) < utcnow():
        return "That code has expired. Ask for a new one."
    if p.get("tries", 0) >= CODE_TRIES:
        return "Too many wrong codes. Ask for a new one."
    if not hmac.compare_digest(p["code_hash"], _hash(code.strip(), user.id)):
        user.verify_pending = {**p, "tries": p.get("tries", 0) + 1}
        return "That code isn't right."
    user.college_email, user.college_verified_at = p["email"], utcnow()
    user.verified_semester = syllabus.semester_of(user.semester)
    user.verify_pending = None
    return None


def verified(user: User) -> bool:
    return bool(user.college_verified_at and user.college_email)


def effective_semester(user: User) -> int | None:
    """The semester a verified student can speak from: what they said, no further than time allows since they proved it."""
    now = syllabus.semester_of(user.semester)
    if not verified(user) or not now:
        return None
    base = user.verified_semester or now
    grown = base + int((utcnow() - user.college_verified_at).days // 182)
    return min(now, grown)


def _studied(db: Session, user: User, subject: str) -> bool:
    chapters = [c.id for c in syllabus._course_chapters(subject, 0)] if subject in syllabus.courses() else []
    if not chapters:
        return False
    done = db.scalar(select(func.count(TopicProgress.id)).where(TopicProgress.user_id == user.id,
                                                                TopicProgress.chapter_id.in_(chapters)))
    return (done or 0) >= MIN_TOPICS


def label(db: Session, user: User, subject: str, shelf: str = "college") -> str | None:
    """Why this student can speak as a senior about `subject` on that shelf (a college's, or "jee"/"neet"), or None."""
    exam = syllabus.exam_of(user.exam_target)
    if shelf in syllabus.ENTRANCE:
        sem = effective_semester(user) if syllabus.is_college(exam) else None
        return f"B.Tech, Sem {sem} · verified" if sem and subject in SCHOOL_SUBJECTS else None
    if syllabus.is_gate(exam):
        return "GATE aspirant · studied it here" if _studied(db, user, subject) else None
    if syllabus.is_placement(exam):
        return "Placement prep · studied it here" if _studied(db, user, subject) else None
    sem = effective_semester(user)
    syl = syllabus.of(user, whole=True) if syllabus.is_college(exam) else None
    took = syl.semester_of(subject) if syl else 0
    return f"Did it in Sem {took} · verified" if sem and 0 < took < sem else None


def courses_done(db: Session, user: User) -> list[str]:
    """The library courses this student can answer as a senior."""
    exam = syllabus.exam_of(user.exam_target)
    if syllabus.is_gate(exam) or syllabus.is_placement(exam):
        mine = syllabus.of(user)
        return [s for s in (mine.subjects if mine else ()) if _studied(db, user, s)]
    sem = effective_semester(user)
    syl = syllabus.of(user, whole=True) if syllabus.is_college(exam) else None
    return [s for n, subjects in (syl.semesters if syl and sem else ()) if n < sem for s in subjects]
