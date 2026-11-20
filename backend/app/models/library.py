from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._util import utcnow


class TopicNote(Base):
    """The notes library: one pre-made note per syllabus topic (or chapter), written once and shared by every
    student of that exam. Not a student's data: nothing here belongs to one account."""

    __tablename__ = "topic_notes"
    __table_args__ = (UniqueConstraint("exam", "kind", "ref_id", name="uq_topic_note"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam: Mapped[str] = mapped_column(String(10), index=True)      # jee | neet (the same topic is taught at different depth)
    kind: Mapped[str] = mapped_column(String(12))                  # detailed (a topic) | capsule (a chapter, last-day revision)
    ref_id: Mapped[str] = mapped_column(String(200), index=True)   # syllabus topic id or chapter id
    content_md: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(10), default="ai")  # seed (shipped with Focs) | ai (written on first request)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # a second model went through the note (formulas, the worked example's arithmetic) and found nothing left to fix
    checked: Mapped[bool | None] = mapped_column(Boolean, default=False)
    reported_by: Mapped[list | None] = mapped_column(JSON, default=list)  # user ids who reported a mistake
    translations: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"hi": md, "hinglish": md}, made on first need
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
