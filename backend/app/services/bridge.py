"""The two ends of a test, turned towards the student.

Before: while a paper is being written (a minute or more on the free AI tier) the student looks over what it will
cover — the chapter's topics, its key points and a few self-check questions from the notes library — and says how
ready they feel for each chapter. After: a gap map puts that feeling next to what the test found, and turns the
result into at most three next steps. Nothing here calls the AI: both have to work while the AI is busy or at its limit.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.mock import MockTest
from app.models.user import User
from app.services import mock, syllabus, topic_notes
from app.services.mock_patterns import BOTANY, chapters_of
from app.services.syllabus import Chapter

MAX_CARDS = 8
FEELINGS = ("sure", "shaky")
STRONG, SHAKY = 0.75, 0.4  # share of a chapter's questions answered right


def key(subject: str, chapter: str) -> str:
    return f"{subject}::{chapter}"


def _library_subject(subject: str) -> str:
    return "Biology" if subject in ("Botany", "Zoology") else subject


def chapter_of(user: User, subject: str, name: str) -> Chapter | None:
    """The syllabus chapter behind a test's (subject, chapter), for links to its notes. None when there is none."""
    subject = _library_subject(subject)
    syl = syllabus.of(user, whole=True)
    found = next((c for c in syl.subject_chapters(subject) if c.name == name), None) if syl else None
    if found is None and subject in syllabus.courses():  # a library course outside the student's own plan
        found = next((c for c in syllabus._course_chapters(subject, 0) if c.name == name), None)
    return found


def _library(user: User) -> str | None:
    syl = syllabus.of(user)
    return syl.library or syl.exam if syl else None


# ---------------------------------------------------------------- reading the notes library
def _section(md: str, title: str) -> str:
    m = re.search(rf"^##\s+{re.escape(title)}\s*$(.*?)(?=^##\s|\Z)", md, re.M | re.S | re.I)
    return m.group(1) if m else ""


def _bullets(text: str, n: int) -> list[str]:
    out = []
    for line in text.splitlines():
        m = re.match(r"\s*(?:[-*]|\d+[.)])\s+(.+)", line)
        if m and 8 <= len(m.group(1)) <= 260:
            out.append(m.group(1).strip())
        if len(out) == n:
            break
    return out


def _self_check(md: str, n: int = 3) -> list[dict[str, str]]:
    """The capsule's "Quick self-check": numbered questions, each with an "Answer:" line under it."""
    out: list[dict[str, str]] = []
    q = None
    for line in _section(md, "Quick self-check").splitlines():
        if m := re.match(r"\s*\d+[.)]\s+(.+)", line):
            q = m.group(1).strip()
        elif (m := re.match(r"\s*\**Answer:?\**:?\s*(.+)", line, re.I)) and q:
            out.append({"q": q, "a": m.group(1).strip()})
            q = None
        if len(out) == n:
            break
    return out


def _card(db: Session, library: str | None, user: User, subject: str, name: str, felt: str | None,
          only: tuple[str, ...] = ()) -> dict[str, Any]:
    """``only``: the topics of the chapter the paper asks about, when it asks about some of them (a last-day test)."""
    ch = chapter_of(user, subject, name)
    topics = [t for t in ch.topics if not only or t.name in only] if ch else []
    points: list[str] = []
    check: list[dict[str, str]] = []
    if ch and library:
        capsule = topic_notes.get(db, library, "capsule", ch.id)
        if capsule and not only:  # a capsule is the whole chapter's
            points = _bullets(_section(capsule.content_md, "Key points"), 4)
            check = _self_check(capsule.content_md)
        for t in topics:
            if len(points) >= 4:
                break
            note = t.notes or (row.content_md if (row := topic_notes.get(db, library, "detailed", t.id)) else "")
            points += _bullets(_section(note, "Quick recap"), 2) if note else []
    return {"subject": subject, "chapter": name, "chapter_id": ch.id if ch else None,
            "topics": [t.name for t in topics][:8], "points": points[:4], "check": check, "felt": felt}


