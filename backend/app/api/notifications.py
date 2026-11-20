"""The bell: what happened for this student since they last looked (a junior asked them, a senior answered them)."""
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models._util import utcnow
from app.models.notification import Notification
from app.models.user import User

router = APIRouter(prefix="/notifications", tags=["notifications"])
SHOWN = 30


def notify(db: Session, user_ids: list[int], kind: str, text: str, link: str | None = None) -> None:
    """Add one notification per student (the caller commits)."""
    for uid in dict.fromkeys(user_ids):  # once each, in order
        db.add(Notification(user_id=uid, kind=kind, text=text[:300], link=link))


@router.get("")
def mine(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id)
                      .order_by(Notification.created_at.desc(), Notification.id.desc()).limit(SHOWN)).all()
    unread = db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.read_at.is_(None)))
    return {"unread": unread or 0, "items": [{"id": n.id, "kind": n.kind, "text": n.text, "link": n.link, "read": n.read_at is not None,
                                              "created_at": n.created_at.isoformat() + "Z" if n.created_at else None} for n in rows]}


@router.post("/read", status_code=204)
def read_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)).values(read_at=utcnow()))
    db.commit()
