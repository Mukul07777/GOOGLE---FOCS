from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api._common import owned_note, owned_session
from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models.doubt import Doubt
from app.models.user import User
from app.schemas.practice import AskIn, DoubtOut
from app.services import ai, usage

router = APIRouter(prefix="/companion", tags=["companion"])


@router.post("/ask", dependencies=[Depends(limit("ask", 30))])
def ask(body: AskIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    context = ""
    if body.session_id:
        session = owned_session(db, user, body.session_id)
        context = "\n\n".join(f"## {n.topic or 'Board'}\n{n.ai_notes or ''}" for n in session.notes[-8:])
    if body.note_id:  # "ask about this board": that board leads the context
        note = owned_note(db, user, body.note_id)
        focus = f"The student is asking about THIS board:\n## {note.topic or 'Board'}\n{note.ai_notes or note.ocr_raw or ''}"
        context = f"{focus}\n\n{context}" if context else focus
    usage.require(db, user, "doubt")
    result = ai.companion(body.question, context, [t.model_dump() for t in body.history], user.exam_target, body.mode,
                          language=user.language)
    if result["source"] != "ai":  # "the tutor can't answer right now" is not an answer worth keeping
        return {"id": None, "answer": result["answer"], "source": result["source"]}
    doubt = Doubt(user_id=user.id, session_id=body.session_id, question=body.question, answer=result["answer"])
    db.add(doubt)
    db.commit()
    usage.charge(db, user, "doubt", result["source"])
    return {"id": doubt.id, "answer": result["answer"], "source": result["source"]}


@router.get("/history", response_model=list[DoubtOut])
def history(
    session_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Doubt).where(Doubt.user_id == user.id)
    if session_id:
        stmt = stmt.where(Doubt.session_id == session_id)
    return db.scalars(stmt.order_by(Doubt.created_at.desc()).limit(limit)).all()
