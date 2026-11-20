from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._util import utcnow


class OutsideTest(Base):
    """A test the student took somewhere else (coaching, school, a printed paper) and brought the result of."""

    __tablename__ = "outside_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160), default="Test")
    taken_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    subjects: Mapped[list | None] = mapped_column(JSON, default=list)   # [{"name", "score", "max"}], when the result shows them
    source: Mapped[str] = mapped_column(String(10), default="manual")   # upload (read from the result) | manual
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)


class WeakTopic(Base):
    """A topic (or a whole chapter) a test showed the student to be weak in. It stays "open" (and is given extra
    weight in the daily plan, last-day revision and practice) until a later check shows the concept is clear."""

    __tablename__ = "weak_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    test_id: Mapped[int | None] = mapped_column(ForeignKey("outside_tests.id"), nullable=True)  # the latest test that showed it
    chapter_id: Mapped[str] = mapped_column(String(120), index=True)
    topic_id: Mapped[str | None] = mapped_column(String(200), nullable=True)  # None: the chapter as a whole
    misses: Mapped[int] = mapped_column(Integer, default=1)                    # questions lost on it, across tests
    note: Mapped[str | None] = mapped_column(Text, nullable=True)              # what went wrong, as the result put it
    status: Mapped[str] = mapped_column(String(10), default="open")            # open | cleared
    checks: Mapped[list | None] = mapped_column(JSON, default=list)            # re-checks: [{"at", "kind", "correct", "total"}]
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
