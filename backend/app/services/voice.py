"""The voice lane: what the teacher says, not just what they write.

The browser records the lecture tab's sound in ~25-second pieces and sends only the ones with speech. Each piece is
transcribed (with the board's topic as a hint for technical words) and dropped; the text is kept as a segment, which
the page shows as captions. Speech is then folded into the notes:

- while a board is on screen, what the teacher said about it becomes that note's "What the teacher said" section,
  written when the lecture moves to the next board (or after two minutes of talk on the same board);
- talk with no board at all (a teacher explaining to camera) becomes a note of its own after two minutes;
- the end-of-lecture revision sheet gets the transcript too, so what the teacher stressed makes it in.

Transcribing costs a little AI allowance (one unit per few pieces) and, because speech to text is paid by the minute,
counts against the week's caption minutes (usage.captions_left). Past either, the board notes carry on and the voice
simply pauses. The shared board notes are never changed: the spoken part belongs to this lecture.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lecture import LectureSegment
from app.models.note import Note
from app.models.session import StudySession
from app.models.user import User
from app.services import ai, live, speech, usage
from app.services.llm import LLMUnavailable

log = logging.getLogger("focs.voice")

FOLD_AFTER_S = 120        # talk on one board (or with none) before it is written up
MIN_FOLD_CHARS = 160      # less than this isn't worth a note
CHUNKS_PER_UNIT = 4       # transcribing four pieces (~100 s) costs one allowance unit
RETRY_AFTER_S = 60        # after a failed write-up, wait before trying again
# Whisper's well-known inventions on music or silence
_HALLUCINATIONS = re.compile(r"^(thank you\.?|thanks for watching!?|please subscribe\.?|you|bye\.?|\.+|music|\[music\]|subtitles by .*)$", re.I)
# the recogniser names what it heard ("tamil"); captions keep the code
_LANG = {"english": "en", "hindi": "hi", "marathi": "mr", "bengali": "bn", "tamil": "ta", "telugu": "te", "gujarati": "gu"}
_LANG.update({code: code for code in _LANG.values()})


def _useful(text: str) -> bool:
    t = text.strip()
    return len(t) >= 12 and not _HALLUCINATIONS.match(t)


def segment_out(s: LectureSegment) -> dict[str, Any]:
    return {"id": s.id, "start_s": s.start_s, "end_s": s.end_s, "text": s.text, "language": s.language, "note_id": s.note_id}


def add(db: Session, user: User, session: StudySession, audio: bytes, filename: str, content_type: str,
        start_s: float, end_s: float) -> dict[str, Any]:
    """One piece of the lecture's sound: transcribed, kept as text, and folded into notes when it's time."""
    st = live._state(session.id)
    if not speech.available():
        return {"skipped": "unavailable"}
    if not usage.captions_left(user):
        return {"skipped": "captions"}
    if not usage.can_spend(db, user, "lecture_audio"):
        return {"skipped": "allowance"}
    try:
        heard = speech.transcribe_full(audio, filename, content_type, hint=st.last_topic or session.title or "",
                                       feature="lecture_audio")
    except LLMUnavailable as exc:
        log.info("lecture audio not transcribed: %s", exc)
        return {"skipped": "busy"}
    usage.charge_captions(db, user, heard.get("duration") or max(0.0, end_s - start_s))
    text = " ".join(heard["text"].split())
    if not _useful(text):
        return {"skipped": "silence"}
    seg = LectureSegment(session_id=session.id, start_s=max(0.0, start_s), end_s=max(start_s, end_s), text=text,
                         language=_LANG.get((heard.get("language") or "").lower(), (heard.get("language") or "")[:10] or None),
                         note_id=st.last_note_id)
    db.add(seg)
    db.commit()
    st.audio_chunks += 1
    if st.audio_chunks % CHUNKS_PER_UNIT == 1:
        usage.charge(db, user, "lecture_audio")
    note = fold(db, user, session)
    return {"segment": segment_out(seg), "spoken_note": note}


def _groups(db: Session, session_id: int) -> dict[int | None, list[LectureSegment]]:
    out: dict[int | None, list[LectureSegment]] = {}
    for s in db.scalars(select(LectureSegment).where(LectureSegment.session_id == session_id, LectureSegment.folded.is_(False))
                        .order_by(LectureSegment.start_s)):
        out.setdefault(s.note_id, []).append(s)
    return out


def _span(segs: list[LectureSegment]) -> float:
    return sum(max(0.0, s.end_s - s.start_s) for s in segs)


def fold(db: Session, user: User, session: StudySession, finishing: bool = False) -> Note | None:
    """Write up the speech that's ready: boards the lecture has moved past, two minutes of talk on the current board,
    two minutes of talk with no board. ``finishing``: the lecture ended, so everything left. Returns a new spoken
    note when one was made."""
    st = live._state(session.id)
    if time.monotonic() < st.voice_retry_at and not finishing:
        return None
    made = None
    for note_id, segs in _groups(db, session.id).items():
        ready = finishing or note_id != st.last_note_id or _span(segs) >= FOLD_AFTER_S
        if not ready or sum(len(s.text) for s in segs) < MIN_FOLD_CHARS:
            continue
        note = db.get(Note, note_id) if note_id else None
        if note_id and note is None:
            continue
        if not (usage.can_spend(db, user, "board_note") and usage.lecture_time_left(user)):  # lecture notes: lecture hours
            return made
        # the whole talk on this board so far, so the section reads as one piece
        said = segs if note is None else db.scalars(select(LectureSegment).where(LectureSegment.session_id == session.id,
                                                                                   LectureSegment.note_id == note_id).order_by(LectureSegment.start_s)).all()
        written = ai.speech_notes(" ".join(s.text for s in said), note.ai_notes if note else None, user.exam_target, user.language)
        if written is None:
            st.voice_retry_at = time.monotonic() + RETRY_AFTER_S
            return made
        if note is not None:
            note.spoken_md = ai.tidy_math(written["notes_md"])
        else:
            made = Note(session_id=session.id, topic=written["topic"], subject=session.subject, ai_notes=ai.tidy_math(written["notes_md"]),
                        ocr_raw="", engine="speech", language=user.language if ai.language_rule(user.language) else None)
            db.add(made)
            db.flush()
            for s in segs:
                s.note_id = made.id
        for s in segs:
            s.folded = True
        db.commit()
        usage.charge(db, user, "board_note", written.get("source"))
    return made


def transcript(db: Session, session_id: int) -> list[LectureSegment]:
    return list(db.scalars(select(LectureSegment).where(LectureSegment.session_id == session_id).order_by(LectureSegment.start_s)))


def summary(db: Session, user: User, session: StudySession) -> dict[str, Any]:
    """One summary of everything the teacher said in a lecture, kept with it and written again only when more speech
    has come in since. When it can't be written now (allowance used up, AI busy), the last one kept, marked stale."""
    pieces = transcript(db, session.id)
    kept = {"summary_md": session.talk_summary, "pieces": session.talk_summary_pieces or 0}
    if not pieces:
        return {"summary_md": None, "pieces": 0}
    if session.talk_summary and session.talk_summary_pieces == len(pieces):
        return {**kept, "source": "kept"}
    if not usage.can_spend(db, user, "talk_summary"):
        return {**kept, "stale": bool(session.talk_summary), "reason": "allowance"}
    boards = "\n\n".join(n.ocr_raw for n in session.notes if n.ocr_raw)
    md = ai.talk_summary([s.text for s in pieces], session.title, user.exam_target, user.language, boards)
    if md is None:
        return {**kept, "stale": bool(session.talk_summary), "reason": "busy"}
    session.talk_summary, session.talk_summary_pieces = md, len(pieces)
    db.commit()
    usage.charge(db, user, "talk_summary")
    return {"summary_md": md, "pieces": len(pieces), "source": "ai"}
