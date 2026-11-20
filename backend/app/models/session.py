from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._util import utcnow


class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    # added in v1.0
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    title_locked: Mapped[bool | None] = mapped_column(Boolean, default=False)  # typed or renamed by the student: never retitled
    subject: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, default="screen", server_default="screen")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    frames_processed: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    # added in v1.2: notes taken for a study room (shared live with everyone in it)
    room_code: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    # one summary of everything the teacher said (services/voice), and how many transcript pieces it covers: it is
    # written again only when more speech has come in since
    talk_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    talk_summary_pieces: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user = relationship("User", back_populates="sessions")
    course = relationship("Course", back_populates="sessions")
    notes = relationship("Note", back_populates="session", cascade="all, delete-orphan",
                         order_by="Note.captured_at")
