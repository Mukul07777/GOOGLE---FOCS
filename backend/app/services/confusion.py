"""The return lane: what a room's lecture left unclear, carried back to the teacher.

Every signal is pinned to the board that was on screen when it came: an anonymous "I'm lost" tap, a wrong
answer to a pop quiz, a doubt. The host sees a live meter while teaching and, after, a confusion map: the
boards ranked by how many students they lost. Counts only: no student is ever named.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.note import Note
from app.models.room import LectureSignal
from app.models.session import StudySession

LOST_EVERY_S = 30      # one "I'm lost" per student per half minute
METER_WINDOW_S = 60    # the live meter counts the last minute
TOP_DOUBTS = 8


def room_boards(db: Session, code: str) -> list[Note]:
    """The room's boards in the order they were written (the shared notes of every note taker)."""
    return [n for n in db.scalars(select(Note).join(StudySession, Note.session_id == StudySession.id)
                                  .where(StudySession.room_code == code).order_by(Note.captured_at, Note.id))
            if (n.ai_notes or n.ocr_raw or "").strip()]


def _excerpt(note: Note, size: int = 90) -> str:
    """The board's first real line, without markdown, short enough for a row."""
    for line in (note.ai_notes or note.ocr_raw or "").splitlines():
        text = re.sub(r"[#*_`>$]|^\s*[-+]\s+|^\s*\d+[.)]\s+", "", line).strip()
        if text and text.lower() != (note.topic or "").strip().lower():
            return text if len(text) <= size else text[: size - 1].rstrip() + "…"
    return ""


def board_label(db: Session, code: str, note_id: int | None) -> dict[str, Any] | None:
    if note_id is None:
        return None
    boards = room_boards(db, code)
    for number, note in enumerate(boards, 1):
        if note.id == note_id:
            return {"note_id": note.id, "number": number, "topic": note.topic or f"Board {number}", "excerpt": _excerpt(note)}
    return None


def current_board(code: str) -> dict[str, Any] | None:
    """The board on screen right now: the room's latest one."""
    with SessionLocal() as db:
        boards = room_boards(db, code)
        return board_label(db, code, boards[-1].id) if boards else None


def record(code: str, kind: str, *, user_id: int | None = None, t_s: float | None = None, note_id: int | None = None,
           ref: str | None = None, text: str | None = None, data: dict | None = None) -> None:
    with SessionLocal() as db:
        db.add(LectureSignal(room_code=code, kind=kind, user_id=user_id, t_s=t_s, note_id=note_id, ref=ref,
                             text=(text or None) and text[:1000], data=data))
        db.commit()


def update_doubt(code: str, doubt_id: str, votes: int, resolved: bool) -> None:
    with SessionLocal() as db:
        row = db.scalar(select(LectureSignal).where(LectureSignal.room_code == code, LectureSignal.kind == "doubt",
                                                    LectureSignal.ref == doubt_id))
        if row is not None:
            row.data = {**(row.data or {}), "votes": votes, "resolved": resolved}
            db.commit()


def meter(events: list[tuple[float, dict | None]], now: float) -> dict[str, Any]:
    """The host's live view: taps in the last minute, and the board most of them point at."""
    recent = [board for at, board in events if now - at <= METER_WINDOW_S]
    pinned = Counter(b["note_id"] for b in recent if b)
    board = None
    if pinned:
        note_id, count = pinned.most_common(1)[0]
        board = {**next(b for b in recent if b and b["note_id"] == note_id), "count": count}
    return {"last_minute": len(recent), "total": len(events), "board": board}


def report(db: Session, code: str) -> dict[str, Any]:
    """The confusion map: the boards ranked by how many students they lost, the quizzes, the top doubts."""
    signals = list(db.scalars(select(LectureSignal).where(LectureSignal.room_code == code).order_by(LectureSignal.id)))
    boards = room_boards(db, code)
    number = {n.id: i for i, n in enumerate(boards, 1)}
    by_note = {n.id: n for n in boards}

    rows: dict[int, dict[str, Any]] = {}
    totals = Counter()
    for s in signals:
        if s.kind not in ("lost", "wrong", "doubt"):
            continue
        totals[s.kind] += 1
        if s.note_id in by_note:
            note = by_note[s.note_id]
            row = rows.setdefault(note.id, {"note_id": note.id, "number": number[note.id], "topic": note.topic or f"Board {number[note.id]}",
                                            "excerpt": _excerpt(note), "lost": 0, "wrong": 0, "doubts": 0, "sure_wrong": 0})
            row["lost" if s.kind == "lost" else "wrong" if s.kind == "wrong" else "doubts"] += 1
            if s.kind == "wrong" and (s.data or {}).get("sure"):
                row["sure_wrong"] += 1
    for row in rows.values():
        row["score"] = row["lost"] + row["wrong"] + row["doubts"]
    ranked = sorted(rows.values(), key=lambda r: (-r["score"], -r["sure_wrong"], -r["lost"], r["number"]))

    start = signals[0].created_at if signals else None
    minutes: dict[int, Counter] = {}
    for s in signals:
        if s.kind in ("lost", "wrong", "doubt") and start and s.created_at:
            minutes.setdefault(_minute(start, s.created_at), Counter())[s.kind] += 1
    last = max(minutes, default=-1)
    timeline = [{"minute": m, "lost": minutes.get(m, Counter())["lost"], "wrong": minutes.get(m, Counter())["wrong"],
                 "doubts": minutes.get(m, Counter())["doubt"]} for m in range(last + 1)]

    quizzes = []
    for s in signals:
        if s.kind == "quiz" and s.data:
            d = s.data
            quizzes.append({"question": s.text or "", "options": d.get("options", []), "counts": d.get("counts", []),
                            "answer_index": d.get("answer_index"), "answered": d.get("answered", 0),
                            "correct": d.get("correct", 0), "board": number.get(s.note_id)})
    doubts = sorted(({"text": s.text or "", "votes": (s.data or {}).get("votes", 0), "resolved": bool((s.data or {}).get("resolved")),
                      "board": number.get(s.note_id)} for s in signals if s.kind == "doubt"),
                    key=lambda d: (-d["votes"], d["resolved"]))[:TOP_DOUBTS]
    return {"totals": {"lost": totals["lost"], "wrong": totals["wrong"], "doubts": totals["doubt"],
                       "quizzes": len(quizzes), "boards": len(boards)},
            "boards": ranked, "timeline": timeline, "quizzes": quizzes, "doubts": doubts}


def _minute(start: datetime, at: datetime) -> int:
    return max(0, int((at - start).total_seconds() // 60))
