"""Check my working, and the tutor that knows the student (see services/working)."""
import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models.user import User
from app.services import gaps, syllabus, usage, vision, working
from app.services.llm import LLMUnavailable

router = APIRouter(prefix="/working", tags=["working"])
BUSY = "The AI is busy right now. Try again in a minute."


def _syl(user: User):
    return syllabus.of(user, whole=True)


def _choice(value: int | None) -> int | None:
    return value if value is not None and 0 <= value < 6 else None


@router.post("/check", dependencies=[Depends(limit("working-check", 10))])
async def check(image: UploadFile = File(...), question: str = Form(..., min_length=1, max_length=2000),
                options: str = Form("[]", max_length=4000), answer: int | None = Form(None), chosen: int | None = Form(None),
                chapter_id: str | None = Form(None, max_length=160), topic: str | None = Form(None, max_length=200),
                subject: str | None = Form(None, max_length=80),
                db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """A page of rough work, read and checked: the first wrong step, the kind of slip, and the root it comes from."""
    if not vision.available():
        raise HTTPException(status_code=503, detail="Checking handwriting needs the image AI, which isn't set up here.")
    try:
        opts = json.loads(options or "[]")
        opts = [str(o) for o in opts] if isinstance(opts, list) else []
    except ValueError:
        opts = []
    data = await image.read(working.MAX_IMAGE_BYTES + 1)
    usage.require(db, user, "working_check")
    try:
        row = working.check(db, user, _syl(user), data, question, opts, _choice(answer), _choice(chosen), chapter_id, topic, subject)
    except working.WorkingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=BUSY) from exc
    usage.charge(db, user, "working_check")
    return working.view(db, row)


@router.get("/fingerprint")
def fingerprint(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """How this student loses marks: careless slips or gaps in ideas. No AI."""
    return working.fingerprint(db, user.id)


@router.get("/{check_id}")
def get_check(check_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    try:
        return working.view(db, working.owned(db, user, check_id))
    except working.WorkingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=4000)


class TutorIn(BaseModel):
    question: str = Field(min_length=1, max_length=1500)
    history: list[Turn] = Field(default_factory=list, max_length=20)
    check_id: int | None = None                                # opened from a checked question
    chapter_id: str | None = Field(default=None, max_length=160)  # or from a chapter


@router.post("/tutor", dependencies=[Depends(limit("tutor", 20))])
def tutor(body: TutorIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """The personal tutor: knows the student's root gaps and slips, and the question or chapter it was opened from."""
    syl = _syl(user)
    try:
        row = working.owned(db, user, body.check_id) if body.check_id else None
    except working.WorkingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    chapter = gaps.chapter(syl, body.chapter_id) if body.chapter_id and row is None else None
    usage.require(db, user, "doubt")
    try:
        out = working.tutor(db, user, syl, body.question, [t.model_dump() for t in body.history], row, chapter)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=BUSY) from exc
    usage.charge(db, user, "doubt")
    return out
