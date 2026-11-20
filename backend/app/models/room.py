from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._util import utcnow


class Room(Base):
    """A live group-study room (presence, chat, shared focus timer)."""

    __tablename__ = "study_rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(6), unique=True, index=True, nullable=False)
    host_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str | None] = mapped_column(String, default="Study Room")
    video_url: Mapped[str | None] = mapped_column(String, default="")
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
    max_members: Mapped[int | None] = mapped_column(Integer, default=20)
    # added in v1.1
    topic: Mapped[str | None] = mapped_column(String, nullable=True)
    # added in v1.2: the session that holds the room's shared board notes
    notes_session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class LectureSignal(Base):
    """What a room's lecture left unclear, pinned to the board on screen at that moment: an anonymous "I'm lost"
    tap, a wrong quiz answer, a doubt, or one quiz's results. The host's confusion map is drawn from these; no
    student is ever named in it."""

    __tablename__ = "lecture_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_code: Mapped[str] = mapped_column(String(6), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # for pacing only, never shown
    kind: Mapped[str] = mapped_column(String(12))                     # lost | wrong | doubt | quiz
    t_s: Mapped[float | None] = mapped_column(Float, nullable=True)   # lecture position, when a video was playing
    note_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # the board on screen
    ref: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)  # a doubt's or a quiz's id
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
