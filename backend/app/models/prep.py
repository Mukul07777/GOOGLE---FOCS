from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._util import utcnow


class StudyGoal(Base):
    """A student's goal and situation (from onboarding): what the mentor plan is built from."""

    __tablename__ = "study_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    exam: Mapped[str] = mapped_column(String(10))           # syllabus: jee | neet | college (the branch is the user's)
    track: Mapped[str] = mapped_column(String(20))          # jee_main | jee_advanced | neet | college
    class_level: Mapped[str] = mapped_column(String(10))    # 11 | 12 | dropper; college: the semester, 1-8
    exam_date: Mapped[date] = mapped_column(Date)
    target: Mapped[str] = mapped_column(String(20))         # a target band, see services/planner.TARGETS
    dream: Mapped[str | None] = mapped_column(String(120), nullable=True)  # "IIT Bombay CSE", "AIIMS Delhi"…
    weekday_hours: Mapped[float] = mapped_column(Float)
    weekend_hours: Mapped[float] = mapped_column(Float)
    coaching: Mapped[str] = mapped_column(String(10), default="self")  # self | online | offline
    # where they stand today, per subject and class: {"Physics": {"11": "done", "12": "none"}, …}
    standing: Mapped[dict | None] = mapped_column(JSON, default=dict)
    # the plan's expected syllabus completion over time, fixed when the goal is set: [[iso date, percent], …]
    baseline: Mapped[list | None] = mapped_column(JSON, default=list)
    # the student's own edits to the plan: {"day_hours": [Mon…Sun], "pinned": [chapter ids, next first],
    # "skipped": [chapter ids left out]} (see services/planner)
    edits: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)


class TopicProgress(Base):
    """A syllabus topic the student has finished studying."""

    __tablename__ = "topic_progress"
    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_topic_progress"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    chapter_id: Mapped[str] = mapped_column(String(120), index=True)
    topic_id: Mapped[str] = mapped_column(String(200))
    done_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)


class ChapterRevision(Base):
    """One revision of a finished chapter (spaced revision: about a week, a month and three months later)."""

    __tablename__ = "chapter_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    chapter_id: Mapped[str] = mapped_column(String(120), index=True)
    revised_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)


class PlanTask(Base):
    """A task the student added to a day's plan themselves."""

    __tablename__ = "plan_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(160))
    minutes: Mapped[int] = mapped_column(Integer, default=30)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)


class PlanCheck(Base):
    """A task from the daily plan the student ticked off ("hide:<task>": a planned task they took off today's list)."""

    __tablename__ = "plan_checks"
    __table_args__ = (UniqueConstraint("user_id", "day", "task", name="uq_plan_check"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    task: Mapped[str] = mapped_column(String(200))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
