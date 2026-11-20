from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._util import utcnow


class SharedNote(Base):
    """AI notes for one board, reused for every student who captures the same board: many students watch
    the same popular lectures, so each board only needs writing up once. Holds no student data."""

    __tablename__ = "shared_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam: Mapped[str] = mapped_column(String(20), index=True)  # notes are written for an exam's syllabus
    text_hash: Mapped[str] = mapped_column(String(40), index=True)  # exact match on the normalised board text
    # four 16-bit bands of a 64-bit simhash: near-identical boards (OCR noise) share at least one band
    band0: Mapped[int] = mapped_column(Integer, index=True)
    band1: Mapped[int] = mapped_column(Integer, index=True)
    band2: Mapped[int] = mapped_column(Integer, index=True)
    band3: Mapped[int] = mapped_column(Integer, index=True)
    text: Mapped[str] = mapped_column(Text)  # normalised board text, to confirm a near match
    is_lecture: Mapped[bool] = mapped_column(Boolean, default=True)
    topic: Mapped[str | None] = mapped_column(String, nullable=True)
    subject: Mapped[str | None] = mapped_column(String, nullable=True)
    notes_md: Mapped[str] = mapped_column(Text, default="")
    board: Mapped[str | None] = mapped_column(Text, nullable=True)  # the board as the vision model read it: OCR text misreads signs
    translations: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"hi": md, "hinglish": md}, made on first need
    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
