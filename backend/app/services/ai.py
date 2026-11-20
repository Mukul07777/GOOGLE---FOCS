"""High-level AI features. Each function tries the LLM first and falls back to
deterministic offline logic (``offline.py``) so the product never hard-fails."""
from __future__ import annotations

import logging
import re
from typing import Any

from app.core.config import settings
from app.services import offline, syllabus
from app.services.math_text import clean_option
from app.services.llm import LLMUnavailable, fix_latex, llm, restore_backslashes, wrap_formula_bullets
from app.services.text_utils import clean_ocr, guess_subject

log = logging.getLogger("focs.ai")

SUBJECTS = "Physics | Chemistry | Mathematics | Biology | Computer Science | Economics | Commerce | General"

NOTES_SYSTEM = """You are Focs, a meticulous {exam} teacher. You receive the text of ONE frame of a lecture video
(blackboard, whiteboard, pen-tablet or slide): either OCR text, which can contain recognition errors, player/browser
UI text and fragments, or the board read exactly from the image. Reconstruct ONLY the academic content as crisp,
exam-oriented notes.

Rules:
- Ignore video-player UI, channel names, watermarks, timestamps, browser tabs, "subscribe", teacher/brand names.
- Fix obvious OCR mistakes using subject knowledge (e.g. "v2 = u2 + 2as" -> $v^2 = u^2 + 2as$), but never add
  facts the board does not support.
- Copy a question or problem statement exactly as the board states it.
- Markdown only. Math in LaTeX: $...$ inline, $$...$$ for important standalone equations.
- Let the board decide the shape: boards differ, so the notes must too. Use only the headings this board earns, in the
  order it was taught, from this list, and never a heading with nothing real under it:
  "### Definition" (a term the board defines, in one or two lines),
  "### Key ideas" (bullets, each "- **Idea** — what it means" when it has a name),
  "### Formulas" (bullets, each formula with what it is for),
  "### Derivation" (the board's own steps as a numbered list),
  "### Steps" (a method or process, as a numbered list),
  "### Compare" (a Markdown table, when the board sets two or more things side by side),
  "### Worked example" (the problem exactly as the board states it, then the board's own steps as a numbered list and
  its answer. Write no step, sign chart, interval, root or answer the board text doesn't contain, even when you could
  work it out: the teacher may still be writing, the notes are rewritten as the board grows, and a slip of yours
  would sit in a student's notes as if the teacher wrote it. Leave the section out when the board has no problem or
  it can't be read: never make up one of your own),
  "### Exam tip" (one line, only if the teacher gave one or it follows directly from the board).
- Open with one plain line saying what this board is about, unless the board is that one line.
- Length follows the board: a board with a line or two gets a sentence or two and no headings; a full board gets up to
  220 words. Never pad. No preamble, no closing remarks.

Grounding: write only what the board says. Never describe a diagram, graph or number line you were not given as text,
and never turn an interval, a coordinate or a mark on a line into a length, an overlap or any other number the board
doesn't state. Say nothing about the exam itself (its syllabus, paper pattern, marks, "asked in <year>") and name no
past-year paper: you can't check any of it.

Return a JSON object:
{{"is_lecture": true, "topic": "<= 6 words", "subject": "{subjects}",
  "notes_md": "...", "key_terms": ["..."], "formulas": ["LaTeX without $"]}}
If the text has no academic content, return {{"is_lecture": false}}."""

CHECKPOINT_SYSTEM = """You write one-question checkpoints for {exam} students. The lecture just moved from
"{prev}" to "{new}". Using ONLY the notes provided, write ONE MCQ that checks the single most important idea
of "{prev}". Use LaTeX ($...$) for math. Options must be plausible and must NOT start with letters like "A)".
Return JSON: {{"question": "...", "options": ["...", "...", "...", "..."], "explanation": "...", "answer_index": 0}}
Write the explanation first, solving the question step by step, then set answer_index to the option it reaches."""

QUIZ_SYSTEM = """You are an expert {exam} paper setter. Build a practice set from the study material.
Difficulty: {difficulty}. Match real {exam} patterns. Use LaTeX ($...$) for math. Options must NOT start with
letter prefixes. Every question must be answerable from the material plus standard syllabus knowledge.
Return JSON:
{{"topic": "<= 6 words", "subject": "{subjects}",
  "mcq": [{{"q": "...", "options": ["...", "...", "...", "..."], "explanation": "...", "answer_index": 0}}],
  "true_false": [{{"statement": "...", "answer": true, "explanation": "..."}}],
  "subjective": [{{"q": "...", "key_points": ["...", "..."], "model_answer": "..."}}]}}
Counts: {n_mcq} mcq, {n_tf} true_false, {n_subj} subjective.
For each mcq write the explanation first, solving it, then set answer_index to the option it reaches. Exactly one
option may be correct: check every other option fails, including every boundary and critical point (e.g. a zero of
the numerator in an inequality), before you finish. No two options may be the same value or statement written
differently (1 C/s and 1 C·s⁻¹, 0.5 and 1/2). In explanations name an option by its text, never by a number
("option 0", "option 4"). Never refer to a figure, picture or diagram: the student sees text only.{level}"""

# A second model checks each practice question before a student sees it (as mock questions are checked).
CHECK_QUIZ = """You check multiple-choice questions written for {exam} students. Solve each one yourself, carefully and
independently of the given key, then test every option on its own against the question as written: an option is
correct if it is a true answer to the question. The same value in another notation or unit form (1 C/s and
1 C·s⁻¹, 0.5 and 1/2) is a second correct option. List every correct option (there may be more than one, or none).
Also read the given explanation: "explanation_ok" is false if its working has a mistake, skips a case (such as a
critical point) or contradicts itself. Return JSON with one entry per question, in order:
{{"answers": [{{"n": 1, "correct": [<every correct option index, 0-3>], "explanation_ok": true,
  "working": "your own solution in 1-4 short sentences, LaTeX in $...$"}}]}}"""

EVALUATE_SYSTEM = """You are a fair but strict {exam} examiner. Grade the student's answer against the key points.
The answer may have been spoken and transcribed: ignore filler words, missing punctuation and speech-to-text slips
(a formula may be read out in words), and accept Hindi or Hinglish.
Return JSON: {{"score": 0-10 integer, "grade": "Excellent|Good|Needs work|Incorrect",
"points_covered": ["..."], "points_missed": ["..."],
"feedback": "2-3 sentences. Socratic: point at what to reconsider rather than giving the full answer."}}"""

