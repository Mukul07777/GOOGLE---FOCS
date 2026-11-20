"""Check my working: the student's rough work under a question, read by a model that sees images and checked step by
step, the way a good teacher marks a copy. It finds the FIRST step that goes wrong, says what kind of slip it is (a
sign or a sum, or a real gap in an idea), and, when the question's chapter has a root-cause chain (services/gaps), which
earlier chapter the slip comes from. That joins three things no other app joins:

    the scribble  ->  the exact wrong step  ->  the root gap years behind it  ->  the five-minute fix (gaps.lesson)

Every check is kept (never the drawing, only what was read), so the student gets a mistake fingerprint (careless or
conceptual?), a slip that lands on a root counts as evidence for silent tracing (gaps.suspects), and the tutor
(``tutor``) answers follow-ups knowing the step, the root gaps and the slips: one personal tutor, opened from a
question or from a chapter."""
from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.gap import GapTrace, PrereqMap
from app.models.mock import BankQuestion, MockTest
from app.models.user import User
from app.models.weak import WeakTopic
from app.models.working import WorkingCheck
from app.services import ai, gaps, syllabus, vision
from app.services.llm import LLMUnavailable, fix_latex, llm, restore_backslashes
from app.services.syllabus import Chapter, Syllabus

log = logging.getLogger("focs.working")

# what went wrong, in a teacher's words; the first four are slips (the idea was there), the rest are gaps in the idea
ERRORS: dict[str, str] = {
    "arithmetic": "Arithmetic slip", "sign": "Sign slip", "units": "Units slip", "misread": "Misread the question",
    "formula": "Wrong formula", "setup": "Wrong set-up", "concept": "Concept gap", "algebra": "Algebra", "incomplete": "Stopped early",
}
CARELESS = frozenset({"arithmetic", "sign", "units", "misread"})
MAX_STEPS = 20
FINGERPRINT_WINDOW = 40  # the latest checks a fingerprint is drawn from
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # the app shrinks photos first; this only lets an unshrunk one through


class WorkingError(ValueError):
    """Bad input the student can fix (an empty pad, a question that isn't theirs)."""


PAD_LINE = "solved this question on a rough pad. The image is their own handwriting (a stylus or a\nfinger, so it can be messy)."
PHOTO_LINE = ("solved this question on paper. The image is a phone photo of their working: it may be tilted, shadowed or\n"
              "blurred, and may include printed text, the printed question, working for other questions, or crossed-out lines.\n"
              "Read ONLY the working for THIS question: ignore printed text and crossed-out work. If you cannot find working for\n"
              "this question in the photo, treat the page as unreadable.")

PROMPT = """A {exam} student {source_line} Read their working and check it the way a great teacher marks a copy: find the FIRST step
that goes wrong, not just whether the final answer is right.

Question: \"\"\"{question}\"\"\"
{extra}
Return ONLY a JSON object:
{{"readable": true or false (false when there is no working in the image that can be read),
  "steps": [{{"text": "each step you read, in order, as the student wrote it (math in LaTeX inside $...$)", "ok": true or false}}],
  "first_wrong": the index in steps of the first wrong step, or null when every step is right,
  "verdict": "right" (the working reaches the correct answer) | "wrong" | "incomplete" (right so far, but it stops early),
  "error_type": null when right, else exactly one of: {errors},
  "what_went_wrong": one or two sentences to the student about that exact step (null when right),
  "hint": a question or a nudge that lets them find the fix themselves, without giving the answer away (null when right),
  "fix": the corrected step with its math (null when right),
  "root_link": {root_rule},
  "earlier_idea": the earlier, school-level idea this mistake shows is shaky, in a few words; null for a pure slip}}
Rules: a slip in a sum or a sign is a slip ("arithmetic" / "sign"), not a gap in the concept: say so kindly. Never invent
steps the student did not write. Steps with no mistake are "ok": true."""


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).strip()


