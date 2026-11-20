from pydantic import BaseModel, Field

from app.schemas.common import ORM, UTCDateTime


class NoteOut(ORM):
    id: int
    session_id: int
    topic: str | None = None
    subject: str | None = None
    ai_notes: str | None = ""
    language: str | None = None
    spoken_md: str | None = None
    ocr_raw: str | None = ""
    ocr_confidence: float | None = None
    engine: str | None = None
    has_image: bool = False
    is_pinned: bool | None = False
    captured_at: UTCDateTime | None = None
    updated_at: UTCDateTime | None = None


class NoteUpdate(BaseModel):
    ai_notes: str | None = Field(default=None, max_length=20000)
    topic: str | None = Field(default=None, max_length=120)
    is_pinned: bool | None = None


class NotePage(BaseModel):
    items: list[NoteOut]
    total: int