TEACHBACK_SYSTEM = """You are a warm but exacting {exam} teacher. A student was asked to explain "{topic}" in their
own words, as if teaching a friend. The answer may have been spoken and transcribed: ignore filler words, missing
punctuation and speech-to-text slips (a formula may be read out in words), and accept Hindi or Hinglish. Judge how
well they understand the topic: against the reference notes when some are given, otherwise against standard
syllabus knowledge. This is a short spoken explanation, not a written derivation: full marks need the idea, the rule
or formula behind it and a sensible example, not every result of the topic. Reward correct ideas in any wording; a
confident but wrong statement costs more than a gap. Write math as LaTeX in $...$.
Return JSON: {{"score": 0-10 integer, "grade": "Excellent|Good|Needs work|Incorrect",
"points_covered": ["what they got right, at most 12 words each"],
"points_missed": ["at most 3: the most important things still missing or wrong, at most 12 words each"],
"feedback": "2-3 sentences said to the student: what was right, then the one idea to fix or add. Correct any wrong statement plainly."}}"""

COMPANION_SYSTEM = {
    "explain": "Answer clearly and directly, like the best {exam} teacher in India. Show the key step, and the formula "
               "only if the topic has one: never invent a formula.",
    "socratic": "Use the Socratic method: do NOT give the final answer. Ask 1-2 guiding questions and give a hint.",
    "simple": "Explain like the student is seeing this for the first time: an everyday analogy, then the idea.",
    "steps": "Solve or explain it as numbered steps a student can copy into their notebook: given, idea, working, "
             "a final line '**Answer:** …'. Name the formula used at each step.",
    "hinglish": "Answer in natural Hinglish (Hindi written in English letters, mixed with English technical terms), "
                "the way a friendly Indian coaching teacher talks: 'Dekho, torque basically ek turning effect hai…'. "
                "Keep formulas and terms in English. {tone}",
}
# "the way Indian students talk" brought a photo doubt's solution back opening "Yo, ek simple problem hai"
HINGLISH_TONE = ("Friendly but respectful, like a teacher speaking to a student: no slang such as yo, bro, yaar or "
                 "dude, and no hype.")

_SHEET_FORMULAS = """A Markdown table with its |---|---|---| line: | Formula | Meaning | Use when |  with LaTeX in $...$. Never put a "|" inside a
formula (write \\lvert x \\rvert for absolute values). Leave this section out when the lecture has no formulas; in a
subject of words (Biology, History, a language) use "## Key terms" instead, a table: | Term | Meaning |."""
_SHEET_CHECK = """numbered questions, each followed on the next line by "   Answer: <short answer>"."""
_SHEET_MISTAKE = """each "- **Mistake:** what students get wrong **Instead:** the correct idea"."""

# How much a sheet holds follows how much was studied: a ten-minute lecture isn't a two-hour one with less in it.
SHEET_SHAPES = {
    "short": {"max_tokens": 1300, "cards": "3-5", "shape": f"""This was a short lecture, so write a half-page quick recap with these "## " sections, in order:
## In one line
One sentence: what this lecture was about.
## Key points
3-5 bullets, each "- **Point** — one-line explanation".
## Formula sheet
{_SHEET_FORMULAS}
## Quick self-check
2 {_SHEET_CHECK}"""},
    "standard": {"max_tokens": 2200, "cards": "6-10", "shape": f"""Write a one-page revision sheet with these "## " sections, in order, leaving out any the
lecture truly has nothing for:
## Overview
2-3 plain sentences: what the lecture covered and why it matters.
## Key concepts
4-8 bullets, each "- **Concept** — one-line explanation".
## Compare
A Markdown table, only when the lecture sets two or more things side by side.
## Formula sheet
{_SHEET_FORMULAS}
## Common mistakes
2-5 bullets, {_SHEET_MISTAKE}
## Memory tricks
1-3 bullets with a mnemonic or intuition (skip if none is natural).
## Quick self-check
3-5 {_SHEET_CHECK}
## Practise next
2-4 bullets of concrete next steps: problem types and chapter topics from THIS lecture."""},
    "long": {"max_tokens": 2600, "cards": "10-14", "shape": f"""This was a long lecture, so a flat list would bury it. Write a study guide that follows the lecture's own parts,
with these "## " sections, in order:
## Overview
3-4 plain sentences: the journey of the lecture, from where it began to where it ended.
## Lecture map
A numbered list of the 3-6 parts the lecture falls into, in the order taught, each "1. **Part name** — what it covers".
## Part 1: <part name>
One section like this for each part of the map, with its own number: 3-6 bullets, each "- **Concept** — one-line
explanation", with that part's key formula in $...$ where it has one.
## Formula sheet
{_SHEET_FORMULAS}
## Common mistakes
3-6 bullets, {_SHEET_MISTAKE}
## Quick self-check
5-8 {_SHEET_CHECK} Cover every part of the lecture, not just the start.
## Practise next
3-5 bullets of concrete next steps: problem types and chapter topics from THIS lecture."""},
}
SHEET_CHARS = 9000  # what a sheet reads of a lecture: with its answer it must stay under the free tier's one-request limit


def sheet_size(notes: list[dict[str, str]]) -> str:
    """How big a sheet this lecture earns, from how much was actually taught."""
    words = sum(len((n.get("notes_md") or "").split()) for n in notes)
    if len(notes) <= 3 and words < 350:
        return "short"
    return "long" if len(notes) >= 14 or words >= 2200 else "standard"


def lecture_material(notes: list[dict[str, str]], limit: int = SHEET_CHARS) -> str:
    """The notes of a whole lecture within ``limit``: every board gets its share, so the end of a long lecture isn't
    dropped. A board that needs less leaves its share to the others."""
    bodies = [n.get("notes_md") or "" for n in notes]
    room = limit - sum(len(n.get("topic") or "Board") + 6 for n in notes)
    left, share = list(range(len(bodies))), max(0, room) // max(1, len(bodies))
    while True:
        fits = [i for i in left if len(bodies[i]) <= share]
        if not fits or len(fits) == len(left):
            break
        room -= sum(len(bodies[i]) for i in fits)
        left = [i for i in left if i not in fits]
        share = max(0, room) // len(left)
    out = [f"## {n.get('topic') or 'Board'}\n{b if len(b) <= share or i not in left else b[:share]}"
           for i, (n, b) in enumerate(zip(notes, bodies))]
    return "\n\n".join(out)


