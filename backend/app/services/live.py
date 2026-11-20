"""Live lecture pipeline: frame → which board → (once the board is done) OCR → notes → (checkpoint).

A board is written up once, when the lecture moves on from it, rather than when it first appears: measured on real
PW lectures (2026-10-20), most boards are written over minutes, and notes for a board's first lines were paid for
again at every refresh. So a board gets its notes when the next board appears, when it has been still for
BOARD_SETTLE_S (the browser asks), when the student ends the lecture or presses Capture now, and, while the teacher
is still writing on it, BOARD_REFRESH_S after it appeared and again every BOARD_REFRESH_S while it grows, so a long
derivation is never a long wait. Which board a frame shows is decided from its strokes (ocr/ink.py), not its OCR
text, which on handwriting is junk; the OCR runs only for a write-up.

Those write-ups run in the background (LIVE_WRITE_BEHIND) while the lecture goes on, and their notes come back with a
later frame: a frame request that waited for the AI kept the browser from sending the next frame, so the board read
got 8 s per model, and the cheap Gemini models, often slow or overloaded, lost most boards to one that costs twice as
much. In the background a read can wait for them. The first board, Capture now and the end of a lecture are written
while the student waits.

Per-session state lives in memory. It only exists to avoid redundant work, so losing it on
restart is harmless — the next frame simply starts a fresh board.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models._util import utcnow
from app.models.note import Note
from app.models.session import StudySession
from app.models.user import User
from app.services import ai, ledger, shared_notes, storage, translate, usage, vision
from app.services.ocr import decode_image, hamming, ocr_engine, phash
from app.services.ocr.ink import Ink, ink_map, match, new_writing, same_board as same_strokes
from app.services.text_utils import clean_ocr, same_board, similarity, topics_differ

log = logging.getLogger("focs.live")

# Fitted on three recorded lectures (PW physics and maths on a pen tablet, a Hindi NEET zoology board; 2026-10-20):
NEW_WRITING = 0.15   # share of a board's writing added since its notes that is worth writing them again
MIN_INK = 20         # grid cells with writing below which a frame is a blank board (or between two slides)
KEEP_BOARDS = 8      # earlier boards remembered, for a teacher who goes back to one (about 150 KB each)
FRAME_SIDE = 1600    # a held frame is kept as a JPEG this size (what the browser sends)
LECTURE_GAP_S = 60   # lecture time counted for a gap between two frames at most (the student paused, or left the tab)


@dataclass(eq=False)  # one board is one object (and its fields are arrays)
class _Board:
    """One board as the lecture shows it: the frame its notes are written from (the fullest view since the last
    write-up: the teacher standing in front hides part of it), the latest frame's writing, which the next frame is
    compared with, and what was written up from it."""
    jpeg: bytes | None  # the frame to write up (as a JPEG: a frame as pixels is 2.7 MB); None once that's done
    ink: Ink            # its strokes
    frame_hash: int
    latest: Ink
    first_at: float
    note_id: int | None = None
    topic: str | None = None
    written: Ink | None = None  # the strokes when its notes were last written
    written_at: float | None = None
    not_board: bool = False  # the AI said it isn't lecture content (the teacher's camera, a title card)
    left_at: float | None = None  # when the lecture moved on from it, while its notes wait (see _due)

    def see(self, img: np.ndarray, ink: Ink, frame_hash: int, take: bool = False) -> None:
        """A frame of this board. ``take``: write up this one (the student pressed Capture now)."""
        self.latest = ink
        if take or self.jpeg is None or ink.amount >= 0.9 * self.ink.amount:
            self.jpeg, self.ink, self.frame_hash = storage.jpeg(img, FRAME_SIDE), ink, frame_hash

    def unwritten(self) -> bool:
        if self.not_board or self.jpeg is None:
            return False
        return self.written is None or new_writing(self.written, self.ink) >= NEW_WRITING


@dataclass
class _State:
    last_hash: int | None = None
    board: _Board | None = None
    # A view that is none of the known boards becomes the board once a second frame shows it too, or the screen stays
    # on it until the browser's settle ping. The teacher walking up to the camera (a PW lecture does it every few
    # minutes, for half a minute) changes with every gesture, so it never does: the board behind isn't finished early
    # and the close-up costs nothing.
    candidate: _Board | None = None
    boards: list[_Board] = field(default_factory=list)  # earlier boards of the lecture, the latest last
    last_topic: str | None = None
    last_note_id: int | None = None  # the latest board's note (the voice lane files what was said under it)
    last_notes_md: str = ""
    # what the AI recently said is not a board (the teacher's camera, a title card): seen again, it costs nothing
    not_boards: list[str] = field(default_factory=list)
    recent_questions: list[str] = field(default_factory=list)
    seen_at: float | None = None   # monotonic time of the last frame or settle ping: the lecture time between counts
    jobs: list[Future] = field(default_factory=list)  # write-ups running in the background
    finished: list[dict] = field(default_factory=list)  # their results, reported with the next frame or settle ping
    audio_chunks: int = 0          # lecture sound pieces transcribed (the voice lane charges every few)
    voice_retry_at: float = 0.0    # after a failed spoken write-up, not before this monotonic time
    clips: list[tuple[float, float]] = field(default_factory=list)  # lecture-by-link stretches written up (seconds)
    lock: threading.Lock = field(default_factory=threading.Lock)


_states: dict[int, _State] = {}
_states_guard = threading.Lock()


def _state(session_id: int) -> _State:
    with _states_guard:
        return _states.setdefault(session_id, _State())


def recent_questions(session_id: int) -> list[str]:
    return list(_state(session_id).recent_questions)


def remember_question(session_id: int, question: str) -> None:
    st = _state(session_id)
    st.recent_questions = (st.recent_questions + [question])[-10:]


def idle_seconds(session_id: int) -> float | None:
    """Seconds since this server last saw a frame or settle ping for the lecture; None if it never has (or has
    restarted since)."""
    with _states_guard:
        st = _states.get(session_id)
    return None if st is None or st.seen_at is None else time.monotonic() - st.seen_at


def forget(session_id: int) -> None:
    with _states_guard:
        _states.pop(session_id, None)


def _live_engine(engine: str | None) -> str | None:
    """The OCR for a live frame. While a vision model reads each board for its notes, the OCR text is only the
    fallback and the key for notes shared between students, and FocsOCR alone does that for a third of the CPU,
    which on a laptop playing the lecture is the difference between a smooth video and a stutter at every board."""
    if engine is None and vision.available() and ocr_engine.resolve_mode(None) == "auto":
        return "focs"
    return engine


def _write_notes(db: Session, user: User, text: str, prev_topic: str | None, patient: bool = True,
                 img: np.ndarray | None = None, ocr_used: str | None = None) -> tuple[dict, bool]:
    """Notes for a board: shared ones another student's capture already paid for, else AI (or basic notes once
    the allowance is used up). Returns the notes and whether they are full AI-quality notes.

    With the frame and a vision model, the AI notes are written from the board read off the image (kept as
    ``notes["board"]``): line-by-line OCR splits a fraction over two lines and drops the sign between two
    fractions, and the notes would then answer a different question. When the vision model finds nothing academic
    on the frame, that is the answer: no notes call. When the vision models are all busy and the frame was read by
    FocsOCR alone (``ocr_used``), it is read again by the full ensemble first: the notes then rest on the best OCR
    there is (kept as ``notes["ocr_text"]``)."""
    shared = shared_notes.lookup(db, text, user.exam_target)
    if shared is not None:
        return _in_language(db, user, text, shared), True
    # past the day's lecture hours (or the fair-use ceiling): basic notes, never a stopped lecture
    ai_ok = usage.can_spend(db, user, "board_note") and usage.lecture_time_left(user)
    board = vision.read_board(storage.jpeg(img), patient=patient) if ai_ok and img is not None else None
    if board == "":
        return {"is_lecture": False, "source": "vision"}, ai_ok
    notes_text = text
    if board is None and img is not None and ocr_used == "focs" and ocr_engine.resolve_mode(None) == "auto":
        fuller = clean_ocr(ocr_engine.run(img, "auto").text)
        if len(fuller) >= settings.OCR_MIN_CHARS:
            notes_text = fuller
    notes = ai.generate_notes(notes_text, user.exam_target, prev_topic, offline_only=not ai_ok, patient=patient, board=board)
    if notes_text is not text:
        notes["ocr_text"] = notes_text
    if board and notes.get("source") == "ai":
        notes["board"] = board
    shared_notes.store(db, text, user.exam_target, notes)
    return _in_language(db, user, text, notes), ai_ok


def _in_language(db: Session, user: User, text: str, notes: dict) -> dict:
    """The board's notes in the student's language. They are written (and shared) in English; each translation is
    made once and kept with the shared notes. When it can't be made, the English with a notice."""
    lang = user.language
    if not translate.wanted(lang) or not notes.get("is_lecture"):
        return notes
    md = shared_notes.translation(db, text, user.exam_target, lang) if notes.get("source") in ("ai", "shared") else None
    if md is None:
        if notes.get("source") not in ("ai", "shared") or not usage.can_spend(db, user, "board_note"):
            return {**notes, "language_note": translate.notice(lang)}
        md, ok = translate.translate(notes["notes_md"], lang, user.exam_target, "lecture notes")
        if not ok:
            return {**notes, "language_note": translate.notice(lang)}
        shared_notes.keep_translation(db, text, user.exam_target, lang, md)
    return {**notes, "notes_md": md, "language": lang}


