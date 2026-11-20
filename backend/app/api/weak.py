"""Weak spots: bring the result of a test taken anywhere, see what it showed, and work it off (see services/weak)."""
from datetime import date, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models._util import utcnow
from app.models.user import User
from app.models.weak import OutsideTest, WeakTopic
from app.services import syllabus, topic_notes, usage, weak
from app.services.llm import LLMUnavailable
from app.services.syllabus import Syllabus

router = APIRouter(prefix="/weak", tags=["weak"])

READABLE = ("image/jpeg", "image/png", "image/webp", "application/pdf")


def _syllabus(user: User, *, whole: bool = True) -> Syllabus:
    """The syllabus weak spots are kept against. A college student's weak spots can be in any course (last
    semester's stay on the list); a result is read against the subjects they are studying now (``whole=False``)."""
    syl = syllabus.of(user, whole=whole)
    if syl is None:
        raise HTTPException(status_code=404, detail="Weak spots follow the JEE, NEET, GATE, B.Tech, placements and school (Class 1-12) syllabi. "
                                                    "Set one as what you're preparing for in Settings.")
    return syl


def _overview(db: Session, user: User, syl: Syllabus) -> dict[str, Any]:
    return weak.overview(db, user.id, syl, topic_notes.ready(db, syl.library))


@router.get("")
def overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """The fix-it plan: weak spots still open (most questions lost first), the ones cleared lately, the tests."""
    return _overview(db, user, _syllabus(user))


@router.post("/read", dependencies=[Depends(limit("weak_read", 6))])
def read_result(files: list[UploadFile] = File(...), db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Read an uploaded result (screenshots, photos or a PDF of the score report or marked paper) into a draft:
    the marks, and the weak topics placed in the syllabus. Nothing is saved until the student has checked it."""
    syl = _syllabus(user, whole=False)
    if not 1 <= len(files) <= weak.MAX_FILES:
        raise HTTPException(status_code=422, detail=f"Attach 1 to {weak.MAX_FILES} files.")
    payload = []
    for f in files:
        if f.content_type not in READABLE:
            raise HTTPException(status_code=415, detail="Attach photos or screenshots (JPEG, PNG, WebP) or a PDF.")
        data = f.file.read(weak.MAX_FILE_BYTES + 1)
        if len(data) > weak.MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail="Each file can be up to 10 MB.")
        payload.append((data, f.content_type))
    if weak.reader() == "none":
        raise HTTPException(status_code=503, detail="Reading a result needs the AI, which isn't set up on this server. "
                                                    "You can still add the test and mark the weak topics yourself.")
    usage.require(db, user, "test_analysis")
    try:
        read, how = weak.read_result(payload, syllabus.label(user.exam_target))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="One of those files couldn't be opened. Try a clearer photo or a different file.") from exc
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail="Couldn't read that result right now. Try again in a minute, or mark "
                                                    "the weak topics yourself.") from exc
    out = weak.draft(syl, read, syllabus.label(user.exam_target))
    usage.charge(db, user, "test_analysis")
    return {**out, "read_by": how}


class WeakIn(BaseModel):
    chapter_id: str = Field(max_length=120)
    topic_id: str | None = Field(None, max_length=200)
    misses: int = Field(1, ge=1, le=50)
    note: str | None = Field(None, max_length=300)


class TestIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    taken_on: date | None = None
    score: float | None = Field(None, ge=-1000, le=10000)
    max_score: float | None = Field(None, gt=0, le=10000)
    subjects: list[dict[str, Any]] = Field(default_factory=list, max_length=6)
    weak: list[WeakIn] = Field(default_factory=list, max_length=weak.MAX_WEAK)
    source: Literal["upload", "manual"] = "manual"

    @field_validator("title")
    @classmethod
    def _tidy(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Give the test a name.")
        return v


@router.post("/tests", status_code=201)
def add_test(body: TestIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Save a test and the weak topics it showed (as read from the result and corrected by the student, or marked by hand)."""
    syl = _syllabus(user)
    if body.score is not None and body.max_score is not None and body.score > body.max_score:
        raise HTTPException(status_code=422, detail="The marks you got can't be more than the total.")
    if body.taken_on and not utcnow().date() - timedelta(days=366) <= body.taken_on <= utcnow().date() + timedelta(days=1):
        raise HTTPException(status_code=422, detail="The test date should be within the last year.")
    known = [w for w in body.weak if w.chapter_id in syl.by_id]
    if not known and body.score is None:
        raise HTTPException(status_code=422, detail="Add your marks or at least one weak topic.")
    subjects = [{"name": str(s.get("name"))[:40], "score": s.get("score"), "max": s.get("max")} for s in body.subjects if s.get("name")]
    weak.save_test(db, user.id, syl, title=body.title, taken_on=body.taken_on, score=body.score, max_score=body.max_score,
                   subjects=subjects, weak=[w.model_dump() for w in known], source=body.source)
    return _overview(db, user, syl)


@router.delete("/tests/{test_id}")
def remove_test(test_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Remove a test added by mistake, with the weak spots that came only from it and are still open."""
    syl = _syllabus(user)
    test = db.get(OutsideTest, test_id)
    if test is None or test.user_id != user.id:
        raise HTTPException(status_code=404, detail="Test not found.")
    db.execute(delete(WeakTopic).where(WeakTopic.user_id == user.id, WeakTopic.test_id == test.id, WeakTopic.status == "open"))
    for w in db.scalars(select(WeakTopic).where(WeakTopic.user_id == user.id, WeakTopic.test_id == test.id)):
        w.test_id = None  # cleared ones stay as history
    db.delete(test)
    db.commit()
    return _overview(db, user, syl)


class CheckIn(BaseModel):
    topic_id: str = Field(max_length=200)
    correct: int = Field(ge=0, le=200)
    total: int = Field(ge=1, le=200)


@router.post("/check")
def check(body: CheckIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """A practice set on a topic was finished. If the topic is a weak spot this is its re-check: 70% or better on
    four or more questions clears it."""
    if body.correct > body.total:
        raise HTTPException(status_code=422, detail="More right answers than questions.")
    rows = weak.record_check(db, user.id, body.topic_id, body.correct, body.total)
    mine = [w for w in rows if w.topic_id == body.topic_id]
    return {"weak": bool(rows), "cleared": any(w.status == "cleared" for w in mine), "percent": round(100 * body.correct / body.total),
            "needed": round(weak.CLEAR_AT * 100), "enough_questions": body.total >= weak.CLEAR_MIN}


class StatusIn(BaseModel):
    status: Literal["open", "cleared"]


@router.patch("/{weak_id}")
def set_status(weak_id: int, body: StatusIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """The student's own call: "I've got this now", or "not yet after all"."""
    syl = _syllabus(user)
    row = db.get(WeakTopic, weak_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Weak spot not found.")
    row.status, row.cleared_at = body.status, utcnow() if body.status == "cleared" else None
    if body.status == "open":
        row.created_at = utcnow()  # only tests taken from now on can clear it again
    if body.status == "cleared":
        row.checks = [*(row.checks or []), {"at": utcnow().isoformat() + "Z", "kind": "self", "correct": 0, "total": 0}][-10:]
    db.commit()
    return _overview(db, user, syl)