SUMMARY_SYSTEM = """You turn a lecture's board notes into a revision sheet for a {exam} student revising the night
before the exam. Be concrete and exam-focused; no filler, no emojis. summary_md is one Markdown string holding the whole
sheet, every "## " section below: put nothing in any other key.

{shape}

Grounding: use only what the lecture notes say, and stay in the lecture's own subject. The student's exam is
{exam}, but say nothing about that exam's syllabus, paper pattern, marks or weightage, never claim a topic is
"essential", "important" or "frequently asked" for it, and never cite a past-year question or a year ("a 2023
question"): you can't check any of it. Never put a number in the sheet that the notes don't state.

Return JSON:
{{"title": "<= 8 words, naming what was taught, never just 'Revision sheet'", "subject": "{subjects}", "summary_md": "...",
  "key_formulas": ["LaTeX without $"],
  "flashcards": [{{"front": "question", "back": "answer"}}]}}
Write {cards} flashcards that test understanding, not trivia."""

FLASHCARD_SYSTEM = """Create {n} spaced-repetition flashcards for a {exam} student from the material.
Each card tests ONE idea; fronts are questions, backs are short answers. LaTeX ($...$) for math.
Return JSON: {{"cards": [{{"front": "...", "back": "..."}}]}}"""


def _exam(exam: str | None) -> str:
    return syllabus.label(exam)


def _level(exam: str | None) -> str:
    """For a school class: keep questions inside that class's NCERT book and readable by a child of that age (the
    28 October test found scientific notation in Class 5 and Diophantine equations in Class 8 notes)."""
    m = re.fullmatch(r"cbse_(\d+)", exam or "")
    if not m:
        return ""
    n = int(m.group(1))
    words = 12 if n <= 2 else 20 if n <= 5 else 30
    return (f"\nThis student is in Class {n}. Use only what the Class {n} NCERT book teaches: no method, notation or "
            f"idea from a higher class. Keep every question under {words} words, in simple English a Class {n} "
            "student reads easily.")


def _subject_list(exam: str | None) -> list[str] | None:
    """The subjects a board can be filed under: a college student's are the courses of their branch, everyone else
    with a syllabus has its subjects (no Maths for NEET). None: no syllabus, so the general list."""
    branch = syllabus.exam_of(exam)
    if branch is None:
        return None
    plan = syllabus.get(branch)
    if syllabus.is_college(branch):
        return [*dict.fromkeys(s for _, subjects in plan.semesters for s in subjects), "General"]
    return [*plan.subjects, "General"]


def _subjects(exam: str | None) -> str:
    allowed = _subject_list(exam)
    return " | ".join(allowed) if allowed else SUBJECTS


def fit_subject(subject: str | None, exam: str | None) -> str | None:
    """A subject from the model, the keyword guess or a shared note, kept only if it belongs to the student's exam."""
    allowed = _subject_list(exam)
    if allowed is None or not subject or syllabus.is_college(syllabus.exam_of(exam)):  # (colleges add courses of their own)
        return subject
    return next((s for s in allowed if s.lower() == subject.strip().lower()), "General")


def generate_notes(ocr_text: str, exam: str | None, prev_topic: str | None = None, offline_only: bool = False,
                   patient: bool = True, board: str | None = None) -> dict[str, Any]:
    """``patient``: written in the background, so it may wait a moment for the cheap model (not when a student pressed a button).
    ``board``: the same frame read by the vision model; when given, the notes are written from it instead of the OCR text."""
    cleaned = clean_ocr(ocr_text)
    if not cleaned and not board:  # (a Hindi board: no OCR text, but the vision model read it)
        return {"is_lecture": False, "source": "filter"}
    if offline_only:  # AI allowance used up: basic notes until it resets
        return offline.notes(cleaned)
    context = f'Previous board topic: "{prev_topic}". Reuse that topic name if this board continues it.\n\n' if prev_topic else ""
    text = (f"Board, read from the frame image (exact: trust every symbol, fraction and sign):\n\"\"\"\n{board[:2500]}\n\"\"\""
            if board else "OCR text (handwriting and maths often come out garbled: keep what is clearly readable and "
                          "leave out what isn't, rather than guessing what an expression was):\n"
                          f"\"\"\"\n{cleaned[:2500]}\n\"\"\"")
    # Not the light model: on real boards (2026-10-19) it worked out an answer the board hadn't reached and got it
    # wrong, and called a clear "Physical Quantity / Length - Scale / Mass - Weighing machine" board not a lecture.
    # The bigger one costs about Rs 0.01 more a board.
    light = frozenset(m.strip() for m in settings.LLM_LIGHT_MODEL.split(",") if m.strip())
    system = NOTES_SYSTEM.format(exam=_exam(exam), subjects=_subjects(exam)) + (BOARD_SHOWN if board else "")
    try:
        data = llm.json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": context + text},
            ],
            max_tokens=900, temperature=0.2, skip=light, feature="board_notes", patient=patient,
        )
        if not data.get("is_lecture", True) or not str(data.get("notes_md", "")).strip():
            if board:  # the vision model found academic content (it returns nothing otherwise): keep the board
                return offline.notes(board)
            return {"is_lecture": False, "source": "ai"}
        md = restore_backslashes(wrap_formula_bullets(str(data["notes_md"]).strip()))
        return {
            "is_lecture": True,
            "topic": str(data.get("topic") or "Untitled board")[:80],
            "subject": str(data.get("subject") or guess_subject(cleaned))[:40],
            "notes_md": with_board(md, board) if board else md,
            "key_terms": [str(t) for t in data.get("key_terms", [])][:12],
            "formulas": [str(f) for f in data.get("formulas", [])][:12],
            "source": "ai",
        }
    except LLMUnavailable as exc:
        log.info("notes fallback: %s", exc)
        return offline.notes(board or cleaned)


# With the board read off the frame, its working goes into the notes word for word and the model writes around it.
# Asked only to copy the board's steps, both gpt-oss models still added sign charts of their own, wrong in up to three
# intervals on a real board (2026-10-19): a slip that would sit in a student's notes as if the teacher wrote it.
BOARD_SHOWN = """

Focs adds the board's own text to the notes word for word, in a section of its own. So don't copy the board out,
write no worked example and solve, factorise or chart nothing yourself: give the one-line context, key ideas,
formulas and exam tip that help a student understand what the board shows."""

