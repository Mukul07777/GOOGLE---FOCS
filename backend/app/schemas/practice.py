from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORM, UTCDateTime


# ---------------------------------------------------------------- quiz
class QuizGenerate(BaseModel):
    session_id: int | None = None
    note_ids: list[int] | None = None
    text: str | None = Field(default=None, max_length=12000)
    topic_id: str | None = Field(default=None, max_length=200)  # a syllabus topic: practice on what was just studied
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    n_mcq: int = Field(default=5, ge=0, le=15)
    n_tf: int = Field(default=3, ge=0, le=10)
    n_subjective: int = Field(default=1, ge=0, le=3)

    @model_validator(mode="after")
    def _one_source(self):
        if not (self.session_id or self.note_ids or self.topic_id or (self.text and self.text.strip())):
            raise ValueError("Provide session_id, note_ids, topic_id or text to build a quiz from")
        return self


class AttemptIn(BaseModel):
    topic: str = ""
    question: str
    q_type: Literal["mcq", "true_false", "subjective", "checkpoint", "pop"]
    correct: bool
    score: float = 0
    subject: str = ""
    session_id: int | None = None
    confidence: Literal["sure", "unsure"] | None = None  # locked in as sure, or as a guess


class EvaluateIn(BaseModel):
    question: str
    student_answer: str = Field(min_length=1, max_length=5000)
    key_points: list[str] = []
    model_answer: str = ""
    topic: str = ""
    subject: str = ""
    session_id: int | None = None


class TeachBackIn(BaseModel):
    """A topic explained back in the student's own words, typed or spoken."""
    topic: str = Field(min_length=1, max_length=200)
    answer: str = Field(min_length=1, max_length=5000)
    session_id: int | None = None                                # the lecture it came up in: its boards are the reference
    topic_id: str | None = Field(default=None, max_length=200)   # a syllabus topic: its library note is the reference
    subject: str = ""


class RedoItem(ORM):
    id: int
    topic: str | None
    question: str | None
    q_type: str | None
    subject: str | None
    attempted_at: UTCDateTime | None


# ---------------------------------------------------------------- flashcards
class CardIn(BaseModel):
    front: str = Field(min_length=1, max_length=500)
    back: str = Field(min_length=1, max_length=1000)
    topic: str | None = None
    subject: str | None = None


class CardGenerate(BaseModel):
    note_id: int | None = None
    session_id: int | None = None
    count: int = Field(default=6, ge=1, le=15)


class CardReview(BaseModel):
    grade: Literal["again", "hard", "good", "easy"]


class CardOut(ORM):
    id: int
    front: str
    back: str
    topic: str | None = None
    subject: str | None = None
    session_id: int | None = None
    note_id: int | None = None
    ease: float
    interval_days: float
    repetitions: int
    lapses: int
    due_at: UTCDateTime
    last_reviewed_at: UTCDateTime | None = None
    created_at: UTCDateTime
    intervals: dict[str, str] = {}


# ---------------------------------------------------------------- companion
class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=6000)


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    session_id: int | None = None
    note_id: int | None = None  # "ask about this board": that board's notes lead the context
    mode: Literal["explain", "socratic", "simple", "steps", "hinglish"] = "explain"
    history: list[ChatTurn] = []


class DoubtOut(ORM):
    id: int
    session_id: int | None
    question: str
    answer: str
    created_at: UTCDateTime
