"""Root-cause gap tracing: why a topic doesn't make sense, found by going back through the chapters it rests on.

A student who can't follow torque is rarely missing torque. They are missing the cross product (Class 11 vectors),
which rests on angles and components (Class 10 trigonometry), which rests on similar triangles (Class 9). Coaching
re-teaches the symptom; this finds the cause:

1. Trace. A model picks the chain of prerequisite chapters for the topic, from real chapters of the syllabus and
   the earlier school classes only (never invented ones), closest first, each with the exact idea it supplies and
   one quick question that checks it. The chain is the same for every student, so it is stored once (PrereqMap)
   and only the first student to trace a chapter spends any AI.
2. Diagnose. The student answers the questions. The deepest link they miss is the root gap: fix that and the links
   above it can hold.
3. Fix. A five-minute lesson on the root idea, in the student's language, ending with how it unlocks the topic they
   were stuck on, and a fresh question to show the gap is closed.

Open roots go to the student's Focs Coach, which then plans the root before the symptom.
"""
from __future__ import annotations

import logging
import random
from collections import Counter
from functools import cache
from statistics import median
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models._util import utcnow
from app.models.gap import GapTrace, PrereqMap
from app.models.llm_call import LlmCall
from app.models.mock import BankQuestion
from app.models.user import User
from app.models.weak import WeakTopic
from app.models.working import WorkingCheck
from app.services import ai, question_bank, syllabus
from app.services.llm import LLMUnavailable, llm
from app.services.syllabus import Chapter, Syllabus

log = logging.getLogger("focs.gaps")

MAX_LINKS = 4
POOL_LIMIT = 220
# the school subjects a subject's ideas come from (languages and humanities never feed a science chain)
FAMILY = {
    "Physics": ("Physics", "Mathematics", "Science"),
    "Chemistry": ("Chemistry", "Science", "Mathematics"),
    "Biology": ("Biology", "Science", "Chemistry"),
    "Botany": ("Biology", "Science", "Chemistry"),
    "Zoology": ("Biology", "Science", "Chemistry"),
    "Mathematics": ("Mathematics",),
    "Science": ("Science", "Mathematics"),
}


class GapError(Exception):
    """Something the student should be told plainly (no chain could be found, a step out of order)."""


# ---------------------------------------------------------------------------------------------------- chapters
@cache
def _school_by_id() -> dict[str, Chapter]:
    return {c.id: c for _, c in syllabus._school_chapters().values()}


def chapter(syl: Syllabus | None, chapter_id: str) -> Chapter | None:
    return (syl.by_id.get(chapter_id) if syl else None) or _school_by_id().get(chapter_id)


def _level(ch: Chapter, syl: Syllabus | None) -> int:
    """How far along a student meets this chapter, as a school class (college and GATE come after Class 12)."""
    if syl is not None and syl.kind in ("college", "gate", "placement"):
        return 13
    return ch.cls if 1 <= ch.cls <= 12 else 11


def candidates(syl: Syllabus | None, target: Chapter) -> list[Chapter]:
    """The chapters a chain may use: what comes before the target in the student's own syllabus, and the related
    subjects of the school classes before it."""
    level = _level(target, syl)
    family = FAMILY.get(target.subject, (target.subject, "Mathematics"))
    pool: list[Chapter] = []
    if syl is not None and target.id in syl.by_id:
        same = syl.subject_chapters(target.subject)
        pool += same[max(0, same.index(target) - 14):same.index(target)]
        if target.subject != "Mathematics" and syl.has_subject("Mathematics"):
            pool += [c for c in syl.subject_chapters("Mathematics") if c.cls <= target.cls]
    top = min(level, 11 if level >= 11 else level)  # an entrance syllabus covers Classes 11-12 itself
    for c in _school_by_id().values():
        if c.subject in family and max(5, level - 5) <= c.cls < max(top, 6) and c.id != target.id:
            pool.append(c)
    seen: set[str] = set()
    out = [c for c in pool if c.id != target.id and not (c.id in seen or seen.add(c.id))]
    return out[-POOL_LIMIT:]


