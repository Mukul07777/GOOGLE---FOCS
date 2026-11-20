from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._util import utcnow


class Course(Base):
    """A lecture series the student follows, e.g. "PW Lakshya — Physics"."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    exam_type: Mapped[str] = mapped_column(String, nullable=False, default="jee")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
    # added in v1.0
    color: Mapped[str | None] = mapped_column(String, nullable=True)

    owner = relationship("User", back_populates="courses")
    sessions = relationship("StudySession", back_populates="course")