# what the board section replaces: the model's own copy of the board, and its worked example (asked for none, it
# still wrote one, copying the board a second time)
_OWN_BOARD = re.compile(r"\n*#{2,4} (?:On the board|Worked example)\b.*?(?=\n#{2,4} |\Z)", re.S)
_MD_MARK = re.compile(r"^(#|>|[-+*](?=\s|$))")  # a heading, quote or bullet: escaped with a backslash in front
_MD_NUMBERED = re.compile(r"^(\d+)([.)])(?=\s)")  # "1. ...": the backslash goes before the dot


_DOLLAR = re.compile(r"(?<!\\)\$")
_COMMAND = re.compile(r"\\[a-zA-Z]+")


_DISPLAY = re.compile(r"(?<!\\)\$\$")
_SIGN_ROW = re.compile(r"^[\s|+\-−]+$")  # a sign chart's row of signs: "+ − + −" (OCR often loses the spaces)


def _sign_row(line: str) -> str | None:
    """A row of a sign chart, spaced out and kept as code so it reads as the board wrote it, not as "+ −+−++"."""
    if not _SIGN_ROW.match(line):
        return None
    signs = [c for c in line if c in "+-−|"]
    if sum(c != "|" for c in signs) < 3:
        return None
    return "`" + "  ".join("−" if c == "-" else c for c in signs) + "`"


def tidy_math(md: str) -> str:
    """Notes as they are saved: in each paragraph, a "$$" with no partner (a stray "$$\\ne v" once opened display
    maths that swallowed the rest of the note) is dropped, then a lone "$" is closed at the paragraph's end."""
    out = []
    for para in md.split("\n\n"):
        if para.lstrip().startswith("```"):
            out.append(para)
            continue
        if len(_DISPLAY.findall(para)) % 2:
            *head, tail = _DISPLAY.split(para)
            para = "$$".join(head) + tail  # the last "$$" is the unmatched one
        if len(_DOLLAR.findall(_DISPLAY.sub("", para))) % 2:
            para += "$"
        out.append(para)
    return "\n\n".join(out)


def _literal(line: str) -> str:
    """One board line as a paragraph of its own that renders as written: its maths closed on the line (a reading once
    opened "$\\# \\text{ Trick: }..." and never closed it, and the maths ran on through the next lines), LaTeX outside
    any $...$ wrapped in one, and no Markdown heading or list made of it."""
    if (row := _sign_row(line)) is not None:
        return row
    if len(_DISPLAY.findall(line)) % 2:
        line = _DISPLAY.sub("", line)  # an unmatched "$$" on a board line: its maths stays inline
    dollars = len(_DOLLAR.findall(line))
    if dollars % 2:
        line += "$"
    elif not dollars and _COMMAND.search(line):
        line = f"${line}$"
    if _MD_NUMBERED.match(line):
        return _MD_NUMBERED.sub(r"\1\\\2", line, count=1)
    return "\\" + line if _MD_MARK.match(line) else line


def with_board(notes_md: str, board: str) -> str:
    """The notes with the board's text as a section of its own ("### On the board"), before the exam tip. Each line
    is a paragraph (a trailing-spaces line break didn't survive rendering), and a line that Markdown would read as a
    heading or a list ("# Trick", "+ - + -") is escaped."""
    lines = [ln.strip() for ln in board.splitlines() if ln.strip()]
    if not lines:
        return notes_md
    notes_md = _OWN_BOARD.sub("", notes_md)
    body = "\n\n".join(_literal(ln) for ln in lines)
    section = f"### On the board\n{body}"
    at = notes_md.find("### Exam tip")
    if at < 0:
        return f"{notes_md.rstrip()}\n\n{section}"
    return f"{notes_md[:at].rstrip()}\n\n{section}\n\n{notes_md[at:]}"


def checkpoint(prev_notes_md: str, prev_topic: str, new_topic: str, exam: str | None,
               offline_only: bool = False, language: str | None = None) -> dict[str, Any] | None:
    if offline_only:
        return offline.checkpoint(prev_notes_md, prev_topic)
    try:
        data, model = llm.json_with_model(
            [
                {"role": "system", "content": _in(CHECKPOINT_SYSTEM.format(exam=_exam(exam), prev=prev_topic, new=new_topic), language)},
                {"role": "user", "content": prev_notes_md[:2500]},
            ],
            max_tokens=500, temperature=0.3, tier="light", feature="checkpoint", patient=True,
        )
        q = _sound_question(data, exam, model)
        if q is None:
            return None  # no question beats a wrong one
        return {**q, "topic": prev_topic, "source": "ai"}
    except (LLMUnavailable, ValueError, TypeError) as exc:
        log.info("checkpoint fallback: %s", exc)
        return offline.checkpoint(prev_notes_md, prev_topic)


def _sound_question(data: dict[str, Any], exam: str | None, generator: str) -> dict[str, Any] | None:
    """One generated multiple-choice question, read for its shape and then solved by a second model: None when it is
    malformed or the checker finds no correct option, a second one, or a flaw in the working. (A pop quiz once had no
    right answer among its options and marked a wrong one "Spot on".)"""
    opts = [clean_option(o) for o in data.get("options", [])][:4]
    try:
        idx = int(data.get("answer_index", 0))
    except (TypeError, ValueError):
        raise LLMUnavailable("malformed question")
    if len(opts) != 4 or not 0 <= idx < 4 or not data.get("question") or len(set(opts)) < 4:
        raise LLMUnavailable("malformed question")
    q = {"q": str(data["question"]).strip(),
         "options": opts, "answer_index": idx, "explanation": str(data.get("explanation", ""))}
    kept = _checked_mcqs([q], exam, generator)
    if not kept:
        return None
    k = kept[0]
    return {"question": k["q"], "options": k["options"], "answer_index": k["answer_index"], "explanation": k["explanation"],
            "checked": k.get("checked", False)}


