"""One-time, idempotent data upgrades for databases created by earlier Focs versions."""
from __future__ import annotations

import logging
import re

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.note import Note
from app.models.session import StudySession
from app.services.text_utils import guess_subject

log = logging.getLogger("focs.db")
_HEADING = re.compile(r"^\s*#{1,4}\s+(.+?)\s*#*\s*$", re.MULTILINE)
_GENERIC = {"lecture notes", "notes", "introduction", "key concepts", "important concepts", "board notes", "formulas"}


def _topic_from_markdown(md: str) -> str | None:
    for m in _HEADING.finditer(md or ""):
        title = re.sub(r"[*_`]", "", m.group(1)).strip(" :-")
        if 2 < len(title) <= 80 and title.lower() not in _GENERIC:
            return title
    return None


def backfill_legacy() -> None:
    """Give pre-1.0 notes/sessions a topic, subject and title derived from their notes."""
    with SessionLocal() as db:
        notes = db.scalars(select(Note).where(Note.topic.is_(None), Note.ai_notes.is_not(None))).all()
        for n in notes:
            n.topic = _topic_from_markdown(n.ai_notes or "") or "Board notes"
            n.subject = n.subject or guess_subject(f"{n.ai_notes} {n.ocr_raw}")
        sessions = db.scalars(select(StudySession).where(StudySession.title.is_(None))).all()
        titled = 0
        for s in sessions:
            topics = [n.topic for n in s.notes if n.topic and n.topic != "Board notes"]
            if topics:
                s.title = max(set(topics), key=topics.count)  # most frequent topic
                subjects = [n.subject for n in s.notes if n.subject and n.subject != "General"]
                s.subject = s.subject or (max(set(subjects), key=subjects.count) if subjects else None)
                titled += 1
        if notes or titled:
            db.commit()
            log.info("backfill: %d notes, %d sessions upgraded", len(notes), titled)
