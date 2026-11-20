"""Classes and the parent link: the two ways someone else sees how a student's preparation is going.

A teacher makes a class and gives its code out; a student who joins lets that teacher see their study time, syllabus
progress, test scores and weak chapters (never their notes or doubts). A parent gets a private link from the student
that shows the same for one child, read-only, without an account."""
import secrets
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models.classroom import Classroom, ClassMember, ParentLink
from app.models.user import User
from app.services import gaps, progress, usage
from app.services.llm import LLMUnavailable

router = APIRouter(prefix="/classes", tags=["classes"])
parent = APIRouter(prefix="/parent", tags=["parent"])

CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # (no 0/O, 1/I: codes get read out in a classroom)
MAX_CLASSES, MAX_MEMBERS, MAX_JOINED = 10, 200, 10
WEAKEST_SHOWN = 8


class ClassIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class JoinIn(BaseModel):
    code: str = Field(min_length=4, max_length=12)


def _owned(db: Session, class_id: int, user: User) -> Classroom:
    room = db.get(Classroom, class_id)
    if room is None or room.owner_id != user.id:
        raise HTTPException(status_code=404, detail="That class isn't yours, or was removed.")
    return room


def _count(db: Session, class_id: int) -> int:
    return db.scalar(select(func.count(ClassMember.id)).where(ClassMember.class_id == class_id)) or 0