def find_chapter(syl: Syllabus | None, chapter_id: str | None, topic: str | None, subject: str | None) -> Chapter | None:
    """The question's chapter: by id when the page knows it, else by the topic's name (practice sets know only that)."""
    if chapter_id and (ch := gaps.chapter(syl, chapter_id)):
        return ch
    want = _norm(topic or "")
    if not syl or len(want) < 3:
        return None
    pool = [c for c in syl.chapters if not subject or _norm(c.subject) == _norm(subject)] or list(syl.chapters)
    for c in pool:
        if _norm(c.name) == want:
            return c
    for c in pool:
        name = _norm(c.name)
        if len(name) >= 5 and (name in want or want in name):
            return c
    words = set(want.split()) - {"and", "of", "the", "in", "a", "to"}
    best, score = None, 0.0
    for c in pool:
        theirs = set(_norm(c.name).split()) - {"and", "of", "the", "in", "a", "to"}
        if words and theirs:
            s = len(words & theirs) / len(words | theirs)
            if s > score:
                best, score = c, s
    return best if score >= 0.5 else None


def _text(value: Any, limit: int = 800) -> str | None:
    s = str(value or "").strip()
    return fix_latex(restore_backslashes(s))[:limit] if s and s.lower() != "null" else None


def _index(value: Any, size: int) -> int | None:
    try:
        i = int(value)
    except (TypeError, ValueError):
        return None
    return i if 0 <= i < size else None


def _prompt(user: User, question: str, options: list[str], answer: int | None, chosen: int | None, chain: list[dict],
            solution: str | None = None, *, source: str = "pad") -> str:
    extra = []
    if options:
        extra.append("Options:\n" + "\n".join(f"{'ABCD'[i] if i < 4 else i + 1}. {o}" for i, o in enumerate(options[:6])))
    if answer is not None and 0 <= answer < len(options):
        extra.append(f"The correct option is {'ABCD'[answer] if answer < 4 else answer + 1}.")
    if chosen is not None and 0 <= chosen < len(options):
        extra.append(f"The student picked {'ABCD'[chosen] if chosen < 4 else chosen + 1}.")
    if solution and solution.strip():
        # with a worked solution to compare against, models find the first wrong step far more reliably
        extra.append('A correct worked solution, for reference only (the student may use a different valid method: judge '
                     'THEIR steps on their own merits, and never copy steps from here into "steps"):\n"""'
                     + solution.replace('"""', "'''").strip()[:2500] + '"""')
    if chain:
        extra.append("This question's chapter rests on these earlier chapters (index: chapter, class: the idea it supplies):\n"
                     + "\n".join(f"{i}: {c['name']}, Class {c.get('cls') or '?'}: {c.get('idea') or c['name']}" for i, c in enumerate(chain)))
        rule = "the index of the earlier chapter above that the mistake really comes from, or null when it is a slip or none fits"
    else:
        rule = "null"
    return PROMPT.format(exam=syllabus.label(user.exam_target), question=question.replace('"""', "'''").strip()[:1500], extra="\n".join(extra) + "\n",
                         source_line=PHOTO_LINE if source == "photo" else PAD_LINE, errors=", ".join(ERRORS), root_rule=rule)


def _read(data: dict[str, Any], chain: list[dict]) -> dict[str, Any]:
    """The model's answer, checked: only fields of the right shape, indexes that point at something."""
    if not data.get("readable", True):
        raise WorkingError("Couldn't read any working on the pad. Write the steps a little larger and try again.")
    steps = []
    for row in (data.get("steps") or [])[:MAX_STEPS]:
        text = _text(row.get("text") if isinstance(row, dict) else row, 400)
        if text:
            steps.append({"text": text, "ok": bool(row.get("ok", True)) if isinstance(row, dict) else True})
    if not steps:
        raise WorkingError("Couldn't read any working on the pad. Write the steps a little larger and try again.")
    first = _index(data.get("first_wrong"), len(steps))
    if first is None:
        first = next((i for i, s in enumerate(steps) if not s["ok"]), None)
    verdict = data.get("verdict") if data.get("verdict") in ("right", "wrong", "incomplete") else ("wrong" if first is not None else "right")
    if verdict == "right":
        first = None
    error = data.get("error_type") if data.get("error_type") in ERRORS else None
    if verdict != "right" and error is None:
        error = "incomplete" if verdict == "incomplete" else "concept"
    if verdict == "right":
        error = None
    root = _index(data.get("root_link"), len(chain)) if verdict != "right" and error not in CARELESS else None
    return {"steps": steps, "first_wrong": first, "verdict": verdict, "error_type": error,
            "what_went_wrong": _text(data.get("what_went_wrong"), 600) if verdict != "right" else None,
            "hint": _text(data.get("hint"), 400) if verdict != "right" else None,
            "fix": _text(data.get("fix"), 600) if verdict != "right" else None,
            "root": ({k: chain[root].get(k) for k in ("chapter_id", "name", "subject", "cls", "idea")} if root is not None else None),
            "earlier_idea": _text(data.get("earlier_idea"), 160) if verdict != "right" and error not in CARELESS else None}


