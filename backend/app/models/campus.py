from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._util import utcnow


class CampusItem(Base):
    """A past paper or a set of notes a student shared with others taking the same course (by default, at their
    college). The file is the student's upload; nothing in it is checked by Focs."""

    __tablename__ = "campus_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    college: Mapped[str] = mapped_column(String(20), index=True, default="other")   # iitd | iiitd | dtu | nsut | other
    subject: Mapped[str] = mapped_column(String(60), index=True)                    # a course of the library
    kind: Mapped[str] = mapped_column(String(10), default="paper")                  # paper | notes
    title: Mapped[str] = mapped_column(String(160))
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)                # a paper's year
    exam_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)        # mid | end | quiz | other
    file_path: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(40))
    pages: Mapped[int] = mapped_column(Integer, default=1)
    size: Mapped[int] = mapped_column(Integer, default=0)
    voters: Mapped[list | None] = mapped_column(JSON, default=list)     # user ids who found it useful
    reporters: Mapped[list | None] = mapped_column(JSON, default=list)  # user ids who reported it
    questions: Mapped[list | None] = mapped_column(JSON, nullable=True)  # a paper's questions, once read: [{"no", "text", "marks"}]
    opens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)


class CampusPost(Base):
    """Juniors and seniors of a course talking: a question about it, a senior's tip for it, or an answer to a question.
    Whether the author had already done the course is fixed when they post (they move on, the label shouldn't)."""

    __tablename__ = "campus_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    college: Mapped[str] = mapped_column(String(20), index=True, default="other")
    subject: Mapped[str] = mapped_column(String(60), index=True)                    # a course of the library
    chapter: Mapped[str | None] = mapped_column(String(120), nullable=True)
    kind: Mapped[str] = mapped_column(String(10), default="question")               # question | tip | answer
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("campus_posts.id"), nullable=True, index=True)  # an answer's question
    body: Mapped[str] = mapped_column(Text)
    senior: Mapped[str | None] = mapped_column(String(40), nullable=True)            # "Did it in Sem 3", "GATE aspirant"; None: not a senior
    voters: Mapped[list | None] = mapped_column(JSON, default=list)
    reporters: Mapped[list | None] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
    # an answer Focs drafted the moment the question came in, until a senior checks it ("Checked by a senior (Sem 5)")
    ai: Mapped[bool | None] = mapped_column(Boolean, default=False, server_default="0")
    checked_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    checked_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accepted: Mapped[bool | None] = mapped_column(Boolean, default=False, server_default="0")  # "this answered it", by the asker
