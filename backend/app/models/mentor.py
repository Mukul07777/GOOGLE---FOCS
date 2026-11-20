from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._util import utcnow


class MentorProfile(Base):
    """Someone who cleared an exam and guides students preparing for it: an IIT student for JEE, a ranker for UPSC.
    Listed only once Focs has checked their proof (the proof file is deleted after that review)."""

    __tablename__ = "mentor_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    exam: Mapped[str] = mapped_column(String(10), index=True)          # what they mentor for: jee | neet | upsc | gate | …
    credential: Mapped[str] = mapped_column(String(160))                # "JEE Advanced 2023, AIR 1,204"
    institution: Mapped[str] = mapped_column(String(80))               # "IIT Delhi, B.Tech CSE (3rd year)"
    qualification: Mapped[str | None] = mapped_column(String(160), nullable=True)  # highest education: "B.Tech CSE, IIT Delhi (2026)"
    experience: Mapped[str | None] = mapped_column(Text, nullable=True)            # teaching or mentoring done before
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)           # for Focs to verify them; never shown to students
    call_price_inr: Mapped[int | None] = mapped_column(Integer, nullable=True)     # their price for a private call (None: Focs's default)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True) # the latest application sent for review
    headline: Mapped[str] = mapped_column(String(120), default="")
    about: Mapped[str] = mapped_column(Text, default="")
    topics: Mapped[list | None] = mapped_column(JSON, default=list)     # keys of services/mentors.TOPICS
    languages: Mapped[list | None] = mapped_column(JSON, default=list)  # en | hi
    capacity: Mapped[int] = mapped_column(Integer, default=5)           # students mentored at once
    accepting: Mapped[bool] = mapped_column(Boolean, default=True)
    slots: Mapped[list | None] = mapped_column(JSON, default=list)        # weekly call times, India time: [{"day": 0-6 (Mon), "time": "19:00"}]
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)  # pending | approved | rejected
    proof_path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # A photo for the card: students see only one Focs has checked (photo_path). A new one waits in photo_pending,
    # checked with the application or on its own, while the old one stays up.
    photo_path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    photo_pending: Mapped[str | None] = mapped_column(String(200), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)


class Mentorship(Base):
    """One student and one mentor, over weeks: a request, then a conversation with a check-in every week."""

    __tablename__ = "mentorships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("mentor_profiles.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="requested", index=True)  # requested | active | declined | ended
    goal: Mapped[str] = mapped_column(Text, default="")                 # what the student asked for help with
    share_progress: Mapped[bool] = mapped_column(Boolean, default=True)  # the mentor sees their Focs progress
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_checkin_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mentor_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    student_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reports: Mapped[list | None] = mapped_column(JSON, default=list)    # [{"by": user id, "reason": str, "at": iso}]


class MentorMessage(Base):
    __tablename__ = "mentor_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mentorship_id: Mapped[int] = mapped_column(ForeignKey("mentorships.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(10), default="text")        # text | checkin (carries the week's progress)
    body: Mapped[str] = mapped_column(Text, default="")
    snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow, index=True)


class MentorCall(Base):
    """A private 1:1 video call in a mentorship, paid for by the student (Focs keeps a share). The booking holds its
    slot while the student pays. Afterwards the mentor leaves notes and action items, and the student rates it."""

    __tablename__ = "mentor_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mentorship_id: Mapped[int] = mapped_column(ForeignKey("mentorships.id"), index=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("mentor_profiles.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)   # UTC
    minutes: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(10), default="held", index=True)  # held | booked | done | cancelled
    held_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # an unpaid hold lapses then
    paid_via: Mapped[str] = mapped_column(String(10), default="paid")   # paid | pro (older calls, when Pro included one)
    price_inr: Mapped[int] = mapped_column(Integer, default=0)
    mentor_share_inr: Mapped[int | None] = mapped_column(Integer, nullable=True)  # the price less Focs's share, fixed at booking
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), nullable=True)
    room: Mapped[str] = mapped_column(String(80))                      # the video room's hard-to-guess name
    agenda: Mapped[str] = mapped_column(Text, default="")
    snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # the student's progress when they booked
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)       # the mentor's, after the call
    actions: Mapped[list | None] = mapped_column(JSON, nullable=True)    # [{"text": str, "done": bool}]
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)


class GroupSession(Base):
    """A mentor's master session, like a class on Google Meet: students register (free, paid at the mentor's price, or
    with the one a week Pro includes), write the doubt they want answered, and join the room together. The mentor earns
    their share of every paid or Pro seat. (Older sessions paid a fixed amount, pay_inr, instead.)"""

    __tablename__ = "group_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("mentor_profiles.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)   # UTC
    minutes: Mapped[int] = mapped_column(Integer, default=60)
    topic: Mapped[str] = mapped_column(String(120), default="")         # the session's title
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # what it covers and who it's for
    price_inr: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")  # per seat, set by the mentor (0: free)
    seats: Mapped[int] = mapped_column(Integer, default=25)
    room: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(10), default="scheduled", index=True)  # scheduled | done | cancelled
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    pay_inr: Mapped[int] = mapped_column(Integer, default=0)            # what the mentor earns for it, fixed when scheduled
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)


class GroupSeat(Base):
    """A student's seat in a master session, with the doubt they want answered (the mentor's queue). A paid seat is
    held while the student pays, then booked."""

    __tablename__ = "group_seats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("group_sessions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    doubt: Mapped[str] = mapped_column(Text, default="")
    answered: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str | None] = mapped_column(String(10), default="booked", server_default="booked")  # held | booked | cancelled
    held_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)                    # an unpaid hold lapses then
    paid_via: Mapped[str | None] = mapped_column(String(10), default="free", server_default="pro")  # free | paid | pro (older seats: pro)
    price_inr: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    mentor_share_inr: Mapped[int | None] = mapped_column(Integer, nullable=True)  # the mentor's earning from this seat, fixed when taken
    payment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)


class MentorPayout(Base):
    """Money Focs sent a mentor (by UPI or bank, outside Focs), so what's still owed is known."""

    __tablename__ = "mentor_payouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("mentor_profiles.id"), index=True)
    amount_inr: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
