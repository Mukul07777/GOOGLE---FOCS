"""Weak spots: from the result of a test taken anywhere to a plan for fixing what it showed.

1. Read. The student uploads the result (a screenshot of the score report, the marked paper, a PDF). A model that
   sees images pulls out the marks and every question that went wrong; without one, local OCR and a text model do
   the same from the text. With no AI at all the student marks the weak topics by hand.
2. Place. Each wrong question is placed in the syllabus: by the chapter or topic name printed with it, and
   otherwise by asking a model which chapter the question belongs to.
3. Fix. Every weak topic stays "open" until a re-check shows it is clear: a practice set on the topic (70% or
   better), a chapter test on Focs, or the student saying so. Until then it is in the daily plan, moves up the
   last-day revision order, and practice on it is aimed at what went wrong.

The student always reviews what was read before it is saved: a result is never trusted blind.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models._util import utcnow
from app.models.mock import MockTest
from app.models.weak import OutsideTest, WeakTopic
from app.services import topic_notes, vision
from app.services.llm import LLMUnavailable, llm
from app.services.syllabus import Chapter, Syllabus, Topic

log = logging.getLogger("focs.weak")

MAX_FILES, MAX_PAGES, MAX_FILE_BYTES = 6, 6, 10 * 1024 * 1024
CLEAR_AT = 0.7      # a re-check at 70% or better clears a weak spot…
CLEAR_MIN = 4       # …when it had at least this many questions
MAX_WEAK = 25       # per saved test

READ_PROMPT = """These images are a student's result from a {exam} test taken at {where}: a
score report, a question-wise analysis, a marked answer sheet or the question paper with marks. Read them carefully
and return ONLY a JSON object:
{{"test_name": the test's name if printed, else null,
  "score": marks obtained (a number) or null, "max_score": total marks (a number) or null,
  "subjects": [{{"name": "Physics", "score": 18, "max": 30}}],
  "questions": [{{"no": "12", "subject": "Physics" or null,
                 "area": the chapter or topic printed for this question, else what the question is evidently about, else null,
                 "status": "wrong" | "skipped" | "correct",
                 "about": at most 15 words on what the question asks, if its text is visible, else null}}],
  "weak_areas": [chapter or topic names the report itself lists as weak or needing improvement]}}
Rules: list a question only when the images show whether it was right, wrong or left out; never guess a status.
Copy numbers exactly. Use [] for anything the images do not show."""

PLACE_SYSTEM = """You place {what} in the syllabus. For each numbered item choose the ONE
chapter it belongs to from this list (id | subject | chapter):
{chapters}
Return JSON: {{"items": [{{"i": 0, "chapter_id": "<an id from the list>" or null}}]}}
Use null when {null_when}. Coaching names differ from syllabus names ("NLM" is Laws of Motion,
"GOC" is General Organic Chemistry): go by the subject matter."""
PLACE_NULL = "an item is too vague to place"


# ---------------------------------------------------------------- 1. read
def reader() -> str:
    """How a result would be read right now: by a model that sees it, from OCR text, or not at all."""
    return "vision" if vision.available() else "ocr" if llm.available else "none"


def _images(files: list[tuple[bytes, str]]) -> list[bytes]:
    pages: list[bytes] = []
    for data, content_type in files:
        pages += vision.pdf_pages(data, MAX_PAGES) if "pdf" in content_type else [vision.to_jpeg(data)]
    return pages[:MAX_PAGES]


def _ocr_text(images: list[bytes]) -> str:
    from app.services.ocr import decode_image, ocr_engine

    return "\n\n".join(ocr_engine.run(decode_image(img)).text for img in images).strip()


def read_result(files: list[tuple[bytes, str]], exam: str) -> tuple[dict[str, Any], str]:
    """What the uploaded result says, and how it was read ("vision" | "ocr"). Raises ValueError for unreadable
    files and LLMUnavailable when nothing can read them right now."""
    images = _images(files)
    if not images:
        raise ValueError("no pages")
    college = exam.startswith("B.Tech")
    prompt = READ_PROMPT.format(exam=exam, where="a college (a class test, a mid-semester or an end-semester paper)"
                                if college else "a coaching institute or school")
    if vision.available():
        try:
            return vision.read_json(images, prompt, "test_analysis"), "vision"
        except LLMUnavailable as exc:
            log.info("result: vision failed (%s); trying OCR", exc)
    text = _ocr_text(images)
    if len(text) < 20:
        raise LLMUnavailable("nothing readable in the upload")
    data = llm.json([{"role": "system", "content": prompt.replace("These images are", "This is the OCR text of")},
                     {"role": "user", "content": text[:9000]}], max_tokens=2500, temperature=0.0, feature="test_analysis")
    return data, "ocr"


# ---------------------------------------------------------------- 2. place
def _plain(text: str) -> set[str]:
    """Words of a chapter name or a printed area. "Laws" is noise in a topic title but tells "Laws of Motion" apart."""
    law = {"law"} if {"law", "laws"} & set((text or "").lower().replace("-", " ").replace("'", " ").split()) else set()
    return topic_notes._words(text) | law


def place(syl: Syllabus, subject: str | None, text: str) -> tuple[Chapter, Topic | None] | None:
    """The chapter (and topic, when one is named) a printed "area" refers to, or None when it isn't clear."""
    subject = subject if subject in syl.subjects else None
    found = topic_notes.match(syl, subject, text)
    if found:
        return found
    words = _plain(text)
    best: tuple[float, Chapter] | None = None
    for ch in syl.chapters:
        if subject and ch.subject != subject:
            continue
        name = _plain(ch.name)
        shared = name & words
        cover = len(shared) / max(1, len(name))
        if cover >= 0.75 and len(shared) / max(1, len(words)) >= 0.5 and (best is None or cover > best[0]):
            best = (cover, ch)
    return (best[1], None) if best else None


