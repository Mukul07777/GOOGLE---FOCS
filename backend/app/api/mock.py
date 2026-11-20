from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models.mock import BankQuestion, MockTest
from app.models.user import User
from app.services import ai, bridge, mock, question_bank, syllabus, usage
from app.services.llm import LLMUnavailable
from app.services.mock_patterns import (
    BOARD_MOCK_QUESTIONS,
    CHAPTER_TEST_SIZES,
    COURSE_TEST_SIZES,
    DEFAULT_PATTERN,
    DEFAULT_PATTERNS,
    EXAM_SUBJECTS,
    PATTERNS,
    SYLLABUS,
    chapters_of,
    is_course,
)

router = APIRouter(prefix="/mock", tags=["mock tests"])


class MockCreate(BaseModel):
    pattern: str = DEFAULT_PATTERN
    # chapter tests (pattern "chapter")
    subject: str | None = None
    chapters: list[str] = Field(default_factory=list, max_length=12)  # none, for a college course: all of them (a subject test)
    count: int = 15
    board: bool = False  # a mock board exam: the whole subject (Class 10 and 12)


class ResponsesIn(BaseModel):
    responses: dict[str, dict[str, Any]] = {}
    current_index: int | None = None
    tab_switches: int | None = None


class FeelingIn(BaseModel):
    subject: str = Field(max_length=60)
    chapter: str = Field(max_length=120)
    felt: Literal["sure", "shaky"] | None = None


class ExplainIn(BaseModel):
    language: Literal["hinglish", "hi"]


class ReportIn(BaseModel):
    reason: str = Field(default="", max_length=300)


def _owned(db: Session, user: User, test_id: int) -> MockTest:
    test = db.get(MockTest, test_id)
    if not test or test.user_id != user.id:
        raise HTTPException(status_code=404, detail="Mock test not found")
    return test


def _iso(dt) -> str | None:
    return dt.isoformat() + "Z" if dt else None


def _summary(test: MockTest) -> dict[str, Any]:
    p = mock.pattern_of(test) if test.pattern == "chapter" or test.pattern in PATTERNS else None
    total = (test.result or {}).get("total", {})
    return {
        "id": test.id, "title": test.title, "pattern": test.pattern, "pattern_name": p.name if p else test.pattern,
        "kind": "full" if mock.is_full_mock(test) else "chapter", "config": test.config,
        "status": test.status, "progress": test.progress, "error": test.error, "duration_min": test.duration_min,
        "created_at": _iso(test.created_at), "started_at": _iso(test.started_at), "submitted_at": _iso(test.submitted_at),
        "remaining_sec": mock.remaining_seconds(test) if test.status == "in_progress" else None,
        "score": test.score, "max_score": test.max_score or (p.max_score if p else None),
        "accuracy": total.get("accuracy"), "correct": total.get("correct"), "incorrect": total.get("incorrect"),
        "time_sec": total.get("time_sec"),
        "subjects": [{"subject": s["subject"], "score": s["score"], "max": s["max"]} for s in (test.result or {}).get("subjects", [])],
    }


NO_SCHOOL_TESTS = ("Timed tests and mock board exams open in Class 10 and Class 12, the board years. Until then, learn "
                   "chapter by chapter in the Prep Hub and practise under Practice.")
NO_TESTS = ("Tests follow the JEE, NEET, SSC CGL, GATE, B.Tech, placements and school (Class 1-12) syllabi. Set one of those as what you're "
            "preparing for in Settings.")


def _exam(user: User) -> str:
    """Whose papers a student takes. A student whose exam has no syllabus here (UPSC, CA, other) has none: they are
    never handed another exam's papers."""
    exam = syllabus.exam_of(user.exam_target)
    if exam is None:
        raise HTTPException(status_code=404, detail=NO_TESTS)
    if not syllabus.has_tests(exam):
        raise HTTPException(status_code=403, detail=NO_SCHOOL_TESTS)
    kind = syllabus.group(exam)
    if kind == "placement":  # tested like a semester: one subject (a library course) at a time
        return "college"
    return kind if kind in ("college", "gate", "cbse", "neet", "ssc_cgl") else "jee"


def _subjects(user: User, exam: str) -> set[str]:
    """The subjects a student can be tested on: their own exam's (a B.Tech student's, any course of the library)."""
    if exam in ("college", "gate", "cbse"):
        return set(syllabus.of(user, whole=True).subjects)
    return set(EXAM_SUBJECTS[exam])


