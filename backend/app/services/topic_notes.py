"""The notes library: pre-made detailed notes for every syllabus topic, and a last-day capsule for every chapter.

A note is written once (shipped in app/assets/notes/<exam>.json, pre-built with scripts/build_topic_notes.py, or
written by the AI the first time any student asks for it) and then served to everyone from the database, so the
library costs the same whether one student reads a note or ten thousand do. Notes typed into the syllabus JSON by
hand always win over generated ones.

Board notes from a live lecture link into the same library: ``match`` finds the syllabus topic a board is about.

Notes come with exam questions: ``exam_questions`` picks real past-paper questions (PYQs) on the topic from the
question bank, and when one exists while a note is being written it becomes the note's worked example. Nothing is
ever labelled a past question unless it is one from the bank, with the paper it was imported from.
"""
from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import BACKEND_DIR
from app.models.library import TopicNote
from app.models.mock import BankQuestion
from app.services.llm import LLMUnavailable, llm, restore_backslashes, wrap_formula_bullets
from app.services import syllabus
from app.services.syllabus import Chapter, Syllabus, Topic

log = logging.getLogger("focs.library")

SEED_DIR = BACKEND_DIR / "app" / "assets" / "notes"
RETIRE_AFTER_REPORTS = 3  # students who reported a mistake before a note is thrown away and written again
EXAM_LABEL = {"jee": "JEE (Main and Advanced)", "neet": "NEET UG", "ssc_cgl": "SSC CGL (Tier-I and Tier-II)", "college": "B.Tech (university semester exams)",
              "cbse": "CBSE school, NCERT textbooks"}


def _label(exam: str | None) -> str:
    """How to name a notes library (or, for a board, a student's exam) to the model."""
    return EXAM_LABEL.get(exam or "") or syllabus.label(exam)


# The parts of the prompts that differ between school-level entrance exams and university courses
VOICE = {
    "school": {
        "steps": "(for Biology and descriptive Chemistry: the mechanism,\nsequence or classification, step by step)",
        "level": "{exam}-level problem",
        "mistakes": " (the exam allows no calculator, so nothing about calculators)",
        "asks": "How {short} asks it",
        "asks_body": "2-4 bullets: the question patterns, the usual traps, and the NCERT line, table or diagram worth knowing (never\n"
                     "cite page numbers or years you are not certain of).",
        "standard": "accurate, standard and consistent with NCERT",
        "capsule_standard": "accurate and NCERT-consistent",
    },
    "college": {
        "steps": "(for a descriptive topic: the mechanism, algorithm or\nprocedure, step by step; for an algorithm or a "
                 "program, a short trace or a listing of at most 15 lines in a fenced code block)",
        "level": "problem of the kind a university end-semester paper sets",
        "mistakes": "",
        "asks": "How exams ask it",
        "asks_body": "2-4 bullets: how end-semester papers ask it (short notes, derivations, numericals, \"compare\" and \"justify\"\n"
                     "questions), the usual traps, and how GATE or placement interviews test it where that applies (never cite a\n"
                     "year, a paper or a page number you are not certain of).",
        "standard": "accurate and consistent with the standard textbooks of the course",
        "capsule_standard": "accurate and consistent with the standard textbooks",
    },
}


def _school_level(cls: int | None) -> str:
    """A school class's notes stay inside that class's NCERT book (Class 8 "Square Numbers" notes had brought in
    quadratic and Diophantine equations)."""
    if not cls:
        return ""
    return (f"\n\nThis is for Class {cls}. Use only what the Class {cls} NCERT book teaches: no method, notation or "
            f"idea from a higher class, and plain words a Class {cls} student reads easily."
            + (" Keep it under 300 words." if cls <= 5 else ""))


def _voice(exam: str) -> dict[str, str]:
    voice = VOICE["college" if exam == "college" else "school"]
    return {k: v.format(exam=_label(exam), short=exam.upper()) for k, v in voice.items()}

