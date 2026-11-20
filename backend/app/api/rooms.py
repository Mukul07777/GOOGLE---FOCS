"""Study rooms: watch a lecture together (synced YouTube), discuss, ask AI, and answer live pop quizzes.

Realtime state lives in memory (right for one server; move ``RoomHub`` to Redis to scale out).
Only the host controls the video and starts quizzes; everyone chats, asks doubts and answers.
"""
from __future__ import annotations

import asyncio
import json
import secrets
import string
import time
from collections import deque
from dataclasses import dataclass, field

from anyio import from_thread
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api._common import note_out
from app.core.database import SessionLocal
from app.core.deps import STUDENT, get_current_user, get_db, role_of, user_from_token
from app.core.ratelimit import limit
from app.models._util import utcnow
from app.models.doubt import Doubt
from app.models.note import Note
from app.models.quiz_attempt import QuizAttempt
from app.models.room import Room
from app.models.session import StudySession
from app.models.user import User
from app.services import ai, confusion, live, usage, youtube

router = APIRouter(prefix="/rooms", tags=["rooms"])

CODE_ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "0O1IL")


# ------------------------------------------------------------------ realtime state
@dataclass
class Member:
    ws: WebSocket
    user_id: int
    name: str
    status: str = "focusing"


@dataclass
class RoomState:
    host_id: int = 0
    topic: str = ""
    members: list[Member] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    video: dict = field(default_factory=lambda: {"id": None, "title": None, "playing": False, "position": 0.0,
                                                 "updated_at": time.time(), "captions": False, "rate": 1.0})
    quiz: dict | None = None
    recent_questions: list[str] = field(default_factory=list)
    scores: dict[int, dict] = field(default_factory=dict)
    timer: dict = field(default_factory=lambda: {"mode": "focus", "duration": 25 * 60, "running": False,
                                                 "ends_at": None, "remaining": 25 * 60, "by": None, "paused": False})
    code: str = ""
    note_taker: dict | None = None        # {"id", "name"}: the member whose screen feeds the room's board notes
    notes_session_id: int | None = None
    lost: list[tuple[float, dict | None]] = field(default_factory=list)  # (when, board on screen): "I'm lost" taps
    lost_at: dict[int, float] = field(default_factory=dict)              # each student's last tap, for pacing


class RoomHub:
    def __init__(self) -> None:
        self.rooms: dict[str, RoomState] = {}
        self.lock = asyncio.Lock()

    def state(self, code: str) -> RoomState:
        return self.rooms.setdefault(code, RoomState(code=code))

    def count(self, code: str) -> int:
        return len({m.user_id for m in self.rooms.get(code, RoomState()).members})

    async def send(self, ws: WebSocket, msg: dict) -> None:
        await ws.send_text(json.dumps(msg))

    async def broadcast(self, code: str, msg: dict) -> None:
        state = self.rooms.get(code)
        if not state:
            return
        dead = []
        for m in list(state.members):
            try:
                await self.send(m.ws, msg)
            except Exception:
                dead.append(m)
        for m in dead:
            if m in state.members:
                state.members.remove(m)

    async def send_host(self, code: str, msg: dict) -> None:
        """Only to the host's open connections: the confusion meter is for whoever is teaching."""
        state = self.rooms.get(code)
        if not state:
            return
        for m in list(state.members):
            if m.user_id == state.host_id:
                try:
                    await self.send(m.ws, msg)
                except Exception:
                    pass

    def presence(self, code: str) -> dict:
        seen, members = set(), []
        state = self.state(code)
        for m in state.members:
            if m.user_id not in seen:
                seen.add(m.user_id)
                members.append({"id": m.user_id, "name": m.name, "status": m.status, "host": m.user_id == state.host_id})
        return {"type": "presence", "members": members}


hub = RoomHub()


def _video_view(v: dict) -> dict:
    return {**v, "server_now": time.time()}


def _video_position(v: dict) -> float:
    return v["position"] + ((time.time() - v["updated_at"]) * v.get("rate", 1.0) if v["playing"] else 0.0)


RATES = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)


def _find_doubt(state: RoomState, doubt_id: str) -> dict | None:
    return next((m for m in state.history if m.get("id") == doubt_id and m.get("kind") == "doubt"), None)


def _leaderboard(state: RoomState) -> list[dict]:
    rows = [{"user_id": uid, "helped": 0, **s} for uid, s in state.scores.items()]
    return sorted(rows, key=lambda r: (-r["points"], -r["correct"], r["name"]))[:20]


