from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._util import utcnow

PLANS = ("free", "pro", "team")
COLLEGE_TARGETS = ("college_cse", "college_it", "college_ece", "college_ee", "college_me", "college_ce", "college_ai", "college_che", "college_bt")  # B.Tech branches
GATE_TARGETS = ("gate_cs", "gate_da", "gate_ec", "gate_ee", "gate_me", "gate_ce")  # GATE papers
SCHOOL_TARGETS = tuple(f"cbse_{n}" for n in range(1, 13))  # school, Class 1 to 12 (CBSE, NCERT books)
ROLES = ("student", "mentor")  # two kinds of account: a student studies; a mentor (approved by Focs) guides students
EXAM_TARGETS = ("jee", "neet", "ssc_cgl", "upsc", "gate", "ca", "cbse", "coding", "college", *COLLEGE_TARGETS, *GATE_TARGETS, *SCHOOL_TARGETS, "other")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    hashed_pw: Mapped[str] = mapped_column(String, nullable=False)
    plan: Mapped[str | None] = mapped_column(String, default="free")
    exam_target: Mapped[str | None] = mapped_column(String, default="jee")
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
    # added in v1.0
    class_level: Mapped[str | None] = mapped_column(String, nullable=True)
    daily_goal_min: Mapped[int | None] = mapped_column(Integer, default=60, server_default="60")
    # added in v1.1: AI allowance windows (see services/usage.py)
    usage_window_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    usage_window_used: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    usage_week_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    usage_week_used: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    # lecture captions transcribed in the 7 days from caption_week_start (their own allowance: paid by the minute)
    caption_week_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    caption_week_seconds: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    # lecture time captured in the study day from lecture_day_start (its AI notes are capped in hours a day, by plan)
    lecture_day_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lecture_day_seconds: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    # added in v1.2
    show_on_leaderboard: Mapped[bool | None] = mapped_column(Boolean, default=True, server_default="1")
    consent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # when Terms/Privacy were accepted
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)  # active-user counts
    # added in v1.3: college students (exam_target "college_<branch>"), see services/syllabus
    college: Mapped[str | None] = mapped_column(String(20), nullable=True)   # whose semester plan: iitd | iiitd | dtu | nsut | other
    semester: Mapped[int | None] = mapped_column(Integer, nullable=True)     # 1-8
    subjects: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # the language explanations are written in: en | hinglish | hi (None: English)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # a paid Pro month ends here (None: no end, e.g. switched in dev mode or Institute)
    pro_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # raised when the password changes: tokens issued before stop working (signs out other devices)
    token_version: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")       # the courses they picked (None: the plan's for the semester)
    # Ask a senior: a college email confirmed with a one-time code makes a student a verified senior; the semester
    # they were in then (plus one per six months since) caps the seniority they can claim, whatever they set later
    college_email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    college_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_semester: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verify_pending: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"email", "code_hash", "expires", "tries"}
    login_pending: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # a password sign-in's email code: {"code_hash", "expires", "tries", "sent"}
    # student | mentor: chosen at sign-up and never changed. A mentor account has its own dashboard (/mentor) and can't
    # use the student side; a student can't host. Someone who is both keeps two accounts.
    role: Mapped[str | None] = mapped_column(String(10), default="student", server_default="student")

    courses = relationship("Course", back_populates="owner")
    sessions = relationship("StudySession", back_populates="user")