def _own_patterns(user: User, exam: str) -> set[str]:
    """The full papers a student can take: their exam's (a GATE paper's own; a semester and the boards have none)."""
    if exam in ("college", "gate", "cbse"):
        return {f"{syllabus.of(user).exam}_full"} & set(PATTERNS)
    return {p.id for p in PATTERNS.values() if p.exam == exam}


@router.get("/meta")
def meta(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Patterns and chapters for the student's exam: NEET students get NEET papers and Biology chapters. A college
    student has no full mock: their tests are on one of their subjects (all of it, or some chapters)."""
    exam = _exam(user)
    stock = question_bank.chapter_stock(db)
    if exam in ("college", "gate", "cbse"):
        mine = syllabus.of(user)
        full = PATTERNS.get(f"{mine.exam}_full")  # GATE has a full paper; a semester and the boards are subject by subject
        return {"exam": exam, "patterns": [full.public()] if full else [], "default": full.id if full else None,
                "quota": mock.quota(db, user), "bank": {},
                "syllabus": {s: [c.name for c in mine.subject_chapters(s)] for s in mine.subjects},
                "chapter_stock": {s: stock.get(s, {}) for s in mine.subjects}, "chapter_sizes": list(CHAPTER_TEST_SIZES if exam == "cbse" else COURSE_TEST_SIZES),
                "board_mock": exam == "cbse"}
    return {"exam": exam, "patterns": [p.public() for p in PATTERNS.values() if p.exam == exam], "default": DEFAULT_PATTERNS[exam],
            "quota": mock.quota(db, user), "bank": question_bank.stock(db),
            "syllabus": {s: list(SYLLABUS[s]) for s in EXAM_SUBJECTS[exam]}, "chapter_stock": stock,
            "chapter_sizes": list(CHAPTER_TEST_SIZES)}


@router.get("")
def list_tests(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    mock.finalize_overdue(db, user)
    tests = db.scalars(select(MockTest).where(MockTest.user_id == user.id).order_by(MockTest.created_at.desc())).all()
    for t in tests:
        mock.resume(t)
    return [_summary(t) for t in tests if t.status != "failed" or t.started_at is None]


@router.post("", status_code=201, dependencies=[Depends(limit("mock-create", 6))])
def create_test(body: MockCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    config = None
    exam = _exam(user)
    if body.pattern == "chapter":
        if body.subject not in _subjects(user, exam):
            raise HTTPException(status_code=422, detail="Choose one of your own subjects.")
        if exam == "cbse":  # a school subject's chapters are their class's own (NCERT's)
            known = {c.name: c.weight for c in syllabus.of(user, whole=True).subject_chapters(body.subject)}
            course = False
            if body.board:  # a mock board exam: every chapter, at a board paper's length
                body.chapters, body.count = list(known), BOARD_MOCK_QUESTIONS
        else:
            known = chapters_of(body.subject)
            course = is_course(body.subject)
        chapters = [c for c in dict.fromkeys(body.chapters) if c in known]
        if course and not body.chapters:
            chapters = list(known)  # a subject test: the whole course
        if not known or not chapters or (len(chapters) > 6 and not course and not body.board):
            raise HTTPException(status_code=422, detail="Choose a subject and at least one chapter.")
        sizes = COURSE_TEST_SIZES if course else CHAPTER_TEST_SIZES
        if body.count not in sizes and not body.board:
            raise HTTPException(status_code=422, detail=f"A chapter test has {', '.join(map(str, sizes))} questions.")
        if course:
            chapters = [c for c in known if c in chapters]  # in the order they are taught, so the same test is found again
        config = {"subject": body.subject, "chapters": chapters, "count": body.count, "exam": "college" if course else {"gate": "jee"}.get(exam, exam),
                  **({"board": True} if body.board and exam == "cbse" else {})}
    elif body.pattern not in PATTERNS:
        raise HTTPException(status_code=422, detail="Unknown exam pattern")
    elif body.pattern not in _own_patterns(user, exam):
        raise HTTPException(status_code=422, detail="That paper is for another exam.")
    mock.finalize_overdue(db, user)
    running = db.scalar(select(MockTest).where(MockTest.user_id == user.id, MockTest.status == "in_progress"))
    if running:
        raise HTTPException(status_code=409, detail="Finish or submit the mock you're taking before starting another.")
    if body.pattern != "chapter":
        q = mock.quota(db, user)
        if not q["unlimited"] and not q["left"]:
            mock._require_quota(db, user)
    return _summary(mock.create(db, user, body.pattern, config))


@router.get("/{test_id}")
def get_test(test_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    test = _owned(db, user, test_id)
    if mock.overdue(test):
        mock.submit(db, user, test)
    mock.resume(test)  # (the page polls this while the paper is written)
    out = {**_summary(test), "pattern_info": mock.pattern_of(test).public()}
    if test.status in ("ready", "in_progress"):
        out.update(questions=mock.paper(db, test, with_answers=False) if test.status == "in_progress" else [],
                   responses=test.responses or {}, current_index=test.current_index or 0,
                   tab_switches=test.tab_switches or 0)
    elif test.status == "submitted":
        out.update(questions=mock.paper(db, test, with_answers=True), responses=test.responses or {},
                   result=test.result, tab_switches=test.tab_switches or 0, gap_map=bridge.gap_map(user, test))
    return out


@router.get("/{test_id}/warmup")
def warmup(test_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """What the paper will cover, to look over while it is written: topics, key points and self-check questions
    from the notes library (nothing is written for this), with how ready the student said they feel."""
    return bridge.warmup(db, user, _owned(db, user, test_id))


@router.put("/{test_id}/feeling")
def set_feeling(test_id: int, body: FeelingIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """How ready the student feels for one chapter of the paper; the gap map sets it against the result."""
    test = _owned(db, user, test_id)
    if test.status == "submitted":
        raise HTTPException(status_code=409, detail="This test is already marked.")
    try:
        feelings = bridge.set_feeling(test, body.subject, body.chapter, body.felt)
    except KeyError:
        raise HTTPException(status_code=422, detail="That chapter isn't in this paper.") from None
    db.commit()
    return {"felt": feelings}


@router.post("/{test_id}/start")
def start_test(test_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    test = mock.start(db, user, _owned(db, user, test_id))
    return get_test(test.id, db, user)


@router.put("/{test_id}/responses", dependencies=[Depends(limit("mock-save", 120))])
def save_responses(test_id: int, body: ResponsesIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    test = _owned(db, user, test_id)
    if test.status == "submitted":
        return {"status": "submitted", "remaining_sec": 0}
    if test.status != "in_progress":
        raise HTTPException(status_code=409, detail="This mock hasn't started.")
    mock.save_responses(test, body.responses, body.current_index, body.tab_switches)
    if mock.overdue(test):
        mock.submit(db, user, test)
        return {"status": "submitted", "remaining_sec": 0}
    db.commit()
    return {"status": test.status, "remaining_sec": mock.remaining_seconds(test)}


@router.post("/{test_id}/submit")
def submit_test(test_id: int, body: ResponsesIn | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    test = _owned(db, user, test_id)
    if test.status == "in_progress" and body is not None:
        mock.save_responses(test, body.responses, body.current_index, body.tab_switches)
    if test.status not in ("in_progress", "submitted"):
        raise HTTPException(status_code=409, detail="This mock hasn't started.")
    mock.submit(db, user, test)
    return get_test(test.id, db, user)


@router.delete("/{test_id}", status_code=204)
def discard_test(test_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    test = _owned(db, user, test_id)
    if test.started_at:
        raise HTTPException(status_code=409, detail="A started mock stays in your record.")
    db.delete(test)
    db.commit()


def _paper_question(db: Session, user: User, question_id: int) -> BankQuestion:
    """A question from one of the student's own papers."""
    owned = any(question_id in (t or []) for t in db.scalars(select(MockTest.question_ids).where(MockTest.user_id == user.id)))
    q = db.get(BankQuestion, question_id)
    if not q or not owned:
        raise HTTPException(status_code=404, detail="Question not found")
    return q


@router.post("/questions/{question_id}/explain", dependencies=[Depends(limit("mock-explain", 20))])
def explain_question(question_id: int, body: ExplainIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """A question's solution in Hinglish or Hindi. Written once per question and language, then kept for everyone."""
    q = _paper_question(db, user, question_id)
    done = (q.explained or {}).get(body.language)
    if done:
        return {"language": body.language, "solution": done}
    if not q.solution:
        raise HTTPException(status_code=404, detail="This question has no solution to explain.")
    usage.require(db, user, "doubt")
    try:
        text = ai.explain_in(q.solution, q.question, body.language, user.exam_target)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail="The AI that explains solutions is unreachable. Try again in a minute.") from exc
    q.explained = {**(q.explained or {}), body.language: text}
    db.commit()
    usage.charge(db, user, "doubt")
    return {"language": body.language, "solution": text}


@router.post("/questions/{question_id}/report", status_code=204, dependencies=[Depends(limit("mock-report", 20))])
def report_question(question_id: int, body: ReportIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """A student thinks the key or the question is wrong. Two reports retire a question from new papers."""
    q = _paper_question(db, user, question_id)
    q.reports = (q.reports or 0) + 1
    db.commit()
