from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._util import utcnow


class PrereqMap(Base):
    """What a chapter (or one topic of it) rests on: the chain of earlier chapters, closest first, each with the idea
    it supplies and a question that checks it. The same for every student, so it is worked out once and shared."""

    __tablename__ = "prereq_maps"

    key: Mapped[str] = mapped_column(String(300), primary_key=True)  # "<chapter id>" or "<chapter id>#<topic id>"
    chain: Mapped[list | None] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)


class GapTrace(Base):
    """One student tracing why a topic doesn't make sense: the chain they were checked on, how they did on each
    link, the root gap (the deepest link they missed), the short lesson that fixes it, and whether it held."""

    __tablename__ = "gap_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    chapter_id: Mapped[str] = mapped_column(String(160))
    topic_id: Mapped[str | None] = mapped_column(String(220), nullable=True)
    title: Mapped[str] = mapped_column(String(200))                # what the student is stuck on
    chain: Mapped[list | None] = mapped_column(JSON, default=list)  # the links, each with the student's "result"
    root: Mapped[int | None] = mapped_column(Integer, nullable=True)  # index into chain of the root gap
    lesson: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # questions on the stuck topic itself, from the question bank: three before the trace, three others after the fix,
    # {"before": {"items": [check], "choices": [...] | None, "right": int | None}, "after": {...}}; None: the bank was short
    retest: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="checking")  # checking | found | clear | fixed
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
