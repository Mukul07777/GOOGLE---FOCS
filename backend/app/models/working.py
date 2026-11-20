from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._util import utcnow


class WorkingCheck(Base):
    """One student's rough work on one question, read and checked: the steps Focs read, the first step that went wrong,
    what kind of slip it was, and the earlier idea it comes from. The drawing itself is never kept, only what was read."""

    __tablename__ = "working_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    chapter_id: Mapped[str | None] = mapped_column(String(160), nullable=True)       # the question's chapter, when known
    question: Mapped[str] = mapped_column(String(2000))
    verdict: Mapped[str] = mapped_column(String(12))                                  # right | wrong | incomplete
    error_type: Mapped[str | None] = mapped_column(String(16), nullable=True)         # see services/working.ERRORS
    root_chapter_id: Mapped[str | None] = mapped_column(String(160), nullable=True)   # the earlier chapter the slip comes from
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)                  # the whole reading, for the tutor
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow, index=True)
