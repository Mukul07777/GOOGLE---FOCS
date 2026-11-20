"""Shared lookups and serialisers for the routers."""
from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models._util import utcnow
from app.models.note import Note
from app.models.session import StudySession
from app.models.user import User
from app.schemas.note import NoteOut
from app.schemas.session import SessionOut
from app.services import topic_notes, translate, usage
from app.services.llm import LLMUnavailable
from app.services.syllabus import Chapter, Topic


def owned_session(db: Session, user: User, session_id: int) -> StudySession:
    s = db.get(StudySession, session_id)
    if not s or s.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


def owned_note(db: Session, user: User, note_id: int) -> Note:
    note = db.scalar(
        select(Note).join(StudySession).where(Note.id == note_id, StudySession.user_id == user.id)
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


def note_out(note: Note) -> NoteOut:
    out = NoteOut.model_validate(note)
    out.has_image = bool(note.image_path)
    return out


MAX_SESSION_MIN = 6 * 60  # sessions abandoned without "End" shouldn't count as 3-day study marathons


def session_minutes(s: StudySession) -> float:
    if not s.started_at:
        return 0.0
    end = s.ended_at or (utcnow() if s.is_active else s.started_at)
    return round(min(MAX_SESSION_MIN, max(0.0, (end - s.started_at).total_seconds() / 60)), 1)


IDLE_END = timedelta(minutes=30)  # a live lecture with no frame and no new board for this long was abandoned


def close_idle_sessions(db: Session, user_id: int) -> None:
    """End the student's live lectures that nothing has happened in for IDLE_END. The lecture ends at its last board
    (or its start), so a tab left open overnight adds no study time."""
    from app.services import live

    now = utcnow()
    changed = False
    for s in db.scalars(select(StudySession).where(StudySession.user_id == user_id, StudySession.is_active.is_(True))):
        idle = live.idle_seconds(s.id)
        if idle is not None and idle < IDLE_END.total_seconds():
            continue  # frames are still coming in, even if the board hasn't changed
        last = s.notes[-1].captured_at if s.notes else None
        last = max(t for t in (last, s.started_at) if t) if (last or s.started_at) else None
        if last and now - last < IDLE_END:
            continue
        s.is_active = False
        s.ended_at = last or now
        live.forget(s.id)
        changed = True
    if changed:
        db.commit()


def session_out(s: StudySession, note_count: int | None = None) -> SessionOut:
    out = SessionOut.model_validate(s)
    out.note_count = note_count if note_count is not None else len(s.notes)
    out.duration_min = session_minutes(s)
    return out


def note_counts(db: Session, session_ids: list[int]) -> dict[int, int]:
    if not session_ids:
        return {}
    rows = db.execute(
        select(Note.session_id, func.count(Note.id)).where(Note.session_id.in_(session_ids)).group_by(Note.session_id)
    ).all()
    return {sid: n for sid, n in rows}


NOT_WRITTEN_YET = "can't be written right now: the AI that writes them is unreachable. Try again in a minute."


def _in_language(db: Session, user: User, exam: str, kind: str, ref_id: str, content: str) -> tuple[str, dict]:
    """A library note in the student's language: translated once (and kept with the note for everyone after), or
    the English with a notice when the AI can't make it now. Returns the text and what to tell the page."""
    lang = user.language
    if not translate.wanted(lang):
        return content, {}
    row = topic_notes.get(db, exam, kind, ref_id)
    kept = (row.translations or {}).get(lang) if row is not None else None
    if kept is None and usage.can_spend(db, user, "detailed_notes"):
        kept, ok = translate.translate(content, lang, user.exam_target, "revision notes" if kind == "capsule" else "study notes")
        if ok and row is not None:
            row.translations = {**(row.translations or {}), lang: kept}
            db.commit()
        kept = kept if ok else None
    return (kept, {"language": lang}) if kept else (content, {"language_note": translate.notice(lang)})


def library_notes(db: Session, user: User, exam: str, chapter: Chapter, topic: Topic) -> dict:
    """A topic's detailed notes for this student. Reading the library is free; when the note has to be written
    first, that costs AI allowance (once: everyone after reads it from the library)."""
    if not topic.notes and topic_notes.get(db, exam, "detailed", topic.id) is None:
        usage.require(db, user, "detailed_notes")
    try:
        content, written, checked = topic_notes.topic_note(db, exam, chapter, topic)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"These notes aren't in the library yet and {NOT_WRITTEN_YET}") from exc
    if written:
        usage.charge(db, user, "detailed_notes")
    shown, lang = _in_language(db, user, exam, "detailed", topic.id, content)
    return {"source": "library", "topic_id": topic.id, "title": topic.name, "chapter": chapter.name,
            "subject": chapter.subject, "notes_md": shown, "written_now": written, "checked": checked, **lang,
            "questions": topic_notes.exam_questions(db, exam, chapter, topic, solved_in=content)}


def library_capsule(db: Session, user: User, exam: str, chapter: Chapter) -> dict:
    """A chapter's last-day revision capsule, on the same terms as a topic's notes: free to read, written once."""
    if topic_notes.get(db, exam, "capsule", chapter.id) is None:
        usage.require(db, user, "detailed_notes")
    try:
        content, written, checked = topic_notes.capsule(db, exam, chapter)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"This capsule isn't in the library yet and {NOT_WRITTEN_YET}") from exc
    if written:
        usage.charge(db, user, "detailed_notes")
    shown, lang = _in_language(db, user, exam, "capsule", chapter.id, content)
    return {"source": "library", "title": chapter.name, "chapter": chapter.name, "subject": chapter.subject,
            "notes_md": shown, "written_now": written, "checked": checked, **lang,
            "questions": topic_notes.exam_questions(db, exam, chapter)}