@router.get("")
def my_classes(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """The classes this person teaches, and the ones they have joined."""
    teaching = [{"id": c.id, "name": c.name, "code": c.code, "students": _count(db, c.id)}
                for c in db.scalars(select(Classroom).where(Classroom.owner_id == user.id).order_by(Classroom.created_at.desc()))]
    joined = [{"id": c.id, "name": c.name, "teacher": name, "joined_at": m.joined_at.isoformat() + "Z" if m.joined_at else None}
              for m, c, name in db.execute(select(ClassMember, Classroom, User.full_name).join(Classroom, Classroom.id == ClassMember.class_id)
                                           .join(User, User.id == Classroom.owner_id).where(ClassMember.user_id == user.id))]
    return {"teaching": teaching, "joined": joined}


@router.post("", status_code=201, dependencies=[Depends(limit("class-create", 10))])
def create(body: ClassIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    if (db.scalar(select(func.count(Classroom.id)).where(Classroom.owner_id == user.id)) or 0) >= MAX_CLASSES:
        raise HTTPException(status_code=409, detail=f"You can run up to {MAX_CLASSES} classes. Remove one you no longer teach.")
    for _ in range(20):
        code = "".join(secrets.choice(CODE_LETTERS) for _ in range(6))
        if db.scalar(select(Classroom.id).where(Classroom.code == code)) is None:
            break
    room = Classroom(code=code, owner_id=user.id, name=" ".join(body.name.split()))
    db.add(room)
    db.commit()
    return {"id": room.id, "name": room.name, "code": room.code, "students": 0}


@router.post("/join", dependencies=[Depends(limit("class-join", 10))])
def join(body: JoinIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Join a class with its code. Joining is the student's yes to the teacher seeing their progress."""
    room = db.scalar(select(Classroom).where(Classroom.code == body.code.strip().upper().replace(" ", "")))
    if room is None:
        raise HTTPException(status_code=404, detail="No class has that code. Check it with your teacher.")
    if room.owner_id == user.id:
        raise HTTPException(status_code=409, detail="That is your own class: give this code to your students.")
    if db.scalar(select(ClassMember.id).where(ClassMember.class_id == room.id, ClassMember.user_id == user.id)) is None:
        if _count(db, room.id) >= MAX_MEMBERS:
            raise HTTPException(status_code=409, detail="That class is full. Ask your teacher to make another.")
        if (db.scalar(select(func.count(ClassMember.id)).where(ClassMember.user_id == user.id)) or 0) >= MAX_JOINED:
            raise HTTPException(status_code=409, detail=f"You can be in up to {MAX_JOINED} classes. Leave one first.")
        db.add(ClassMember(class_id=room.id, user_id=user.id))
        db.commit()
    teacher = db.get(User, room.owner_id)
    return {"id": room.id, "name": room.name, "teacher": teacher.full_name if teacher else "Your teacher"}


@router.get("/{class_id}")
def dashboard(class_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """The teacher's view of a class: every student's week, the chapters most of the class is weak in, and where those
    weak spots really start (the earlier chapters their root-cause traces led to)."""
    room = _owned(db, class_id, user)
    students = list(db.scalars(select(User).join(ClassMember, ClassMember.user_id == User.id).where(ClassMember.class_id == room.id)))
    seen = progress.summaries(db, students)
    rows = sorted(({"user_id": s.id, "name": s.full_name, **seen[s.id]} for s in students), key=lambda r: r["name"].lower())
    stuck: Counter = Counter()
    names: dict[str, dict[str, str]] = {}
    for r in rows:
        for spot in r["weak"]:
            stuck[spot["id"]] += 1
            names[spot["id"]] = spot
    done = [r["syllabus"]["percent"] for r in rows if r["syllabus"]["percent"] is not None]
    return {"id": room.id, "name": room.name, "code": room.code, "students": rows,
            "weakest": [{**names[cid], "students": n} for cid, n in stuck.most_common(WEAKEST_SHOWN)],
            "roots": gaps.batch_roots(db, [s.id for s in students]),
            "totals": {"students": len(rows), "active_week": sum(1 for r in rows if r["week_minutes"] > 0),
                       "avg_week_minutes": round(sum(r["week_minutes"] for r in rows) / len(rows)) if rows else 0,
                       "avg_syllabus": round(sum(done) / len(done)) if done else None}}


class RecapIn(BaseModel):
    chapter_id: str = Field(min_length=1, max_length=160)


@router.post("/{class_id}/recap", dependencies=[Depends(limit("class-recap", 6))])
def recap(class_id: int, body: RecapIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """The teacher's ten-minute recap of a gap the batch shares: the lesson its students get, with the check question."""
    room = _owned(db, class_id, user)
    members = list(db.scalars(select(ClassMember.user_id).where(ClassMember.class_id == room.id)))
    usage.require(db, user, "gap_lesson")
    try:
        made, used_ai = gaps.class_recap(db, user, members, body.chapter_id)
    except gaps.GapError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail="The AI is busy right now. Try again in a minute.") from exc
    if used_ai:
        usage.charge(db, user, "gap_lesson")
    return made


@router.delete("/{class_id}", status_code=204)
def remove(class_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    room = _owned(db, class_id, user)
    db.execute(delete(ClassMember).where(ClassMember.class_id == room.id))
    db.delete(room)
    db.commit()


@router.delete("/{class_id}/students/{user_id}", status_code=204)
def remove_student(class_id: int, user_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    room = _owned(db, class_id, user)
    db.execute(delete(ClassMember).where(ClassMember.class_id == room.id, ClassMember.user_id == user_id))
    db.commit()


@router.post("/{class_id}/leave", status_code=204)
def leave(class_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    """Leave a class: the teacher stops seeing this student's progress at once."""
    db.execute(delete(ClassMember).where(ClassMember.class_id == class_id, ClassMember.user_id == user.id))
    db.commit()


# ---------------------------------------------------------------- the parent link
def _link_out(link: ParentLink | None) -> dict[str, Any]:
    return {"token": link.token if link else None, "created_at": link.created_at.isoformat() + "Z" if link and link.created_at else None}


@parent.get("/link")
def parent_link(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    return _link_out(db.scalar(select(ParentLink).where(ParentLink.user_id == user.id)))


@parent.post("/link", dependencies=[Depends(limit("parent-link", 10))])
def make_parent_link(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Make the link (or a new one: the old link stops working)."""
    db.execute(delete(ParentLink).where(ParentLink.user_id == user.id))
    link = ParentLink(user_id=user.id, token=secrets.token_urlsafe(18))
    db.add(link)
    db.commit()
    return _link_out(link)


@parent.delete("/link", status_code=204)
def revoke_parent_link(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    db.execute(delete(ParentLink).where(ParentLink.user_id == user.id))
    db.commit()


@parent.get("/view/{token}", dependencies=[Depends(limit("parent-view", 30))])
def parent_view(token: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """What the link shows, to anyone who has it: no sign-in, nothing that can be changed, no notes or doubts."""
    link = db.scalar(select(ParentLink).where(ParentLink.token == token)) if 10 <= len(token) <= 40 else None
    student = db.get(User, link.user_id) if link else None
    if student is None or not student.is_active:
        raise HTTPException(status_code=404, detail="This link doesn't work any more. Ask for a new one.")
    return {"name": (student.full_name or "Your child").split()[0], **progress.summaries(db, [student])[student.id]}
