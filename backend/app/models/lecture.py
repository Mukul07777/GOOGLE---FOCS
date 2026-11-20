from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._util import utcnow


class LectureSegment(Base):
    """About half a minute of what the teacher said, as text. The audio itself is never kept: it is transcribed and
    dropped. Segments become the captions, the transcript, and the "What the teacher said" part of the notes."""

    __tablename__ = "lecture_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("study_sessions.id"), index=True)
    start_s: Mapped[float] = mapped_column(Float, default=0)   # seconds into the lecture
    end_s: Mapped[float] = mapped_column(Float, default=0)
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)  # what the speech recogniser heard: en | hi | …
    note_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # the board on screen while it was said
    folded: Mapped[bool] = mapped_column(Boolean, default=False)  # already written into a note
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