def generate_quiz(material: str, exam: str | None, difficulty: str = "medium",
                  n_mcq: int = 5, n_tf: int = 3, n_subj: int = 1, language: str | None = None,
                  _topping_up: bool = False) -> dict[str, Any]:
    try:
        data, model = llm.json_with_model(
            [
                {"role": "system", "content": _in(QUIZ_SYSTEM.format(exam=_exam(exam), difficulty=difficulty, subjects=_subjects(exam), level=_level(exam),
                                                                 n_mcq=n_mcq, n_tf=n_tf, n_subj=n_subj), language)},
                {"role": "user", "content": f"Study material:\n{material[:6000]}"},
            ],
            max_tokens=2600, temperature=0.4, feature="practice_set",
        )
        quiz = offline.sanitize_quiz(data)
        quiz["mcq"] = _checked_mcqs(quiz["mcq"], exam, model)
        quiz["true_false"] = _checked_statements(quiz["true_false"], exam)
        for _ in range(0 if _topping_up else 2):  # the checker dropped some: write the missing ones again
            need_mcq, need_tf = n_mcq - len(quiz["mcq"]), n_tf - len(quiz["true_false"])
            if need_mcq <= 0 and need_tf <= 0:
                break
            more = generate_quiz(material, exam, difficulty, max(need_mcq, 0), max(need_tf, 0), 0, language, _topping_up=True)
            if more.get("source") != "ai":
                break
            quiz["mcq"] = [*quiz["mcq"], *more["mcq"]][:n_mcq]
            quiz["true_false"] = [*quiz["true_false"], *more["true_false"]][:n_tf]
        if not quiz["mcq"] and not quiz["true_false"]:
            raise LLMUnavailable("empty quiz")
        quiz["source"] = "ai"
        return quiz
    except LLMUnavailable as exc:
        log.info("quiz fallback: %s", exc)
        return offline.quiz(material, n_mcq, n_tf, n_subj)


def _check_round(asked: str, system: str, n: int, skip: frozenset[str]) -> tuple[dict[int, dict], str]:
    """One checking model's verdicts, by question number, and the model that gave them. Raises LLMUnavailable."""
    data, model = llm.json_with_model([{"role": "system", "content": system}, {"role": "user", "content": asked}],
                                      max_tokens=500 + 300 * n, temperature=0.0, effort="medium", skip=skip,
                                      feature="question_verify")
    rows = {}
    for i, r in enumerate(data.get("answers") or [], 1):
        if isinstance(r, dict):
            try:
                rows[int(r.get("n", i))] = r
            except (TypeError, ValueError):
                continue
    return rows, model


def _single(row: dict | None) -> int | None:
    """The one option a checker found correct, or None when it found none, several, or said nothing usable."""
    try:
        correct = {int(c) for c in (row or {}).get("correct") or []}
    except (TypeError, ValueError):
        return None
    return next(iter(correct)) if len(correct) == 1 and 0 <= next(iter(correct)) < 4 else None


def _checked_mcqs(mcq: list[dict[str, Any]], exam: str | None, generator: str) -> list[dict[str, Any]]:
    """Each question solved by a second model. Agreeing with the key: kept (with the checker's working when the
    explanation was flawed). Naming one other option: a third model breaks the tie, and the question is kept with
    whichever key two of the three agree on (dropping every disputed question left practice sets three questions
    short). No correct option, several, or no agreement: dropped. No second model reachable: kept, "checked": False."""
    if not mcq:
        return mcq

    def ask(items: list[dict[str, Any]]) -> str:
        return "\n\n".join(f"Question {n}:\n{m['q']}\n\nOptions:\n" + "\n".join(f"{i}. {o}" for i, o in enumerate(m["options"]))
                           + f"\n\nGiven key: {m['answer_index']}\nGiven explanation: {m['explanation']}"
                           for n, m in enumerate(items, 1))

    system = CHECK_QUIZ.format(exam=_exam(exam))
    try:
        rows, checker = _check_round(ask(mcq), system, len(mcq), frozenset({generator}))
    except LLMUnavailable as exc:
        log.info("practice check unavailable: %s", exc)
        return [{**m, "checked": False} for m in mcq]
    kept: list[dict[str, Any]] = []
    for n, m in enumerate(mcq, 1):
        row = rows.get(n)
        j = _single(row)
        working = str((row or {}).get("working") or "").strip()
        if j == m["answer_index"]:
            if row.get("explanation_ok") is False and not working:  # right key, wrong working, nothing to replace it
                log.info("practice question dropped, flawed explanation: %.80s", m["q"])
                continue
            kept.append({**m, "explanation": working if row.get("explanation_ok") is False else m["explanation"], "checked": True})
        elif j is not None:
            try:
                third, _ = _check_round(ask([m]), system, 1, frozenset({generator, checker}))
            except LLMUnavailable:
                third = {}
            k = _single(third.get(1))
            if k == j:  # two solvers agree the key was wrong: re-key, with the working that reached it
                kept.append({**m, "answer_index": j, "explanation": working or str(third[1].get("working") or ""), "checked": True})
            elif k == m["answer_index"]:
                kept.append({**m, "checked": True})
            else:
                log.info("practice question dropped, no agreement: %.80s", m["q"])
        else:
            log.info("practice question dropped by the checker: %.80s", m["q"])
    return kept


CHECK_TF = """You check true/false statements written for {exam} students. Decide each one yourself, carefully and
independently of the given key: "true" is whether the statement, exactly as written, is true. Give the reason in one
or two sentences (LaTeX in $...$). Return JSON with one entry per statement, in order:
{{"answers": [{{"n": 1, "true": true, "reason": "..."}}]}}"""


def _checked_statements(items: list[dict[str, Any]], exam: str | None) -> list[dict[str, Any]]:
    """True/false statements checked like multiple-choice questions: a second model decides each; when it disagrees
    with the key a third breaks the tie, and the statement keeps the verdict two of three reached, with its reason."""
    if not items:
        return items

    def ask(ts: list[dict[str, Any]]) -> str:
        return "\n\n".join(f"Statement {n}: {t['statement']}\nGiven key: {'true' if t['answer'] else 'false'}"
                           for n, t in enumerate(ts, 1))

    system = CHECK_TF.format(exam=_exam(exam))
    try:
        rows, checker = _check_round(ask(items), system, len(items), frozenset())
    except LLMUnavailable as exc:
        log.info("true/false check unavailable: %s", exc)
        return items
    kept = []
    for n, t in enumerate(items, 1):
        row = rows.get(n) or {}
        verdict = row.get("true")
        if not isinstance(verdict, bool):
            continue
        if verdict == t["answer"]:
            kept.append(t)
            continue
        try:
            third, _ = _check_round(ask([t]), system, 1, frozenset({checker}))
        except LLMUnavailable:
            third = {}
        tie = (third.get(1) or {}).get("true")
        if tie is verdict:
            kept.append({**t, "answer": verdict, "explanation": str(row.get("reason") or (third[1].get("reason") or ""))})
        elif tie is t["answer"]:
            kept.append(t)
    return kept


