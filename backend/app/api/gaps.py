"""Root-cause gap tracing: why a topic doesn't make sense, and the earlier gap to fix first (see services/gaps)."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models.user import User
from app.services import gaps, syllabus, usage
from app.services.llm import LLMUnavailable

router = APIRouter(prefix="/gaps", tags=["gaps"])


def _syl(user: User):
    return syllabus.of(user, whole=True)


def _run(fn, *args):
    try:
        return fn(*args)
    except gaps.GapError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail="The AI is busy right now. Try again in a minute.") from exc


@router.get("")
def overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Recent traces, the weak spots worth tracing, and the chapters a student can pick from."""
    return gaps.overview(db, user, _syl(user))


@router.get("/genome")
def genome(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict[str, Any]:
    """The Gap Genome: what the exam chapters really rest on, and where real students' trouble starts (counts only)."""
    return gaps.genome(db)


class StartIn(BaseModel):
    chapter_id: str = Field(min_length=1, max_length=160)
    topic_id: str | None = Field(default=None, max_length=220)


@router.post("", dependencies=[Depends(limit("gap-trace", 6))])
def start(body: StartIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Trace a topic back to what it rests on. Free when another student already traced the same chapter."""
    syl = _syl(user)
    target = gaps.chapter(syl, body.chapter_id)
    key = f"{body.chapter_id}#{body.topic_id}" if body.topic_id else body.chapter_id
    if target is not None and db.get(gaps.PrereqMap, key) is None:
        usage.require(db, user, "gap_trace")
    trace, used_ai = _run(gaps.start, db, user, syl, body.chapter_id, body.topic_id)
    if used_ai:
        usage.charge(db, user, "gap_trace")
    return gaps.view(trace)


@router.get("/{trace_id}")
def get_trace(trace_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    return gaps.view(_run(gaps.owned, db, user, trace_id))


class AnswersIn(BaseModel):
    answers: list[int | None] = Field(max_length=gaps.MAX_LINKS)
    before: list[int | None] | None = Field(default=None, max_length=gaps.RETEST)  # the stuck topic's own questions


@router.post("/{trace_id}/answers")
def answers(trace_id: int, body: AnswersIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Mark the checks; the deepest one missed is the root gap."""
    return gaps.view(_run(gaps.answer, db, _run(gaps.owned, db, user, trace_id), body.answers, body.before))


@router.post("/{trace_id}/lesson", dependencies=[Depends(limit("gap-lesson", 6))])
def lesson(trace_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """The five-minute fix for the root gap, in the student's language."""
    trace = _run(gaps.owned, db, user, trace_id)
    if not trace.lesson:
        usage.require(db, user, "gap_lesson")
    trace, used_ai = _run(gaps.lesson, db, user, trace)
    if used_ai:
        usage.charge(db, user, "gap_lesson")
    return gaps.view(trace)


class AfterIn(BaseModel):
    answers: list[int | None] = Field(max_length=gaps.RETEST)


@router.post("/{trace_id}/after")
def after(trace_id: int, body: AfterIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """The stuck topic again, after the fix: the "after" next to the "before"."""
    return gaps.view(_run(gaps.after, db, _run(gaps.owned, db, user, trace_id), body.answers))


class CheckIn(BaseModel):
    choice: int = Field(ge=0, le=3)


@router.post("/{trace_id}/check")
def check(trace_id: int, body: CheckIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    return gaps.view(_run(gaps.recheck, db, _run(gaps.owned, db, user, trace_id), body.choice))