def _topic_in(ch: Chapter, text: str) -> Topic | None:
    """The topic of a chapter that a few words about a question most plainly point to."""
    words = topic_notes._words(text)
    names = {t.id: topic_notes._words(t.name) for t in ch.topics}
    best: tuple[int, Topic] | None = None
    for t in ch.topics:
        shared = names[t.id] & words
        # two words in common, or one that no other topic of the chapter has ("friction", "pulley")
        telling = len(shared) >= 2 or any(sum(w in n for n in names.values()) == 1 for w in shared)
        if telling and (best is None or len(shared) > best[0]):
            best = (len(shared), t)
    return best[1] if best else None


def ask_chapters(syl: Syllabus, items: list[dict[str, Any]], exam: str, what: str = "", null_when: str = PLACE_NULL,
                 feature: str = "test_analysis") -> dict[int, Chapter] | None:
    """Ask a model which chapter each still-unplaced item ({"subject", "text"}) belongs to: item index → chapter, for
    the items it could place. None when no model can be asked right now. ``what``: what the items are;
    ``null_when``: when an item belongs to no chapter."""
    if not items:
        return {}
    chapters = "\n".join(f"{c.id} | {c.subject} | {c.name}" for c in syl.chapters)
    listing = "\n".join(f"{i}. [{it.get('subject') or '?'}] {it['text']}" for i, it in enumerate(items))
    try:
        data = llm.json([{"role": "system", "content": PLACE_SYSTEM.format(what=what or f"questions from a {exam} test",
                                                                           null_when=null_when, chapters=chapters)},
                         {"role": "user", "content": listing}], max_tokens=1200, temperature=0.0, feature=feature)
    except LLMUnavailable as exc:
        log.info("could not place %d items: %s", len(items), exc)
        return None
    out: dict[int, Chapter] = {}
    for row in data.get("items") or []:
        try:
            ch = syl.by_id.get(str(row.get("chapter_id")))
            if ch is not None and 0 <= int(row["i"]) < len(items):
                out[int(row["i"])] = ch
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None and str(value).strip() != "" else None
    except (TypeError, ValueError):
        return None


