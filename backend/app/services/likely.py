"""What a paper is likely to ask: each chapter's most-asked topics.

Judged once per chapter by the AI, from what it knows of the exam's past papers, then kept in the notes library
(kind "asked") and shared by every student of that exam, the way notes are; an export of the library ships them
with Focs. This is a model's reading of past papers, not a count of real past questions: the question bank holds
too few of those to rank topics by.

Last-day revision puts a chapter's most-asked topics first, and for a chapter the student hasn't studied yet lists
only those.
"""
from __future__ import annotations

import logging
import threading
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.library import TopicNote
from app.services import topic_notes
from app.services.llm import LLMUnavailable, llm
from app.services.syllabus import Chapter, Syllabus

log = logging.getLogger("focs.likely")

KIND = "asked"
# chapters ranked in one request; the rest wait for the next. With the room a reasoning model is given to think
# (llm.py adds 4,096 tokens at medium effort) sixteen chapters stay well inside a free tier's 8,000 tokens a minute
AT_ONCE = 16
FEWEST = 3         # a chapter of one or two topics is revised whole: nothing to rank
REST_S = 120.0     # after a request that failed, how long before asking again

ASK_SYSTEM = """You know {exam} papers well. For each chapter below, pick the topics its questions have come from
most often in recent {exam} papers: what a student must not skip the day before the exam. Pick 2 to 4 topics for a
chapter (1 or 2 when it has 4 topics or fewer), the most asked first, by their numbers in that chapter's list. Only
rank the topics listed; never add one.
Return JSON: {{"chapters": [{{"n": <chapter number>, "topics": [<topic number>, ...]}}]}}"""

_asking = threading.Lock()  # one request at a time: two students opening the page together don't both pay for it
_rest_until = 0.0


def known(db: Session, library: str, chapter_ids: list[str]) -> dict[str, list[str]]:
    """Chapter id → its most-asked topic ids, most asked first, for the chapters the library has ranked."""
    if not chapter_ids:
        return {}
    rows = db.execute(select(TopicNote.ref_id, TopicNote.content_md).where(
        TopicNote.exam == library, TopicNote.kind == KIND, TopicNote.ref_id.in_(chapter_ids))).all()
    return {ref: content.split() for ref, content in rows if content.strip()}


def _ask(syl: Syllabus, chapters: list[Chapter]) -> tuple[dict[str, list[str]], str] | None:
    """One request for the lot. Never the light model: asked this, it picked every chapter's first four topics (in
    testing), and no ranking is better than that one. The bigger model's picks held when the lists were shuffled."""
    listing = "\n".join(f"{n}. {ch.name} ({ch.subject})\n" + "\n".join(f"   {i}) {t.name}" for i, t in enumerate(ch.topics, 1))
                        for n, ch in enumerate(chapters, 1))
    exam = topic_notes.EXAM_LABEL.get(syl.library, syl.name)
    light = frozenset(m.strip() for m in settings.LLM_LIGHT_MODEL.split(",") if m.strip())
    try:
        data, model = llm.json_with_model([{"role": "system", "content": ASK_SYSTEM.format(exam=exam)},
                                           {"role": "user", "content": listing}],
                                          max_tokens=200 + 30 * len(chapters), temperature=0.0, effort="medium", skip=light,
                                          feature="lastday_asked")
    except LLMUnavailable as exc:
        log.info("could not rank %d chapters: %s", len(chapters), exc)
        return None
    out: dict[str, list[str]] = {}
    for row in data.get("chapters") or []:
        try:
            n = int(row["n"])
            picks = [int(i) for i in row.get("topics") or []]
        except (KeyError, TypeError, ValueError):
            continue
        if not 1 <= n <= len(chapters):
            continue
        ch = chapters[n - 1]
        ids = list(dict.fromkeys(ch.topics[i - 1].id for i in picks if 1 <= i <= len(ch.topics)))[:4]
        if ids:
            out[ch.id] = ids
    return out, model


def rank(db: Session, syl: Syllabus, chapters: list[Chapter]) -> dict[str, list[str]]:
    """The most-asked topics of these chapters: what the library has, and for chapters it hasn't ranked yet (up to
    AT_ONCE of them) one request to the model now, kept for everyone. A chapter that can't be ranked right now (no
    model, or one resting after a rate limit) is simply left out, and asked again another time."""
    global _rest_until
    library = syl.library or syl.exam
    out = known(db, library, [c.id for c in chapters])
    todo = [c for c in dict.fromkeys(chapters) if c.id not in out and len(c.topics) >= FEWEST][:AT_ONCE]
    if not todo or not llm.available or time.monotonic() < _rest_until or not _asking.acquire(blocking=False):
        return out
    try:
        asked = _ask(syl, todo)
        if asked is None:
            _rest_until = time.monotonic() + REST_S
            return out
        ranked, model = asked
        for ch_id, ids in ranked.items():
            topic_notes._store(db, library, KIND, ch_id, "\n".join(ids), model, checked=False)
            out[ch_id] = ids
        return out
    finally:
        _asking.release()
