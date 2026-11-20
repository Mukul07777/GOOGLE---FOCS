"""Formula book: every formula from the student's board notes, grouped by subject and topic. No AI involved."""
from __future__ import annotations

import re

_HEADING = re.compile(r"^\s*#{2,6}\s+(.*)$")
_BULLET = re.compile(r"^\s*[-*]\s+(.+)$")
_PLAIN = re.compile(r"[^a-z0-9]")


def extract(markdown: str | None) -> list[str]:
    """Bullets under any "Formulas" heading (## or ###) of a note."""
    out: list[str] = []
    in_formulas = False
    for line in (markdown or "").splitlines():
        heading = _HEADING.match(line)
        if heading:
            in_formulas = "formula" in heading.group(1).lower()
            continue
        bullet = _BULLET.match(line)
        if in_formulas and bullet and len(bullet.group(1).strip()) > 2:
            out.append(bullet.group(1).strip())
    return out


def book(notes) -> list[dict]:
    """[{subject, topics: [{topic, formulas: [{text, note_id, session_id}]}]}], newest topics first, duplicates dropped."""
    subjects: dict[str, dict[str, list[dict]]] = {}
    seen: set[tuple[str, str]] = set()
    for n in sorted(notes, key=lambda n: n.captured_at or 0, reverse=True):
        subject = n.subject or "General"
        for text in extract(n.ai_notes):
            key = (subject, _PLAIN.sub("", text.lower()))
            if key in seen:
                continue
            seen.add(key)
            subjects.setdefault(subject, {}).setdefault(n.topic or "Board notes", []).append(
                {"text": text, "note_id": n.id, "session_id": n.session_id})
    return [{"subject": s, "count": sum(len(f) for f in topics.values()),
             "topics": [{"topic": t, "formulas": f} for t, f in topics.items()]}
            for s, topics in sorted(subjects.items(), key=lambda kv: -sum(len(f) for f in kv[1].values()))]