def draft(syl: Syllabus, read: dict[str, Any], exam: str) -> dict[str, Any]:
    """What was read from a result → a draft for the student to check: the marks, the weak topics placed in the
    syllabus with how many questions each cost, and anything that could not be placed."""
    wrong = [q for q in read.get("questions") or [] if isinstance(q, dict) and str(q.get("status", "")).lower() in ("wrong", "skipped", "incorrect")]
    items = [{"subject": q.get("subject"), "text": " ".join(str(x) for x in (q.get("area"), q.get("about")) if x).strip(),
              "area": str(q.get("area") or ""), "label": f"Q{q.get('no')}" if q.get("no") else "", "count": 1} for q in wrong]
    items += [{"subject": None, "text": str(a), "area": str(a), "label": "", "count": 0}
              for a in read.get("weak_areas") or [] if str(a).strip()]
    items = [it for it in items if it["text"]][:120]

    placed: list[tuple[dict, Chapter, Topic | None]] = []
    pending: list[dict] = []
    for it in items:
        found = place(syl, it["subject"], it["area"]) if it["area"] else None
        if found:
            placed.append((it, found[0], found[1] or _topic_in(found[0], it["text"])))
        else:
            pending.append(it)
    asked = ask_chapters(syl, pending, exam) or {}
    unplaced = []
    for i, it in enumerate(pending):
        if i in asked:
            placed.append((it, asked[i], _topic_in(asked[i], it["text"])))
        else:
            unplaced.append(f"{it['label']} {it['text']}".strip()[:140])

    weak: dict[tuple[str, str | None], dict[str, Any]] = {}
    for it, ch, topic in placed:
        row = weak.setdefault((ch.id, topic.id if topic else None), {
            "chapter_id": ch.id, "chapter": ch.name, "subject": ch.subject, "topic_id": topic.id if topic else None,
            "topic": topic.name if topic else None, "misses": 0, "labels": []})
        row["misses"] += it["count"]
        if it["label"]:
            row["labels"].append(it["label"])
    rows = sorted(weak.values(), key=lambda r: -r["misses"])[:MAX_WEAK]
    for r in rows:
        r["misses"] = max(1, r["misses"])  # an area the report only names as weak still counts once
        r["note"] = ", ".join(r.pop("labels")[:12]) or None
    subjects = [{"name": str(s.get("name"))[:40], "score": _number(s.get("score")), "max": _number(s.get("max"))}
                for s in read.get("subjects") or [] if isinstance(s, dict) and s.get("name")][:6]
    return {"title": (str(read.get("test_name") or "").strip() or None), "score": _number(read.get("score")),
            "max_score": _number(read.get("max_score")), "subjects": subjects, "weak": rows, "unplaced": unplaced[:20],
            "questions_read": len([q for q in read.get("questions") or [] if isinstance(q, dict)]), "wrong_read": len(wrong)}


# ---------------------------------------------------------------- 3. fix
def save_test(db: Session, user_id: int, syl: Syllabus, *, title: str, taken_on: date | None, score: float | None,
              max_score: float | None, subjects: list[dict], weak: list[dict], source: str) -> OutsideTest:
    """Keep a test and its weak topics. A topic that is already an open weak spot isn't listed twice: it gains
    the new misses, which is exactly what moves it up everything that weighs weak spots."""
    test = OutsideTest(user_id=user_id, title=title, taken_on=taken_on, score=score, max_score=max_score, subjects=subjects, source=source)
    db.add(test)
    db.flush()
    open_now = {(w.chapter_id, w.topic_id): w for w in db.scalars(
        select(WeakTopic).where(WeakTopic.user_id == user_id, WeakTopic.status == "open"))}
    for item in weak[:MAX_WEAK]:
        ch = syl.by_id.get(item["chapter_id"])
        if ch is None:
            continue
        topic_id = item.get("topic_id") if any(t.id == item.get("topic_id") for t in ch.topics) else None
        misses = max(1, min(50, int(item.get("misses") or 1)))
        row = open_now.get((ch.id, topic_id))
        if row is None:
            row = WeakTopic(user_id=user_id, chapter_id=ch.id, topic_id=topic_id, misses=0, checks=[])
            db.add(row)
            open_now[(ch.id, topic_id)] = row
        row.misses = (row.misses or 0) + misses
        row.test_id, row.note = test.id, (item.get("note") or row.note)
    db.commit()
    return test