def _key(text: str) -> str:
    """A question's text reduced to its letters and digits, for "is this the same question" (spacing, markup aside)."""
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())[:120]


def still_open(db: Session, user: User, question: str) -> bool:
    """Is this a question the student hasn't answered yet: a check in a root-cause trace still being taken, or a
    question of a mock test still running? Checking the working there would hand over the answer."""
    want = _key(question)
    if len(want) < 12:
        return False

    def same(text: str) -> bool:
        k = _key(text)
        return bool(k) and (k.startswith(want[:60]) or want.startswith(k[:60]))

    for t in db.scalars(select(GapTrace).where(GapTrace.user_id == user.id, GapTrace.status == "checking")):
        texts = [(link.get("check") or {}).get("q", "") for link in t.chain or []]
        texts += [item.get("q", "") for item in ((t.retest or {}).get("before") or {}).get("items", [])]
        if any(same(x) for x in texts):
            return True
    running = [i for ids in db.scalars(select(MockTest.question_ids).where(
        MockTest.user_id == user.id, MockTest.status.in_(("ready", "in_progress")))) for i in (ids or [])]
    if running:
        return any(same(q) for q in db.scalars(select(BankQuestion.question).where(BankQuestion.id.in_(running[:400]))))
    return False


def check(db: Session, user: User, syl: Syllabus | None, image: bytes, question: str, options: list[str] | None,
          answer: int | None, chosen: int | None, chapter_id: str | None, topic: str | None, subject: str | None,
          solution: str | None = None, source: str = "pad") -> WorkingCheck:
    """Read and check one page of working, drawn on the pad or photographed on paper. Raises WorkingError, LLMUnavailable."""
    if not image or len(image) > MAX_IMAGE_BYTES:
        raise WorkingError("The picture of your working is empty or too large.")
    if not question.strip():
        raise WorkingError("Which question is this working for?")
    if still_open(db, user, question):
        raise WorkingError("Answer the question first: then Focs checks your working.")
    try:
        jpeg = vision.to_jpeg(image)
    except ValueError as exc:
        raise WorkingError("That isn't an image Focs can read.") from exc
    target = find_chapter(syl, chapter_id, topic, subject)
    chain: list[dict] = []
    if target is not None and (kept := db.get(PrereqMap, target.id)) is not None:
        chain = list(kept.chain or [])
    options = [str(o)[:300] for o in (options or [])][:6]
    data = vision.read_json([jpeg], _prompt(user, question, options, answer, chosen, chain, solution, source=source), "working_check", max_tokens=2400)
    read = _read(data, chain)
    row = WorkingCheck(user_id=user.id, chapter_id=target.id if target else None, question=question.strip()[:2000],
                       verdict=read["verdict"], error_type=read["error_type"],
                       root_chapter_id=read["root"]["chapter_id"] if read["root"] else None,
                       result={**read, "options": options, "answer": answer, "chosen": chosen,
                               "chapter": {"id": target.id, "name": target.name, "subject": target.subject} if target else None,
                               "has_chain": bool(chain), "source": source})
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def owned(db: Session, user: User, check_id: int) -> WorkingCheck:
    row = db.get(WorkingCheck, check_id)
    if row is None or row.user_id != user.id:
        raise WorkingError("That check isn't yours.")
    return row