# ---------------------------------------------------------------------------------------------------- the chain
TRACE_SYSTEM = """You find why a student can't follow a topic: the earlier ideas it rests on, the way a great teacher
diagnoses a weak student. Think about what a student must ALREADY know before this topic can make sense.

Choose a chain of 2 to {most} prerequisite chapters, ONLY from the CANDIDATES (copy each id exactly):
- Every link must be a genuine prerequisite: an idea TAUGHT IN THAT CANDIDATE CHAPTER (not an idea of the topic
  itself, and not one the chapter doesn't teach). Torque, for instance, is not a prerequisite of rotational motion.
- Order: link 1 is what the topic uses most directly; each next link is what the previous one rests on, going
  DOWN to earlier classes (the class never goes up along the chain).
- At least one link must come from Class 10 or earlier: that is where most real gaps start (algebra, ratios,
  trigonometry, graphs, basic science).
For each link give:
- chapter_id
- idea: the exact concept from that chapter the topic needs (3 to 8 words)
- why: one line on how the topic (or the link above) uses it
- check: one multiple-choice question testing exactly that idea, answerable in under a minute without a calculator:
  {{"q": the question, "options": 4 short options, "answer": index 0-3 of the right one, "explain": one line}}
Return {{"chain": [...]}}. Use $...$ for maths."""