def evaluate_answer(question: str, answer: str, key_points: list[str], model_answer: str, exam: str | None,
                    language: str | None = None) -> dict[str, Any]:
    try:
        data = llm.json(
            [
                {"role": "system", "content": _in(EVALUATE_SYSTEM.format(exam=_exam(exam)), language)},
                {"role": "user", "content": f"Question: {question}\nKey points: {key_points}\n"
                                            f"Model answer: {model_answer}\nStudent answer: {answer}"},
            ],
            max_tokens=500, temperature=0.2, feature="grade_answer",
        )
        data["score"] = max(0, min(10, int(float(data.get("score", 0)))))
        data.setdefault("grade", "Good" if data["score"] >= 6 else "Needs work")
        data.setdefault("points_covered", []); data.setdefault("points_missed", []); data.setdefault("feedback", "")
        data["source"] = "ai"
        return data
    except (LLMUnavailable, ValueError, TypeError) as exc:
        log.info("evaluate fallback: %s", exc)
        return offline.evaluate(answer, key_points)


def _graded(data: dict[str, Any]) -> dict[str, Any]:
    """Model grading → exactly what the UI shows."""
    score = max(0, min(10, int(float(data.get("score", 0)))))
    return {"score": score, "grade": str(data.get("grade") or ("Good" if score >= 6 else "Needs work")),
            "points_covered": [str(p) for p in data.get("points_covered") or []][:6],
            "points_missed": [str(p) for p in data.get("points_missed") or []][:6],
            "feedback": str(data.get("feedback") or ""), "source": "ai"}


def teach_back(topic: str, answer: str, reference_md: str, exam: str | None, language: str | None = None) -> dict[str, Any]:
    """Grade a topic explained back in the student's own words. Without the AI it can only be compared with the
    reference notes; with neither there is nothing honest to say, so LLMUnavailable is raised."""
    user = f"Student's explanation:\n\"\"\"\n{answer}\n\"\"\""
    if reference_md.strip():
        user = f"Reference notes:\n{reference_md[:5000]}\n\n{user}"
    try:
        data = llm.json([{"role": "system", "content": _in(TEACHBACK_SYSTEM.format(exam=_exam(exam), topic=topic), language)},
                         {"role": "user", "content": user}], max_tokens=600, temperature=0.2, feature="grade_answer")
        graded = _graded(data)
        graded["points_missed"] = graded["points_missed"][:3]
        return graded
    except (ValueError, TypeError) as exc:
        log.info("teach-back: malformed grading: %s", exc)
        raise LLMUnavailable("malformed grading") from exc
    except LLMUnavailable as exc:
        key_points = offline.key_points(reference_md)
        if not key_points:
            raise
        log.info("teach-back fallback: %s", exc)
        return offline.evaluate(answer, key_points)


# The mother tongues a student can learn in, each in its own script: code -> (name, script, a slip to warn against).
# Marathi shares Devanagari with Hindi, and the model drifts into Hindi unless told which words give it away.
MOTHER_TONGUES = {
    "hi": ("Hindi", "Devanagari", ""),
    "mr": ("Marathi", "Devanagari", " Marathi, not Hindi: आहे, नाही, आणि, मध्ये, never है, नहीं, और, में."),
    "bn": ("Bengali", "Bengali", ""),
    "ta": ("Tamil", "Tamil", ""),
    "te": ("Telugu", "Telugu", ""),
    "gu": ("Gujarati", "Gujarati", ""),
}

LANGUAGES = {
    "hinglish": ("Write in Hinglish: everyday Hindi in Roman script mixed with English, the way a good Indian teacher "
                 "explains in class (\"Yahan acceleration constant hai, isliye...\"). Keep technical terms, formulas and "
                 f"units in English. {HINGLISH_TONE}"),
    **{code: (f"Write in {name}, in {script} script.{slip} Keep technical terms in English where Indian classrooms do "
              "(velocity, matrix, deadlock), and every formula, symbol and unit exactly as it is.")
       for code, (name, script, slip) in MOTHER_TONGUES.items()},
}


# Said again after the student's own words: the model weighs the last message most, and with only the system rule a
# "difference between X and Y" doubt came back as an all-English table.
REPLY_IN = {
    "hinglish": ("\n\n(Reply in Hinglish: Hindi sentences in Roman script, only the technical words in English. That goes for "
                 "headings and table cells too: \"Apna alag memory space hota hai\", not \"Has its own memory space\". "
                 "Open with a Hinglish sentence and end with a Hinglish takeaway, even around a table.)"),
    **{code: f"\n\n(Reply in {name}, {script} script, including headings and table cells.{slip})"
       for code, (name, script, slip) in MOTHER_TONGUES.items()},
}


def _in(system: str, language: str | None) -> str:
    """A system prompt with the student's language rule added (unchanged for English)."""
    rule = language_rule(language)
    return f"{system}\n\nLanguage: {rule} JSON keys stay in English." if rule else system


def language_rule(language: str | None) -> str:
    """The instruction that makes an explanation come out in the student's language ("" for English)."""
    return LANGUAGES.get(language or "", "")


def explain_in(solution: str, question: str, language: str, exam: str | None) -> str:
    """A worked solution said again in the student's language: the same steps and answer, the math untouched."""
    system = (f"You explain a worked solution to a {_exam(exam)} student. {language_rule(language)} "
              "Keep every step, number and the final answer exactly as in the solution; you may add a short line "
              "that says why a step is taken. Copy every LaTeX expression exactly, with its backslashes and $ signs. "
              "Markdown only, no preamble, under 250 words.")
    # the language said again last: with only the system rule ("keep technical terms in English") a solution, mostly
    # technical terms, often came back in English
    user = f"Question:\n{question[:1500]}\n\nSolution:\n{solution[:2500]}{REPLY_IN.get(language, '')}"
    out = llm.chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                   max_tokens=2500, temperature=0.3, feature="explain_language")
    return fix_latex(restore_backslashes(out))