def _score(state: RoomState, uid: int, name: str) -> dict:
    return state.scores.setdefault(uid, {"name": name, "points": 0, "correct": 0, "answered": 0, "helped": 0})


def _quiz_public(q: dict) -> dict:
    return {"id": q["id"], "question": q["question"], "options": q["options"], "deadline": q["deadline"],
            "seconds": q["seconds"], "server_now": time.time(), "answered": len(q["answers"])}


def _timer_view(timer: dict) -> dict:
    view = dict(timer)
    if timer["running"] and timer["ends_at"]:
        view["remaining"] = max(0, round(timer["ends_at"] - time.time()))
    view["server_now"] = time.time()
    return view


def _context(state: RoomState, window: float = 300) -> tuple[str, str]:
    """(caption excerpt around the current video position, recent discussion)."""
    v = state.video
    captions = youtube.caption_window(v["id"], _video_position(v), window) if v["id"] else ""
    board = _board_notes(state.code)
    if board:
        captions = f"Board notes (latest last):\n{board}\n\n{captions}".strip()
    chat = "\n".join(f"{m.get('user', 'AI')}: {m.get('text') or m.get('question', '')}"
                     for m in state.history[-12:] if m.get("type") in ("chat", "ai"))
    return captions, chat


# ------------------------------------------------------------------ REST
class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)  # required: a room is never silently called "Study Room"
    video_url: str = Field(default="", max_length=500)
    topic: str = Field(default="", max_length=120)
    max_members: int = Field(default=20, ge=2, le=100)


    @field_validator("name")
    @classmethod
    def _named(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Give the room a name.")
        return v.strip()


class RoomJoin(BaseModel):
    code: str = Field(min_length=4, max_length=8)


class QuizStart(BaseModel):
    seconds: int = Field(default=30, ge=10, le=120)
    note_id: int | None = None  # a check on one board (from the confusion map) instead of the last few minutes


class Recap(BaseModel):
    note_id: int


class RoomAsk(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    doubt_id: str | None = Field(default=None, max_length=20)


def _room_out(room: Room, user: User) -> dict:
    return {"id": room.id, "code": room.code, "name": room.name, "video_url": room.video_url, "topic": room.topic,
            "is_host": room.host_id == user.id, "max_members": room.max_members,
            "online": hub.count(room.code), "is_active": room.is_active,
            "created_at": room.created_at.isoformat() + "Z" if room.created_at else None}


def _active_room(db: Session, code: str) -> Room:
    room = db.scalar(select(Room).where(Room.code == code.strip().upper(), Room.is_active.is_(True)))
    if not room:
        raise HTTPException(status_code=404, detail="No active room with that code.")
    return room


@router.post("", status_code=201)
def create_room(body: RoomCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if body.video_url and not youtube.video_id(body.video_url):
        raise HTTPException(status_code=422, detail="Paste a YouTube link (youtube.com/watch?v=… or youtu.be/…).")
    for _ in range(20):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if not db.scalar(select(Room).where(Room.code == code)):
            break
    room = Room(code=code, host_id=user.id, name=body.name, video_url=body.video_url, topic=body.topic or None,
                max_members=body.max_members, is_active=True)
    db.add(room)
    db.commit()
    db.refresh(room)
    return _room_out(room, user)


@router.get("")
def my_rooms(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rooms = db.scalars(select(Room).where(Room.host_id == user.id, Room.is_active.is_(True))
                       .order_by(Room.created_at.desc()).limit(20)).all()
    return [_room_out(r, user) for r in rooms]


@router.post("/join")
def join_room(body: RoomJoin, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    room = _active_room(db, body.code)
    if hub.count(room.code) >= (room.max_members or 20) and user.id not in {m.user_id for m in hub.state(room.code).members}:
        raise HTTPException(status_code=409, detail="This room is full.")
    return _room_out(room, user)


@router.post("/{code}/close", status_code=204)
async def close_room(code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    room = db.scalar(select(Room).where(Room.code == code.upper()))
    if not room or room.host_id != user.id:
        raise HTTPException(status_code=403, detail="Only the host can close this room.")
    room.is_active = False
    db.commit()
    await hub.broadcast(room.code, {"type": "closed"})


@router.post("/{code}/quiz", dependencies=[Depends(limit("room-quiz", 10))])
async def pop_quiz(code: str, body: QuizStart, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Host: pause the video for everyone and pop an AI question about what was just taught."""
    room = _active_room(db, code)
    if room.host_id != user.id:
        raise HTTPException(status_code=403, detail="Only the host can start a quiz.")
    state = hub.state(room.code)
    if state.quiz and not state.quiz["revealed"]:
        raise HTTPException(status_code=409, detail="A question is already live.")
    if body.note_id is not None:
        board = await run_in_threadpool(_board, room.code, body.note_id)
        if board is None:
            raise HTTPException(status_code=404, detail="That board isn't in this room.")
        captions = f"Board notes:\n{board['notes']}"
    else:
        board = await run_in_threadpool(confusion.current_board, room.code)
        captions, _ = await run_in_threadpool(_context, state)
    topic = state.topic or room.topic or ""
    # the room's name ("QA room", "Evening group") isn't a topic: guessing from it wrote questions on the wrong subject
    if not (topic.strip() or (state.video.get("title") or "").strip() or captions.strip()):
        raise HTTPException(status_code=422, detail="Set the room's topic first, so the question is about what you're studying.")
    usage.require(db, user, "room_quiz")
    q = await run_in_threadpool(ai.room_question, state.video.get("title") or "", topic,
                                captions, user.exam_target, state.recent_questions)
    if not q:
        raise HTTPException(status_code=503, detail="Couldn't write a question right now — add a topic or a video with captions.")
    v = state.video
    was_playing = bool(v["id"] and v["playing"])
    if was_playing:  # everyone stops to think
        v.update(position=_video_position(v), playing=False, updated_at=time.time())
        await hub.broadcast(room.code, {"type": "video", "video": _video_view(v), "reason": "quiz"})
    quiz = {"id": secrets.token_hex(5), **q, "seconds": body.seconds, "deadline": time.time() + body.seconds,
            "answers": {}, "revealed": False, "was_playing": was_playing,
            "topic": state.topic or v.get("title") or room.name, "note_id": board["note_id"] if board else None}
    state.quiz = quiz
    usage.charge(db, user, "room_quiz", q.get("source"))
    state.recent_questions = (state.recent_questions + [q["question"]])[-10:]
    await hub.broadcast(room.code, {"type": "quiz", "quiz": _quiz_public(quiz)})
    asyncio.create_task(_reveal_later(room.code, quiz["id"], body.seconds))
    return {"id": quiz["id"], "source": q["source"]}


async def _reveal_later(code: str, quiz_id: str, seconds: int) -> None:
    await asyncio.sleep(seconds)
    await _reveal(code, quiz_id)


async def _reveal(code: str, quiz_id: str) -> None:
    state = hub.rooms.get(code)
    q = state.quiz if state else None
    if not q or q["id"] != quiz_id or q["revealed"]:
        return
    q["revealed"] = True
    counts = [0, 0, 0, 0]
    right = []
    for uid, a in q["answers"].items():
        counts[a["choice"]] += 1
        s = state.scores.setdefault(uid, {"name": a["name"], "points": 0, "correct": 0, "answered": 0})
        s["answered"] += 1
        if a["choice"] == q["answer_index"]:
            # 10 for a correct answer + up to 5 for answering fast
            s["points"] += 10 + round(5 * max(0.0, (q["deadline"] - a["at"]) / q["seconds"]))
            s["correct"] += 1
            right.append(a["name"])
    await hub.broadcast(code, {"type": "quiz_result", "result": {
        "id": q["id"], "answer_index": q["answer_index"], "explanation": q["explanation"], "counts": counts,
        "correct_names": right, "answered": len(q["answers"]), "leaderboard": _leaderboard(state)}})
    await run_in_threadpool(_save_attempts, q, code)
    if q["was_playing"]:
        await asyncio.sleep(6)  # time to read the explanation, then the lecture continues
        v = state.video
        if not v["playing"] and state.quiz is q:
            v.update(playing=True, updated_at=time.time())
            await hub.broadcast(code, {"type": "video", "video": _video_view(v), "reason": "resume"})


def _save_attempts(q: dict, code: str = "") -> None:
    """Room answers count towards each student's stats and redo queue; for the host's confusion map, every wrong
    answer is pinned to the board the question was about, and the question's results are kept."""
    counts = [0, 0, 0, 0]
    with SessionLocal() as db:
        for uid, a in q["answers"].items():
            ok = a["choice"] == q["answer_index"]
            counts[a["choice"]] += 1
            db.add(QuizAttempt(user_id=uid, topic=str(q.get("topic") or "")[:120], question=q["question"],
                               q_type="room", correct=ok, score=10 if ok else 0, needs_redo=not ok, confidence=a.get("confidence")))
        db.commit()
    if not code:
        return
    for uid, a in q["answers"].items():
        if a["choice"] != q["answer_index"]:
            confusion.record(code, "wrong", user_id=uid, note_id=q.get("note_id"), ref=q["id"],
                             data={"sure": a.get("confidence") == "sure"})
    confusion.record(code, "quiz", note_id=q.get("note_id"), ref=q["id"], text=q["question"],
                     data={"options": q["options"], "counts": counts, "answer_index": q["answer_index"],
                           "answered": len(q["answers"]), "correct": counts[q["answer_index"]] if 0 <= q["answer_index"] < 4 else 0})


@router.post("/{code}/ask", dependencies=[Depends(limit("room-ask", 20))])
async def ask_ai(code: str, body: RoomAsk, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Anyone: ask the AI; the answer is shared with the whole room."""
    room = _active_room(db, code)
    state = hub.state(room.code)
    usage.require(db, user, "room_ask")
    captions, chat = await run_in_threadpool(_context, state, 420)
    v = state.video
    context = f"Group study room watching: {v.get('title') or room.name}\nTopic: {state.topic or 'not set'}\n"
    if captions:
        context += f"What the teacher said in the last few minutes:\n{captions}\n"
    if chat:
        context += f"\nRecent discussion in the room:\n{chat}"
    result = await run_in_threadpool(ai.companion, body.question, context, [], user.exam_target, "explain", user.language)
    msg = {"type": "ai", "id": secrets.token_hex(6), "question": body.question, "user": user.full_name,
           "user_id": user.id, "answer": result["answer"], "source": result["source"], "at": time.time(),
           "doubt_id": body.doubt_id}
    doubt = _find_doubt(state, body.doubt_id) if body.doubt_id else None
    if doubt is not None:
        doubt["ai_answer_id"] = msg["id"]
        await hub.broadcast(room.code, {"type": "doubt", "doubt": doubt})
    state.history.append(msg)
    state.history = state.history[-120:]
    db.add(Doubt(user_id=user.id, question=body.question, answer=result["answer"]))
    db.commit()
    usage.charge(db, user, "room_ask", result["source"])
    await hub.broadcast(room.code, msg)
    return {"ok": True}


# ------------------------------------------------------------------ shared board notes
# One member shares the room tab; Focs reads the board off the video and everyone gets the notes live.
# Each note taker's notes live in their own session (tagged with the room code), so they also land in
# their library; everyone else can save a copy to theirs.
class NotesStart(BaseModel):
    take_over: bool = False


def _room_notes(db: Session, code: str) -> list[Note]:
    return list(db.scalars(select(Note).join(StudySession, Note.session_id == StudySession.id)
                           .where(StudySession.room_code == code).order_by(Note.captured_at)))


def _board_notes(code: str | None, last: int = 3) -> str:
    if not code:
        return ""
    with SessionLocal() as db:
        notes = [n for n in _room_notes(db, code) if (n.ai_notes or "").strip()][-last:]
    return "\n\n".join(f"## {n.topic or 'Board'}\n{n.ai_notes}" for n in notes)[-3000:]


@router.post("/{code}/notes/start")
async def start_room_notes(code: str, body: NotesStart | None = None, db: Session = Depends(get_db),
                           user: User = Depends(get_current_user)):
    room = _active_room(db, code)
    state = hub.state(room.code)
    taker = state.note_taker
    online = {m.user_id for m in state.members}
    take_over = bool(body and body.take_over and room.host_id == user.id)
    if taker and taker["id"] != user.id and taker["id"] in online and not take_over:
        raise HTTPException(status_code=409, detail=f"{taker['name']} is already taking notes for the room.")
    session = db.scalar(select(StudySession).where(StudySession.user_id == user.id, StudySession.room_code == room.code)
                        .order_by(StudySession.started_at.desc()))
    if session is None:
        # not "active": a room session must never show up as the student's own live lecture
        session = StudySession(user_id=user.id, source="room", room_code=room.code, is_active=False,
                               title=state.topic or room.name)
        db.add(session)
        db.commit()
        db.refresh(session)
    state.note_taker = {"id": user.id, "name": user.full_name}
    state.notes_session_id = room.notes_session_id = session.id
    db.commit()
    await hub.broadcast(room.code, {"type": "note_taker", "note_taker": state.note_taker})
    return {"session_id": session.id}


@router.post("/{code}/notes/stop", status_code=204)
async def stop_room_notes(code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    room = _active_room(db, code)
    state = hub.state(room.code)
    if state.note_taker and (state.note_taker["id"] == user.id or room.host_id == user.id):
        session = db.get(StudySession, state.notes_session_id) if state.notes_session_id else None
        if session is not None:
            taker = db.get(User, session.user_id)
            if taker is not None:  # the board still being written gets its final notes, for everyone
                done = await run_in_threadpool(live.settle, db, taker, session, False)
                if done.get("also_updated") is not None:  # a board the lecture had moved on from, written up now too
                    note = note_out(done["also_updated"]).model_dump(mode="json")
                    await hub.broadcast(room.code, {"type": "note", "status": done.get("also_status", "updated"), "note": note,
                                                    "by": taker.full_name})
                if done.get("note") is not None:
                    note = note_out(done["note"]).model_dump(mode="json")
                    await hub.broadcast(room.code, {"type": "note", "status": done["status"], "note": note, "by": taker.full_name})
            session.ended_at = utcnow()
            db.commit()
        state.note_taker = None
        await hub.broadcast(room.code, {"type": "note_taker", "note_taker": None})


@router.get("/{code}/notes")
def list_room_notes(code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    room = _active_room(db, code)
    return [note_out(n).model_dump(mode="json") for n in _room_notes(db, room.code)]


@router.post("/{code}/notes/save", status_code=201)
def save_room_notes(code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Copy the room's board notes into the student's own library: also once the host has closed the room, which is
    when everyone is offered it."""
    room = db.scalar(select(Room).where(Room.code == code.strip().upper()))
    if not room:
        raise HTTPException(status_code=404, detail="No room with that code.")
    notes = [n for n in _room_notes(db, room.code) if (n.ai_notes or "").strip()]
    if not notes:
        raise HTTPException(status_code=409, detail="No board notes in this room yet.")
    title = (hub.state(room.code).topic if room.is_active else None) or room.topic or room.name
    copy = StudySession(user_id=user.id, source="room-copy", is_active=False, title=f"{title} (room notes)",
                        subject=next((n.subject for n in notes if n.subject), None),
                        started_at=notes[0].captured_at, ended_at=notes[-1].captured_at)
    db.add(copy)
    db.flush()
    for n in notes:  # text only: snapshots stay with the note taker's copy
        db.add(Note(session_id=copy.id, ocr_raw=n.ocr_raw, ai_notes=n.ai_notes, topic=n.topic, subject=n.subject,
                    captured_at=n.captured_at, engine=n.engine, ocr_confidence=n.ocr_confidence))
    db.commit()
    return {"session_id": copy.id, "notes": len(notes)}


# ------------------------------------------------------------------ the return lane: confusion back to the teacher
def _board(code: str, note_id: int) -> dict | None:
    """One of the room's boards: its label and its notes."""
    with SessionLocal() as db:
        label = confusion.board_label(db, code, note_id)
        note = db.get(Note, note_id) if label else None
        return {**label, "notes": (note.ai_notes or note.ocr_raw or "")[:3000]} if note else None


def _host_room(db: Session, code: str, user: User) -> Room:
    room = db.scalar(select(Room).where(Room.code == code.strip().upper()))
    if not room or room.host_id != user.id:
        raise HTTPException(status_code=404, detail="Only the room's host can see this.")
    return room


@router.get("/{code}/report")
def confusion_report(code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The host's confusion map: which boards lost the room, from "I'm lost" taps, wrong answers and doubts.
    Open or closed rooms alike; counts only, never names."""
    room = _host_room(db, code, user)
    live_state = hub.rooms.get(room.code)
    return {"code": room.code, "name": room.name, "topic": room.topic, "is_active": bool(room.is_active),
            "live": confusion.meter(live_state.lost, time.time()) if live_state else None,
            **confusion.report(db, room.code)}


@router.post("/{code}/recap", dependencies=[Depends(limit("room-ask", 20))])
async def recap(code: str, body: Recap, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Host, from the confusion map: explain one board again, simply, for the whole room."""
    room = _active_room(db, code)
    if room.host_id != user.id:
        raise HTTPException(status_code=403, detail="Only the host can send a recap.")
    board = await run_in_threadpool(_board, room.code, body.note_id)
    if board is None:
        raise HTTPException(status_code=404, detail="That board isn't in this room.")
    usage.require(db, user, "room_ask")
    question = f"Many of us got lost at board {board['number']} ({board['topic']}). Explain it again, simply, step by step."
    result = await run_in_threadpool(ai.companion, question, f"The board:\n{board['notes']}", [], user.exam_target, "simple", user.language)
    msg = {"type": "ai", "id": secrets.token_hex(6), "question": f"Recap of board {board['number']}: {board['topic']}",
           "user": user.full_name, "user_id": user.id, "answer": result["answer"], "source": result["source"], "at": time.time(),
           "recap": True}
    state = hub.state(room.code)
    state.history = (state.history + [msg])[-120:]
    usage.charge(db, user, "room_ask", result["source"])
    await hub.broadcast(room.code, msg)
    return {"ok": True}


async def _lost(code: str, state: RoomState, uid: int, ws: WebSocket) -> None:
    """A student's anonymous "I'm lost": pinned to the board on screen, counted on the host's meter."""
    now = time.time()
    wait = confusion.LOST_EVERY_S - (now - state.lost_at.get(uid, 0.0))
    if wait > 0:
        await hub.send(ws, {"type": "lost_ack", "ok": False, "wait": int(wait) + 1})
        return
    state.lost_at[uid] = now
    board = await run_in_threadpool(confusion.current_board, code)
    t_s = round(_video_position(state.video)) if state.video["id"] else None
    state.lost.append((now, board))
    state.lost = state.lost[-500:]
    await run_in_threadpool(lambda: confusion.record(code, "lost", user_id=uid, t_s=t_s, note_id=board["note_id"] if board else None))
    await hub.send(ws, {"type": "lost_ack", "ok": True, "wait": confusion.LOST_EVERY_S, "board": board})
    await hub.send_host(code, {"type": "confusion", "meter": confusion.meter(state.lost, now)})


def broadcast_note(code: str, payload: dict) -> None:
    """Called from the (threaded) capture endpoint when a room's board notes change."""
    try:
        from_thread.run(hub.broadcast, code, {"type": "note", **payload})
    except Exception:  # never let a broadcast failure break the capture itself
        pass


# ------------------------------------------------------------------ WebSocket
async def _refuse(ws: WebSocket, code: int, reason: str) -> None:
    """Close an accepted socket with a reason. (Closing before accepting turns into a bare HTTP 403, which browsers
    report as a dropped connection (1006), and the client would keep reconnecting forever.)"""
    await ws.close(code=code, reason=reason)


async def _first_message_token(ws: WebSocket) -> str | None:
    """The sign-in token, sent as the first message ({"type": "auth", "token": ...}) so that it never sits in a URL,
    where server and proxy logs would keep it. None when the client left before sending it."""
    try:
        first = json.loads(await asyncio.wait_for(ws.receive_text(), timeout=AUTH_WAIT_S))
    except WebSocketDisconnect:
        return None
    except (asyncio.TimeoutError, ValueError):
        return ""
    return str(first.get("token") or "") if isinstance(first, dict) and first.get("type") == "auth" else ""


AUTH_WAIT_S = 15
# Per connection, at most this many messages in FLOOD_WINDOW_S; the rest are dropped. A member's normal traffic (chat,
# votes, the host's video sync every few seconds, a ping every 25 s) is far below it; a script spamming a room is not.
FLOOD_MESSAGES, FLOOD_WINDOW_S = 40, 10.0


@router.websocket("/ws/{code}")
async def room_socket(ws: WebSocket, code: str, token: str = ""):
    code = code.upper()
    await ws.accept()
    if not token:  # current clients send it as the first message; older ones (until they reload) in the URL
        token = await _first_message_token(ws)
        if token is None:
            return
    with SessionLocal() as db:
        user = user_from_token(token, db)
        room = db.scalar(select(Room).where(Room.code == code, Room.is_active.is_(True)))
        name = user.full_name if user else ""
        uid = user.id if user else 0
        max_members = (room.max_members or 20) if room else 0
        host_id, room_topic, room_video = (room.host_id, room.topic, room.video_url) if room else (0, None, None)
    if not user:
        return await _refuse(ws, 4401, "Sign in again")
    if role_of(user) != STUDENT:  # study rooms are a student area (app/api/__init__.py); a socket has no router check
        return await _refuse(ws, 4403, "Study rooms are for student accounts")
    if not room:
        return await _refuse(ws, 4404, "This room was closed or never existed")
    state = hub.state(code)
    if hub.count(code) >= max_members and uid not in {m.user_id for m in state.members}:
        return await _refuse(ws, 4409, "Room is full")

    if not state.host_id:  # first connection after a server start: restore persisted room settings
        state.host_id, state.topic = host_id, room_topic or ""
        vid = youtube.video_id(room_video or "")
        if vid and not state.video["id"]:
            state.video.update(id=vid, title=await asyncio.to_thread(youtube.title, vid), playing=False, position=0.0,
                               updated_at=time.time(), captions=await asyncio.to_thread(youtube.has_captions, vid))
    member = Member(ws=ws, user_id=uid, name=name)
    async with hub.lock:
        state.members.append(member)
    my_answer = state.quiz["answers"].get(uid, {}).get("choice") if state.quiz else None
    await hub.send(ws, {
        "type": "welcome", "you": {"id": uid, "name": name, "host": uid == state.host_id},
        "history": state.history[-60:], "timer": _timer_view(state.timer), "video": _video_view(state.video),
        "topic": state.topic, "leaderboard": _leaderboard(state),
        "quiz": _quiz_public(state.quiz) if state.quiz and not state.quiz["revealed"] else None, "my_answer": my_answer,
        "note_taker": state.note_taker,
        "confusion": confusion.meter(state.lost, time.time()) if uid == state.host_id else None,
    })
    await hub.broadcast(code, hub.presence(code))
    await hub.broadcast(code, {"type": "system", "text": f"{name} joined", "at": time.time()})

    recent: deque[float] = deque()
    try:
        while True:
            raw = await ws.receive_text()
            now = time.monotonic()
            while recent and now - recent[0] > FLOOD_WINDOW_S:
                recent.popleft()
            if len(recent) >= FLOOD_MESSAGES:
                continue
            recent.append(now)
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict):
                continue
            kind = msg.get("type")
            is_host = uid == state.host_id
            if kind == "chat":
                text = str(msg.get("text", "")).strip()[:1000]
                if not text:
                    continue
                out = {"type": "chat", "id": secrets.token_hex(6), "user": name, "user_id": uid, "text": text,
                       "kind": "doubt" if msg.get("kind") == "doubt" else "message", "at": time.time()}
                if out["kind"] == "doubt":
                    out.update(votes=[], replies=[], resolved=False,
                               video_at=round(_video_position(state.video)) if state.video["id"] else None)
                    board = await run_in_threadpool(confusion.current_board, code)
                    await run_in_threadpool(lambda: confusion.record(
                        code, "doubt", user_id=uid, t_s=out["video_at"], note_id=board["note_id"] if board else None,
                        ref=out["id"], text=text, data={"votes": 0, "resolved": False}))
                state.history.append(out)
                state.history = state.history[-120:]
                await hub.broadcast(code, out)
            elif kind in ("vote", "reply", "resolve", "accept"):
                doubt = _find_doubt(state, str(msg.get("id", "")))
                if doubt is None:
                    continue
                owner_or_host = uid == doubt["user_id"] or is_host
                if kind == "vote":  # "me too": the most-wanted doubts rise to the top
                    doubt["votes"] = [v for v in doubt["votes"] if v != uid] if uid in doubt["votes"] else doubt["votes"] + [uid]
                elif kind == "reply":
                    text = str(msg.get("text", "")).strip()[:800]
                    if not text or len(doubt["replies"]) >= 30:
                        continue
                    doubt["replies"].append({"id": secrets.token_hex(5), "user": name, "user_id": uid, "text": text,
                                             "at": time.time(), "accepted": False})
                elif kind == "resolve" and owner_or_host:
                    doubt["resolved"] = not doubt["resolved"]
                elif kind == "accept" and owner_or_host:
                    reply = next((r for r in doubt["replies"] if r["id"] == msg.get("reply_id")), None)
                    if reply is None or reply["accepted"]:
                        continue
                    reply["accepted"], doubt["resolved"] = True, True
                    if reply["user_id"] != doubt["user_id"]:  # helping someone else earns points
                        s = _score(state, reply["user_id"], reply["user"])
                        s["points"] += 5
                        s["helped"] = s.get("helped", 0) + 1
                        await hub.broadcast(code, {"type": "leaderboard", "leaderboard": _leaderboard(state)})
                else:
                    continue
                if kind in ("vote", "resolve", "accept"):
                    await run_in_threadpool(confusion.update_doubt, code, doubt["id"], len(doubt["votes"]), doubt["resolved"])
                await hub.broadcast(code, {"type": "doubt", "doubt": doubt})
            elif kind == "answer" and state.quiz and not state.quiz["revealed"]:
                q = state.quiz
                choice = msg.get("choice")
                if msg.get("quiz_id") == q["id"] and isinstance(choice, int) and 0 <= choice < 4 \
                        and uid not in q["answers"] and time.time() <= q["deadline"] + 1:
                    sure = msg.get("confidence")
                    q["answers"][uid] = {"choice": choice, "at": time.time(), "name": name,
                                         "confidence": sure if sure in ("sure", "unsure") else None}
                    await hub.broadcast(code, {"type": "quiz_progress", "id": q["id"], "answered": len(q["answers"])})
                    if len(q["answers"]) >= hub.count(code):  # everyone answered: no need to wait
                        asyncio.create_task(_reveal(code, q["id"]))
            elif kind == "video" and is_host:
                v = state.video
                action = msg.get("action")
                if action == "load":
                    vid = youtube.video_id(str(msg.get("url", "")))
                    if not vid:
                        await hub.send(ws, {"type": "error", "text": "That doesn't look like a YouTube link."})
                        continue
                    title = await asyncio.to_thread(youtube.title, vid)
                    v.update(id=vid, title=title, playing=False, position=0.0, updated_at=time.time(),
                             captions=await asyncio.to_thread(youtube.has_captions, vid))
                    await run_in_threadpool(_persist_room, code, f"https://www.youtube.com/watch?v={vid}", None)
                elif action in ("play", "pause", "seek", "sync", "rate") and v["id"]:
                    try:
                        position = max(0.0, float(msg.get("position", _video_position(v))))
                        rate = float(msg.get("rate", v.get("rate", 1.0)))
                    except (TypeError, ValueError):
                        continue
                    rate = rate if rate in RATES else v.get("rate", 1.0)
                    playing = {"play": True, "pause": False}.get(action, bool(msg.get("playing", v["playing"])))
                    if action == "sync" and abs(position - _video_position(v)) < 0.75 and playing == v["playing"] \
                            and rate == v.get("rate", 1.0):
                        continue  # a heartbeat with nothing new: no need to wake everyone up
                    v.update(position=position, playing=playing, updated_at=time.time(), rate=rate)
                else:
                    continue
                await hub.broadcast(code, {"type": "video", "video": _video_view(v), "reason": action})
            elif kind == "topic" and is_host:
                state.topic = str(msg.get("topic", "")).strip()[:120]
                await run_in_threadpool(_persist_room, code, None, state.topic)
                await hub.broadcast(code, {"type": "topic", "topic": state.topic})
            elif kind == "reaction":
                emoji = str(msg.get("emoji", ""))[:8]
                if emoji:
                    await hub.broadcast(code, {"type": "reaction", "user": name, "emoji": emoji})
            elif kind == "status":
                member.status = str(msg.get("status", "focusing"))[:20]
                await hub.broadcast(code, hub.presence(code))
            elif kind == "timer":
                t = state.timer
                action = msg.get("action")
                if action == "start":
                    if msg.get("minutes"):
                        t["duration"] = t["remaining"] = int(max(1, min(120, float(msg["minutes"]))) * 60)
                        t["mode"] = msg.get("mode", "focus") if msg.get("mode") in ("focus", "break") else "focus"
                    t["running"], t["paused"], t["ends_at"] = True, False, time.time() + t["remaining"]
                elif action == "pause" and t["running"]:
                    t["remaining"], t["running"], t["ends_at"] = max(0, int(t["ends_at"] - time.time())), False, None
                    t["paused"] = True  # explicit: a pause right after starting still reads as "paused"
                elif action == "reset":
                    t["running"], t["ends_at"], t["remaining"] = False, None, t["duration"]
                    t["paused"] = False
                t["by"] = name
                await hub.broadcast(code, {"type": "timer", "timer": _timer_view(t)})
            elif kind == "lost" and not is_host:
                await _lost(code, state, uid, ws)
            elif kind == "ping":
                await hub.send(ws, {"type": "pong", "server_now": time.time()})
    except WebSocketDisconnect:
        pass
    finally:
        async with hub.lock:
            if member in state.members:
                state.members.remove(member)
        if state.note_taker and state.note_taker["id"] == uid and uid not in {m.user_id for m in state.members}:
            state.note_taker = None  # the note taker left: their capture has stopped
            await hub.broadcast(code, {"type": "note_taker", "note_taker": None})
        await hub.broadcast(code, hub.presence(code))
        await hub.broadcast(code, {"type": "system", "text": f"{name} left", "at": time.time()})


def _persist_room(code: str, video_url: str | None, topic: str | None) -> None:
    with SessionLocal() as db:
        room = db.scalar(select(Room).where(Room.code == code))
        if not room:
            return
        if video_url is not None:
            room.video_url = video_url
        if topic is not None:
            room.topic = topic or None
        db.commit()
