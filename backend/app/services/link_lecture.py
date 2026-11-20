"""Lecture by link: a YouTube lecture played inside Focs, for phones (which can't share a tab) and anyone else.

The page plays the video and, every couple of minutes of it actually watched, sends the stretch just played. Gemini
watches that stretch of the video itself (YouTube links are read by Google directly: nothing is downloaded here),
board and voice together, and writes one note. Where Gemini can't be reached, the video's captions are written up
instead, like the voice lane does. Stretches already written up (the student rewound) cost nothing.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.core.config import settings
from app.models.note import Note
from app.models.session import StudySession
from app.models.user import User
from app.services import ai, ledger, live, usage, vision, youtube
from app.services.llm import LLMUnavailable, ensure_budget, fix_latex, parse_json, restore_backslashes
from app.services.text_utils import topics_differ

log = logging.getLogger("focs.link")

MIN_CLIP_S = 20
MAX_CLIP_S = 600
COVERED = 0.7   # a stretch this much inside ones already written up is a rewatch
TIMEOUT_S = 90.0
NATIVE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

CLIP_PROMPT = """You are Focs, a meticulous {exam} teacher. This is one stretch ({start} to {end}) of a recorded lecture{title}.
Watch it: read what is written on the board or slides and listen to what the teacher says.
Write the study notes a strong student would take from THIS stretch only.
- Only what the lecture shows or says. Never solve a problem the teacher didn't solve, finish a calculation they left,
  or add topics, examples or formulas they didn't give. Copy formulas and numbers exactly as written.
- Markdown: short "##" sections, bullets, the teacher's method as numbered steps when they worked something out,
  and their warnings or exam tips. Math in LaTeX ($...$ inline, $$...$$ for display).
- "board": what is written on the board in this stretch, plain text, line by line (empty if nothing is written).
- When the stretch has no teaching at all (an intro, an advert, chatter, a break), set "lecture" to false.
Return JSON only: {{"lecture": true, "topic": "a short topic name", "subject": "one of: {subjects}",
"board": "...", "notes_md": "..."}}"""


def _clock(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def _key() -> str:
    if settings.GEMINI_API_KEY:
        return settings.GEMINI_API_KEY
    return settings.LLM_FALLBACK_API_KEY if "generativelanguage" in settings.LLM_FALLBACK_BASE_URL else ""


def _models() -> list[str]:
    return [m for m in vision.models() if m.startswith("gemini")]


def available() -> bool:
    return bool(_key() and _models())


def _watch(vid: str, start: float, end: float, prompt: str) -> dict[str, Any]:
    """Gemini's notes on one stretch of a YouTube video. Raises LLMUnavailable when no model answers."""
    ensure_budget()
    body = {"contents": [{"parts": [
                {"file_data": {"file_uri": f"https://www.youtube.com/watch?v={vid}"},
                 "video_metadata": {"start_offset": f"{int(start)}s", "end_offset": f"{int(end)}s"}},
                {"text": prompt}]}],
            # low resolution: a board is still legible, at a third of the tokens
            "generationConfig": {"mediaResolution": "MEDIA_RESOLUTION_LOW", "temperature": 0.2, "maxOutputTokens": 3000}}
    tried = []
    for model in _models():
        try:
            r = httpx.post(NATIVE.format(model=model), json=body, headers={"x-goog-api-key": _key()}, timeout=TIMEOUT_S)
        except httpx.HTTPError as exc:
            tried.append(f"{model} {type(exc).__name__}")
            continue
        if r.status_code >= 400:
            tried.append(f"{model} {r.status_code}")
            if r.status_code == 400:  # a private, age-restricted or deleted video: no model will see it
                raise LLMUnavailable(f"video not readable: {r.text[:200]}")
            continue
        try:
            data = r.json()
            text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"] if not p.get("thought"))
            meta = data.get("usageMetadata") or {}
            ledger.record("link_lecture", model, {"prompt_tokens": meta.get("promptTokenCount"),
                                                  "completion_tokens": meta.get("candidatesTokenCount")})
            return parse_json(text)
        except (ValueError, KeyError, IndexError, LLMUnavailable):
            tried.append(f"{model} unreadable")
    raise LLMUnavailable(f"video models busy ({', '.join(tried)})")