def _reading(notes: dict, text: str) -> str:
    """What the note keeps as the board's text: the vision reading, else the fullest OCR."""
    return notes.get("board") or notes.get("ocr_text") or text


def _rewrite(note: Note, notes: dict, text: str, image_path: str, frame_hash: int,
             confidence: float | None, engine: str | None) -> None:
    storage.delete(note.image_path)
    note.ocr_raw, note.ai_notes, note.image_path, note.language = _reading(notes, text), ai.tidy_math(notes["notes_md"]), image_path, notes.get("language")
    note.topic, note.subject = notes["topic"], notes["subject"]
    note.ocr_confidence, note.engine, note.board_hash = confidence, engine, f"{frame_hash:016x}"
    note.updated_at = utcnow()


def _add_note(db: Session, session: StudySession, notes: dict, text: str, image_path: str, frame_hash: int,
              confidence: float | None, engine: str | None) -> Note:
    note = Note(session_id=session.id, ocr_raw=_reading(notes, text), ai_notes=ai.tidy_math(notes["notes_md"]), board_hash=f"{frame_hash:016x}", language=notes.get("language"),
                topic=notes["topic"], subject=notes["subject"], ocr_confidence=confidence, engine=engine, image_path=image_path)
    db.add(note)
    if not session.subject and notes.get("subject") not in (None, "", "General"):
        session.subject = notes["subject"]
    if not session.title:
        session.title = notes["topic"]
    return note


