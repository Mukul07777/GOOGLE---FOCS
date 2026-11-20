"""Question bank for full mock tests.

Questions come from a seed file shipped with Focs (app/assets/bank/jee_main.json) and from the LLM.
An AI-written question only counts as *verified* when a different model, solving it from scratch,
reaches the same answer; questions students report as wrong are retired automatically.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.services.math_text import clean_option
from app.core.config import BACKEND_DIR
from app.models.mock import BankQuestion
from app.services.llm import LLMUnavailable, llm, next_free_in
from app.services.mock_patterns import chapter_targets, chapters_of

log = logging.getLogger("focs.bank")

SEED_FILE = BACKEND_DIR / "app" / "assets" / "bank" / "jee_main.json"
RETIRE_AFTER_REPORTS = 2
# students found the papers too direct: a weighted shuffle where an easy question is picked about 0.4 times as readily as
# a medium one (a quarter easy in the bank gives about one in eight in a paper), a hard one twice as readily
DIFFICULTY_WEIGHT = {"easy": 0.4, "hard": 2.0}
BATCH = 5

GEN_MCQ = r"""You are a senior {exam} paper setter for {subject}. Write {n} ORIGINAL single-correct multiple-choice
questions in the exact style and difficulty of recent {exam} (NTA) papers.
Chapters to cover (spread the questions across them): {chapters}.
Difficulty mix: about 30% easy, 50% medium, 20% hard.
Rules:
- Self-contained, unambiguous, all data given, numerically consistent; standard values only (g = 10 m/s^2 unless stated).
- Exactly one correct option among 4. Distractors come from typical student mistakes. No two options may be the same
  value or statement written differently (1 C/s and 1 C·s⁻¹, 0.5 and 1/2).
- Solve every question completely BEFORE fixing its answer, then double-check the marked option matches your solution.
- Math in LaTeX inside $...$; chemical formulas as $\mathrm{{H_2SO_4}}$ (never \ce{{}}). Options must not start
  with labels like "(A)" or "1)".
Return JSON: {{"questions": [{{"chapter": "<one of the chapters>", "difficulty": "easy|medium|hard",
"question": "...", "options": ["...", "...", "...", "..."], "answer_index": 0,
"solution": "the final worked solution as printed in a solutions booklet, 2-6 lines, no thinking aloud"}}]}}"""

GEN_NUM = r"""You are a senior {exam} paper setter for {subject}. Write {n} ORIGINAL numerical-value questions
(JEE Main Section B style): the answer is a single INTEGER between 0 and 9999 that the student types in.
Chapters to cover (spread the questions across them): {chapters}.
Difficulty mix: about 30% easy, 50% medium, 20% hard.
Rules:
- Self-contained, unambiguous, all data given; design the numbers so the exact answer is an integer
  (or say "nearest integer" in the question when rounding is intended).
- Solve every question completely BEFORE fixing its answer, then double-check it.
- Math in LaTeX inside $...$; chemical formulas as $\mathrm{{H_2SO_4}}$ (never \ce{{}}).
Return JSON: {{"questions": [{{"chapter": "<one of the chapters>", "difficulty": "easy|medium|hard",
"question": "...", "answer": 12, "solution": "the final worked solution as printed in a solutions booklet, 2-6 lines, no thinking aloud"}}]}}"""

GEN_MCQ_COLLEGE = r"""You are a professor setting an objective test for the B.Tech course "{subject}". Write {n}
ORIGINAL single-correct multiple-choice questions at the level of university end-semester exams and GATE.
Chapters to cover (spread the questions across them): {chapters}.
Difficulty mix: about 30% easy, 50% medium, 20% hard. Mix questions that test a concept with ones that need a short
calculation or, where the course has them, a trace of an algorithm, a few lines of code or a small circuit described
in words (a biology or chemistry course has none of those: use its own experiments, data and processes).
Rules:
- Self-contained, unambiguous, all data given; standard notation and the conventions of the standard textbooks.
- Money is Indian rupees in plain text: ₹1,20,000 (never the $ sign, which starts math here).
- Exactly one correct option among 4. Distractors come from typical student mistakes. No two options may be the same
  value or statement written differently (1 C/s and 1 C·s⁻¹, 0.5 and 1/2).