def _paper_chapters(test: MockTest) -> list[tuple[str, str]]:
    """The chapters a paper covers: a chapter test's or a last-day test's own; for a full mock, a rotating few of each
    subject's heaviest."""
    cfg = test.config or {}
    if cfg.get("parts"):
        return [(p["subject"], c) for p in cfg["parts"] if p.get("count") for c in p["chapters"]][:MAX_CARDS]
    if cfg.get("chapters"):
        return [(cfg["subject"], c) for c in cfg["chapters"]][:MAX_CARDS]
    p = mock.pattern_of(test)
    per = max(1, MAX_CARDS // max(1, len(p.subjects)))
    out = []
    for subject in p.subjects:
        weights = chapters_of(_library_subject(subject))
        if subject in ("Botany", "Zoology"):
            weights = {c: w for c, w in weights.items() if (c in BOTANY) == (subject == "Botany")}
        heavy = sorted(weights, key=lambda c: -weights[c])[: per * 3]
        start = (test.id * per) % max(1, len(heavy))
        out += [(subject, c) for c in (heavy[start:] + heavy[:start])[:per]]
    return out


def warmup(db: Session, user: User, test: MockTest) -> dict[str, Any]:
    felt = test.confidence or {}
    library = _library(user)
    only = mock.pattern_of(test).topics  # a last-day test: subject → chapter → the topics it asks about
    cards = [_card(db, library, user, s, c, felt.get(key(s, c)), tuple(only.get(s, {}).get(c, ()))) for s, c in _paper_chapters(test)]
    return {"cards": cards, "status": test.status, "progress": test.progress}


def set_feeling(test: MockTest, subject: str, chapter: str, felt: str | None) -> dict[str, str]:
    k = key(subject, chapter)
    if k not in {key(s, c) for s, c in _all_chapters(test)}:
        raise KeyError(k)
    feelings = dict(test.confidence or {})
    if felt in FEELINGS:
        feelings[k] = felt
    else:
        feelings.pop(k, None)
    test.confidence = feelings  # (a new dict: the JSON column only notices a reassignment)
    return feelings


def _all_chapters(test: MockTest) -> list[tuple[str, str]]:
    p = mock.pattern_of(test)
    return [(s, c) for s in p.subjects for c in chapters_of(_library_subject(s))]


# ---------------------------------------------------------------- after the test
def _level(share: float) -> str:
    return "strong" if share >= STRONG else "shaky" if share >= SHAKY else "gap"


def gap_map(user: User, test: MockTest) -> dict[str, Any] | None:
    result = test.result or {}
    if not result.get("chapters"):
        return None
    felt = test.confidence or {}
    rows = []
    for c in result["chapters"]:
        asked = c["correct"] + c["incorrect"] + c["unattempted"]
        if not asked:
            continue
        attempted = c["correct"] + c["incorrect"]
        # judged on the questions answered, not those left blank; one or none answered is too little to call a gap
        share = c["correct"] / attempted if attempted else 0.0
        level = _level(share) if attempted >= 2 else "untried"
        f = felt.get(key(c["subject"], c["chapter"]))
        flag = ("blind_spot" if f == "sure" and share < 0.5 else "hidden_strength" if f == "shaky" and share >= STRONG else None)
        ch = chapter_of(user, c["subject"], c["chapter"])
        rows.append({"subject": c["subject"], "chapter": c["chapter"], "chapter_id": ch.id if ch else None, "asked": asked, "attempted": attempted,
                     "correct": c["correct"], "wrong": c["incorrect"], "share": round(100 * share), "level": level, "felt": f, "flag": flag})
    order = {"gap": 0, "shaky": 1, "strong": 2, "untried": 3}
    rows.sort(key=lambda r: (r["flag"] != "blind_spot", order[r["level"]], r["share"], -r["asked"]))
    return {"chapters": rows, "steps": _steps(user, rows), "summary": _summary(rows)}


def _summary(rows: list[dict]) -> str:
    strong = sum(r["level"] == "strong" for r in rows)
    weak = [r["chapter"] for r in rows if r["level"] == "gap"]
    blind = [r["chapter"] for r in rows if r["flag"] == "blind_spot"]
    hidden = [r["chapter"] for r in rows if r["flag"] == "hidden_strength"]
    parts = [f"Solid on {strong} of {len(rows)} chapter{'' if len(rows) == 1 else 's'}."]
    untried = [r["chapter"] for r in rows if r["level"] == "untried"]
    shaky = [r["chapter"] for r in rows if r["level"] == "shaky"]
    if weak:
        parts.append(f"Real gaps: {_list(weak)}.")
    if shaky:
        parts.append(f"Shaky: {_list(shaky)}.")
    if untried:
        parts.append(f"Too few answers to judge: {_list(untried)}.")
    if blind:
        parts.append(f"You felt sure about {_list(blind)}, but the test disagrees: start there.")
    if hidden:
        parts.append(f"You know {_list(hidden)} better than you thought.")
    return " ".join(parts)


def _list(names: list[str], most: int = 3) -> str:
    names = names[:most]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _steps(user: User, rows: list[dict]) -> list[dict[str, Any]]:
    weak = [r for r in rows if r["level"] in ("gap", "shaky")]
    college = syllabus.family(syllabus.exam_of(user.exam_target)) == "college"
    if all(r["level"] == "untried" for r in rows):
        return [{"kind": "stretch", "title": "Answer more questions to see your gaps",
                 "detail": "Too few questions were answered to judge any chapter. Take the paper again and attempt every "
                           "question you can."}]
    if not weak:
        return [{"kind": "stretch", "title": "Every chapter held up: go for a longer paper",
                 "detail": "Take a bigger test, or a whole subject, to find what this one was too short to show."}]
    steps: list[dict[str, Any]] = []
    first = weak[0]
    if first["chapter_id"]:
        why = ("you felt sure about it but got " if first["flag"] == "blind_spot" else "you got ") + f"{first['correct']} of {first['attempted']} answered"
        steps.append({"kind": "revise", "title": f"Re-read {first['chapter']}", "chapter_id": first["chapter_id"],
                      "detail": f"Start here: {why}. Read the notes topic by topic, then the common mistakes."})
    by_subject: dict[str, list[str]] = {}
    for r in weak:
        subject = _library_subject(r["subject"])
        if r["chapter"] in chapters_of(subject):
            by_subject.setdefault(subject, []).append(r["chapter"])
    if by_subject:
        subject, chapters = max(by_subject.items(), key=lambda kv: len(kv[1]))
        chapters = chapters[:3]
        steps.append({"kind": "retest", "title": f"Re-test {_list(chapters)} in 10 questions", "subject": subject,
                      "chapters": chapters, "count": 10,
                      "detail": "Fresh questions on just these chapters, after you revise. This is how you know the gap has closed."})
    if college:
        steps.append({"kind": "senior", "title": f"Ask a senior about {first['chapter']}", "subject": _library_subject(first["subject"]),
                      "chapter": first["chapter"],
                      "detail": "Students who passed this course know what the exam asks from it. Ask, or read what they already said."})
    elif wrong := sum(r["wrong"] for r in rows):
        steps.append({"kind": "redo", "title": f"Redo the {wrong} question{'' if wrong == 1 else 's'} you got wrong",
                      "detail": "Wrong answers wait in your redo queue: solve each again without looking at the solution."})
    return steps[:3]
