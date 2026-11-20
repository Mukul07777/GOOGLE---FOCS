from pydantic import BaseModel, Field

from app.schemas.common import ORM, UTCDateTime


class CourseIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    exam_type: str = "jee"
    description: str | None = Field(default=None, max_length=1000)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class CourseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class CourseOut(ORM):
    id: int
    name: str
    exam_type: str
    description: str | None = None
    color: str | None = None
    created_at: UTCDateTime | None = None
    session_count: int = 0