DETAILED_SYSTEM = """You are a senior {exam} teacher writing the detailed study notes for ONE syllabus topic. The
reader has just watched a lecture on it and wants the complete, correct picture in one place.

Topic: "{topic}"
Chapter: "{chapter}" ({where})
Other topics of this chapter, which have their own notes (mention them only where they connect): {siblings}

Write Markdown with EXACTLY these "## " sections, in this order (omit one only if it truly does not apply):
## In one line
One or two plain sentences: what this topic is and why it matters for {exam}.
## Core ideas
4-7 bullets, each "- **Idea** — explanation", building up from the basics.
## Formulas and definitions
A Markdown table with exactly three columns, | Formula or term | Meaning | Use when |. Write each formula itself in
the first column, as LaTeX inside $...$. Never put a "|" inside a formula
(write \\lvert x \\rvert for absolute values). For topics without formulas, tabulate the key terms or classes instead.
## How it works
The derivation or the reasoning in 4-8 short numbered steps {steps}.
## Worked example
One {level}. "**Given:**", "**Approach:**", numbered working, and a last line "**Answer:** ...".
Pick data that makes the arithmetic come out clean, state the value of every constant you use, and re-check every
step of the arithmetic before you write the answer.
## Common mistakes
3-5 bullets, each on ONE line: "- **Mistake:** what students get wrong **Instead:** the correct idea". Real
conceptual or procedural errors of this topic{mistakes}.
## {asks}
{asks_body}
## Quick recap
3-5 one-line bullets a student can revise in thirty seconds.

Rules: {standard}; SI units; state any value you use; no filler, no emojis, no
preamble and no closing remarks; 450-750 words; math in LaTeX ($...$ inline, $$...$$ for the key equations).
Reply with the Markdown only."""

BOARD_SYSTEM = """You are a senior {exam} teacher. A student captured a board from a lecture; below are the short
notes Focs made from it and the raw board text. Write the DETAILED version of these notes: everything on the board,
explained properly, plus what a student needs around it to really understand the idea.

Write Markdown with these "## " sections, in this order (omit one only if it truly does not apply):
## In one line
## Core ideas
4-7 bullets, each "- **Idea** — explanation".
## Formulas and definitions
A Markdown table with exactly three columns, | Formula or term | Meaning | Use when |. Write each formula itself in
the first column, as LaTeX inside $...$ (never a "|" inside a formula).
## How it works
The derivation or reasoning in short numbered steps.
## Worked example
One exam-level problem with "**Given:**", "**Approach:**", numbered working and a last line "**Answer:** ...".
If the board shows a problem, solve that one; otherwise pick data that works out to clean numbers. Re-check every
step of the arithmetic before you write the answer.
## Common mistakes
3-5 bullets, each on ONE line: "- **Mistake:** ... **Instead:** ...".
## Quick recap
3-5 one-line bullets.

Rules: stay on the board's topic; accurate and standard; no filler, no emojis, no preamble; 350-650 words; math in
LaTeX ($...$ inline, $$...$$ for key equations). Reply with the Markdown only."""

CAPSULE_SYSTEM = """You are a senior {exam} teacher. Write the LAST-DAY revision capsule for one chapter: what a
student who has already studied it should run through the day before the exam. No teaching from scratch.

Chapter: "{chapter}" ({where}). Its topics: {topics}

Write Markdown with EXACTLY these "## " sections, in this order:
## Must-know formulas
A Markdown table with exactly two columns, | Formula or fact | Use when |. Write each formula itself in the first
column, as LaTeX inside $...$ (never a "|" inside a formula). The 6-12 that actually get asked.
## Key points
5-8 one-line bullets: results, conditions, sign conventions, exceptions.
## Common mistakes
3-5 bullets, each on ONE line: "- **Mistake:** ... **Instead:** ...".
## Quick self-check
4 numbered questions, each followed on the next line by "   Answer: <short answer>".

Rules: {capsule_standard}; no filler, no emojis, no preamble; 220-380 words. Reply with the Markdown only."""