def _clean_check(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    options = [str(o).strip() for o in raw.get("options") or [] if str(o).strip()]
    try:
        answer = int(raw.get("answer"))
    except (TypeError, ValueError):
        return None
    q = str(raw.get("q") or raw.get("question") or "").strip()
    if not q or len(options) != 4 or not 0 <= answer < 4:
        return None
    return agreeing({"q": q, "options": options, "answer": answer, "explain": str(raw.get("explain") or "").strip()})


def _plain(text: str) -> str:
    """A value written one way for comparing ("6π m." and "6π m" agree): letters, digits and maths signs only."""
    return "".join(ch for ch in text.lower() if ch.isalnum() or ch in "/^-+·×√°%")


def agreeing(check: dict[str, Any]) -> dict[str, Any]:
    """The check with its answer matching its own working. The model sometimes marks one option while its working
    lands on another ("C = 2πr = 2π·3 = 6π m" with 9π m marked right), and a student who knew it was told they were
    wrong. The working is the one to trust; only a single exact match counts, anything less certain is left alone."""
    explain = str(check.get("explain") or "")
    if "=" not in explain:
        return check
    value = _plain(explain.rsplit("=", 1)[1])
    hits = [i for i, option in enumerate(check["options"]) if value and _plain(option) == value]
    if len(hits) == 1 and hits[0] != check["answer"]:
        log.info("gap check answer corrected to match its working: %r", check["q"][:80])
        return {**check, "answer": hits[0]}
    return check


def _ask_chain(syl: Syllabus | None, target: Chapter, topic_name: str | None) -> list[dict[str, Any]]:
    pool = candidates(syl, target)
    if not pool:
        raise GapError("There are no earlier chapters to trace this one back to.")
    by_id = {c.id: c for c in pool}
    listing = "\n".join(f"{c.id} | Class {c.cls if 1 <= c.cls <= 12 else '11-12'} | {c.subject} | {c.name}" for c in pool)
    what = f"{target.subject}: {target.name}" + (f" (the topic: {topic_name})" if topic_name else "")
    data = llm.json([{"role": "system", "content": TRACE_SYSTEM.format(most=MAX_LINKS)},
                     {"role": "user", "content": f"TOPIC: {what}\n\nCANDIDATES (id | class | subject | chapter):\n{listing}"}],
                    max_tokens=4000, temperature=0.1, effort="medium", feature="gap_trace")  # shared by every student: worth thinking
    chain: list[dict[str, Any]] = []
    for link in data.get("chain") or []:
        if not isinstance(link, dict):
            continue
        ch = by_id.get(str(link.get("chapter_id") or "").strip())
        check = _clean_check(link.get("check"))
        if ch is None or check is None or any(x["chapter_id"] == ch.id for x in chain):
            continue  # an invented chapter, a broken question or a repeat: dropped, never shown
        if chain and chain[-1]["cls"] and 1 <= ch.cls <= 12 and ch.cls > chain[-1]["cls"]:
            continue  # the chain only goes down to earlier classes
        chain.append({"chapter_id": ch.id, "name": ch.name, "subject": ch.subject, "cls": ch.cls if 1 <= ch.cls <= 12 else None,
                      "idea": str(link.get("idea") or ch.name).strip()[:120], "why": str(link.get("why") or "").strip()[:240],
                      "check": check})
    if not chain:
        raise GapError("Couldn't work out what this topic rests on right now. Try again in a minute.")
    return chain[:MAX_LINKS]


def prereq_chain(db: Session, syl: Syllabus | None, target: Chapter, topic_id: str | None, topic_name: str | None) -> tuple[list, bool]:
    """The chain for a chapter (or one of its topics), and whether the AI had to be asked (False: shared, free)."""
    key = f"{target.id}#{topic_id}" if topic_id else target.id
    hit = db.get(PrereqMap, key)
    if hit and hit.chain:
        chain = [{**link, "check": agreeing(link["check"])} for link in hit.chain]
        if chain != hit.chain:  # kept before answers were checked against their working: corrected once, for everyone
            hit.chain = chain
            db.commit()
        return chain, False
    chain = _ask_chain(syl, target, topic_name)
    db.merge(PrereqMap(key=key, chain=chain))
    db.commit()
    return chain, True


# ---------------------------------------------------------------------------------------------------- a trace
RETEST = 3  # questions on the stuck topic itself: asked before the trace, and three different ones after the fix


def _bank_check(row: BankQuestion) -> dict[str, Any] | None:
    """A bank question as a check, when it can be shown as one: four text options and no pictures."""
    options = [str(o).strip() for o in row.options or []]
    try:
        right = int(row.answer)
    except (TypeError, ValueError):
        return None
    if len(options) != 4 or not all(options) or not 0 <= right < 4 or row.media:
        return None
    return {"q": row.question, "options": options, "answer": right, "explain": (row.solution or "").strip()[:600]}


def _retest(db: Session, user: User, target: Chapter) -> dict[str, Any] | None:
    """Questions on the topic the student is stuck on, from the question bank (no AI): three before the trace and
    three others after the fix, so the student and their teacher see whether fixing the root helped. None when the
    bank doesn't have six it can show."""
    rows, _ = question_bank.pick(db, target.subject, "mcq", 4 * RETEST, set(), chapters=[target.name], exam=user.exam_target)
    items = [c for c in (_bank_check(r) for r in rows) if c][: 2 * RETEST]
    if len(items) < 2 * RETEST:
        return None
    return {"before": {"items": items[:RETEST], "choices": None, "right": None},
            "after": {"items": items[RETEST:], "choices": None, "right": None}}


def _scored(retest: dict[str, Any], phase: str, choices: list[int | None]) -> dict[str, Any]:
    part = retest[phase]
    if len(choices) != len(part["items"]):
        raise GapError("Answer every question (or skip it) first.")
    right = sum(c == item["answer"] for c, item in zip(choices, part["items"]))
    return {**retest, phase: {**part, "choices": list(choices), "right": right}}


def start(db: Session, user: User, syl: Syllabus | None, chapter_id: str, topic_id: str | None) -> tuple[GapTrace, bool]:
    target = chapter(syl, chapter_id)
    if target is None:
        raise GapError("That chapter isn't in your syllabus.")
    topic = next((t for t in target.topics if t.id == topic_id), None) if topic_id else None
    chain, used_ai = prereq_chain(db, syl, target, topic.id if topic else None, topic.name if topic else None)
    trace = GapTrace(user_id=user.id, chapter_id=target.id, topic_id=topic.id if topic else None,
                     title=f"{topic.name} ({target.name})" if topic else target.name,
                     chain=[{**link, "result": None} for link in chain], status="checking")
    try:
        trace.retest = _retest(db, user, target)
    except Exception:  # the before-and-after questions are a bonus: a bank problem never stops a trace
        log.exception("no retest questions for %s", target.id)
    db.add(trace)
    db.commit()
    return trace, used_ai


def owned(db: Session, user: User, trace_id: int) -> GapTrace:
    trace = db.get(GapTrace, trace_id)
    if trace is None or trace.user_id != user.id:
        raise GapError("That trace doesn't exist.")
    return trace


def answer(db: Session, trace: GapTrace, choices: list[int | None], before: list[int | None] | None = None) -> GapTrace:
    """Mark each link; the root gap is the deepest link missed (fix the bottom and the ones above it can hold).
    ``before``: the answers to the questions on the stuck topic itself, the "before" of before-and-after."""
    db.refresh(trace, with_for_update=True)  # two taps at once: the second waits, then sees the first one's answers
    if trace.status != "checking":
        raise GapError("These questions are already answered.")
    chain = [dict(link) for link in trace.chain or []]
    if len(choices) != len(chain):
        raise GapError("Answer every question (or skip it) first.")
    if trace.retest and before is not None:
        trace.retest = _scored(trace.retest, "before", before)
    for link, choice in zip(chain, choices):
        link["choice"] = choice
        link["result"] = "right" if choice == link["check"]["answer"] else "wrong"  # a skip counts as not known yet
    missed = [i for i, link in enumerate(chain) if link["result"] == "wrong"]
    trace.chain = chain
    trace.root = missed[-1] if missed else None
    trace.status = "found" if missed else "clear"
    db.commit()
    return trace


LESSON_SYSTEM = """You fix one gap in a student's foundations in five minutes. The student is stuck on "{target}"
because they don't yet have this earlier idea: "{idea}" (from {chapter}, {where}).

Write the fix in Markdown, under 220 words:
1. The idea in plain words, the way a good senior would explain it.
2. An everyday example from Indian life.
3. One short worked example.
4. A last line starting "How this unlocks {target}:" that connects it to what they were stuck on.
Use $...$ for maths. Then one NEW multiple-choice question (different from: "{old_q}") that shows the gap is closed.
Return {{"lesson_md": "...", "check": {{"q", "options": 4, "answer": 0-3, "explain"}}}}."""


def lesson(db: Session, user: User, trace: GapTrace) -> tuple[GapTrace, bool]:
    """The short lesson for the root gap, shared between students who share the gap and the language."""
    if trace.status not in ("found", "fixed") or trace.root is None:
        raise GapError("There's no root gap to fix on this trace.")
    if trace.lesson:
        return trace, False
    made, used_ai = _made_lesson(db, trace.chain[trace.root], trace.title, trace.chapter_id, user.language)
    trace.lesson = {**made, "result": None}
    db.commit()
    return trace, used_ai


def _made_lesson(db: Session, link: dict[str, Any], title: str, chapter_id: str, language: str | None,
                 before_ai: Callable[[], None] | None = None) -> tuple[dict[str, Any], bool]:
    """The five-minute lesson on one earlier idea behind one topic, in one language: written once, then shared by every
    student (and teacher) who needs the same one. (lesson, whether the AI was asked)"""
    key = f"lesson:{link['chapter_id']}:{link['idea'][:80]}:{chapter_id}:{language or 'en'}"
    hit = db.get(PrereqMap, key)
    if hit and hit.chain:
        return hit.chain, False
    if before_ai:
        before_ai()  # e.g. the usage check: only a lesson that has to be written costs anything
    where = f"Class {link['cls']}" if link.get("cls") else "earlier in your course"
    data = llm.json([{"role": "system", "content": ai._in(LESSON_SYSTEM.format(
                        target=title, idea=link["idea"], chapter=link["name"], where=where, old_q=link["check"]["q"]), language)},
                     # the language said again after the request: with only the system rule a Hinglish lesson came back in English
                     {"role": "user", "content": f"Why the topic needs it: {link.get('why') or link['idea']}{ai.REPLY_IN.get(language or '', '')}"}],
                    max_tokens=2200, temperature=0.3, feature="gap_lesson")
    check = _clean_check(data.get("check"))
    md = str(data.get("lesson_md") or "").strip()
    if not md or check is None:
        raise GapError("Couldn't write the lesson right now. Try again in a minute.")
    made = {"md": ai.fix_latex(md), "check": check}
    db.merge(PrereqMap(key=key, chain=made))
    return made, True


def class_recap(db: Session, teacher: User, user_ids: list[int], root_chapter_id: str,
                before_ai: Callable[[], None] | None = None) -> tuple[dict[str, Any], bool]:
    """A batch's "teach first": the five-minute lesson on an earlier gap several of its students share, in the
    teacher's language, with its check question and answer, for a ten-minute recap in class. Students who already got
    that lesson have paid for it: then it costs nothing. (recap, whether the AI was asked)"""
    traces = db.scalars(select(GapTrace).where(GapTrace.user_id.in_(user_ids or [-1]), GapTrace.status.in_(("found", "fixed")))).all()
    hits = [t for t in traces if t.root is not None and t.chain and t.root < len(t.chain) and t.chain[t.root]["chapter_id"] == root_chapter_id]
    if not hits:
        raise GapError("No student in this class has that gap.")
    target = Counter(t.chapter_id for t in hits).most_common(1)[0][0]  # the topic most of them were stuck on
    sample = next(t for t in hits if t.chapter_id == target)
    link = sample.chain[sample.root]
    made, used_ai = _made_lesson(db, link, sample.title, sample.chapter_id, teacher.language, before_ai)
    db.commit()
    return {"chapter_id": link["chapter_id"], "name": link["name"], "cls": link.get("cls"), "idea": link["idea"],
            "stuck_on": sample.title, "students": len({t.user_id for t in hits}), "md": made["md"], "check": made["check"]}, used_ai


def recheck(db: Session, trace: GapTrace, choice: int) -> GapTrace:
    db.refresh(trace, with_for_update=True)  # two taps at once: the second waits, then sees the first one's answers
    if not trace.lesson:
        raise GapError("Read the lesson first.")
    if trace.status == "fixed":
        raise GapError("This gap is already closed.")
    right = choice == trace.lesson["check"]["answer"]
    result = "right" if right else "wrong"
    # the first try is the one that measures the lesson: a retry after "not yet" can be a guess among what's left
    trace.lesson = {**trace.lesson, "choice": choice, "result": result, "first": trace.lesson.get("first") or result}
    if right:
        trace.status = "fixed"
    db.commit()
    return trace


# ---------------------------------------------------------------------------------------------------- what's shown
def after(db: Session, trace: GapTrace, choices: list[int | None]) -> GapTrace:
    """The stuck topic again, once its root gap is fixed: did fixing the root help?"""
    db.refresh(trace, with_for_update=True)  # two taps at once: the second waits, then sees the first one's answers
    if trace.status != "fixed" or not trace.retest:
        raise GapError("Fix the root gap first.")
    if trace.retest["after"]["right"] is not None:
        raise GapError("These questions are already answered.")
    trace.retest = _scored(trace.retest, "after", choices)
    db.commit()
    return trace


def _retest_view(trace: GapTrace) -> dict[str, Any] | None:
    """The before-and-after questions, their answers kept on the server until answered (the "after" ones stay hidden
    until the root is fixed)."""
    if not trace.retest:
        return None
    out = {}
    for phase in ("before", "after"):
        part = trace.retest[phase]
        done = part["right"] is not None
        shown = phase == "before" or trace.status == "fixed"
        out[phase] = {"items": [item if done else {"q": item["q"], "options": item["options"]} for item in part["items"]] if shown else [],
                      "choices": part["choices"], "right": part["right"], "total": len(part["items"])}
    return out


def view(trace: GapTrace) -> dict[str, Any]:
    """A trace for the app. While the questions are open, their answers stay on the server."""
    answered = trace.status != "checking"
    chain = []
    for link in trace.chain or []:
        check = link["check"] if answered else {"q": link["check"]["q"], "options": link["check"]["options"]}
        chain.append({**{k: v for k, v in link.items() if k != "check"}, "check": check})
    lesson_out = None
    if trace.lesson:
        solved = trace.lesson.get("result") == "right"  # the answer only once they have it: after "not yet", they try again for real
        c = trace.lesson["check"]
        lesson_out = {"md": trace.lesson["md"], "result": trace.lesson.get("result"), "choice": trace.lesson.get("choice"),
                      "check": c if solved else {"q": c["q"], "options": c["options"]}}
    return {"id": trace.id, "title": trace.title, "chapter_id": trace.chapter_id, "topic_id": trace.topic_id,
            "status": trace.status, "root": trace.root, "chain": chain, "lesson": lesson_out, "retest": _retest_view(trace),
            "created_at": trace.created_at.isoformat() + "Z" if trace.created_at else None}


def overview(db: Session, user: User, syl: Syllabus | None) -> dict[str, Any]:
    traces = db.scalars(select(GapTrace).where(GapTrace.user_id == user.id).order_by(GapTrace.id.desc()).limit(12)).all()
    weak = db.scalars(select(WeakTopic).where(WeakTopic.user_id == user.id, WeakTopic.status == "open")
                      .order_by(WeakTopic.misses.desc()).limit(10)).all()
    suggestions = []
    for w in weak:
        ch = chapter(syl, w.chapter_id)
        if ch is None:
            continue
        topic = next((t for t in ch.topics if t.id == w.topic_id), None)
        suggestions.append({"chapter_id": ch.id, "topic_id": topic.id if topic else None, "subject": ch.subject,
                            "name": topic.name if topic else ch.name, "chapter": ch.name, "misses": w.misses})
    chapters = [{"id": c.id, "subject": c.subject, "name": c.name, "cls": c.cls} for c in (syl.chapters if syl else ())]
    return {"traces": [view(t) for t in traces], "suggestions": suggestions, "chapters": chapters,
            "suspects": suspects(db, user.id, syl),
            "fixed": sum(t.status == "fixed" for t in traces)}


def open_roots(db: Session, user_id: int) -> list[dict[str, Any]]:
    """Root gaps found and not yet fixed (for a study plan to put first)."""
    rows = db.scalars(select(GapTrace).where(GapTrace.user_id == user_id, GapTrace.status == "found")
                      .order_by(GapTrace.id.desc()).limit(6)).all()
    out = []
    for t in rows:
        if t.root is None or not t.chain:
            continue
        link = t.chain[t.root]
        out.append({"stuck_on": t.title, "root": link["idea"], "chapter": link["name"], "cls": link.get("cls"), "trace_id": t.id})
    return out


BATCH_ROOTS_SHOWN = 6


def batch_roots(db: Session, user_ids: list[int]) -> dict[str, Any]:
    """Where a whole class's trouble really starts: every member's traced root gaps, added up by the earlier chapter
    they lead to. "Rotational Motion is weak" tells a teacher what to re-teach; "five of the eight students stuck on
    it are missing Class 10 trigonometry" tells them what to teach first. Counts only: no student is named."""
    out: dict[str, Any] = {"traced": 0, "with_root": 0, "fixed": 0, "roots": []}
    if not user_ids:
        return out
    traces = db.scalars(select(GapTrace).where(GapTrace.user_id.in_(user_ids), GapTrace.status != "checking")).all()
    roots: dict[str, dict[str, Any]] = {}
    traced, rooted, fixed = set(), set(), set()
    for t in traces:
        traced.add(t.user_id)
        if t.root is None or not t.chain or t.root >= len(t.chain):
            continue
        link = t.chain[t.root]
        rooted.add(t.user_id)
        r = roots.setdefault(link["chapter_id"], {"chapter_id": link["chapter_id"], "name": link["name"], "subject": link.get("subject"),
                                                  "cls": link.get("cls"), "ideas": Counter(), "students": set(), "fixed": set(),
                                                  "stuck_on": Counter()})
        r["ideas"][link["idea"]] += 1
        r["students"].add(t.user_id)
        r["stuck_on"][t.title] += 1
        if t.status == "fixed":
            r["fixed"].add(t.user_id)
            fixed.add(t.user_id)
    ranked = sorted(roots.values(), key=lambda r: (-len(r["students"]), r["cls"] or 99, r["name"]))
    out.update(traced=len(traced), with_root=len(rooted), fixed=len(fixed), roots=[{
        "chapter_id": r["chapter_id"], "name": r["name"], "subject": r["subject"], "cls": r["cls"],
        "idea": r["ideas"].most_common(1)[0][0], "students": len(r["students"]), "fixed": len(r["fixed"]),
        "share": round(100 * len(r["students"]) / len(rooted)), "stuck_on": [name for name, _ in r["stuck_on"].most_common(3)],
    } for r in ranked[:BATCH_ROOTS_SHOWN]])
    return out


GAP_FEATURES = ("gap_trace", "gap_lesson")
DEMO_PREFIX = "demo.focs."  # scripts/seed_demo.py's accounts


def proof(db: Session, only: set[int] | None = None) -> dict[str, Any]:
    """How root-cause tracing goes for real students, from the app's own records (never estimated): how often a trace
    finds an earlier gap, how often the five-minute fix works on the re-check, how long fixing takes, how many traces
    reused a chain another student's trace had already paid for, and what the AI behind it cost per student."""
    real = (select(User.id).where(User.id.in_(only or [-1])) if only is not None  # the caller's own "real" (scripts/evidence.py)
            else select(User.id).where(User.email.not_like(f"{DEMO_PREFIX}%")))  # the seeded demo accounts never count
    started = db.scalar(select(func.count(GapTrace.id)).where(GapTrace.user_id.in_(real))) or 0
    done = db.scalars(select(GapTrace).where(GapTrace.status != "checking", GapTrace.user_id.in_(real))).all()
    chains = db.scalar(select(func.count(PrereqMap.key))) or 0
    usd = float(db.scalar(select(func.coalesce(func.sum(LlmCall.cost_usd), 0.0))
                          .where(LlmCall.feature.in_(GAP_FEATURES), LlmCall.user_id.in_(real))) or 0.0)
    return summarize(list(done), started, chains, usd)


def summarize(done: list[GapTrace], started: int, chains: int, usd: float) -> dict[str, Any]:
    """proof()'s figures from the finished traces, the traces started, the chains the AI built and what it cost."""
    rooted = [t for t in done if t.root is not None and t.chain and t.root < len(t.chain)]
    lessons = [t for t in rooted if t.lesson]
    rechecked = [t for t in lessons if t.lesson.get("result") is not None]
    fixed = [t for t in rooted if t.status == "fixed"]
    minutes = [(t.updated_at - t.created_at).total_seconds() / 60 for t in fixed if t.updated_at and t.created_at]
    classes = Counter(t.chain[t.root].get("cls") for t in rooted if t.chain[t.root].get("cls"))
    students = len({t.user_id for t in done})

    def pct(part: int, whole: int) -> int | None:
        return round(100 * part / whole) if whole else None

    # the stuck topic itself, before the trace and after the fix, for the students who did both
    pairs = [t.retest for t in done if t.retest and t.retest["before"]["right"] is not None and t.retest["after"]["right"] is not None]

    def score(phase: str) -> int | None:
        return pct(sum(r[phase]["right"] for r in pairs), sum(len(r[phase]["items"]) for r in pairs))

    return {
        "students": students, "traces": len(done), "with_root": len(rooted), "root_rate": pct(len(rooted), len(done)),
        "root_classes": [{"cls": c, "traces": n} for c, n in classes.most_common(5)],
        "lessons": len(lessons), "fixed": len(fixed), "recheck_pass": pct(sum(t.lesson.get("first", t.lesson.get("result")) == "right" for t in rechecked), len(rechecked)),
        "median_minutes_to_fix": round(median(minutes), 1) if minutes else None,
        "chains_built": chains, "reused": pct(max(0, started - chains), started),
        "retest_pairs": len(pairs), "retest_before": score("before"), "retest_after": score("after"),
        "ai_usd": round(usd, 4), "ai_usd_per_student": round(usd / students, 4) if students else None,
    }


def shuffle_seed(trace: GapTrace) -> int:  # kept for a later option order per student; the order is fixed for now
    return random.Random(trace.id).randint(0, 3)


__all__ = ["GapError", "LLMUnavailable", "answer", "candidates", "chapter", "lesson", "open_roots", "overview", "owned",
           "prereq_chain", "recheck", "start", "utcnow", "view"]


# ---------------------------------------------------------------------------------------------------- the genome
@cache
def _exam_by_id() -> dict[str, Chapter]:
    out: dict[str, Chapter] = {}
    for exam in ("jee", "neet"):
        try:
            out.update({c.id: c for c in syllabus.get(exam).chapters})
        except Exception:  # a missing syllabus file only shrinks the map
            log.warning("genome: no %s syllabus", exam)
    return out


def genome(db: Session) -> dict[str, Any]:
    """The Gap Genome: every shared chain put together into one map of what the exam chapters really rest on, and,
    from real students' traces, where their trouble actually starts. The shape comes from the chains (one per
    chapter, the same for everyone); the weights come only from real traces (never the seeded demo accounts).
    Counts only: no student is named."""
    exam, school = _exam_by_id(), _school_by_id()
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str], int] = {}
    under: dict[str, set[str]] = {}  # chapter -> the exam chapters that rest on it

    def node(cid: str, name: str, subject: str | None, cls: int | None, kind: str) -> dict[str, Any]:
        return nodes.setdefault(cid, {"id": cid, "name": name, "subject": subject, "cls": cls, "kind": kind,
                                      "underpins": 0, "roots": 0, "fixed": 0})

    targets = 0
    for key, chain in db.execute(select(PrereqMap.key, PrereqMap.chain)).all():
        if key.startswith("lesson:") or not chain:
            continue
        target_id = key.split("#", 1)[0]
        ch = exam.get(target_id) or school.get(target_id)
        if ch is None:
            continue
        targets += 1
        node(ch.id, ch.name, ch.subject, None, "exam")
        prev = ch.id
        for link in chain:
            cid = link["chapter_id"]
            node(cid, link["name"], link.get("subject"), link.get("cls"), "school" if link.get("cls") else "exam")
            under.setdefault(cid, set()).add(ch.id)
            edges[(prev, cid)] = edges.get((prev, cid), 0) + 1
            prev = cid
    for cid, tops in under.items():
        nodes[cid]["underpins"] = len(tops)

    real = select(User.id).where(User.email.not_like(f"{DEMO_PREFIX}%"))
    traces = db.scalars(select(GapTrace).where(GapTrace.status != "checking", GapTrace.user_id.in_(real))).all()
    students: set[int] = set()
    rooted = 0
    for t in traces:
        students.add(t.user_id)
        if t.root is None or not t.chain or t.root >= len(t.chain):
            continue
        link = t.chain[t.root]
        n = nodes.get(link["chapter_id"]) or node(link["chapter_id"], link["name"], link.get("subject"), link.get("cls"), "school")
        n["roots"] += 1
        n["fixed"] += t.status == "fixed"
        rooted += 1

    foundations = sorted((n for n in nodes.values() if n["underpins"]), key=lambda n: (-n["underpins"], -n["roots"], n["cls"] or 99))
    return {
        "exam_chapters": targets, "foundations": len(foundations), "links": len(edges),
        "students": len(students), "traces": len(traces), "rooted": rooted,
        "top": foundations[:8],
        "nodes": list(nodes.values()),
        "edges": [{"from": a, "to": b, "weight": w} for (a, b), w in edges.items()],
    }