BLIND_SPOT_WEIGHT = 2  # a question answered "sure" and got wrong counts as two lost


def add_blind_spots(db: Session, user_id: int, syl: Syllabus, counts: dict[str, int], where: str) -> None:
    """Chapters where a Focs test found the student sure and wrong. They join (or strengthen) the open weak spots,
    each such question counting double, so they lead the daily plan and last-day revision until a re-check clears them."""
    open_now = {w.chapter_id: w for w in db.scalars(select(WeakTopic).where(WeakTopic.user_id == user_id, WeakTopic.status == "open",
                                                                         WeakTopic.topic_id.is_(None)))}
    for chapter_id, n in counts.items():
        if chapter_id not in syl.by_id:
            continue
        row = open_now.get(chapter_id)
        if row is None:
            row = WeakTopic(user_id=user_id, chapter_id=chapter_id, topic_id=None, misses=0, checks=[])
            db.add(row)
            open_now[chapter_id] = row
        row.misses = (row.misses or 0) + BLIND_SPOT_WEIGHT * n
        row.note = f"Sure, and wrong, in {where}: a blind spot"
    db.commit()


def record_check(db: Session, user_id: int, topic_id: str, correct: int, total: int, kind: str = "practice") -> list[WeakTopic]:
    """A practice set on a topic has been finished: note it on the weak spots it concerns (the topic itself, or its
    chapter listed as a whole) and clear them when the result shows the concept is clear."""
    chapter_id = topic_id.rsplit(".", 1)[0]
    rows = [w for w in db.scalars(select(WeakTopic).where(WeakTopic.user_id == user_id, WeakTopic.status == "open",
                                                          WeakTopic.chapter_id == chapter_id))
            if w.topic_id in (topic_id, None)]
    for w in rows:
        w.checks = [*(w.checks or []), {"at": utcnow().isoformat() + "Z", "kind": kind, "correct": correct, "total": total}][-10:]
        if w.topic_id == topic_id and total >= CLEAR_MIN and correct / total >= CLEAR_AT:  # a chapter needs a chapter test
            w.status, w.cleared_at = "cleared", utcnow()
    db.commit()
    return rows


def refresh(db: Session, user_id: int, syl: Syllabus) -> None:
    """Clear the weak spots that a chapter test taken on Focs since has shown to be fine."""
    rows = db.scalars(select(WeakTopic).where(WeakTopic.user_id == user_id, WeakTopic.status == "open")).all()
    if not rows:
        return
    oldest = min(w.created_at or utcnow() for w in rows)
    tests = db.execute(select(MockTest.submitted_at, MockTest.result).where(
        MockTest.user_id == user_id, MockTest.status == "submitted", MockTest.submitted_at > oldest)).all()
    changed = False
    for w in rows:
        ch = syl.by_id.get(w.chapter_id)
        if ch is None:
            continue
        correct = attempted = 0
        for submitted_at, result in tests:
            if submitted_at and submitted_at > (w.created_at or oldest):
                for row in (result or {}).get("chapters") or []:
                    subject = "Biology" if row.get("subject") in ("Botany", "Zoology") else row.get("subject")
                    if row.get("chapter") == ch.name and subject in (None, ch.subject):  # two courses can share a chapter name
                        correct += int(row.get("correct") or 0)
                        attempted += int(row.get("attempted") or 0)
        if attempted >= CLEAR_MIN + 1 and correct / attempted >= CLEAR_AT:
            w.status, w.cleared_at = "cleared", utcnow()
            w.checks = [*(w.checks or []), {"at": utcnow().isoformat() + "Z", "kind": "chapter_test", "correct": correct, "total": attempted}][-10:]
            changed = True
    if changed:
        db.commit()


def open_by_chapter(db: Session, user_id: int) -> dict[str, int]:
    """Chapter id → questions lost there that haven't been cleared yet (what last-day revision weighs)."""
    out: dict[str, int] = {}
    for chapter_id, misses in db.execute(select(WeakTopic.chapter_id, WeakTopic.misses).where(
            WeakTopic.user_id == user_id, WeakTopic.status == "open")):
        out[chapter_id] = out.get(chapter_id, 0) + (misses or 1)
    return out