# ---------------------------------------------------------------- reading
def get(db: Session, exam: str, kind: str, ref_id: str) -> TopicNote | None:
    return db.scalar(select(TopicNote).where(TopicNote.exam == exam, TopicNote.kind == kind, TopicNote.ref_id == ref_id))


def ready(db: Session, exam: str, kind: str = "detailed") -> set[str]:
    """Ids that already have a note in the library."""
    return set(db.scalars(select(TopicNote.ref_id).where(TopicNote.exam == exam, TopicNote.kind == kind)))


# ---------------------------------------------------------------- writing
def _tidy(raw: str, min_words: int) -> str:
    """Model output → the Markdown we store, or LLMUnavailable when it isn't a usable note."""
    text = raw.strip()
    wrapped = re.match(r"^```(?:markdown|md)?[ \t]*\n", text)
    if wrapped and text.endswith("```"):  # the whole reply in one fence: unwrap it (fences inside a note are code, and stay)
        text = text[wrapped.end():-3].strip()
    start = text.find("## ")
    if start > 0:  # a preamble before the first section
        text = text[start:]
    text = restore_backslashes(wrap_formula_bullets(text))
    if len(re.findall(r"^## ", text, flags=re.MULTILINE)) < 3 or len(text.split()) < min_words:
        raise LLMUnavailable("the model did not return a complete note")
    return text


REVIEW_SYSTEM = """You are the second teacher who checks {exam} study notes before they are published to
thousands of students. Check the note below for errors of substance only (ignore style, length and formatting):
1. every formula, definition, value and stated fact is correct and standard;
2. the worked example: solve it yourself from the given data, step by step, and compare every intermediate number
   and the final answer with the note's;
3. each "Instead" under common mistakes really is the correct idea.
Return JSON: {{"ok": true or false, "problems": ["specific: what is wrong, and what it should be"]}}
"ok" is true only when nothing needs correcting; list at most 6 problems."""

FIX_SYSTEM = """You wrote the study note below. A second teacher found these problems in it:
{problems}
Correct exactly these problems (re-do any calculation that is affected, all the way to the final answer) and change
nothing else. Reply with the full corrected note in the same Markdown structure, and nothing but the note."""

REVIEW_ROUNDS = 2  # a note is corrected at most this many times before it is stored as it stands


def review(exam: str, note_md: str, writer: str) -> list[str] | None:
    """A different model checks the note. [] = nothing wrong, a list = what to correct,
    None = no second model could be reached (the note stays unchecked)."""
    try:
        data, _ = llm.json_with_model(
            [{"role": "system", "content": REVIEW_SYSTEM.format(exam=_label(exam))},
             {"role": "user", "content": note_md}],
            max_tokens=900, temperature=0.0, effort="medium", skip=frozenset({writer}), feature="notes_review")
    except LLMUnavailable as exc:
        log.info("library: review unavailable: %s", exc)
        return None
    problems = [str(p).strip() for p in data.get("problems") or [] if str(p).strip()][:6]
    return [] if data.get("ok") is True or not problems else problems


def _ask(system: str, user: str, max_tokens: int, min_words: int, feature: str) -> tuple[str, str]:
    raw, model = llm.chat_with_model([{"role": "system", "content": system}, {"role": "user", "content": user}],
                                     max_tokens=max_tokens, temperature=0.3, effort="medium", feature=feature)
    return _tidy(raw, min_words), model


def _checked(exam: str, note_md: str, writer: str, max_tokens: int, min_words: int) -> tuple[str, bool]:
    """Have a second model check a note meant for everyone, correcting what it finds. Returns (note, passed):
    ``passed`` is False when no second model was available or problems remained after the last correction."""
    for attempt in range(REVIEW_ROUNDS + 1):
        problems = review(exam, note_md, writer)
        if problems is None:
            return note_md, False
        if not problems:
            return note_md, True
        if attempt == REVIEW_ROUNDS:
            break
        log.info("library: correcting %d problem(s) the reviewer found", len(problems))
        try:
            raw, _ = llm.chat_with_model(
                [{"role": "system", "content": FIX_SYSTEM.format(problems="\n".join(f"- {p}" for p in problems))},
                 {"role": "user", "content": note_md}],
                max_tokens=max_tokens, temperature=0.1, effort="medium", feature="notes_review")
            corrected = _tidy(raw, min_words)
        except LLMUnavailable:
            return note_md, False
        if set(_sections(note_md)) - set(_sections(corrected)):
            log.info("library: a correction dropped a section; keeping the note as it was")
            return note_md, False  # a correction that loses part of the note is worse than the problem it fixed
        note_md = corrected
    return note_md, False


