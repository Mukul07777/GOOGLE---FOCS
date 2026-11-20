from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._util import utcnow


class BankQuestion(Base):
    """Shared question bank for full mock tests. Every AI-written question is solved again by a
    different model before it is marked verified; students can report a wrong one."""

    __tablename__ = "bank_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    exam: Mapped[str] = mapped_column(String, default="jee_main", index=True)
    subject: Mapped[str] = mapped_column(String, index=True)
    chapter: Mapped[str] = mapped_column(String, default="")
    # the syllabus topic (its name) a question was written for, when it was asked for one (a last-day test on some
    # topics of a chapter); None: anywhere in the chapter
    topic: Mapped[str | None] = mapped_column(String, nullable=True)
    qtype: Mapped[str] = mapped_column(String, default="mcq")  # mcq | numerical
    difficulty: Mapped[str | None] = mapped_column(String, default="medium")
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    answer: Mapped[str] = mapped_column(String)  # option index for mcq, the value for numerical
    solution: Mapped[str | None] = mapped_column(Text, default="")
    verified: Mapped[bool | None] = mapped_column(Boolean, default=False)
    reports: Mapped[int | None] = mapped_column(Integer, default=0)
    source: Mapped[str | None] = mapped_column(String, default="ai")  # seed | ai | pyq (a past exam question)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # PYQs: the exam year
    paper: Mapped[str | None] = mapped_column(String, nullable=True)  # PYQs: "JEE Main 2019 (Jan)", "NEET 2021"…
    fingerprint: Mapped[str] = mapped_column(String, index=True)
    # the solution rewritten in another language, once someone asked for it: {"hinglish": md, "hi": md}
    explained: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # pictures a question needs (SSC reasoning figures): {"figures": [url], "options": [url | None] | None}; options
    # given as pictures have "" as their text
    media: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # the question as the paper printed it in Hindi: {"question": text, "options": [text] | None}
    hindi: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)


class MockTest(Base):
    __tablename__ = "mock_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    pattern: Mapped[str] = mapped_column(String, default="jee_main_30")  # a PATTERNS id, or "chapter"
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)     # chapter tests: subject, chapters, count
    title: Mapped[str | None] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="preparing")  # preparing | ready | in_progress | submitted | failed
    progress: Mapped[int | None] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_min: Mapped[int] = mapped_column(Integer, default=180)
    question_ids: Mapped[list | None] = mapped_column(JSON, default=list)
    responses: Mapped[dict | None] = mapped_column(JSON, default=dict)  # qid -> {a, m, v, t}
    current_index: Mapped[int | None] = mapped_column(Integer, default=0)
    tab_switches: Mapped[int | None] = mapped_column(Integer, default=0)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # how ready the student said they felt, chapter by chapter, while the paper was written: "Subject::Chapter" -> sure | shaky
    confidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # each MCQ's options shown in this paper's own order (services/mock.option_order); papers from before stay as stored
    shuffled: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