# ---------------------------------------------------------------------------------------------------- silent tracing
SUSPECT_MIN_CHAPTERS = 2  # one weak chapter could be anything; two resting on the same idea point at it
SUSPECTS_SHOWN = 3


def suspects(db: Session, user_id: int, syl: Syllabus | None) -> list[dict[str, Any]]:
    """Root gaps Focs suspects before the student answers a single question, from what they already did: the open
    weak spots (mock tests, uploaded results, blind spots) joined to the shared chains. When two or more weak exam
    chapters rest on the same earlier chapter, that chapter is the likely root. No AI, no quiz: the trace that
    follows only confirms it. Roots the student has already traced are left out."""
    weak = db.scalars(select(WeakTopic).where(WeakTopic.user_id == user_id, WeakTopic.status == "open")).all()
    misses: Counter[str] = Counter()
    for w in weak:
        misses[w.chapter_id] += w.misses or 1
    # checked rough work (services/working): a slip the reader traced to an earlier chapter points at it directly
    slips: dict[str, Counter[str]] = {}
    for exam_id, root_id in db.execute(select(WorkingCheck.chapter_id, WorkingCheck.root_chapter_id).where(
            WorkingCheck.user_id == user_id, WorkingCheck.root_chapter_id.is_not(None), WorkingCheck.chapter_id.is_not(None))).all():
        slips.setdefault(root_id, Counter())[exam_id] += 1
        misses[exam_id] += 0  # the chapter joins the pool even with no mock-test miss
    if len(misses) < SUSPECT_MIN_CHAPTERS:
        return []
    chains = {k: v for k, v in db.execute(select(PrereqMap.key, PrereqMap.chain).where(PrereqMap.key.in_(list(misses)))).all() if v}
    traced = db.scalars(select(GapTrace).where(GapTrace.user_id == user_id, GapTrace.status != "checking")).all()
    done_roots = {t.chain[t.root]["chapter_id"] for t in traced if t.root is not None and t.chain and t.root < len(t.chain)}
    cleared = {link["chapter_id"] for t in traced for link in (t.chain or []) if link.get("result") == "right"}
    return suspects_from(misses, chains, syl, slips=slips, skip=done_roots | cleared)[:SUSPECTS_SHOWN]


