"""Campus: past papers and notes that students of a course share with each other, college by college.

A file is whatever the student uploaded: Focs doesn't check it, and says so. Two reports hide an item. A paper's
questions can be read out of it once (by the model that sees images) so each can be opened and explained."""
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models._util import utcnow
from app.models.campus import CampusItem
from app.models.user import User
from app.services import images, storage, syllabus, usage, vision
from app.services.llm import LLMUnavailable, restore_backslashes

router = APIRouter(prefix="/campus", tags=["campus"])

TYPES = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_BYTES = 15 * 1024 * 1024
HIDE_AFTER_REPORTS = 2
READ_PAGES = 6

READ_PAPER = """These pages are a {subject} question paper from a university exam. List its questions in order.
Return ONLY a JSON object: {{"questions": [{{"no": "1(a)", "text": "the question exactly as printed, math in LaTeX inside $...$",
"marks": marks if printed else null}}]}}
Keep sub-parts as separate questions. Leave out instructions, headers and anything that is not a question. Use []
when no question can be read."""


def _courses_student(user: User) -> str:
    """The student's exam, when it is one whose subjects are library courses (a B.Tech branch, a GATE paper)."""
    exam = syllabus.exam_of(user.exam_target)
    if syllabus.family(exam) != "college":
        raise HTTPException(status_code=404, detail="Campus is where B.Tech and GATE students share past papers and notes. "
                                                    "Set one of those as what you're preparing for in Settings.")
    return exam  # type: ignore[return-value]


def _out(item: CampusItem, user: User, names: dict[int, str]) -> dict[str, Any]:
    return {"id": item.id, "kind": item.kind, "subject": item.subject, "title": item.title, "year": item.year, "exam_kind": item.exam_kind,
            "college": item.college, "pages": item.pages, "size": item.size, "votes": len(item.voters or []),
            "voted": user.id in (item.voters or []), "mine": item.user_id == user.id, "by": names.get(item.user_id, "A student"),
            "has_questions": item.questions is not None, "opens": item.opens or 0,
            "created_at": item.created_at.isoformat() + "Z" if item.created_at else None}


def _names(db: Session, items: list[CampusItem]) -> dict[int, str]:
    """First name and initial only: enough to thank someone, not enough to find them."""
    ids = {i.user_id for i in items}
    out = {}
    for uid, name in db.execute(select(User.id, User.full_name).where(User.id.in_(ids))) if ids else []:
        parts = (name or "A student").split()
        out[uid] = parts[0] + (f" {parts[-1][0]}." if len(parts) > 1 else "")
    return out


def _item(db: Session, item_id: int) -> CampusItem:
    item = db.get(CampusItem, item_id)
    if item is None or len(item.reporters or []) >= HIDE_AFTER_REPORTS:
        raise HTTPException(status_code=404, detail="That file isn't here any more.")
    return item