def _sections(note_md: str) -> list[str]:
    return [h.strip().lower() for h in re.findall(r"^## +(.+)$", note_md, flags=re.MULTILINE)]


PYQ_EXAMPLE = """

Use this real past exam question as the worked example. Start that section with the line "**{paper}**", quote the
question exactly as given, then solve it step by step. Its confirmed answer is: {answer}. Your working must reach it.
Question: {question}{options}"""


def write_topic(exam: str, chapter: Chapter, topic: Topic, pyq: dict[str, Any] | None = None) -> tuple[str, str, bool]:
    """Write the detailed notes of a topic with the AI and have a second model check them. ``pyq``: a real past
    question on the topic, to be solved as the note's worked example.
    Returns (markdown, model, checked); raises LLMUnavailable."""
    siblings = "; ".join(t.name for t in chapter.topics if t.id != topic.id) or "none"
    system = DETAILED_SYSTEM.format(exam=_label(exam), topic=topic.name, chapter=chapter.name, where=syllabus.place(chapter),
                                    siblings=siblings, **_voice(exam))
    system += _school_level(getattr(chapter, "cls", None)) if exam == "cbse" else ""
    ask = f'Write the detailed notes for "{topic.name}".'
    if pyq:
        options = "".join(f"\n({'ABCD'[i]}) {o}" for i, o in enumerate(pyq["options"] or []))
        answer = f"({'ABCD'[int(pyq['answer'])]}) {pyq['options'][int(pyq['answer'])]}" if pyq["options"] else pyq["answer"]
        ask += PYQ_EXAMPLE.format(paper=pyq["paper"], question=pyq["question"], options=options, answer=answer)
    note, model = _ask(system, ask, 2600, 220, "detailed_notes")
    note, checked = _checked(exam, note, model, 2600, 220)
    return note, model, checked


def write_capsule(exam: str, chapter: Chapter) -> tuple[str, str, bool]:
    system = CAPSULE_SYSTEM.format(exam=_label(exam), chapter=chapter.name, where=syllabus.place(chapter),
                                   topics="; ".join(t.name for t in chapter.topics), capsule_standard=_voice(exam)["capsule_standard"])
    note, model = _ask(system, f'Write the last-day capsule for "{chapter.name}".', 1500, 110, "revision_capsule")
    note, checked = _checked(exam, note, model, 1500, 110)
    return note, model, checked


def write_board(exam: str | None, topic: str | None, notes_md: str, board_text: str) -> str:
    """The detailed write-up of one captured board (for boards no library note covers)."""
    system = BOARD_SYSTEM.format(exam=_label(exam))
    user = f"Board topic: {topic or 'unknown'}\n\nShort notes:\n{notes_md[:3000]}\n\nRaw board text:\n\"\"\"\n{board_text[:2000]}\n\"\"\""
    note, model = _ask(system, user, 2400, 160, "detailed_notes")
    return _checked(exam or "exam", note, model, 2400, 160)[0]


def _store(db: Session, exam: str, kind: str, ref_id: str, content: str, model: str | None, checked: bool,
           source: str = "ai") -> TopicNote:
    row = TopicNote(exam=exam, kind=kind, ref_id=ref_id, content_md=content, model=model, source=source, checked=checked,
                    reported_by=[])
    db.add(row)
    try:
        db.commit()
    except IntegrityError:  # another student asked for the same note a moment earlier: theirs is as good
        db.rollback()
        row = get(db, exam, kind, ref_id) or row
    return row