@dataclass
class _Job:
    """What a write-up needs, taken from the board under the session lock, so the AI part can run without it."""
    img: np.ndarray
    ink: Ink
    noted: Ink | None  # the strokes the board's note was written from, if it has one
    frame_hash: int
    topic: str | None
    not_boards: list[str]
    force: bool


def _snapshot(st: _State, board: _Board, force: bool = False) -> _Job:
    """Take what this write-up will use, and mark the board written (it is, as far as the next frame is concerned)."""
    job = _Job(decode_image(board.jpeg), board.ink, board.written, board.frame_hash, board.topic or st.last_topic,
               list(st.not_boards), force)
    board.written, board.written_at = board.ink, time.monotonic()
    if board is not st.board:  # a board the lecture has left: its frame is not needed again
        board.jpeg = None
    return job


def _compose(db: Session, user: User, job: _Job, patient: bool, engine: str | None) -> dict:
    """The AI part of a write-up: OCR, the board read and the notes. Needs no session lock."""
    ocr = ocr_engine.run(job.img, _live_engine(engine))
    text = clean_ocr(ocr.text)
    out = {"ocr": ocr, "text": text}
    if len(text) < settings.OCR_MIN_CHARS and not vision.available():  # Hindi or a scrawl: only a vision model reads it
        return {**out, "status": "no_text"}
    if not job.force and text and any(similarity(text, t) >= settings.TEXT_NOVELTY_THRESHOLD or same_board(text, t)
                                      for t in job.not_boards):
        return {**out, "status": "not_lecture", "known": True}
    notes, ai_ok = _write_notes(db, user, text, job.topic, patient, job.img, ocr_used=ocr.engine)
    if not notes.get("is_lecture"):
        return {**out, "status": "not_lecture"}
    return {**out, "status": "notes", "notes": notes, "ai_ok": ai_ok}