def companion(question: str, context_md: str, history: list[dict[str, str]], exam: str | None, mode: str = "explain",
              language: str | None = None) -> dict[str, Any]:
    style = COMPANION_SYSTEM.get(mode, COMPANION_SYSTEM["explain"]).format(exam=_exam(exam), tone=HINGLISH_TONE)
    system = (
        f"You are Focs, an AI study companion for {_exam(exam)} students, answering doubts while they watch a lecture. "
        f"{style} Use Markdown and LaTeX ($...$). Keep it under 180 words unless the doubt truly needs more. "
        "The answer is read in a narrow side panel, often on a phone: short lines, lists rather than long paragraphs, "
        "a table only for two or three short columns, and long equations on their own line as $$...$$. "
        "If the doubt is unrelated to studies, gently steer back."
    )
    if context_md:
        system += f"\n\nThe board notes from this lecture so far (use them as context):\n{context_md[-3500:]}"
    else:
        system += ("\n\nNo board has been captured yet. If the student refers to 'the board' or 'this', "
                   "say in one line that Focs hasn't read a board yet, then help with whatever they asked.")
    # last, so it outweighs the English context and question: without it a comparison table came back all English
    if rule := language_rule(language):
        system += f"\n\nLanguage: {rule} This applies to every line, including headings, lists and table cells."
    messages = [{"role": "system", "content": system}]
    for turn in history[-6:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": str(turn["content"])[:1500]})
    messages.append({"role": "user", "content": question + REPLY_IN.get(language or "", "")})
    try:
        return {"answer": fix_latex(llm.chat(messages, max_tokens=700, temperature=0.4, feature="doubt")), "source": "ai"}
    except LLMUnavailable as exc:
        log.info("companion fallback: %s", exc)
        return {"answer": offline.companion(question, context_md), "source": "offline"}


SPEECH_SYSTEM = """You are Focs, a careful {exam} teacher's assistant. Below is what the teacher SAID during part of a
lecture (a speech-to-text transcript: ignore filler, false starts and recognition slips; it may be Hindi or Hinglish).
{board}Write the notes a student needs from the talk: explanations, reasons, examples, warnings ("this comes in the exam",
"students often get this wrong") and anything said but not written. Never repeat what the board already has.
First line: TOPIC: <= 6 words. Then Markdown bullets only, math in LaTeX ($...$): as many as the talk earned, from 2 for
a short passage to 8 for a long one. No preamble."""


def speech_notes(transcript: str, board_md: str | None, exam: str | None, language: str | None = None) -> dict[str, Any] | None:
    """Notes from what the teacher said (see services/voice). None when the AI can't be reached (try again later)."""
    board = f"The board at that time already has these notes:\n{board_md[:1500]}\n\n" if board_md else "There was no board at that time.\n"
    try:
        out = llm.chat([{"role": "system", "content": _in(SPEECH_SYSTEM.format(exam=_exam(exam), board=board), language)},
                        {"role": "user", "content": transcript[-5000:]}],
                       max_tokens=700, temperature=0.3, tier="light", feature="spoken_notes")
    except LLMUnavailable as exc:
        log.info("spoken notes not written: %s", exc)
        return None
    first, _, rest = out.strip().partition("\n")
    head = first.strip().strip("*#_ ").strip()  # (models dress it up: "**TOPIC: …**", "## TOPIC: …")
    topic = head.split(":", 1)[1].strip().strip("*_ ") if head.upper().startswith("TOPIC:") else ""
    body = (rest if topic else out).strip()
    if not body:
        return None
    return {"topic": (topic or "What the teacher said")[:80], "notes_md": fix_latex(restore_backslashes(body)), "source": "ai"}


TALK_SYSTEM = """You are Focs, a careful {exam} teacher's assistant. Below is what the teacher SAID in {part}a lecture{title}
(a speech-to-text transcript: it may be Hindi, Hinglish or English, with filler, false starts and recognition slips).
{boards}Summarise what the teacher said, for a student revising it later.
- Only what the teacher actually said: the points they explained and why, the method they gave, and their warnings and
  exam tips ("this comes in the exam", "students often get this wrong"). Never solve a problem, finish a calculation
  or add examples, steps or topics they didn't say.
- 3-8 short Markdown bullets in the order said, one or two lines each; fewer when the talk is short or hard to make
  out. Math in LaTeX ($...$).
- Skip filler, jokes and anything the transcript garbles beyond recovery.
No heading, no preamble."""

TALK_BOARDS = "What was on the board, only to read the teacher's references right (don't summarise it):\n{text}\n\n"

TALK_MERGE_SYSTEM = """Below are summaries of consecutive parts of one {exam} lecture, in order. Merge them into one
summary of the whole lecture: 4-12 short Markdown bullets in the order said, repeats dropped, every warning and exam
tip kept. Add nothing the parts don't say. Math in LaTeX ($...$). No heading, no preamble."""

TALK_CHUNK = 6000      # characters of transcript per AI call: within the cheap model's per-minute token limit
TALK_MAX_PARTS = 12    # a longer lecture is cut into bigger parts rather than more of them


def talk_summary(pieces: list[str], title: str | None, exam: str | None, language: str | None = None,
                 boards: str = "") -> str | None:
    """A summary of everything the teacher said (see services/voice). A long lecture is summarised part by part and the
    parts merged. ``boards``: the lecture's board text, so "this one over x plus 1" is read as the board has it.
    None when the AI can't be reached (try again later)."""
    size = max(TALK_CHUNK, sum(len(p) + 1 for p in pieces) // TALK_MAX_PARTS + 1)
    parts, cur = [], ""
    for p in pieces:
        if cur and len(cur) + len(p) + 1 > size:
            parts.append(cur)
            cur = ""
        cur = f"{cur} {p}".strip()
    if cur:
        parts.append(cur)
    if not parts:
        return None
    named = f' on "{title}"' if title else ""
    board = TALK_BOARDS.format(text=boards.strip()[:1500]) if boards.strip() else ""
    try:
        done = [llm.chat([{"role": "system", "content": _in(TALK_SYSTEM.format(
                              exam=_exam(exam), title=named, boards=board,
                              part=f"part {i + 1} of {len(parts)} of " if len(parts) > 1 else ""), language)},
                          {"role": "user", "content": text}],
                         max_tokens=600, temperature=0.1, tier="light", feature="talk_summary").strip()
                for i, text in enumerate(parts)]
        out = done[0] if len(done) == 1 else llm.chat(
            [{"role": "system", "content": _in(TALK_MERGE_SYSTEM.format(exam=_exam(exam)), language)},
             {"role": "user", "content": "\n\n".join(f"Part {i + 1}:\n{d}" for i, d in enumerate(done))}],
            max_tokens=800, temperature=0.1, tier="light", feature="talk_summary").strip()
    except LLMUnavailable as exc:
        log.info("talk summary not written: %s", exc)
        return None
    return fix_latex(restore_backslashes(out)) or None


def summarize_session(notes: list[dict[str, str]], exam: str | None, offline_only: bool = False,
                      language: str | None = None) -> dict[str, Any]:
    if offline_only:
        return offline.summary(notes)
    material = lecture_material(notes)
    size = SHEET_SHAPES[sheet_size(notes)]
    system = SUMMARY_SYSTEM.format(exam=_exam(exam), subjects=_subjects(exam), shape=size["shape"], cards=size["cards"])
    messages = [{"role": "system", "content": _in(system, language)}, {"role": "user", "content": material}]
    try:
        data = llm.json(messages, max_tokens=size["max_tokens"], temperature=0.3, feature="revision_sheet")
        if str(data.get("summary_md", "")).count("## ") < 2:  # the sections went missing: one more try, not a thin sheet
            data = llm.json([*messages, {"role": "user", "content": "Write the whole sheet again: summary_md must hold every section."}],
                            max_tokens=size["max_tokens"], temperature=0.2, feature="revision_sheet")
        cards = _checked_cards(offline.sanitize_cards(data.get("flashcards", [])), exam)
        return {"title": str(data.get("title") or "Lecture summary")[:100],
                "subject": str(data.get("subject") or guess_subject(material)),
                "summary_md": str(data.get("summary_md", "")).strip(),
                "key_formulas": [str(f) for f in data.get("key_formulas", [])][:20],
                "flashcards": cards, "source": "ai"}
    except LLMUnavailable as exc:
        log.info("summary fallback: %s", exc)
        return offline.summary(notes)


CHECK_CARDS = """You check flashcards written for {exam} students. For each card, work out the answer to its front
yourself, independently of the back, then compare: "ok" is true only when the back is a correct and complete answer
to the front, with every number, sign, bracket and boundary right. Return JSON, one entry per card, in order:
{{"cards": [{{"n": 1, "ok": true}}]}}"""


def _checked_cards(cards: list[dict[str, str]], exam: str | None) -> list[dict[str, str]]:
    """Cards a second model agrees with. When no second model can be reached the cards stay (a flashcard is the
    student's to edit); a card the checker rejects is dropped (one said the intersection of (2x-3)/5 <= 0 and > -2
    was [-0.5, 1.5]; it is (-3.5, 1.5])."""
    if not cards or not llm.available:
        return cards
    asked = "\n\n".join(f"Card {n}\nFront: {c['front']}\nBack: {c['back']}" for n, c in enumerate(cards, 1))
    try:
        data = llm.json([{"role": "system", "content": CHECK_CARDS.format(exam=_exam(exam))}, {"role": "user", "content": asked}],
                        max_tokens=100 + 25 * len(cards), temperature=0.0, effort="medium", feature="question_verify")
    except LLMUnavailable as exc:
        log.info("flashcard check unavailable: %s", exc)
        return cards
    rows = {r.get("n", n): r for n, r in enumerate(data.get("cards") or [], 1) if isinstance(r, dict)}
    if not rows:
        return cards
    kept = [c for n, c in enumerate(cards, 1) if rows.get(n, {}).get("ok") is not False]
    return kept or cards[:0]


def flashcards(material: str, exam: str | None, n: int = 6, language: str | None = None) -> list[dict[str, str]]:
    try:
        data = llm.json(
            [
                {"role": "system", "content": _in(FLASHCARD_SYSTEM.format(exam=_exam(exam), n=n), language)},
                {"role": "user", "content": material[:5000]},
            ],
            max_tokens=1200, temperature=0.3, tier="light", feature="flashcards",
        )
        cards = _checked_cards(offline.sanitize_cards(data.get("cards", [])), exam)
        if cards:
            return cards[:n]
        raise LLMUnavailable("no cards")
    except LLMUnavailable as exc:
        log.info("flashcards fallback: %s", exc)
        return offline.flashcards(material)[:n]


ROOM_MCQ_SYSTEM = """You run live pop quizzes for a group of {exam} students watching a lecture together.
Write ONE multiple-choice question that checks understanding of what was just taught (prefer the transcript
excerpt; otherwise the lecture title/topic). Exam level, unambiguous, answerable in 30 seconds without long
calculation. LaTeX in $...$ for math. Options must be plausible and must NOT start with letters like "A)".
If the transcript is in Hindi or Hinglish, write the question in clear English unless told otherwise below.
Avoid repeating these recent questions: {recent}
Return JSON: {{"question": "...", "options": ["...", "...", "...", "..."], "explanation": "1-2 sentences, with the working", "answer_index": 0}}
Write the explanation first, solving the question, then set answer_index to the option it reaches."""


def room_question(title: str, topic: str, transcript: str, exam: str | None, recent: list[str],
                  language: str | None = None) -> dict[str, Any] | None:
    context = f"Lecture title: {title or 'unknown'}\nTopic: {topic or 'unknown'}\n"
    if transcript:
        context += f"Transcript of the last few minutes:\n\"\"\"{transcript[-3500:]}\"\"\""
    messages = [
        {"role": "system", "content": _in(ROOM_MCQ_SYSTEM.format(exam=_exam(exam), recent="; ".join(recent[-5:]) or "none"), language)},
        {"role": "user", "content": context},
    ]
    try:
        for _ in range(3):  # a question the checkers can't agree on is written again
            data, model = llm.json_with_model(messages, max_tokens=900, temperature=0.4, tier="light", feature="quiz_question")
            if q := _sound_question(data, exam, model):
                return {**q, "source": "ai"}
        raise LLMUnavailable("no question the checkers agreed on")  # a question from the notes themselves instead
    except (LLMUnavailable, ValueError, TypeError) as exc:
        log.info("room question fallback: %s", exc)
        material = transcript or f"{title}\n{topic}"
        q = offline.quiz(material, n_mcq=1, n_tf=0, n_subj=0)
        if not q["mcq"]:
            return None
        m = q["mcq"][0]
        return {"question": m["q"], "options": m["options"], "answer_index": m["answer_index"],
                "explanation": m["explanation"], "source": "offline"}
