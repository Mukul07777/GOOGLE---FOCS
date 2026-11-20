from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.api._common import NOT_WRITTEN_YET, library_notes, note_out, owned_note
from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models._util import utcnow
from app.models.flashcard import Flashcard
from app.models.note import Note
from app.models.session import StudySession
from app.models.user import User
from app.schemas.note import NoteOut, NotePage, NoteUpdate
from app.services import ai, formulas, storage, syllabus, topic_notes, usage
from app.services.llm import LLMUnavailable

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("", response_model=NotePage)
def list_notes(
    q: str | None = Query(None, max_length=120),
    session_id: int | None = None,
    subject: str | None = None,
    pinned: bool | None = None,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Note).join(StudySession).where(StudySession.user_id == user.id)
    if session_id:
        stmt = stmt.where(Note.session_id == session_id)
    if subject:
        stmt = stmt.where(Note.subject == subject)
    if pinned is not None:
        stmt = stmt.where(Note.is_pinned.is_(pinned))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Note.ai_notes.ilike(like), Note.topic.ilike(like), Note.ocr_raw.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    notes = db.scalars(stmt.order_by(Note.captured_at.desc()).offset(offset).limit(limit)).all()
    return NotePage(items=[note_out(n) for n in notes], total=total)


@router.get("/formulas")
def formula_book(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Every formula from the student's board notes, grouped by subject and topic."""
    notes = db.scalars(select(Note).join(StudySession).where(StudySession.user_id == user.id,
                                                             Note.ai_notes.ilike("%formula%"))).all()
    return formulas.book(notes)


@router.get("/{note_id}", response_model=NoteOut)
def get_note(note_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return note_out(owned_note(db, user, note_id))


@router.get("/{note_id}/image")
def note_image(note_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = storage.read(owned_note(db, user, note_id).image_path)
    if not data:
        raise HTTPException(status_code=404, detail="No snapshot for this note")
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.patch("/{note_id}", response_model=NoteOut)
def update_note(note_id: int, body: NoteUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    note = owned_note(db, user, note_id)
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(note, k, v)
    if "ai_notes" in changes or "topic" in changes:
        note.updated_at = utcnow()
    db.commit()
    return note_out(note)


@router.post("/{note_id}/regenerate", response_model=NoteOut)
def regenerate_note(note_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    note = owned_note(db, user, note_id)
    usage.require(db, user, "regenerate_note")
    result = ai.generate_notes(note.ocr_raw or "", user.exam_target)
    if not result.get("is_lecture"):
        raise HTTPException(status_code=422, detail="No lecture content could be recovered from this board.")
    note.ai_notes, note.topic, note.subject = result["notes_md"], result["topic"], ai.fit_subject(result["subject"], user.exam_target)
    note.updated_at, note.detailed_md = utcnow(), None  # the detailed version was written from the old notes
    db.commit()
    usage.charge(db, user, "regenerate_note", result.get("source"))
    return note_out(note)


@router.post("/{note_id}/detailed", dependencies=[Depends(limit("detailed_notes", 20))])
def detailed_notes(note_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The optional detailed version of a board's notes, given when the student asks. A board on a syllabus topic
    gets that topic's pre-made note from the library; any other board gets a detailed write-up of its own."""
    note = owned_note(db, user, note_id)
    if note.detailed_md:
        return {"source": "board", "title": note.topic or "Board notes", "notes_md": note.detailed_md, "written_now": False}
    syl = syllabus.of(user)  # a college student's boards are matched against the subjects they are studying
    if syl:
        found = topic_notes.match(syl, note.subject, note.topic, note.ai_notes or "")
        if found:
            return library_notes(db, user, syl.library, *found)
    if len((note.ai_notes or "").strip()) < 40:
        raise HTTPException(status_code=422, detail="This board doesn't have enough on it for detailed notes.")
    usage.require(db, user, "detailed_notes")
    try:
        note.detailed_md = topic_notes.write_board(user.exam_target, note.topic, note.ai_notes or "", note.ocr_raw or "")
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Detailed notes for this board {NOT_WRITTEN_YET}") from exc
    db.commit()
    usage.charge(db, user, "detailed_notes")
    return {"source": "board", "title": note.topic or "Board notes", "notes_md": note.detailed_md, "written_now": True}


@router.delete("/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    note = owned_note(db, user, note_id)
    storage.delete(note.image_path)
    db.execute(update(Flashcard).where(Flashcard.note_id == note.id).values(note_id=None))  # keep the cards
    db.delete(note)
    db.commit()