def _record(db: Session, user: User, session: StudySession, st: _State, board: _Board, job: _Job, done: dict) -> dict:
    """The write-up kept: a new note, or the board's note rewritten with what was added (a new note of its own when
    the page has scrolled on past what that note covers). Call with the session lock held. Returns the frame result:
    status "created"/"updated" with the note, or "not_lecture"/"no_text"."""
    ocr, text = done["ocr"], done["text"]
    base = {"ocr": ocr.to_dict()}
    if done["status"] == "no_text":
        db.commit()
        return {**base, "status": "no_text"}
    if done["status"] == "not_lecture":
        board.not_board = board.note_id is None  # a board that had notes keeps them
        if text and not done.get("known"):  # a PW lecture cuts to the teacher's camera again and again: ask the AI once
            st.not_boards = [*st.not_boards[-4:], text]
        db.commit()
        return {**base, "status": "not_lecture"}

    notes, ai_ok = done["notes"], done["ai_ok"]
    notes = {**notes, "subject": ai.fit_subject(notes.get("subject"), user.exam_target)}
    image_path = storage.save_frame(session.id, job.img)
    note = db.get(Note, board.note_id) if board.note_id and job.noted is not None and same_strokes(job.noted, job.ink) else None
    if note is not None:
        _rewrite(note, notes, text, image_path, job.frame_hash, ocr.confidence, ocr.engine)
        status = "updated"
    else:
        note = _add_note(db, session, notes, text, image_path, job.frame_hash, ocr.confidence, ocr.engine)
        status = "created"
    db.commit()
    db.refresh(note)
    usage.charge(db, user, "board_note", notes.get("source"))

    checkpoint = None
    if status == "created" and st.last_topic and st.last_notes_md and topics_differ(st.last_topic, notes["topic"]):
        checkpoint = ai.checkpoint(st.last_notes_md, st.last_topic, notes["topic"], user.exam_target,
                                   offline_only=not usage.can_spend(db, user, "checkpoint"), language=user.language)
        if checkpoint:
            usage.charge(db, user, "checkpoint", checkpoint.get("source"))
    board.note_id, board.topic = note.id, notes["topic"]
    st.last_topic, st.last_note_id, st.last_notes_md = notes["topic"], note.id, notes["notes_md"]
    return {**base, "status": status, "note": note, "checkpoint": checkpoint, "ai_source": notes.get("source"),
            "basic_mode": not ai_ok, "language_note": notes.get("language_note")}


def _write_up(db: Session, user: User, session: StudySession, st: _State, board: _Board, *, patient: bool = True,
              force: bool = False, engine: str | None = None) -> dict:
    """A board's notes, written now, while the caller waits. Call with the session lock held."""
    job = _snapshot(st, board, force)
    return _record(db, user, session, st, board, job, _compose(db, user, job, patient, engine))


