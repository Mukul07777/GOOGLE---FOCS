from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._util import utcnow


class Doubt(Base):
    """A question asked to the AI companion, kept so students can revisit their doubts."""

    __tablename__ = "doubts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("study_sessions.id"), nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    explained: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"hi": md, "hinglish": md}, written on first ask
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