def fingerprint(db: Session, user_id: int) -> dict[str, Any]:
    """How this student loses marks: careless slips or gaps in ideas, from their latest checked working. No AI."""
    rows = db.execute(select(WorkingCheck.verdict, WorkingCheck.error_type).where(WorkingCheck.user_id == user_id)
                      .order_by(WorkingCheck.id.desc()).limit(FINGERPRINT_WINDOW)).all()
    wrong = [e for v, e in rows if v != "right" and e]
    kinds = Counter(wrong)
    slips = sum(n for k, n in kinds.items() if k in CARELESS)
    return {"checked": len(rows), "right": sum(1 for v, _ in rows if v == "right"), "mistakes": len(wrong),
            "slips": slips, "gaps": len(wrong) - slips,
            "careless_share": round(100 * slips / len(wrong)) if wrong else None,
            "kinds": [{"type": k, "label": ERRORS[k], "count": n, "careless": k in CARELESS} for k, n in kinds.most_common()]}


def _again(db: Session, user_id: int, root_chapter_id: str | None) -> dict[str, Any] | None:
    """The same root behind earlier slips too, and the student's own trace of it, when there is one."""
    if not root_chapter_id:
        return None
    times = db.scalar(select(func.count()).select_from(WorkingCheck)
                      .where(WorkingCheck.user_id == user_id, WorkingCheck.root_chapter_id == root_chapter_id)) or 0
    trace = None
    for t in db.scalars(select(GapTrace).where(GapTrace.user_id == user_id, GapTrace.root.is_not(None))
                        .order_by(GapTrace.id.desc()).limit(30)):
        if t.chain and t.root < len(t.chain) and t.chain[t.root]["chapter_id"] == root_chapter_id:
            trace = {"id": t.id, "status": t.status}
            break
    return {"times": times, "trace": trace}


def view(db: Session, row: WorkingCheck) -> dict[str, Any]:
    r = dict(row.result or {})
    return {"id": row.id, "question": row.question, "verdict": row.verdict, "steps": r.get("steps") or [],
            "first_wrong": r.get("first_wrong"), "error_type": row.error_type, "error_label": ERRORS.get(row.error_type or ""),
            "careless": row.error_type in CARELESS, "what_went_wrong": r.get("what_went_wrong"), "hint": r.get("hint"),
            "fix": r.get("fix"), "root": r.get("root"), "earlier_idea": r.get("earlier_idea"), "chapter": r.get("chapter"),
            "has_chain": bool(r.get("has_chain")), "again": _again(db, row.user_id, row.root_chapter_id),
            "fingerprint": fingerprint(db, row.user_id), "created_at": row.created_at.isoformat() if row.created_at else None}


def root_evidence(db: Session, user_id: int) -> list[tuple[str, str]]:
    """(the question's chapter, the earlier chapter the slip came from) for every checked slip that landed on a root:
    silent tracing counts these next to mock-test misses (gaps.suspects)."""
    return [(c, r) for c, r in db.execute(select(WorkingCheck.chapter_id, WorkingCheck.root_chapter_id)
                                          .where(WorkingCheck.user_id == user_id, WorkingCheck.root_chapter_id.is_not(None),
                                                 WorkingCheck.chapter_id.is_not(None))).all()]


# ---------------------------------------------------------------- the tutor

TUTOR_SYSTEM = """You are Focs, a personal tutor for one {exam} student. Unlike a general chatbot you know this student:
what they are working on, the exact step they got wrong, the earlier gaps behind their trouble, and how they usually lose
marks (below). Use it: connect your answer to their step and their gaps whenever it helps, and say so plainly ("this is
the same Class 10 idea that tripped you in torque").
Teach like a patient teacher: one idea at a time, short lines, a worked line of math when it helps, and end with ONE
short question back that makes them think (not when they only asked for the answer). Markdown and LaTeX ($...$).
Under 170 words unless the question truly needs more. If they ask something unrelated to studies, gently steer back."""


