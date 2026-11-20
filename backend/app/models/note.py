from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._util import utcnow


class Note(Base):
    """One board snapshot turned into study notes."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("study_sessions.id"), nullable=False)
    ocr_raw: Mapped[str | None] = mapped_column(Text, default="")
    ai_notes: Mapped[str | None] = mapped_column(Text, default="")
    board_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
    # added in v1.0
    topic: Mapped[str | None] = mapped_column(String, nullable=True)
    subject: Mapped[str | None] = mapped_column(String, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    engine: Mapped[str | None] = mapped_column(String, nullable=True)
    image_path: Mapped[str | None] = mapped_column(String, nullable=True)
    is_pinned: Mapped[bool | None] = mapped_column(Boolean, default=False, server_default="0")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # the optional detailed write-up of this board, when no library note covers its topic (see services/topic_notes)
    detailed_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # what the teacher said while this board was up (services/voice); the board notes above stay shared and unchanged
    spoken_md: Mapped[str | None] = mapped_column(Text, nullable=True)  # the notes' language when not English (hi | hinglish)
    # where this board sits in the syllabus, placed the first time last-day revision needed it: "<exam>:<topic id or
    # chapter id>", or "<exam>:" when it belongs to no chapter (api/prep.py, _lecture_chapters)
    chapter_ref: Mapped[str | None] = mapped_column(String, nullable=True)

    session = relationship("StudySession", back_populates="notes")
