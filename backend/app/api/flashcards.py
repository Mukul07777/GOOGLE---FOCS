from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api._common import owned_note, owned_session
from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models._util import utcnow
from app.models.flashcard import Flashcard
from app.models.user import User
from app.schemas.practice import CardGenerate, CardIn, CardOut, CardReview
from app.services import ai, srs, usage
from app.services.llm import llm

router = APIRouter(prefix="/flashcards", tags=["flashcards"])


def _out(card: Flashcard) -> CardOut:
    out = CardOut.model_validate(card)
    out.intervals = srs.preview_intervals(card)
    return out


def _owned(db: Session, user: User, card_id: int) -> Flashcard:
    card = db.get(Flashcard, card_id)
    if not card or card.user_id != user.id:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@router.get("", response_model=list[CardOut])
def list_cards(
    due: bool = False,
    session_id: int | None = None,
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Flashcard).where(Flashcard.user_id == user.id)
    if due:
        stmt = stmt.where(Flashcard.due_at <= utcnow())
    if session_id:
        stmt = stmt.where(Flashcard.session_id == session_id)
    order = Flashcard.due_at.asc() if due else Flashcard.created_at.desc()
    return [_out(c) for c in db.scalars(stmt.order_by(order).limit(limit))]


@router.get("/stats")
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    now = utcnow()
    base = select(func.count(Flashcard.id)).where(Flashcard.user_id == user.id)
    return {
        "total": db.scalar(base) or 0,
        "due": db.scalar(base.where(Flashcard.due_at <= now)) or 0,
        # never reviewed yet: "new", not "learning"
        "new": db.scalar(base.where(Flashcard.last_reviewed_at.is_(None))) or 0,
        "learning": db.scalar(base.where(Flashcard.last_reviewed_at.is_not(None), Flashcard.repetitions < 2)) or 0,
        "mature": db.scalar(base.where(Flashcard.interval_days >= 21)) or 0,
    }


@router.post("", response_model=CardOut, status_code=201)
def create_card(body: CardIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    card = Flashcard(user_id=user.id, due_at=utcnow(), **body.model_dump())
    db.add(card)
    db.commit()
    db.refresh(card)
    return _out(card)


@router.post("/generate", response_model=list[CardOut], status_code=201, dependencies=[Depends(limit("cards", 15))])
def generate_cards(body: CardGenerate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if body.note_id:
        note = owned_note(db, user, body.note_id)
        material, topic, subject, session_id = note.ai_notes or "", note.topic, note.subject, note.session_id
    elif body.session_id:
        s = owned_session(db, user, body.session_id)
        material = "\n\n".join(n.ai_notes or "" for n in s.notes)
        topic, subject, session_id = s.title, s.subject, s.id
    else:
        raise HTTPException(status_code=422, detail="Provide note_id or session_id")
    if len(material.strip()) < 30:
        raise HTTPException(status_code=422, detail="This board is too short to make flashcards from yet.")
    usage.require(db, user, "flashcards")
    cards = []
    for c in ai.flashcards(material, user.exam_target, body.count, language=user.language):
        card = Flashcard(user_id=user.id, session_id=session_id, note_id=body.note_id, front=c["front"], back=c["back"],
                         topic=topic, subject=subject, due_at=utcnow())
        db.add(card)
        cards.append(card)
    db.commit()
    usage.charge(db, user, "flashcards", "ai" if llm.available else "offline")
    return [_out(c) for c in cards]


@router.post("/{card_id}/review", response_model=CardOut)
def review_card(card_id: int, body: CardReview, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    card = srs.review(_owned(db, user, card_id), body.grade)
    db.commit()
    return _out(card)


@router.patch("/{card_id}", response_model=CardOut)
def edit_card(card_id: int, body: CardIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    card = _owned(db, user, card_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(card, k, v)
    db.commit()
    return _out(card)


@router.delete("/{card_id}", status_code=204)
def delete_card(card_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(_owned(db, user, card_id))
    db.commit()
