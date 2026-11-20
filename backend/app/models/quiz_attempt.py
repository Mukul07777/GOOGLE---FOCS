from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._util import utcnow


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("study_sessions.id"), nullable=True)
    topic: Mapped[str | None] = mapped_column(String, default="")
    question: Mapped[str | None] = mapped_column(Text, default="")
    q_type: Mapped[str | None] = mapped_column(String, default="mcq")  # mcq | true_false | subjective | checkpoint
    correct: Mapped[bool | None] = mapped_column(Boolean, default=False)
    score: Mapped[float | None] = mapped_column(Float, default=0)
    exam_target: Mapped[str | None] = mapped_column(String, default="jee")
    subject: Mapped[str | None] = mapped_column(String, default="")
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
    needs_redo: Mapped[bool | None] = mapped_column(Boolean, default=False)
    # how sure the student said they were when locking the answer in: sure | unsure (None: not asked)
    confidence: Mapped[str | None] = mapped_column(String(6), nullable=True)
