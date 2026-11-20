from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, selectinload

from app.api._common import can_reopen, close_idle_sessions, fold_pause, note_counts, note_out, owned_session, reopen, session_out
from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models._util import utcnow
from app.models.doubt import Doubt
from app.models.flashcard import Flashcard
from app.models.lecture import LectureSegment
from app.models.quiz_attempt import QuizAttempt
from app.models.session import StudySession
from app.models.user import User
from app.schemas.session import SessionDetail, SessionEndOut, SessionOut, SessionStart, SessionUpdate
from app.services import ai, calibration, live, storage, usage, voice, youtube

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _close(session: StudySession) -> None:
    """Close a session the student abandoned: it ended at its last captured board."""
    session.is_active = False
    session.ended_by = "replaced"
    session.pause_since = None
    if not session.ended_at:
        last_note = session.notes[-1].captured_at if session.notes else None
        session.ended_at = last_note or session.started_at or utcnow()
    live.forget(session.id)


@router.post("", response_model=SessionOut, status_code=201)
def start_session(body: SessionStart, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # A student watches one lecture at a time: close whatever was left running.
    for old in db.scalars(select(StudySession).where(StudySession.user_id == user.id, StudySession.is_active.is_(True))):
        _close(old)
    if body.source == "link":  # a YouTube lecture played inside Focs (services/link_lecture)
        vid = youtube.video_id(body.video_url or "")
        if not vid:
            raise HTTPException(status_code=422, detail="Paste a YouTube lecture link (youtube.com/watch?v=… or youtu.be/…).")
        body = body.model_copy(update={"video_url": f"https://www.youtube.com/watch?v={vid}"})
    session = StudySession(user_id=user.id, is_active=True, **body.model_dump())
    session.title_locked = bool((session.title or "").strip())
    if body.source == "link" and not session.title_locked:
        session.title = (youtube.title(youtube.video_id(body.video_url or "") or "") or "")[:120] or None
    db.add(session)
    db.commit()
    db.refresh(session)
    return session_out(session, 0)


@router.get("", response_model=list[SessionOut])
def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    course_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    close_idle_sessions(db, user.id)
    q = select(StudySession).where(StudySession.user_id == user.id)
    if course_id:
        q = q.where(StudySession.course_id == course_id)
    sessions = db.scalars(q.order_by(StudySession.started_at.desc()).offset(offset).limit(limit)).all()
    counts = note_counts(db, [s.id for s in sessions])
    return [session_out(s, counts.get(s.id, 0)) for s in sessions]


@router.get("/active", response_model=SessionOut | None)
def active_session(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    close_idle_sessions(db, user.id)
    s = db.scalar(select(StudySession).where(StudySession.user_id == user.id, StudySession.is_active.is_(True))
                  .order_by(StudySession.started_at.desc()))
    return session_out(s) if s else None


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = owned_session(db, user, session_id)
    detail = SessionDetail(**session_out(s).model_dump())
    detail.notes = [note_out(n) for n in s.notes]
    return detail


@router.patch("/{session_id}", response_model=SessionOut)
def update_session(session_id: int, body: SessionUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = owned_session(db, user, session_id)
    changes = body.model_dump(exclude_unset=True)
    if "title" in changes:
        changes["title"] = (changes["title"] or "").strip() or None
        if not changes["title"]:
            raise HTTPException(status_code=422, detail="Give the lecture a name.")
        s.title_locked = True
    for k, v in changes.items():
        setattr(s, k, v)
    db.commit()
    return session_out(s)


class Alive(BaseModel):
    paused: bool = False
    paused_for_s: float = Field(0, ge=0, le=604800)


@router.post("/{session_id}/alive", dependencies=[Depends(limit("alive", 30))])
def alive(session_id: int, body: Alive | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The lecture's tab is still open (sent about once a minute, also while the video is paused). Keeps the lecture
    from being closed as abandoned and reopens one the idle rule closed. Counts no lecture time."""
    body = body or Alive()
    s = owned_session(db, user, session_id)
    reopened, gap = False, 0.0
    if not s.is_active:
        if not can_reopen(db, s):
            return {"active": False, "reopened": False, "paused_for_s": 0.0}
        gap = max(0.0, (utcnow() - s.ended_at).total_seconds()) if s.ended_at else 0.0  # how long it sat closed
        reopen(db, s)
        reopened = True
    now = utcnow()
    before, s.alive_at = s.alive_at, now
    if body.paused:
        if not s.pause_since:
            # not before the last heartbeat: what came before it was counted then (or a frame or sound ended it)
            since = now - timedelta(seconds=body.paused_for_s)
            s.pause_since = max(since, before) if before else since
    else:
        fold_pause(s)
    db.commit()
    paused_for = max(gap, (now - s.pause_since).total_seconds()) if s.pause_since else gap
    return {"active": True, "reopened": reopened, "paused_for_s": round(paused_for, 1)}


@router.post("/{session_id}/end", response_model=SessionEndOut)
def end_session(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = owned_session(db, user, session_id)
    live.settle(db, user, s, patient=False)  # the board the teacher was still writing on gets its final notes
    voice.fold(db, user, s, finishing=True)   # ...and what the teacher said about the last boards
    fold_pause(s)  # a pause still going on when the student ends is not lecture time
    s.is_active = False
    s.ended_by = "student"
    s.ended_at = s.ended_at or utcnow()
    live.forget(s.id)
    notes = [{"topic": n.topic, "notes_md": (n.ai_notes or "") + (f"\n\nWhat the teacher said:\n{n.spoken_md}" if n.spoken_md else "")}
             for n in s.notes if (n.ai_notes or "").strip()]
    if not notes:
        db.commit()
        return SessionEndOut(session=session_out(s), summary_md="", key_formulas=[], flashcards_created=0, source="none",
                             calibration=_calibration(db, user, s))

    # the revision sheet never fails: past the allowance it's built offline
    result = ai.summarize_session(notes, user.exam_target, offline_only=not usage.can_spend(db, user, "revision_sheet"),
                                  language=user.language)
    s.summary = result["summary_md"]
    if result.get("title") and not s.title_locked and (not s.title or s.title == (s.notes[0].topic if s.notes else None)):
        s.title = result["title"]
    subject = ai.fit_subject(result.get("subject"), user.exam_target)
    if not s.subject and subject and subject != "General":
        s.subject = subject
    for card in result.get("flashcards", []):
        db.add(Flashcard(user_id=user.id, session_id=s.id, front=card["front"], back=card["back"],
                         topic=s.title, subject=s.subject, due_at=utcnow()))
    db.commit()
    usage.charge(db, user, "revision_sheet", result.get("source"))
    return SessionEndOut(session=session_out(s), summary_md=result["summary_md"], key_formulas=result.get("key_formulas", []),
                         flashcards_created=len(result.get("flashcards", [])), source=result.get("source", "ai"),
                         calibration=_calibration(db, user, s))


def _calibration(db: Session, user: User, s) -> dict | None:
    """The lecture's quizzes, sure vs right, with the line to start from (None when nothing was locked in)."""
    cal = calibration.report(db, user.id, session_id=s.id)
    return {**cal, "headline": calibration.headline(cal)} if cal["answers"] else None


@router.post("/{session_id}/pop-quiz", dependencies=[Depends(limit("pop-quiz", 20))])
def pop_quiz(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """One quick MCQ on what the lecture has covered so far (latest boards first), never repeating recent ones."""
    s = owned_session(db, user, session_id)
    notes = [n for n in s.notes if (n.ai_notes or "").strip()][-3:]
    if not notes:
        raise HTTPException(status_code=409, detail="Focs will quiz you once the first board has been captured.")
    material = "\n\n".join(f"## {n.topic or 'Board'}\n{n.ai_notes}" for n in notes)
    topic = notes[-1].topic or s.title or ""
    usage.require(db, user, "pop_quiz")
    q = ai.room_question(s.title or topic, topic, material, user.exam_target, live.recent_questions(s.id), language=user.language)
    if not q:
        raise HTTPException(status_code=503, detail="Couldn't write a question right now — try again in a minute.")
    live.remember_question(s.id, q["question"])
    usage.charge(db, user, "pop_quiz", q.get("source"))
    return {**q, "topic": topic}


@router.get("/{session_id}/export", response_class=PlainTextResponse)
def export_markdown(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = owned_session(db, user, session_id)
    title = s.title or f"Lecture {s.id}"
    parts = [f"# {title}", f"_{s.subject or 'General'} · {s.started_at:%d %b %Y}_" if s.started_at else ""]
    if s.summary:
        parts += ["## Summary", s.summary]
    parts.append("## Board notes")
    for i, n in enumerate(s.notes, 1):
        stamp = f"{n.captured_at:%H:%M}" if n.captured_at else ""
        parts += [f"### {i}. {n.topic or 'Board'}  <small>{stamp}</small>", n.ai_notes or ""]
    md = "\n\n".join(p for p in parts if p)
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in title).strip()[:60] or "focs-notes"
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{safe}.md"'})


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = db.scalar(select(StudySession).options(selectinload(StudySession.notes))
                  .where(StudySession.id == session_id, StudySession.user_id == user.id))
    if not s:
        return
    for n in s.notes:
        storage.delete(n.image_path)
    storage.delete_session(s.id)
    # keep the student's cards, attempts and doubts; just detach them from the deleted lecture
    db.execute(update(Flashcard).where(Flashcard.session_id == s.id).values(session_id=None, note_id=None))
    db.execute(update(QuizAttempt).where(QuizAttempt.session_id == s.id).values(session_id=None))
    db.execute(update(Doubt).where(Doubt.session_id == s.id).values(session_id=None))
    db.execute(delete(LectureSegment).where(LectureSegment.session_id == s.id))  # what the teacher said goes with the lecture
    live.forget(s.id)
    db.delete(s)
    db.commit()