# Frames being read at once. A server reading more frames than it has cores only makes every one of them slow (25
# students at once: 35 s a frame, then failures); past this, a frame is "busy" and comes again 5 s later.
_frame_slots = threading.BoundedSemaphore(settings.FRAME_SLOTS or max(2, os.cpu_count() or 2))
FORCE_WAIT_S = 20.0  # Capture now: the student is watching for it

_writer = ThreadPoolExecutor(max_workers=8, thread_name_prefix="focs-notes")  # mostly waiting on the AI providers


def _write_behind(session_id: int, user_id: int, board: _Board, job: _Job, engine: str | None) -> None:
    """A write-up in the background: its own database session, the AI part without the session lock (the lecture's
    frames carry on), and its cost on the student's own account (the per-student ceiling counts it)."""
    token = ledger.current_user.set(user_id)
    try:
        with SessionLocal() as db:
            user, session = db.get(User, user_id), db.get(StudySession, session_id)
            if user is None or session is None:
                return
            done = _compose(db, user, job, True, engine)
            st = _state(session_id)
            if not st.lock.acquire(timeout=120):
                log.warning("live: a background write-up gave up waiting for session %s", session_id)
                return
            try:
                result = _record(db, user, session, st, board, job, done)
            finally:
                st.lock.release()
            if result.get("note") is not None:  # (the note's id: it is read again in the request that reports it)
                st.finished.append({**_finished(result), "also_updated": result["note"].id})
    except Exception:
        log.exception("live: a background write-up failed (session %s)", session_id)
    finally:
        ledger.current_user.reset(token)


def _write_soon(db: Session, user: User, session: StudySession, st: _State, board: _Board, engine: str | None) -> dict:
    """A board's notes, in the background (LIVE_WRITE_BEHIND: they come back with a later frame), else now."""
    if not settings.LIVE_WRITE_BEHIND:
        return _write_up(db, user, session, st, board, engine=engine)
    job = _snapshot(st, board)
    st.jobs = [f for f in st.jobs if not f.done()] + [_writer.submit(_write_behind, session.id, user.id, board, job, engine)]
    return {}


def _report(db: Session, st: _State, result: dict) -> dict:
    """Add a background write-up that has finished to this frame's result (one a frame; the rest come next)."""
    if result.get("also_updated") is not None or not st.finished:
        return result
    done = dict(st.finished.pop(0))
    note = db.get(Note, done["also_updated"])
    if note is None:
        return result
    done["also_updated"] = note
    return {**result, **{k: v for k, v in done.items() if v is not None or k not in result}}


def _drain(st: _State, timeout: float = 180) -> None:
    """Wait for the write-ups still running (the lecture is ending). Call without the session lock."""
    for job in list(st.jobs):
        try:
            job.result(timeout=timeout)
        except Exception:  # logged where it ran; one lost write-up must not stop the lecture ending
            pass
    st.jobs = []


def _count_time(user: User, st: _State) -> None:
    """The lecture time since the last frame or settle ping, towards the study day's lecture hours."""
    now = time.monotonic()
    if st.seen_at is not None:
        usage.count_lecture(user, min(now - st.seen_at, LECTURE_GAP_S))
    st.seen_at = now


def _finished(done: dict) -> dict:
    """A board's write-up, reported as the "also_" part of the result of a frame that showed another board."""
    if done.get("note") is None:
        return {}
    return {"also_updated": done["note"], "also_status": done["status"], "checkpoint": done.get("checkpoint"),
            "ai_source": done.get("ai_source"), "basic_mode": done.get("basic_mode"), "language_note": done.get("language_note")}


def _merge(into: _Board, other: _Board) -> None:
    """One frame showed both: they are one board (seen past the teacher from two sides, say)."""
    into.first_at = min(into.first_at, other.first_at)
    if into.note_id is None and other.note_id is not None:
        into.note_id, into.topic, into.written, into.written_at = other.note_id, other.topic, other.written, other.written_at
    if other.jpeg is not None and other.ink.amount > into.ink.amount:
        into.jpeg, into.ink, into.frame_hash = other.jpeg, other.ink, other.frame_hash
    into.not_board = into.not_board and other.not_board