def for_plan(db: Session, user_id: int, syl: Syllabus, today_start: datetime) -> list[dict[str, Any]]:
    """The weak spots the daily plan works on: the open ones, and any cleared today (so today's task shows done)."""
    rows = db.scalars(select(WeakTopic).where(WeakTopic.user_id == user_id)).all()
    out = []
    for w in rows:
        ch = syl.by_id.get(w.chapter_id)
        if ch is None or (w.status != "open" and not (w.cleared_at and w.cleared_at >= today_start)):
            continue
        topic = next((t for t in ch.topics if t.id == w.topic_id), None)
        out.append({"id": w.id, "chapter_id": ch.id, "chapter": ch.name, "subject": ch.subject, "misses": w.misses or 1,
                    "topic": {"id": topic.id, "name": topic.name} if topic else None, "cleared": w.status != "open"})
    return sorted(out, key=lambda r: (-r["misses"], r["id"]))


def aim(db: Session, user_id: int, topic_id: str) -> str:
    """A line for the question writer when the student practises a topic that is one of their weak spots."""
    chapter_id = topic_id.rsplit(".", 1)[0]
    rows = [w for w in db.scalars(select(WeakTopic).where(WeakTopic.user_id == user_id, WeakTopic.status == "open",
                                                          WeakTopic.chapter_id == chapter_id)) if w.topic_id in (topic_id, None)]
    if not rows:
        return ""
    lost = sum(w.misses or 1 for w in rows)
    return (f"\n\nThis topic is a weak spot for this student: they lost {lost} question{'s' if lost != 1 else ''} on it in a recent "
            "test. Keep exactly the counts asked for, and across the set check the core concept from different angles "
            "(direct use, a conceptual trap, an application), so the result shows whether the concept is now clear.")


def overview(db: Session, user_id: int, syl: Syllabus, library: set[str]) -> dict[str, Any]:
    refresh(db, user_id, syl)
    tests = {t.id: t for t in db.scalars(select(OutsideTest).where(OutsideTest.user_id == user_id))}
    rows = db.scalars(select(WeakTopic).where(WeakTopic.user_id == user_id)).all()
    recent = utcnow() - timedelta(days=30)
    items = []
    for w in rows:
        ch = syl.by_id.get(w.chapter_id)
        if ch is None or (w.status != "open" and (w.cleared_at or recent) < recent):
            continue
        topic = next((t for t in ch.topics if t.id == w.topic_id), None)
        test = tests.get(w.test_id)
        checks = w.checks or []
        items.append({
            "id": w.id, "status": w.status, "misses": w.misses or 1, "note": w.note,
            "chapter": {"id": ch.id, "name": ch.name, "subject": ch.subject},
            "topic": {"id": topic.id, "name": topic.name} if topic else None,
            "test": {"id": test.id, "title": test.title} if test else None,
            "last_check": checks[-1] if checks else None, "checks": len(checks),
            "notes_ready": (topic.id in library or bool(topic.notes)) if topic else False,
            "cleared_at": w.cleared_at.isoformat() + "Z" if w.cleared_at else None,
        })
    items.sort(key=lambda r: (r["status"] != "open", -r["misses"], r["id"]))
    return {
        "reader": reader(),
        "open": [i for i in items if i["status"] == "open"],
        "cleared": [i for i in items if i["status"] != "open"],
        "tests": [{"id": t.id, "title": t.title, "taken_on": t.taken_on.isoformat() if t.taken_on else None, "score": t.score,
                   "max_score": t.max_score, "subjects": t.subjects or [], "source": t.source,
                   "created_at": t.created_at.isoformat() + "Z" if t.created_at else None,
                   "weak": sum(1 for w in rows if w.test_id == t.id)}
                  for t in sorted(tests.values(), key=lambda t: t.created_at or utcnow(), reverse=True)],
        "limits": {"files": MAX_FILES, "clear_percent": round(CLEAR_AT * 100), "clear_min": CLEAR_MIN},
    }