def suspects_from(misses: Counter[str], chains: dict[str, list], syl: Syllabus | None, *,
                  slips: dict[str, Counter[str]] | None = None, skip: set[str] = frozenset()) -> list[dict[str, Any]]:
    """Silent tracing itself, with no database: weak exam chapters (``misses``: chapter id -> questions lost) joined to
    their chains. An earlier chapter under two or more of them is a suspect. ``slips``: checked working that pointed at a
    root; ``skip``: earlier chapters already traced (found, or shown to hold). Also used by scripts/evidence.py."""
    slips = slips or {}
    found: dict[str, dict[str, Any]] = {}
    for exam_id, chain in chains.items():
        if exam_id not in misses:
            continue
        for link in chain or []:
            cid = link["chapter_id"]
            if cid in skip:
                continue  # already shown to be the gap, or shown to hold
            here = misses[exam_id] + slips.get(cid, Counter())[exam_id]
            if not here:
                continue  # a chapter in the pool only for a slip that led elsewhere
            s = found.setdefault(cid, {"chapter_id": cid, "name": link["name"], "subject": link.get("subject"),
                                       "cls": link.get("cls"), "idea": link.get("idea") or link["name"], "evidence": {}})
            s["evidence"][exam_id] = here
    out = []
    for s in found.values():
        if len(s["evidence"]) < SUSPECT_MIN_CHAPTERS:
            continue
        ev = sorted(s["evidence"].items(), key=lambda kv: -kv[1])
        names = [(chapter(syl, cid).name if chapter(syl, cid) else cid) for cid, _ in ev]
        out.append({**{k: v for k, v in s.items() if k != "evidence"},
                    "because": names, "misses": sum(n for _, n in ev),
                    "trace_chapter_id": ev[0][0]})  # confirm it by tracing the weakest of them
    out.sort(key=lambda s: (-len(s["because"]), -s["misses"], s["cls"] or 99))
    return out