def _move_to(st: _State, board: _Board, now: float) -> None:
    """The lecture is on ``board`` now. The board before gets its notes BOARD_AWAY_S later (see _due), unless the
    lecture is back on it by then: after half a minute at the camera, a PW teacher goes on writing where they were."""
    prev = st.board
    if prev is not None and prev is not board:
        prev.left_at, prev.latest = now, prev.ink  # (a board coming back is compared with its fullest view)
        st.boards = [b for b in st.boards if b is not prev][-(KEEP_BOARDS - 1):] + [prev]
    st.boards = [b for b in st.boards if b is not board]
    board.left_at = None
    st.board, st.candidate = board, None


def _due(db: Session, user: User, session: StudySession, st: _State, now: float, *, everything: bool = False,
         patient: bool = True, engine: str | None = None) -> dict:
    """Notes for a board the lecture left BOARD_AWAY_S ago, one a call (every one, ``everything``: the lecture is
    ending), as the "also_" part of a frame result. A board left after less than BOARD_MIN_S gets none."""
    result: dict = {}
    for b in list(st.boards):
        if b.left_at is None:
            continue
        if not b.unwritten() or (b.note_id is None and b.left_at - b.first_at < settings.BOARD_MIN_S):
            b.left_at = None
            continue
        if everything or now - b.left_at >= settings.BOARD_AWAY_S:
            b.left_at = None
            if everything:
                result = _finished(_write_up(db, user, session, st, b, patient=patient, engine=engine)) or result
            else:
                result = _finished(_write_soon(db, user, session, st, b, engine))
                break
    return result


def _waiting(st: _State) -> bool:
    return st.candidate is not None or any(b.left_at is not None for b in st.boards) or bool(st.finished) or (
        any(not f.done() for f in st.jobs)) or (st.board is not None and st.board.unwritten())


def settle(db: Session, user: User, session: StudySession, patient: bool = True) -> dict:
    """The screen stopped changing (or the lecture is ending: ``patient=False``, someone is waiting, and every board
    still waiting for its notes gets them now): the board on screen gets its notes, if what is on it is new."""
    st = _state(session.id)
    if not _waiting(st):
        return {"status": "unchanged"}
    if not patient:  # the lecture is ending: the write-ups running in the background first
        _drain(st)
    if not st.lock.acquire(timeout=60):
        return {"status": "busy"}
    try:
        if patient:  # (a lecture ending is not more lecture time)
            _count_time(user, st)
        now = time.monotonic()
        if st.candidate is not None:  # the screen stayed on it: that's the board now
            _move_to(st, st.candidate, now)
        also = _due(db, user, session, st, now, everything=not patient, patient=patient)
        done = {}
        if st.board is not None and st.board.unwritten():
            done = (_write_soon(db, user, session, st, st.board, None) if patient
                    else _write_up(db, user, session, st, st.board, patient=False))
        also = _report(db, st, also)
        running = any(not f.done() for f in st.jobs)
        db.commit()
    finally:
        st.lock.release()
    if done.get("note") is not None:
        return {**also, **{k: v for k, v in done.items() if v is not None or k not in also}}
    if also:  # a board written in the background, or one the lecture had left
        return {"status": also["also_status"], "note": also["also_updated"],
                **{k: v for k, v in also.items() if not k.startswith("also_")}}
    if running:  # still being written: ask again in a moment
        return {"status": "growing", "settle_after": settings.BOARD_SETTLE_S}
    return {"status": "unchanged"}


CAMERA_HASH_SLACK = 4  # a camera on a desk: light and sensor noise move a few hash bits on an unchanged board


