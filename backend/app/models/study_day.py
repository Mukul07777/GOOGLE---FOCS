from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StudyDay(Base):
    """Focus minutes for one student on one local calendar day, built from one-minute heartbeats
    sent while they actually study (lecture, mock, practice, flashcards, rooms, revision)."""

    __tablename__ = "study_days"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_study_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    minutes: Mapped[int] = mapped_column(Integer, default=0)
    by_activity: Mapped[dict | None] = mapped_column(JSON, default=dict)
    last_beat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