def topic_note(db: Session, exam: str, chapter: Chapter, topic: Topic) -> tuple[str, bool, bool]:
    """The detailed notes of a topic: hand-written, from the library, or written now.
    Returns (markdown, written_now, checked)."""
    if topic.notes:
        return topic.notes, False, True
    row = get(db, exam, "detailed", topic.id)
    written = row is None
    if row is None:
        past = [q for q in exam_questions(db, exam, chapter, topic, limit=1) if q["real"] and q["match"] == "topic"]
        content, model, checked = write_topic(exam, chapter, topic, past[0] if past else None)
        row = _store(db, exam, "detailed", topic.id, content, model, checked)
    return row.content_md, written, bool(row.checked)


def capsule(db: Session, exam: str, chapter: Chapter) -> tuple[str, bool, bool]:
    """A chapter's last-day revision capsule, from the library or written now. Returns (markdown, written_now, checked)."""
    row = get(db, exam, "capsule", chapter.id)
    written = row is None
    if row is None:
        content, model, checked = write_capsule(exam, chapter)
        row = _store(db, exam, "capsule", chapter.id, content, model, checked)
    return row.content_md, written, bool(row.checked)


def report(db: Session, exam: str, kind: str, ref_id: str, user_id: int) -> bool:
    """A student says the note has a mistake. Once enough different students do, it is thrown away and written
    again on the next request. Returns True when that happened."""
    row = get(db, exam, kind, ref_id)
    if row is None:
        return False
    reporters = sorted({*(row.reported_by or []), user_id})
    if len(reporters) >= RETIRE_AFTER_REPORTS:
        db.delete(row)
        db.commit()
        log.info("library: retired %s %s/%s after %d reports", kind, exam, ref_id, len(reporters))
        return True
    row.reported_by = reporters
    db.commit()
    return False


# ---------------------------------------------------------------- exam questions that go with a note
REPORTED_OUT = 2  # the question bank retires a question two students reported


def _question_out(q: BankQuestion, match: str) -> dict[str, Any]:
    real = q.source == "pyq" and bool(q.paper)
    return {"id": q.id, "real": real, "paper": q.paper if real else None, "year": q.year if real else None, "match": match,
            "qtype": q.qtype, "difficulty": q.difficulty, "question": q.question, "options": q.options, "answer": q.answer,
            "solution": q.solution or "", **({"media": q.media} if q.media else {}), **({"hindi": q.hindi} if q.hindi else {})}


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def exam_questions(db: Session, exam: str, chapter: Chapter, topic: Topic | None = None, limit: int = 3,
                   solved_in: str = "") -> list[dict[str, Any]]:
    """Questions from the bank that show how the exam asks this topic (or, with no topic, this chapter): real past
    questions first, newest first. A question counts as "on the topic" when it shares the topic's distinctive
    words; with none of those, a couple from the same chapter are offered and marked as such.
    ``solved_in``: the note these go with. A question it already works through isn't offered again to try."""
    from app.services.question_bank import exam_family, own_first

    family = exam_family(exam, chapter.subject)  # Physics and Chemistry: JEE Main and NEET share their questions
    rows = db.scalars(select(BankQuestion).where(
        BankQuestion.subject == chapter.subject, BankQuestion.chapter == chapter.name,
        func.coalesce(BankQuestion.reports, 0) < REPORTED_OUT)).all()
    rows = [q for q in rows if (q.exam or "jee_main") in family]  # never a college or board question
    if solved_in:
        note = _squash(solved_in)
        rows = [q for q in rows if _squash(q.question)[:50] not in note]
    if not rows:
        return []
    order = lambda q: (own_first(exam, q.exam), q.source != "pyq", not q.verified, -(q.year or 0), q.id)  # noqa: E731
    if topic is None:
        return [_question_out(q, "chapter") for q in sorted(rows, key=order)[:limit]]

    words = {q.id: _words(f"{q.question} {q.solution or ''}") for q in rows}
    count = len(rows)
    weight = lambda w: math.log((count + 1) / (sum(w in ws for ws in words.values()) + 1)) + 0.2  # noqa: E731 (rare = telling)
    wanted = _words(topic.name)
    full = sum(weight(w) for w in wanted) or 1
    scored = []
    for q in rows:
        shared = wanted & words[q.id]
        score = sum(weight(w) for w in shared) / full
        if shared and score >= 0.4:
            scored.append((score, q))
    scored.sort(key=lambda sq: (order(sq[1])[0], -sq[0], order(sq[1])))
    if scored:
        return [_question_out(q, "topic") for _, q in scored[:limit]]
    return [_question_out(q, "chapter") for q in sorted(rows, key=order)[:2] if q.source == "pyq"]