def _from_captions(vid: str, start: float, end: float, user: User) -> dict[str, Any] | None:
    said = youtube.caption_window(vid, end, end - start)
    if len(said) < 160:
        return None
    out = ai.speech_notes(said, None, user.exam_target, user.language)
    return out and {"lecture": True, "topic": out["topic"], "notes_md": out["notes_md"], "board": "", "engine": "captions"}


def _covered(st: live._State, start: float, end: float) -> bool:
    seen = sum(max(0.0, min(end, b) - max(start, a)) for a, b in st.clips)
    return seen >= COVERED * (end - start)


def read_clip(db, user: User, session: StudySession, start: float, end: float) -> dict[str, Any]:
    """One watched stretch of the lecture → a note. Status: created, nothing (no teaching in it), rewatch, allowance,
    busy (try the same stretch again later)."""
    vid = youtube.video_id(session.video_url or "")
    start, end = max(0.0, start), max(0.0, end)
    st = live._state(session.id)
    st.seen_at = time.monotonic()  # a lecture being watched isn't idle (api/_common.close_idle_sessions)
    if not vid or end - start < MIN_CLIP_S:
        return {"status": "nothing"}
    start = max(start, end - MAX_CLIP_S)
    if _covered(st, start, end):
        return {"status": "rewatch"}
    if not (usage.can_spend(db, user, "board_note") and usage.lecture_time_left(user)):
        return {"status": "allowance"}
    title = f' titled "{session.title}"' if session.title else ""
    prompt = ai._in(CLIP_PROMPT.format(exam=ai._exam(user.exam_target), subjects=ai._subjects(user.exam_target), start=_clock(start), end=_clock(end), title=title),
                    user.language)
    written: dict[str, Any] | None = None
    if available():
        try:
            written = {**_watch(vid, start, end, prompt), "engine": "video"}
        except LLMUnavailable as exc:
            log.info("clip not watched: %s", exc)
    if written is None:
        written = _from_captions(vid, start, end, user)
    if written is None:
        return {"status": "busy"}
    st.clips.append((start, end))
    usage.count_lecture(user, end - start)
    md = str(written.get("notes_md") or "").strip()
    if written.get("lecture") is False or not md:
        db.commit()
        return {"status": "nothing"}
    topic = str(written.get("topic") or "Lecture notes").strip()[:80]
    subject = ai.fit_subject(str(written.get("subject") or "").strip() or None, user.exam_target)
    note = Note(session_id=session.id, topic=topic, subject=subject if subject != "General" else session.subject,
                ai_notes=ai.tidy_math(fix_latex(restore_backslashes(md))), ocr_raw=str(written.get("board") or "")[:6000],
                engine=written["engine"], language=user.language if ai.language_rule(user.language) else None)
    db.add(note)
    if not session.subject and subject not in (None, "General"):
        session.subject = subject
    if not session.title:
        session.title = topic
    db.commit()
    db.refresh(note)
    usage.charge(db, user, "board_note")
    checkpoint = None
    if st.last_topic and st.last_notes_md and topics_differ(st.last_topic, topic):
        checkpoint = ai.checkpoint(st.last_notes_md, st.last_topic, topic, user.exam_target,
                                   offline_only=not usage.can_spend(db, user, "checkpoint"), language=user.language)
        if checkpoint:
            usage.charge(db, user, "checkpoint", checkpoint.get("source"))
    st.last_topic, st.last_note_id, st.last_notes_md = topic, note.id, note.ai_notes
    return {"status": "created", "note": note, "checkpoint": checkpoint}
