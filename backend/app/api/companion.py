import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api._common import owned_note, owned_session
from app.core.database import SessionLocal
from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models.doubt import Doubt
from app.models.user import User
from app.schemas.practice import AskIn, DoubtOut
from app.services import ai, usage

router = APIRouter(prefix="/companion", tags=["companion"])


def _context(db: Session, user: User, body: AskIn) -> str:
    context = ""
    if body.session_id:
        session = owned_session(db, user, body.session_id)
        context = "\n\n".join(f"## {n.topic or 'Board'}\n{n.ai_notes or ''}" for n in session.notes[-8:])
    if body.note_id:  # "ask about this board": that board leads the context
        note = owned_note(db, user, body.note_id)
        focus = f"The student is asking about THIS board:\n## {note.topic or 'Board'}\n{note.ai_notes or note.ocr_raw or ''}"
        context = f"{focus}\n\n{context}" if context else focus
    return context


def _keep(db: Session, user: User, body: AskIn, result: dict) -> dict:
    """Save an AI answer as a doubt and charge it; the offline fallback is neither kept nor charged."""
    if result["source"] != "ai":  # "the tutor can't answer right now" is not an answer worth keeping
        return {"id": None, "answer": result["answer"], "source": result["source"]}
    doubt = Doubt(user_id=user.id, session_id=body.session_id, question=body.question, answer=result["answer"])
    db.add(doubt)
    db.commit()
    usage.charge(db, user, "doubt", result["source"])
    return {"id": doubt.id, "answer": result["answer"], "source": result["source"]}


@router.post("/ask", dependencies=[Depends(limit("ask", 30))])
def ask(body: AskIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    context = _context(db, user, body)
    usage.require(db, user, "doubt")
    result = ai.companion(body.question, context, [t.model_dump() for t in body.history], user.exam_target, body.mode,
                          language=user.language)
    return _keep(db, user, body, result)


@router.post("/ask/stream", dependencies=[Depends(limit("ask", 30))])
def ask_stream(body: AskIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """/ask, word by word (Server-Sent Events): `delta` events carry the answer as it is written, then one `done`
    event carries what /ask returns. Ownership and the allowance are checked before the stream opens, so those
    still answer with an ordinary error status."""
    context = _context(db, user, body)
    usage.require(db, user, "doubt")
    history = [t.model_dump() for t in body.history]
    exam, language, user_id = user.exam_target, user.language, user.id

    def events():
        for kind, value in ai.companion_stream(body.question, context, history, exam, body.mode, language=language):
            if kind == "delta":
                yield f"event: delta\ndata: {json.dumps(value)}\n\n"
                continue
            # the request's own session closes once the response starts, so the answer is saved in a fresh one
            with SessionLocal() as own:
                me = own.get(User, user_id)
                out = _keep(own, me, body, value) if me else {"id": None, **value}
            yield f"event: done\ndata: {json.dumps(out)}\n\n"

    # text/event-stream: the gzip middleware passes it through untouched, so each piece reaches the page at once
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