@router.get("")
def browse(subject: str | None = Query(None, max_length=60), kind: Literal["paper", "notes"] | None = None,
           scope: Literal["mine", "all"] = "mine", db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """What has been shared: for the student's own subjects (or one of them), at their college or everywhere."""
    _courses_student(user)
    mine = syllabus.of(user)
    college = syllabus.college_of(user.college)
    # (with no subject chosen: the student's own subjects, and whatever they shared themselves)
    stmt = select(CampusItem).where(CampusItem.subject == subject if subject
                                    else CampusItem.subject.in_(mine.subjects) | (CampusItem.user_id == user.id))
    if kind:
        stmt = stmt.where(CampusItem.kind == kind)
    if scope == "mine" and college != "other":
        stmt = stmt.where(CampusItem.college == college)
    items = [i for i in db.scalars(stmt.order_by(CampusItem.created_at.desc()).limit(300)) if len(i.reporters or []) < HIDE_AFTER_REPORTS]
    items.sort(key=lambda i: (-len(i.voters or []), -(i.year or 0)))
    names = _names(db, items)
    return {"college": college, "college_name": syllabus.COLLEGES[college]["name"], "subjects": list(mine.subjects),
            "catalogue": sorted(syllabus.courses()), "items": [_out(i, user, names) for i in items]}


@router.post("", status_code=201, dependencies=[Depends(limit("campus-upload", 6))])
def share(file: UploadFile = File(...), kind: Literal["paper", "notes"] = Form(...), subject: str = Form(..., max_length=60),
          title: str = Form(..., min_length=3, max_length=160), year: int | None = Form(None, ge=2000, le=2100),
          exam_kind: Literal["mid", "end", "quiz", "other"] | None = Form(None),
          db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Share a past paper or your notes for a course. Only share what is yours to share."""
    _courses_student(user)
    if subject not in syllabus.courses():
        raise HTTPException(status_code=422, detail="Choose the course this belongs to.")
    if file.content_type not in TYPES:
        raise HTTPException(status_code=415, detail="Share a PDF or a photo (JPEG, PNG, WebP).")
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="The file can be up to 15 MB.")
    try:
        pages = vision.pdf_page_count(data) if file.content_type == "application/pdf" else 1
        if file.content_type != "application/pdf":
            vision.to_jpeg(data)  # (opens it: a file that isn't really an image is turned away)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="That file couldn't be opened. Check it isn't damaged or locked.") from exc
    item = CampusItem(user_id=user.id, college=syllabus.college_of(user.college), subject=subject, kind=kind, title=" ".join(title.split()),
                      year=year if kind == "paper" else None, exam_kind=exam_kind if kind == "paper" else None, file_path="",
                      content_type=file.content_type, pages=pages, size=len(data), voters=[], reporters=[])
    db.add(item)
    db.flush()
    item.file_path = f"campus/{item.id}.{TYPES[file.content_type]}"
    storage._put(item.file_path, data)
    db.commit()
    return _out(item, user, _names(db, [item]))


@router.get("/{item_id}/file")
def open_file(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    _courses_student(user)
    item = _item(db, item_id)
    data = storage.read(item.file_path)
    if data is None:
        raise HTTPException(status_code=404, detail="That file isn't here any more.")
    item.opens = (item.opens or 0) + 1
    db.commit()
    return Response(data, media_type=item.content_type, headers={"Content-Disposition": f'inline; filename="focs-campus-{item.id}.{TYPES[item.content_type]}"',
                                                                 "Cache-Control": "private, max-age=3600"})


@router.get("/{item_id}/page/{number}")
def page(item_id: int, number: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    """One page of a shared file as a picture: what the Android app shows, since it cannot display a PDF."""
    _courses_student(user)
    item = _item(db, item_id)
    data = storage.read(item.file_path)
    if data is None or not 1 <= number <= (item.pages or 1):
        raise HTTPException(status_code=404, detail="That page isn't here.")
    try:
        if item.content_type == "application/pdf":
            import pymupdf

            with pymupdf.open(stream=data, filetype="pdf") as doc:
                picture = images.pdf_page_jpeg(doc[number - 1], 130)
        else:
            picture = vision.to_jpeg(data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="That page couldn't be opened.") from exc
    if number == 1:
        item.opens = (item.opens or 0) + 1
        db.commit()
    return Response(picture, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.post("/{item_id}/vote")
def vote(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """"This helped": once per student, and again to take it back."""
    _courses_student(user)
    item = _item(db, item_id)
    voters = list(item.voters or [])
    item.voters = [v for v in voters if v != user.id] if user.id in voters else [*voters, user.id]
    db.commit()
    return {"votes": len(item.voters), "voted": user.id in item.voters}


@router.post("/{item_id}/report", status_code=204)
def report(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    """Wrong course, unreadable, or not theirs to share. Two different students reporting hides it."""
    _courses_student(user)
    item = _item(db, item_id)
    item.reporters = sorted({*(item.reporters or []), user.id})
    db.commit()


@router.delete("/{item_id}", status_code=204)
def remove(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    item = db.get(CampusItem, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="That isn't yours to remove.")
    storage.delete(item.file_path)
    db.delete(item)
    db.commit()


@router.post("/{item_id}/questions", dependencies=[Depends(limit("campus-read", 6))])
def questions(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """The questions of a shared paper, read out of it. Read once (that uses AI allowance), then kept for everyone."""
    _courses_student(user)
    item = _item(db, item_id)
    if item.kind != "paper":
        raise HTTPException(status_code=422, detail="Only a question paper has questions to list.")
    if item.questions is None:
        if not vision.available():
            raise HTTPException(status_code=503, detail="Reading a paper needs the AI that sees images, which isn't set up on this server.")
        usage.require(db, user, "test_analysis")
        data = storage.read(item.file_path)
        if data is None:
            raise HTTPException(status_code=404, detail="That file isn't here any more.")
        try:
            pages = vision.pdf_pages(data, READ_PAGES) if item.content_type == "application/pdf" else [vision.to_jpeg(data)]
            read = vision.read_json(pages, READ_PAPER.format(subject=item.subject), "campus_paper", max_tokens=6000)
        except (ValueError, LLMUnavailable) as exc:
            raise HTTPException(status_code=503, detail="Couldn't read that paper right now. Try again in a minute.") from exc
        found = []
        for q in (read.get("questions") or [])[:60]:
            text = restore_backslashes(str(q.get("text") or "").strip()) if isinstance(q, dict) else ""
            if len(text) >= 8:
                try:
                    marks = float(q["marks"]) if q.get("marks") is not None else None
                except (TypeError, ValueError):
                    marks = None
                found.append({"no": str(q.get("no") or len(found) + 1)[:12], "text": text[:2000], "marks": marks})
        item.questions = found
        db.commit()
        usage.charge(db, user, "test_analysis", "ai")
    return {"id": item.id, "title": item.title, "subject": item.subject, "questions": item.questions, "read_at": utcnow().isoformat() + "Z"}