def process_frame(db: Session, user: User, session: StudySession, img: np.ndarray,
                  *, force: bool = False, engine: str | None = None, camera: bool = False) -> dict:
    """One frame of the lecture. ``force``: the student pressed Capture now, so the board on it is written up at once
    (if anything on it is new), with no waiting for the cheap model and no "not a board" memory."""
    st = _state(session.id)
    if not st.lock.acquire(blocking=False):
        return {"status": "busy"}  # previous frame of this session still processing; drop this one
    if not _frame_slots.acquire(timeout=FORCE_WAIT_S if force else settings.FRAME_WAIT_S):
        st.lock.release()
        log.info("frame for session %s dropped: the server is reading as many frames as it can", session.id)
        return {"status": "busy"}
    try:
        session.frames_processed = (session.frames_processed or 0) + 1
        _count_time(user, st)
        frame_hash = phash(img)
        same = settings.FRAME_HASH_THRESHOLD + (CAMERA_HASH_SLACK if camera else 0)
        if not force and st.last_hash is not None and hamming(frame_hash, st.last_hash) <= same:
            db.commit()
            return {"status": "unchanged"}
        st.last_hash = frame_hash
        now = time.monotonic()
        ink = ink_map(img)
        if not force and ink.amount < MIN_INK:
            db.commit()
            return {"status": "no_text"}

        known = [b for b in (st.board, st.candidate) if b is not None] + st.boards[::-1]
        scored = [(max(match(b.latest, ink), match(b.ink, ink) if b.ink is not b.latest else 0.0), b) for b in known]
        matches = [(k, b) for k, b in scored if k > 0]
        if matches:
            found = st.board if any(b is st.board for _, b in matches) else max(matches, key=lambda m: m[0])[1]
            for _, other in matches:
                if other is not found:
                    _merge(found, other)
                    st.boards = [b for b in st.boards if b is not other]
                    if other is st.candidate:
                        st.candidate = None
            found.see(img, ink, frame_hash, take=force)
            if found is st.candidate and not force and now - found.first_at < settings.BOARD_MIN_S:
                db.commit()  # a new view, not settled yet: the teacher's camera changes with every gesture
                return {"status": "growing", "settle_after": settings.BOARD_SETTLE_S}
            if found is st.board:
                st.candidate = None  # whatever came between was a flash (the teacher at the camera, a transition)
            else:  # the new view held, or the teacher went back to an earlier board
                _move_to(st, found, now)
        else:
            new = _Board(storage.jpeg(img, FRAME_SIDE), ink, frame_hash, ink, now)
            if st.board is not None and not force:
                st.candidate = new
                db.commit()
                return {"status": "growing", "settle_after": settings.BOARD_SETTLE_S}
            _move_to(st, new, now)
        result = _due(db, user, session, st, now, engine=engine)
        board = st.board

        long_wait = now - (board.written_at if board.written_at is not None else board.first_at) >= settings.BOARD_REFRESH_S
        first = st.last_note_id is None and not st.jobs  # nothing written yet: notes at once, so the student sees it works
        if (force and (board.unwritten() or board.not_board)) or (first and board.unwritten()):
            done = _write_up(db, user, session, st, board, patient=not force, force=force, engine=engine)
            return _report(db, st, {**result, **{k: v for k, v in done.items() if v is not None or k not in result}})
        if long_wait and board.unwritten():  # still being written on: its notes so far
            done = _write_soon(db, user, session, st, board, engine)
            if done.get("note") is not None:  # written now (LIVE_WRITE_BEHIND off)
                return _report(db, st, {**result, **{k: v for k, v in done.items() if v is not None or k not in result}})
        result = _report(db, st, result)
        db.commit()
        if board.not_board:
            return {**result, "status": "not_lecture"}
        if board.unwritten():
            return {**result, "status": "growing", "settle_after": settings.BOARD_SETTLE_S}
        return {**result, "status": "duplicate"}
    finally:
        _frame_slots.release()
        st.lock.release()
