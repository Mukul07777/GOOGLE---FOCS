from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORM, UTCDateTime
from app.schemas.note import NoteOut


class SessionStart(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    subject: str | None = Field(default=None, max_length=40)
    course_id: int | None = None
    video_url: str | None = Field(default="", max_length=500)
    source: Literal["screen", "upload", "camera", "link"] = "screen"


class SessionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    subject: str | None = Field(default=None, max_length=40)
    course_id: int | None = None


class SessionOut(ORM):
    id: int
    title: str | None = None
    subject: str | None = None
    source: str | None = "screen"
    video_url: str | None = ""
    course_id: int | None = None
    is_active: bool | None = False
    started_at: UTCDateTime | None = None
    ended_at: UTCDateTime | None = None
    frames_processed: int | None = 0
    note_count: int = 0
    duration_min: float = 0
    summary: str | None = None


class SessionDetail(SessionOut):
    notes: list[NoteOut] = []


class SessionEndOut(BaseModel):
    session: SessionOut
    summary_md: str
    key_formulas: list[str]
    flashcards_created: int
    source: str
    # the lecture's quizzes, sure vs right (services/calibration): where to start
    calibration: dict | None = None
