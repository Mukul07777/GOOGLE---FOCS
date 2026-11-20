"""While the AI works: one small thing to do from the student's own material, so no wait is dead time.

A flashcard that's due, a question from the redo queue, or a formula from their notes, the ones on the topic of
what they're waiting for first. Nothing here calls the AI: it has to work exactly when the AI is busy.
"""
import zlib
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models._util import utcnow
from app.models.flashcard import Flashcard
from app.models.note import Note
from app.models.quiz_attempt import QuizAttempt
from app.models.session import StudySession
from app.models.user import User
from app.services import formulas

router = APIRouter(prefix="/wait", tags=["wait"])


def _on(topic: str, *fields: str | None) -> bool:
    """Does any of these fields mention the topic (or the topic mention it)?"""
    t = topic.strip().lower()
    return bool(t) and any(f and (t in f.lower() or f.lower() in t) for f in fields)


def _pick(rows: list, topic: str, fields) -> Any:
    return next((r for r in rows if _on(topic, *fields(r))), None) or (rows[0] if rows else None)


@router.get("/task")
def task(topic: str = Query("", max_length=160), skip: str = Query("", max_length=40),
         db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """One small task: a due flashcard, else a redo question, else a formula. `skip` = "card:12" etc., to get
    the next one after doing (or passing on) this one."""
    cards = list(db.scalars(select(Flashcard).where(Flashcard.user_id == user.id, Flashcard.due_at <= utcnow())
                            .order_by(Flashcard.due_at).limit(50)))
    cards = [c for c in cards if f"card:{c.id}" != skip]
    card = _pick(cards, topic, lambda c: (c.topic, c.subject, c.front))
    if card is not None:
        return {"kind": "card", "id": card.id, "front": card.front, "back": card.back, "topic": card.topic}

    redos = list(db.scalars(select(QuizAttempt).where(QuizAttempt.user_id == user.id, QuizAttempt.needs_redo.is_(True),
                                                      QuizAttempt.question != "")
                            .order_by(QuizAttempt.attempted_at.desc()).limit(50)))
    redos = [r for r in redos if f"redo:{r.id}" != skip]
    redo = _pick(redos, topic, lambda r: (r.topic, r.subject, r.question))
    if redo is not None:
        return {"kind": "redo", "id": redo.id, "question": redo.question, "topic": redo.topic}

    notes = db.scalars(select(Note).join(StudySession).where(StudySession.user_id == user.id, Note.ai_notes.ilike("%formula%"))
                       .order_by(Note.captured_at.desc()).limit(40)).all()
    found = [(t["topic"], s["subject"], f["text"]) for s in formulas.book(notes) for t in s["topics"] for f in t["formulas"]]
    found = [f for f in found if f"formula:{zlib.crc32(f[2].encode())}" != skip]
    formula = _pick(found, topic, lambda f: (f[0], f[1]))
    if formula is not None:
        return {"kind": "formula", "id": zlib.crc32(formula[2].encode()), "formula": formula[2], "topic": formula[0], "subject": formula[1]}
    return {"kind": "none"}