- Solve every question completely BEFORE fixing its answer, then double-check the marked option matches your solution.
- Math in LaTeX inside $...$. If a question needs code, give it as plain text, six short lines at the most, and never
  mention these rules in the question. Options must not start with labels like "(A)" or "1)".
Return JSON: {{"questions": [{{"chapter": "<one of the chapters>", "difficulty": "easy|medium|hard",
"question": "...", "options": ["...", "...", "...", "..."], "answer_index": 0,
"solution": "the final worked solution as printed in a solutions booklet, 2-6 lines, no thinking aloud"}}]}}"""

GEN_MCQ_BOARD = r"""You set CBSE {level} papers in {subject}, from the NCERT book for the class. Write {n} ORIGINAL
single-correct multiple-choice questions of the kind a {level} paper opens with: straight from the NCERT chapter, testing
one idea each, a few of them competency-based (a short situation, then the question). {age}
Chapters to cover (spread the questions across them): {chapters}.{covers}
Difficulty mix: about 40% easy, 45% medium, 15% hard (hard for the class: no JEE-style multi-step problems).
{language}
Rules:
- Inside the NCERT book for the class: every fact, term, value and kind of calculation a question needs is one the
  chapter teaches. Nothing from a higher class or beyond the textbook (no data, units or sums the book doesn't use).
  A hard question asks for more careful thinking about the book's content, never for knowing more than it.
- Money is Indian rupees in plain text: ₹1,20,000 (never the $ sign, which starts math here, and never "Rs." in math).
- Self-contained, unambiguous, all data given; NCERT terms, symbols and values.
- Exactly one correct option among 4. Distractors come from typical student mistakes. No two options may be the same
  value or statement written differently (1 C/s and 1 C·s⁻¹, 0.5 and 1/2).
- Solve every question completely BEFORE fixing its answer, then double-check the marked option matches your solution.
- Math in LaTeX inside $...$; chemical formulas as $\mathrm{{H_2SO_4}}$ (never \ce{{}}). Options must not start
  with labels like "(A)" or "1)".
Return JSON: {{"questions": [{{"chapter": "<one of the chapters>", "difficulty": "easy|medium|hard",
"question": "...", "options": ["...", "...", "...", "..."], "answer_index": 0,
"solution": "the final worked solution as printed in a solutions booklet, 2-5 lines, no thinking aloud"}}]}}"""

GEN_MCQ_SSC = r"""You are a senior SSC CGL paper setter for {subject}. Write {n} ORIGINAL single-correct multiple-choice
questions in the exact style, wording and difficulty of recent SSC CGL Tier-I and Tier-II papers (2022-2025).
Chapters to cover (spread the questions across them): {chapters}.
Difficulty mix: about 35% easy, 45% medium, 20% hard (SSC hard: a quick trick or two steps, never a long derivation).
Rules:
- Solvable in under a minute by a well-prepared candidate, without a calculator; numbers that work out cleanly.
- Text only: never a question that needs a figure, picture, graph or table image (no mirror images, paper folding,
  embedded or counting figures).
- Money is Indian rupees in plain text: ₹1,20,000 (never the $ sign, which starts math here).
- General Awareness: settled facts only (history, polity, geography, economy, science, static GK). Never current
  affairs or anything that changes year to year (office holders, latest rankings, recent events, "current" figures).
- English: standard British/Indian usage as SSC tests it.
- Exactly one correct option among 4. Distractors come from typical candidate mistakes. No two options may be the same
  value or statement written differently.
- Solve every question completely BEFORE fixing its answer, then double-check the marked option matches your solution.
- Math in LaTeX inside $...$. Options must not start with labels like "(A)" or "1)".
Return JSON: {{"questions": [{{"chapter": "<one of the chapters>", "difficulty": "easy|medium|hard",
"question": "...", "options": ["...", "...", "...", "..."], "answer_index": 0,
"solution": "the final worked solution as printed in a solutions booklet, 2-5 lines, with the quick SSC method where
there is one, no thinking aloud"}}]}}"""

VERIFY_MCQ = """Solve this {exam} {subject} question carefully and independently. Then test every option on its own
against the question as written: list each option that is a correct answer (there may be more than one, or none).
The same value in another notation or unit form counts as a second correct option.
Return JSON: {{"correct": [<every correct option index, 0-3>]}}"""

VERIFY_NUM = """Solve this {exam} {subject} numerical-value question carefully and independently.
The answer is an integer. Return JSON: {{"answer": <integer>}}"""

# a batch is checked in one call: a fifth of the requests, and of the tokens, of checking question by question
VERIFY_MCQS = """Solve each of these {exam} {subject} questions carefully and independently of the others. Test every
option on its own against the question as written, and list each option that is a correct answer (there may be more
than one, or none); the same value in another notation or unit form counts as a second correct option. Return JSON
with one entry per question, in order:
{{"answers": [{{"n": 1, "correct": [<every correct option index, 0-3>]}}]}}"""

VERIFY_NUMS = """Solve each of these {exam} {subject} numerical-value questions carefully and independently of the
others. Each answer is an integer. Return JSON with one entry per question, in order:
{{"answers": [{{"n": 1, "answer": <integer>}}]}}"""

# added to a writing prompt when some chapters are limited to some of their topics (a last-day test)
TOPIC_RULE = """
A chapter followed by "only:" is limited to the topics listed after it: every question on it tests one of those
topics, and its JSON also has "topic": that topic, copied exactly as listed."""

# What one request may ask for. A free AI tier counts the answer's allowance against a per-minute budget (8,000
# tokens on Groq's), and turns away a request that asks for more than that in one go.
GEN_MAX_TOKENS = 2400
LONGEST_WAIT = 75.0  # for a rate limit to lift, in one go


# A solutions booklet doesn't think aloud: these give away a model that changed its mind mid-solution. The words
# themselves are ordinary ("hold and wait" is a deadlock condition, "No, the graph is acyclic" is an answer), so
# "wait" and "no" only count as an interjection: opening a sentence or between commas, followed by a pause.
_SHAKY = re.compile(r"(?:^|[.!?:;]\s+|\n\s*)(?:wait|hold on)\s*[,!.…—–-]+\s|,\s*wait\s*[,—–-]|\bwait a (?:second|minute|moment)\b|"
                    r"\bno,\s+(?:wait|that'?s (?:not|wrong)|that is (?:not|wrong)|actually|sorry)\b|"
                    r"\b(?:hmm+|oops|let'?s (?:verify|check|re-?check|recompute|re-?evaluate)|i think|"
                    r"that (?:doesn'?t|does not) (?:match|work)|this contradicts|my mistake|actually,)", re.IGNORECASE)
MAX_SOLUTION_CHARS = 1100


def looks_clean(question: str, solution: str) -> bool:
    return not _SHAKY.search(question) and not _SHAKY.search(solution) and len(solution) <= MAX_SOLUTION_CHARS


def fingerprint(text: str) -> str:
    return hashlib.sha1(re.sub(r"[^a-z0-9]", "", text.lower())[:400].encode()).hexdigest()


# ---------------------------------------------------------------- seed
def load_seed(db: Session, path: Path = SEED_FILE) -> int:
    """Add seed questions that aren't in the bank yet. Idempotent."""
    if not path.exists():
        return 0
    items = json.loads(path.read_text(encoding="utf-8"))
    known = set(db.scalars(select(BankQuestion.fingerprint)))
    added = 0
    for it in items:
        fp = fingerprint(it["question"])
        if fp in known or not looks_clean(it["question"], it.get("solution", "")):
            continue
        db.add(BankQuestion(exam=it.get("exam", "jee_main"), subject=it["subject"], chapter=it.get("chapter", ""),
                            qtype=it["qtype"], difficulty=it.get("difficulty", "medium"), question=it["question"],
                            options=it.get("options"), answer=str(it["answer"]), solution=it.get("solution", ""),
                            verified=bool(it.get("verified", True)), source="seed", fingerprint=fp))
        known.add(fp)
        added += 1
    if added:
        db.commit()
        log.info("question bank: loaded %d seed questions", added)
    return added


# ---------------------------------------------------------------- generation
def _topic_of(said: str, allowed: tuple[str, ...] | list[str]) -> str | None:
    """The listed topic a model said a question tests: as listed, or as a fragment of it either way round."""
    said = said.strip().lower()
    if not said:
        return None
    return (next((t for t in allowed if t.lower() == said), None)
            or next((t for t in allowed if len(said) >= 4 and (said in t.lower() or t.lower() in said)), None))


LEANS_ON_ANOTHER = re.compile(r"\bquestion\s+\d+\b|\b(previous|above|preceding|earlier|last)\s+question\b", re.I)


def _clean(item: dict[str, Any], subject: str, qtype: str, chapters: list[str],
           topics: dict[str, Any] | None = None) -> dict[str, Any] | None:
    q = str(item.get("question") or "").strip()
    if len(q) < 25 or LEANS_ON_ANOTHER.search(q):  # ("using the cash flows of question 2": each is asked on its own)
        return None
    chapter = str(item.get("chapter") or "").strip()
    if chapter not in chapters_of(subject):
        chapter = next((c for c in chapters if c.lower() in chapter.lower() or chapter.lower() in c.lower()), chapters[0])
    if not looks_clean(q, str(item.get("solution") or "")):
        return None
    difficulty = str(item.get("difficulty") or "").lower()
    out = {"subject": subject, "chapter": chapter, "qtype": qtype, "question": q,
           "difficulty": difficulty if difficulty in ("easy", "medium", "hard") else "medium",
           "solution": str(item.get("solution") or "").strip(),
           # unlabelled, it stays a question on the chapter: it may not be on the topic it was asked for
           "topic": _topic_of(str(item.get("topic") or ""), (topics or {}).get(chapter) or ())}
    if qtype == "mcq":
        opts = [str(o).strip() for o in item.get("options") or []]
        try:
            idx = int(item.get("answer_index"))
        except (TypeError, ValueError):
            return None
        if len(opts) != 4 or len({o.lower() for o in opts}) != 4 or any(not o for o in opts) or not 0 <= idx < 4:
            return None
        # drop "(A) " / "A) " / "(1) " labels, but never touch values like "1:2" or "2.5"
        out.update(options=[clean_option(re.sub(r"^(?:\([A-Da-d1-4]\)|[A-Da-d][).])\s+", "", o)) for o in opts], answer=str(idx))
    else:
        try:
            value = float(item.get("answer"))
        except (TypeError, ValueError):
            return None
        if not value.is_integer() or not 0 <= value <= 99999:
            return None
        out.update(options=None, answer=str(int(value)))
    return out


def only_correct(row: dict[str, Any], answer: int) -> bool:
    """A checker's verdict on a multiple-choice question: True only when the keyed option is the one and only correct
    option. Two correct options make a broken question even when the key names one of them."""
    correct = row.get("correct")
    if isinstance(correct, list):
        return {int(c) for c in correct} == {answer}
    return int(row.get("answer_index")) == answer  # an older-style reply that names a single option


def _render(q: dict[str, Any]) -> str:
    if q["qtype"] == "mcq":
        return q["question"] + "\n\nOptions:\n" + "\n".join(f"{i}. {o}" for i, o in enumerate(q["options"]))
    return q["question"]


def verify(q: dict[str, Any], generator: str) -> bool | None:
    """Solve the question with a different model. True = same answer, False = disagrees,
    None = no independent model was available."""
    system = (VERIFY_MCQ if q["qtype"] == "mcq" else VERIFY_NUM).format(subject=q["subject"], exam=_label(q.get("exam")))
    try:
        data, _ = llm.json_with_model([{"role": "system", "content": system}, {"role": "user", "content": _render(q)}],
                                      max_tokens=300, temperature=0.0, effort="medium", skip=frozenset({generator}),
                                      feature="question_verify")
    except LLMUnavailable as exc:
        log.info("verify unavailable: %s", exc)
        return None
    try:
        if q["qtype"] == "mcq":
            return only_correct(data, int(q["answer"]))
        return abs(float(data.get("answer")) - float(q["answer"])) < 1e-6
    except (TypeError, ValueError):
        return False


def _patient(call, deadline: float | None, skip: frozenset[str] = frozenset()):
    """Run an AI call. When it fails because every model is resting after a rate limit, wait for the first to be
    free and try again, while the deadline allows (no deadline: one try, as when a student is watching)."""
    while True:
        try:
            return call()
        except LLMUnavailable:
            wait = next_free_in(skip)
            if deadline is None or wait <= 0 or wait > LONGEST_WAIT or time.monotonic() + wait >= deadline:
                raise
            log.info("every model is rate-limited: waiting %.0fs for one", wait)
            time.sleep(wait + 0.5)


def verify_batch(items: list[dict[str, Any]], generator: str, deadline: float | None = None) -> list[bool | None]:
    """Solve a batch of questions (one subject, one kind) with a different model, in one call. For each: True = same
    answer, False = disagrees, None = no second opinion could be had."""
    if not items:
        return []
    mcq = items[0]["qtype"] == "mcq"
    system = (VERIFY_MCQS if mcq else VERIFY_NUMS).format(subject=items[0]["subject"], exam=_label(items[0].get("exam")))
    asked = "\n\n".join(f"Question {n}:\n{_render(item)}" for n, item in enumerate(items, 1))
    skip = frozenset({generator})
    try:
        data, _ = _patient(lambda: llm.json_with_model(
            [{"role": "system", "content": system}, {"role": "user", "content": asked}],
            max_tokens=150 + 60 * len(items), temperature=0.0, effort="medium", skip=skip, feature="question_verify"), deadline, skip)
    except LLMUnavailable as exc:
        log.info("verify unavailable: %s", exc)
        return [None] * len(items)
    answers = {}
    for n, row in enumerate(data.get("answers") or [], 1):
        if isinstance(row, dict):
            answers[row.get("n") if isinstance(row.get("n"), int) else n] = row
    out: list[bool | None] = []
    for n, item in enumerate(items, 1):
        row = answers.get(n)
        if row is None:
            out.append(None)
            continue
        try:
            out.append(only_correct(row, int(item["answer"])) if mcq else abs(float(row.get("answer")) - float(item["answer"])) < 1e-6)
        except (TypeError, ValueError):
            out.append(False)
    return out


def _school_level(subject: str, chapters: list[str]) -> dict[str, str]:
    """Which school class a board-style paper is for, read from its chapters (school chapter names are unique within
    a subject across the classes), how to write for that age, and what each chapter covers in its NCERT book (a
    chapter's name alone can mislead: Class 5's "We the Travellers" is about large numbers, not speed)."""
    from app.services import syllabus

    classes = sorted({c for c in (syllabus.school_class(subject, ch) for ch in chapters) if c})
    cls = classes[-1] if classes else 12
    level = f"Class {cls} board" if cls in (10, 12) else f"Class {cls} school"
    age = ("Write for young children: very short sentences, simple everyday words, one small step a question."
           if cls <= 5 else "Keep the language simple and clear for the age." if cls <= 8 else "")
    covered = [f"{ch}: {'; '.join(topics)}" for ch in chapters if (topics := syllabus.school_topics(subject, ch))]
    covers = ("\nWhat each chapter covers in the NCERT book (ask only about this, at this class's level): "
              + " | ".join(covered) + ".") if covered else ""
    tongue = next((lang for lang in ("Hindi", "Sanskrit") if subject.startswith(lang)), None)
    language = (f"Write every question, option and solution in {tongue} (Devanagari)." if tongue
                else "Write every question, option and solution in English.")
    return {"level": level, "age": age, "covers": covers, "language": language}


def _label(exam: str | None) -> str:
    return {"neet": "NEET", "ssc_cgl": "SSC CGL", "jee_advanced": "JEE Advanced", "college": "university-level (B.Tech)", "cbse": "CBSE school (NCERT)"}.get(exam or "", "JEE Main")


def generate_batch(subject: str, qtype: str, chapters: list[str], n: int = BATCH, exam: str = "jee_main",
                   deadline: float | None = None, topics: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Write n questions with the LLM, then keep only those a second model agrees with. With a ``deadline``
    (a paper being prepared in the background) a rate limit is waited out instead of failing the batch.
    ``topics``: chapter → the only topics of it to ask about (a last-day test on part of a chapter)."""
    own = {"college": GEN_MCQ_COLLEGE, "cbse": GEN_MCQ_BOARD, "ssc_cgl": GEN_MCQ_SSC}.get(exam) if qtype == "mcq" else None
    template = own or (GEN_MCQ if qtype == "mcq" else GEN_NUM)
    limited = {c: list(topics[c]) for c in chapters if topics and topics.get(c)}
    listed = "; ".join(f"{c} (only: {', '.join(limited[c])})" if c in limited else c for c in chapters)
    system = template.format(subject=subject, n=n, chapters=listed, exam=_label(exam), **_school_level(subject, chapters)) + (TOPIC_RULE if limited else "")
    try:
        data, model = _patient(lambda: llm.json_with_model(
            [{"role": "system", "content": system}, {"role": "user", "content": f"Write the {n} questions now."}],
            max_tokens=GEN_MAX_TOKENS, temperature=0.7, effort="low", feature="question_bank"), deadline)
    except LLMUnavailable as exc:
        log.warning("bank generation failed (%s %s): %s", subject, qtype, str(exc)[:200])
        return []
    written = []
    for item in data.get("questions") or []:
        q = _clean(item, subject, qtype, chapters, limited) if isinstance(item, dict) else None
        if q:
            q["exam"] = exam
            written.append(q)
    out = []
    for q, verdict in zip(written, verify_batch(written, model, deadline), strict=True):
        if verdict is False:
            log.info("bank: dropped a %s %s question the verifier disagreed with", subject, qtype)
            continue
        q["verified"] = bool(verdict)
        out.append(q)
    return out


def generate(subject: str, qtype: str, need: dict[str, int], workers: int = 2,
             on_progress=None, exam: str = "jee_main", deadline: float | None = None,
             topics: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Generate roughly the per-chapter counts in ``need`` (a few extra to cover verifier rejections). Two batches
    at a time: the models share one per-minute budget, so more in parallel only trips the rate limit sooner.
    ``topics``: chapter → the only topics of it to ask about."""
    queue = [c for c, k in need.items() for _ in range(k)]
    random.shuffle(queue)
    queue += random.sample(queue, k=min(len(queue), max(1, len(queue) // 3)))  # ~30% extra
    batches = [sorted(set(queue[i:i + BATCH])) for i in range(0, len(queue), BATCH)]
    sizes = [len(queue[i:i + BATCH]) for i in range(0, len(queue), BATCH)]
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for got in pool.map(lambda args: generate_batch(subject, qtype, *args, exam=exam, deadline=deadline, topics=topics),
                            zip(batches, sizes, strict=True)):
            results += got
            if on_progress:
                on_progress(len(got))
    return results


def store(db: Session, items: list[dict[str, Any]]) -> int:
    known = set(db.scalars(select(BankQuestion.fingerprint)))
    added = 0
    for q in items:
        fp = fingerprint(q["question"])
        if fp in known:
            continue
        db.add(BankQuestion(exam=q.get("exam") or "jee_main", subject=q["subject"], chapter=q["chapter"], qtype=q["qtype"],
                            difficulty=q["difficulty"], topic=q.get("topic"),
                            question=q["question"], options=q["options"], answer=q["answer"], solution=q["solution"],
                            verified=q.get("verified", False), source="ai", fingerprint=fp))
        known.add(fp)
        added += 1
    db.commit()
    return added


# ---------------------------------------------------------------- selection
def _pool(db: Session, subject: str, qtype: str, exclude: set[int]) -> list[BankQuestion]:
    rows = db.scalars(select(BankQuestion).where(
        BankQuestion.subject == subject, BankQuestion.qtype == qtype,
        func.coalesce(BankQuestion.reports, 0) < RETIRE_AFTER_REPORTS)).all()
    return [q for q in rows if q.id not in exclude]


# JEE Main and NEET ask the same Physics and Chemistry chapters at a similar level: each exam's questions on them
# serve both (the student's own first). JEE Advanced is a level above NEET, so it serves JEE students only.
SHARED_SUBJECTS = ("Physics", "Chemistry")


def exam_family(exam: str | None, subject: str | None = None) -> tuple[str, ...]:
    """The bank's exam values a student's questions may come from, their own exam's first; () for any.
    JEE is Main and Advanced; on a shared subject JEE takes NEET's questions too, and NEET takes JEE Main's."""
    if exam in ("college", "cbse", "jee_advanced", "ssc_cgl"):  # an Advanced paper is never padded with Main-level questions
        return (exam,)
    shared = subject in SHARED_SUBJECTS
    if exam == "neet":
        return ("neet", "jee_main") if shared else ("neet",)
    if exam:
        return ("jee_main", "jee_advanced", "neet") if shared else ("jee_main", "jee_advanced")
    return ()


def own_first(exam: str | None, q_exam: str | None) -> int:
    """0 for a question of the student's own exam (JEE Main for a JEE student), 1 for one shared from another."""
    return 0 if (q_exam or "jee_main") == ("neet" if exam == "neet" else exam if exam in ("college", "cbse", "jee_advanced", "ssc_cgl") else "jee_main") else 1


ON_TOPIC = 0.5  # of what is distinctive in a topic's name, the share a question must share to be about it


def on_topics(rows: list[BankQuestion], topics: dict[str, Any]) -> list[BankQuestion]:
    """The questions that may go in a test where some chapters are limited to some of their topics (chapter → topic
    names): any question of an unlimited chapter; of a limited one, those written for one of its topics, or that
    plainly are about one, sharing most of what is distinctive in its name (words that are rare among the chapter's
    questions count for more, as in topic_notes.exam_questions)."""
    from app.services.topic_notes import _words

    keep: list[BankQuestion] = []
    limited: dict[str, list[BankQuestion]] = {}
    for q in rows:
        (limited.setdefault(q.chapter, []) if topics.get(q.chapter) else keep).append(q)
    for chapter, qs in limited.items():
        allowed = set(topics[chapter])
        words = {q.id: _words(f"{q.question} {q.solution or ''}") for q in qs}
        weight = lambda w: math.log((len(qs) + 1) / (sum(w in ws for ws in words.values()) + 1)) + 0.2  # noqa: E731
        wanted = [w for w in (_words(t) for t in allowed) if w]
        for q in qs:
            if q.topic:  # written for a topic: it counts for that one only
                if q.topic in allowed:
                    keep.append(q)
                continue
            if any(sum(weight(w) for w in want & words[q.id]) / sum(weight(w) for w in want) >= ON_TOPIC for want in wanted):
                keep.append(q)
    return keep


def _words(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", (text or "").lower()))


def near_duplicate(a: frozenset[str], b: frozenset[str]) -> bool:
    """Two questions that ask the same thing in nearly the same words (the bank's fingerprint only catches exact
    copies, and "next number in 2, 4, 8, 16" came twice in one Class 6 paper)."""
    return bool(a and b) and len(a & b) / len(a | b) >= 0.9


def pick(db: Session, subject: str, qtype: str, n: int, exclude: set[int],
         chapters: tuple[str, ...] | list[str] | None = None, exam: str | None = None,
         topics: dict[str, Any] | None = None) -> tuple[list[BankQuestion], dict[str, int]]:
    """Choose n questions spread over chapters by weight, from the student's own exam (``exam_family``: Physics and
    Chemistry are shared by JEE Main and NEET; what is still short is written for their exam, never taken from a
    college or board bank), their own exam's first, then verified, random within. ``topics``: chapter → the only topics of it a question may be on (``on_topics``).
    Returns the picks and, when the bank is short, how many more each chapter needs."""
    pool = [q for q in _pool(db, subject, qtype, exclude) if not chapters or q.chapter in chapters]
    if topics:
        pool = on_topics(pool, topics)
    pool.sort(key=lambda q: random.random() ** (1 / DIFFICULTY_WEIGHT.get(q.difficulty, 1.0)), reverse=True)
    family = exam_family(exam, subject)
    # stable: verified first, random within; SSC papers take the real past-paper questions (English and Hindi, figures)
    # before the ones written to fill a chapter
    pool.sort(key=lambda q: (not q.verified, exam == "ssc_cgl" and q.source != "pyq"))
    mine = [q for q in pool if not family or (q.exam or "jee_main") in family]
    own = [q for q in mine if not family or own_first(exam, q.exam) == 0]
    shared = [q for q in mine if family and own_first(exam, q.exam) == 1]
    targets = chapter_targets(subject, n, chapters)
    chosen: list[BankQuestion] = []
    used: set[int] = set()
    asked: list[frozenset[str]] = []

    def take(group: list[BankQuestion], k: int, chapter: str | None = None) -> int:
        got = []
        for q in group:
            if len(got) >= k:
                break
            if q.id in used or (chapter is not None and q.chapter != chapter):
                continue
            used.add(q.id)
            # a figure question's words are the same in every paper ("Select the correct mirror image"): its pictures
            # tell it apart
            words = _words(q.question) | frozenset((q.media or {}).get("figures") or [])
            if any(near_duplicate(words, w) for w in asked):
                continue
            asked.append(words)
            got.append(q)
        chosen.extend(got)
        return len(got)

    # their own exam's questions chapter by chapter, then its spare ones of any chosen chapter; only then the
    # questions shared from the other exam (a NEET paper is NEET questions while they last)
    short = {c: k - take(own, k, c) for c, k in targets.items()}
    take(own, n - len(chosen))
    short = {c: k - (take(shared, min(k, n - len(chosen)), c) if k and len(chosen) < n else 0) for c, k in short.items()}
    take(shared, n - len(chosen))
    missing = {} if len(chosen) >= n else {c: k for c, k in short.items() if k}
    return chosen[:n], missing


def chapter_stock(db: Session) -> dict[str, dict[str, int]]:
    """Usable questions per chapter: chapter tests on well-stocked chapters start instantly."""
    rows = db.execute(select(BankQuestion.subject, BankQuestion.chapter, func.count())
                      .where(func.coalesce(BankQuestion.reports, 0) < RETIRE_AFTER_REPORTS)
                      .group_by(BankQuestion.subject, BankQuestion.chapter)).all()
    out: dict[str, dict[str, int]] = {}
    for subject, chapter, count in rows:
        out.setdefault(subject, {})[chapter] = count
    return out


def stock(db: Session) -> dict[str, dict[str, int]]:
    rows = db.execute(select(BankQuestion.subject, BankQuestion.qtype, func.count())
                      .where(func.coalesce(BankQuestion.reports, 0) < RETIRE_AFTER_REPORTS)
                      .group_by(BankQuestion.subject, BankQuestion.qtype)).all()
    out: dict[str, dict[str, int]] = {}
    for subject, qtype, count in rows:
        out.setdefault(subject, {})[qtype] = count
    return out