def _student(db: Session, user: User, syl: Syllabus | None) -> str:
    lines = []
    if roots := gaps.open_roots(db, user.id):
        lines.append("Root gaps found and not fixed yet: " + "; ".join(
            f"{r['root']} (Class {r['cls'] or '?'} {r['chapter']}, behind {r['stuck_on']})" for r in roots[:4]))
    fixed = db.scalars(select(GapTrace).where(GapTrace.user_id == user.id, GapTrace.status == "fixed").limit(4)).all()
    if fixed:
        lines.append("Gaps they fixed: " + "; ".join(t.chain[t.root]["idea"] for t in fixed if t.root is not None and t.chain))
    weak = db.scalars(select(WeakTopic).where(WeakTopic.user_id == user.id, WeakTopic.status == "open")
                      .order_by(WeakTopic.misses.desc()).limit(5)).all()
    if weak:
        lines.append("Weak chapters: " + ", ".join(gaps.chapter(syl, w.chapter_id).name if gaps.chapter(syl, w.chapter_id) else w.chapter_id
                                                   for w in weak))
    fp = fingerprint(db, user.id)
    if fp["mistakes"]:
        lines.append(f"How they lose marks (last {fp['checked']} checked solutions): "
                     + ", ".join(f"{k['label'].lower()} x{k['count']}" for k in fp["kinds"][:4])
                     + (f"; {fp['careless_share']}% are careless slips" if fp["careless_share"] is not None else ""))
    return "\n".join(f"- {line}" for line in lines) or "- Nothing yet: this is one of their first questions."


def _on_this(row: WorkingCheck) -> str:
    r = row.result or {}
    steps = "\n".join(f"{i + 1}. {s['text']}{'  <- first wrong step' if i == r.get('first_wrong') else ''}"
                      for i, s in enumerate(r.get("steps") or []))
    root = r.get("root")
    return (f"The question: {row.question}\nTheir working, as read from their working:\n{steps}\n"
            f"Verdict: {row.verdict}" + (f"; {ERRORS.get(row.error_type or '', '')}: {r.get('what_went_wrong')}" if row.verdict != "right" else "")
            + (f"\nCorrect step: {r.get('fix')}" if r.get("fix") else "")
            + (f"\nThe earlier chapter it comes from: {root['name']} (Class {root.get('cls') or '?'}): {root.get('idea')}" if root else ""))


def tutor(db: Session, user: User, syl: Syllabus | None, question: str, history: list[dict[str, str]],
          row: WorkingCheck | None = None, chapter: Chapter | None = None) -> dict[str, Any]:
    """One tutor, opened from a checked question (``row``) or from a chapter (``chapter``), knowing the student.
    Raises LLMUnavailable."""
    system = TUTOR_SYSTEM.format(exam=syllabus.label(user.exam_target))
    system += f"\n\nAbout this student:\n{_student(db, user, syl)}"
    if row is not None:
        system += f"\n\nWhat they are working on right now:\n{_on_this(row)}"
    elif chapter is not None:
        kept = db.get(PrereqMap, chapter.id)
        rests = "; ".join(f"{c['name']} (Class {c.get('cls') or '?'}): {c.get('idea')}" for c in (kept.chain if kept else None) or [])
        system += f"\n\nThe chapter they opened the tutor from: {chapter.name} ({chapter.subject})." + (f"\nIt rests on: {rests}" if rests else "")
    if rule := ai.language_rule(user.language):
        system += f"\n\nLanguage: {rule}"
    messages = [{"role": "system", "content": system}]
    for turn in history[-8:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": str(turn["content"])[:1500]})
    messages.append({"role": "user", "content": question.strip()[:1500] + ai.REPLY_IN.get(user.language or "", "")})
    return {"answer": fix_latex(llm.chat(messages, max_tokens=700, temperature=0.4, feature="tutor"))}


__all__ = ["CARELESS", "ERRORS", "LLMUnavailable", "WorkingError", "check", "find_chapter", "fingerprint", "owned",
           "root_evidence", "tutor", "view"]