# ---------------------------------------------------------------- seed (notes shipped with Focs)
def load_seed(db: Session) -> int:
    """Add the notes shipped in app/assets/notes/*.json that the library doesn't have yet. Idempotent."""
    if not SEED_DIR.exists():
        return 0
    added = 0
    for path in sorted(SEED_DIR.glob("*.json")):
        try:
            items: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("library: could not read %s: %s", path.name, exc)
            continue
        known = {(e, k, r) for e, k, r in db.execute(select(TopicNote.exam, TopicNote.kind, TopicNote.ref_id))}
        for it in items:
            key = (it.get("exam"), it.get("kind", "detailed"), it.get("ref_id"))
            if not all(key) or key in known or not str(it.get("content_md", "")).strip():
                continue
            db.add(TopicNote(exam=key[0], kind=key[1], ref_id=key[2], content_md=it["content_md"], source="seed",
                             model=it.get("model"), checked=bool(it.get("checked")), reported_by=[]))
            known.add(key)
            added += 1
    if added:
        db.commit()
        log.info("library: loaded %d notes shipped with Focs", added)
    return added


def export(db: Session, exam: str) -> list[dict[str, Any]]:
    rows = db.scalars(select(TopicNote).where(TopicNote.exam == exam).order_by(TopicNote.kind, TopicNote.ref_id)).all()
    return [{"exam": r.exam, "kind": r.kind, "ref_id": r.ref_id, "content_md": r.content_md, "model": r.model,
             "checked": bool(r.checked)} for r in rows]


# ---------------------------------------------------------------- which topic is this board about?
_GENERIC = set("""the a an and or of in on to for with from by its their into is are as at vs versus introduction intro
basics basic concept concepts overview notes note board lecture part types type example examples problem problems
numerical numericals question questions solved formula formulas derivation definition law laws theory method methods
application applications class chapter topic revision summary""".split())


def _words(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9]+", (text or "").lower().replace("'s", "")):
        if w in _GENERIC or (len(w) < 3 and not w.isdigit()):
            continue
        out.add(w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w)  # plurals
    return out


def match(syl: Syllabus, subject: str | None, title: str | None, body: str = "") -> tuple[Chapter, Topic] | None:
    """The syllabus topic a board is about, from its title (and its notes, to break ties). Deliberately strict:
    a board that only loosely resembles a topic gets its own write-up instead of the wrong library note."""
    name = _words(title or "")
    if not name:
        return None
    text = _words(body)
    chapters = [c for c in syl.chapters if c.subject == subject] if subject in syl.subjects else list(syl.chapters)
    best: tuple[float, Chapter, Topic] | None = None
    for ch in chapters:
        chapter_words = _words(ch.name)
        in_chapter = len(chapter_words & (name | text)) / max(1, len(chapter_words))
        for t in ch.topics:
            topic_words = _words(t.name)
            shared = topic_words & name
            if not topic_words or not shared:
                continue
            of_topic, of_title = len(shared) / len(topic_words), len(shared) / len(name)
            # one shared word is only a match when it is the whole of both names ("Power" is not "Power of a lens")
            enough = len(shared) >= 2 or (of_topic == 1 and of_title == 1)
            if not enough or max(of_topic, of_title) < 0.6:
                continue
            score = of_topic + of_title + 0.5 * in_chapter + 0.3 * len(topic_words & text) / len(topic_words)
            if best is None or score > best[0]:
                best = (score, ch, t)
    return (best[1], best[2]) if best else None
