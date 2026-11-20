"""Full-length mock tests: paper assembly, NTA-style timing, grading and analysis."""
from __future__ import annotations

import logging
import random
import re
import threading
import time
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models._util import utcnow
from app.models.mock import BankQuestion, MockTest
from app.models.quiz_attempt import QuizAttempt
from app.models.user import User
from app.services import question_bank as bank
from app.services import usage
from app.services.llm import llm
from app.services.mock_patterns import PATTERNS, Pattern, bank_source, test_pattern

log = logging.getLogger("focs.mock")

SUBMIT_GRACE = timedelta(seconds=45)  # network slack for the last autosave
WEEK = timedelta(days=7)
# The written questions put the right answer first or second about 70% of the time (and fourth about 3%), so a paper
# shows each MCQ's options in its own order (MockTest.shuffled). Older papers keep the order their saved answers point at.
# options that point at other options ("both (a) and (b)", "all of the above") or a solution that names one: kept as written
_POSITIONAL = re.compile(r"\b(all|none|both|neither)\b.*\b(above|these|of the|and|nor)\b|\([a-d]\)|\boptions?\s*\(?[a-d1-4]\b", re.I)


# ---------------------------------------------------------------- quota
def mocks_per_week(plan: str | None) -> int:
    plan = plan or "free"
    return {"team": settings.MOCKS_TEAM_PER_WEEK, "pro": settings.MOCKS_PRO_PER_WEEK}.get(plan, settings.MOCKS_FREE_PER_WEEK)


def mock_offers() -> list[dict[str, int]]:
    """Mocks on sale one at a time: (id, how many, price). Empty when they are off sale."""
    out = []
    if settings.MOCK_PRICE_INR:
        out.append({"id": "one", "count": 1, "price_inr": settings.MOCK_PRICE_INR})
    if settings.MOCK_PACK_INR and settings.MOCK_PACK_SIZE > 1:
        out.append({"id": "pack", "count": settings.MOCK_PACK_SIZE, "price_inr": settings.MOCK_PACK_INR})
    return out


def credits(db: Session, user: User) -> int:
    """Bought mocks not yet taken: every paid mock purchase, less the mocks started on one (config "paid")."""
    from app.models.payment import Payment

    bought = sum(int(p.ref_id or 0) for p in db.scalars(select(Payment).where(
        Payment.user_id == user.id, Payment.purpose == "mocks", Payment.status == "paid")))
    if not bought:
        return 0
    spent = sum(1 for c in db.scalars(select(MockTest.config).where(
        MockTest.user_id == user.id, MockTest.pattern != "chapter", MockTest.started_at.is_not(None))) if (c or {}).get("paid"))
    return max(0, bought - spent)


def quota(db: Session, user: User) -> dict[str, Any]:
    """Full mocks *started* in the last 7 days (creating and reading the instructions is free), plus bought ones.
    The week's own come first; a bought mock is used only once they are gone."""
    limit = mocks_per_week(user.plan)
    since = utcnow() - WEEK
    started = [(at, cfg) for at, cfg in db.execute(select(MockTest.started_at, MockTest.config).where(
        MockTest.user_id == user.id, MockTest.started_at >= since, MockTest.pattern != "chapter")
        .order_by(MockTest.started_at)).all() if not (cfg or {}).get("paid")]
    resets = (started[0][0] + WEEK).isoformat() + "Z" if started else None
    free_left = None if not limit else max(0, limit - len(started))
    bought = 0 if not limit else credits(db, user)
    return {"used": len(started), "limit": limit or None, "unlimited": not limit,
            "left": None if not limit else free_left + bought, "free_left": free_left, "credits": bought,
            "resets_at": resets, "offers": mock_offers() if limit and (user.plan or "free") != "team" else []}


def _require_quota(db: Session, user: User) -> dict[str, Any]:
    from fastapi import HTTPException

    q = quota(db, user)
    if q["unlimited"] or q["left"]:
        return q
    plan = user.plan or "free"
    paying = bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)
    offers = q["offers"] if paying else []
    buy = ", ".join(f"{o['count']} for ₹{o['price_inr']}" for o in offers)
    buy = f"buy more ({buy})" if buy else ""
    pro = "get Pro for unlimited mocks" if plan == "free" and paying else ""
    choices = " or ".join(x for x in (buy, pro) if x)
    raise HTTPException(status_code=402, detail=(
        f"You've used your {q['limit']} full mock test{'s' if q['limit'] != 1 else ''} for this week."
        + (f" You can {choices}." if choices else "")
        + " Your next free one unlocks 7 days after your earliest mock this week."))


# ---------------------------------------------------------------- assembly
def pattern_of(test: MockTest) -> Pattern:
    if test.pattern == "chapter":
        return test_pattern(test.config or {})
    return PATTERNS[test.pattern]


def is_full_mock(test: MockTest) -> bool:
    return test.pattern != "chapter"


def _layout(p: Pattern) -> list[tuple[str, Any]]:
    """Paper order: Physics A, Physics B, Chemistry A, …  -> [(subject, section), …] per question slot."""
    return [(subject, s) for subject in p.subjects for s in p.sections_for(subject) for _ in range(s.count)]


def _seen_ids(db: Session, user_id: int) -> set[int]:
    seen: set[int] = set()
    for ids in db.scalars(select(MockTest.question_ids).where(MockTest.user_id == user_id)):
        seen.update(ids or [])
    return seen


def assemble(db: Session, test: MockTest, user_id: int) -> dict[tuple[str, str], dict[str, int]]:
    """Fill the paper from the bank. Returns what is still missing per (subject, qtype)."""
    p = pattern_of(test)
    seen = _seen_ids(db, user_id) - set(test.question_ids or [])
    ids: list[int] = []
    missing: dict[tuple[str, str], dict[str, int]] = {}
    for subject in p.subjects:
        source, chapters = bank_source(subject, p.chapters)  # NEET's Botany and Zoology come from Biology
        for s in p.sections_for(subject):
            chosen, short = bank.pick(db, source, s.qtype, s.count, exclude=seen | set(ids), chapters=chapters, exam=p.level or p.exam,
                                      topics=p.topics.get(subject))
            if len(chosen) < s.count:
                # every question in the bank was already in this student's earlier mocks: allow repeats
                # rather than fail, but only after unseen ones
                more, _ = bank.pick(db, source, s.qtype, s.count - len(chosen), exclude=set(ids) | {q.id for q in chosen},
                                    chapters=chapters, exam=p.level or p.exam, topics=p.topics.get(subject))
                chosen += more
            if len(chosen) < s.count:
                short = short or {"": s.count - len(chosen)}
                before = missing.get((subject, s.qtype), {})  # a subject can have two sections of one kind (1-mark, 2-mark)
                missing[(subject, s.qtype)] = {c: before.get(c, 0) + short.get(c, 0) for c in {*before, *short}}
            ids += [q.id for q in chosen]
    if not missing:
        test.question_ids = ids
        test.status, test.progress = "ready", 100
    return missing


def create(db: Session, user: User, pattern_id: str, config: dict | None = None) -> MockTest:
    """A full mock (pattern_id from PATTERNS) or a short test (pattern_id "chapter" + config: a chapter or subject
    test, or a last-day test)."""
    p = test_pattern(config or {}) if pattern_id == "chapter" else PATTERNS[pattern_id]
    # an unstarted paper of the same kind is reused instead of piling up new ones
    for existing in db.scalars(select(MockTest).where(MockTest.user_id == user.id, MockTest.pattern == pattern_id,
                                                      MockTest.status.in_(("preparing", "ready")))):
        if pattern_id != "chapter" or existing.config == config:
            resume(existing)
            return existing
    n = 1 + len(db.scalars(select(MockTest.id).where(MockTest.user_id == user.id, MockTest.pattern != "chapter")).all())
    title = f"{p.name} · {p.short}" if pattern_id == "chapter" else f"Full mock #{n} · {p.short}"
    test = MockTest(user_id=user.id, shuffled=True, pattern=p.id, config=config, title=title, duration_min=p.duration_min,
                    status="preparing", progress=0, question_ids=[], responses={})
    db.add(test)
    db.commit()
    missing = assemble(db, test, user.id)
    if missing:
        if not llm.available:
            test.status, test.error = "failed", "The question bank is short and AI is offline — add an LLM key to backend/.env."
        else:
            if pattern_id == "chapter":  # writing fresh questions for a chapter test uses AI allowance
                if not usage.can_spend(db, user, "practice_set"):
                    db.delete(test)
                    db.commit()
                    usage.require(db, user, "practice_set")  # raises 402 with when the allowance resets
                usage.charge(db, user, "practice_set")
            _start(test)
    db.commit()
    db.refresh(test)
    return test


def _start(test: MockTest) -> None:
    threading.Thread(target=_prepare, args=(test.id, test.user_id), name=f"mock-{test.id}", daemon=True).start()


def resume(test: MockTest) -> None:
    """A paper left "preparing" by a restart (a deploy, the server stopped) has no one writing it any more: pick the
    work up again, or the student waits on it for ever and asking for the same test hands back the same paper."""
    if test.status != "preparing" or not llm.available:
        return
    with _resuming:  # two polls at once start one writer
        if not any(t.name == f"mock-{test.id}" for t in threading.enumerate()):
            _start(test)


_resuming = threading.Lock()


PREPARE_ROUNDS = 6  # of writing: the checker turns some questions down, so one round can come up short
# How long a paper may take to write. Most are ready in under a minute; on a free AI tier a long one waits out
# rate limits several times, and that is better than failing: the student sees the progress and can leave the page.
PREPARE_BUDGET_S = {"chapter": 8 * 60, "full": 25 * 60}


def _prepare(test_id: int, user_id: int) -> None:
    """Background: write the missing questions, then assemble the paper. What a round leaves short (questions the
    second model disagreed with, near-duplicates) is written again, a couple of times at most."""
    with SessionLocal() as db:
        test = db.get(MockTest, test_id)
        if test is None or test.status != "preparing":  # (resumed just as the last writer finished: never re-pick a paper)
            return
        try:
            missing = assemble(db, test, user_id)
            total = sum(sum(v.values()) for v in missing.values()) or 1
            done = 0

            def progress(n: int) -> None:
                nonlocal done
                done += n
                test.progress = min(95, int(100 * done / total))
                db.commit()

            p = pattern_of(test)
            deadline = time.monotonic() + PREPARE_BUDGET_S["full" if is_full_mock(test) else "chapter"]
            for _ in range(PREPARE_ROUNDS):
                for (subject, qtype), need in missing.items():
                    need = {c: k for c, k in need.items() if c} or bank.chapter_targets(subject, sum(need.values()), p.chapters)
                    source, _ = bank_source(subject)
                    bank.store(db, bank.generate(source, qtype, need, on_progress=progress, deadline=deadline,
                                                 exam=p.level or (p.exam if p.exam in ("neet", "ssc_cgl", "college", "cbse") else "jee_main"),
                                                 topics=p.topics.get(subject)))
                missing = assemble(db, test, user_id)
                if not missing or time.monotonic() >= deadline:
                    break
            if missing:
                test.status = "failed"
                test.error = ("The AI that writes questions is at its limit right now, so this paper isn't complete. "
                              "What was written is kept: try again in a few minutes and it will be ready sooner.")
            db.commit()
        except Exception as exc:  # never leave a paper stuck in "preparing"
            log.exception("mock preparation failed")
            db.rollback()
            test = db.get(MockTest, test_id)
            test.status, test.error = "failed", "Something went wrong while writing this paper. Try again in a few minutes."
            db.commit()


# ---------------------------------------------------------------- taking the test
def deadline(test: MockTest):
    return test.started_at + timedelta(minutes=test.duration_min) if test.started_at else None


def remaining_seconds(test: MockTest) -> int | None:
    d = deadline(test)
    return None if d is None else max(0, int((d - utcnow()).total_seconds()))


def start(db: Session, user: User, test: MockTest) -> MockTest:
    if test.status == "in_progress":
        return test
    if test.status != "ready":
        from fastapi import HTTPException

        raise HTTPException(status_code=409, detail="This paper isn't ready yet.")
    if is_full_mock(test):
        q = _require_quota(db, user)
        if not q["unlimited"] and not q["free_left"]:  # the week's own are gone: this one uses a bought mock
            test.config = {**(test.config or {}), "paid": True}
    test.status, test.started_at = "in_progress", utcnow()
    db.commit()
    return test


def questions(db: Session, test: MockTest) -> list[BankQuestion]:
    rows = {q.id: q for q in db.scalars(select(BankQuestion).where(BankQuestion.id.in_(test.question_ids or [])))}
    return [rows[i] for i in test.question_ids or [] if i in rows]


def option_order(test: MockTest, q: BankQuestion) -> list[int] | None:
    """The order this paper shows q's options in (shown position -> stored index), or None for as written. Fixed per
    paper and question, so a refresh or the result page shows the same order the student answered in."""
    opts = q.options or []
    if q.qtype != "mcq" or len(opts) < 2 or not test.shuffled:
        return None
    if any(_POSITIONAL.search(str(o)) for o in opts) or _POSITIONAL.search(q.solution or ""):
        return None
    return random.Random(f"{test.id}:{q.id}").sample(range(len(opts)), len(opts))


def shown_answer(test: MockTest, q: BankQuestion) -> str:
    """The key as this paper shows it: the position of the right option on screen (the value, for a numerical)."""
    order = option_order(test, q)
    try:
        return str(order.index(int(q.answer))) if order else q.answer
    except ValueError:
        return q.answer


def paper(db: Session, test: MockTest, with_answers: bool) -> list[dict[str, Any]]:
    p = pattern_of(test)
    out = []
    # strict=False: a question retired after the paper was made just drops out
    for no, (q, (subject, section)) in enumerate(zip(questions(db, test), _layout(p), strict=False), 1):
        order = option_order(test, q)
        options = [q.options[i] for i in order] if order else q.options
        item = {"id": q.id, "no": no, "subject": subject, "section": section.key, "qtype": q.qtype,
                "question": q.question, "options": options, "paper": q.paper,  # paper: "JEE Main 2019" on a PYQ
                **pictures_and_hindi(q, order)}
        if with_answers:
            item.update(answer=shown_answer(test, q), solution=q.solution, chapter=q.chapter, difficulty=q.difficulty)
        out.append(item)
    return out


def pictures_and_hindi(q: BankQuestion, order: list[int] | None = None) -> dict[str, Any]:
    """What an SSC question carries besides its text, its options put in the order shown: the figures it needs
    ("media") and the paper's own Hindi version ("hindi")."""
    out: dict[str, Any] = {}
    if q.media:
        opts = q.media.get("options")
        out["media"] = {"figures": q.media.get("figures") or [],
                        "options": [opts[i] for i in order] if opts and order else opts}
    if q.hindi:
        hopts = q.hindi.get("options")
        out["hindi"] = {"question": q.hindi.get("question"), "options": [hopts[i] for i in order] if hopts and order else hopts}
    return out


def save_responses(test: MockTest, responses: dict[str, Any], current_index: int | None, tab_switches: int | None) -> None:
    clean: dict[str, dict[str, Any]] = {}
    allowed = {str(i) for i in test.question_ids or []}
    for qid, r in (responses or {}).items():
        if qid not in allowed or not isinstance(r, dict):
            continue
        a = r.get("a")
        a = None if a in (None, "") else str(a)[:20]
        clean[qid] = {"a": a, "m": bool(r.get("m")), "v": bool(r.get("v")), "t": max(0, min(int(r.get("t") or 0), 4 * 3600))}
        if r.get("c") in ("sure", "unsure"):
            clean[qid]["c"] = r["c"]  # how sure the student was (confidence vs reality)
    test.responses = clean
    if current_index is not None:
        test.current_index = max(0, min(current_index, len(test.question_ids or []) - 1))
    if tab_switches is not None:
        test.tab_switches = max(test.tab_switches or 0, tab_switches)


def overdue(test: MockTest) -> bool:
    d = deadline(test)
    return test.status == "in_progress" and d is not None and utcnow() > d + SUBMIT_GRACE


# ---------------------------------------------------------------- grading
def _is_correct(q: BankQuestion, a: str, order: list[int] | None = None) -> bool:
    try:
        if q.qtype == "mcq":
            shown = int(a)
            if order:
                if not 0 <= shown < len(order):
                    return False
                shown = order[shown]  # the position the student picked -> the option as stored
            return shown == int(q.answer)
        return abs(float(a) - float(q.answer)) < 1e-6
    except ValueError:
        return False


def _blank() -> dict[str, Any]:
    return {"score": 0.0, "max": 0, "correct": 0, "incorrect": 0, "unattempted": 0, "negative": 0.0, "time_sec": 0}


def _finish(b: dict[str, Any]) -> dict[str, Any]:
    attempted = b["correct"] + b["incorrect"]
    b["attempted"] = attempted
    b["score"], b["negative"] = round(b["score"], 2), round(b["negative"], 2)  # thirds of a mark add up untidily
    b["accuracy"] = round(100 * b["correct"] / attempted) if attempted else 0
    return b


def grade(db: Session, test: MockTest) -> dict[str, Any]:
    p = pattern_of(test)
    qs = questions(db, test)
    responses = test.responses or {}
    total = _blank()
    subjects: dict[str, dict[str, Any]] = {}
    chapters: dict[tuple[str, str], dict[str, Any]] = {}
    per_question = []
    evaluated_in_section: dict[tuple[str, str], int] = {}

    for q, (subject, section) in zip(qs, _layout(p), strict=False):
        r = responses.get(str(q.id)) or {}
        a, t = r.get("a"), int(r.get("t") or 0)
        sb = subjects.setdefault(subject, {**_blank(), "subject": subject, "sections": {}})
        sec = sb["sections"].setdefault(section.key, {**_blank(), "key": section.key, "label": section.label})
        ch = chapters.setdefault((subject, q.chapter), {**_blank(), "subject": subject, "chapter": q.chapter})
        key = (subject, section.key)
        counted = a is not None and evaluated_in_section.get(key, 0) < section.attempt
        if counted:
            evaluated_in_section[key] = evaluated_in_section.get(key, 0) + 1
        if not counted:
            outcome, marks = "unattempted", 0.0
        elif _is_correct(q, a, option_order(test, q)):
            outcome, marks = "correct", float(section.correct)
        else:
            outcome, marks = "incorrect", float(section.wrong)
        for b in (total, sb, sec, ch):
            b[outcome] += 1
            b["score"] += marks
            b["time_sec"] += t
            if marks < 0:
                b["negative"] += -marks
        per_question.append({"id": q.id, "subject": subject, "section": section.key, "chapter": q.chapter,
                             "outcome": outcome, "marks": marks, "time_sec": t, "answer": a, "marked": bool(r.get("m")),
                             "confidence": r.get("c")})

    for subject, sb in subjects.items():
        sb["max"] = int(round(sum(s.attempt * s.correct for s in p.sections_for(subject))))
        for sec in sb["sections"].values():
            s = next(x for x in p.sections_for(subject) if x.key == sec["key"])
            sec["max"] = int(s.attempt * s.correct)
            _finish(sec)
        sb["sections"] = list(sb["sections"].values())
        _finish(sb)
    total["max"] = p.max_score
    _finish(total)
    chapter_rows = sorted((_finish(c) for c in chapters.values()), key=lambda c: (c["score"], -c["incorrect"]))
    return {"total": total, "subjects": list(subjects.values()), "chapters": chapter_rows,
            "questions": per_question, "insights": _insights(total, list(subjects.values()), per_question)}


def _fmt(sec: int) -> str:
    return f"{sec // 60} min {sec % 60:02d} s" if sec >= 60 else f"{sec} s"


def _insights(total: dict, subjects: list[dict], qs: list[dict]) -> list[str]:
    out: list[str] = []
    if total["unattempted"] == len(qs):
        return ["You didn't answer any question, so there's nothing to judge yet. Read the solutions below, then take "
                "this paper again and answer every question you can."]
    if total["negative"]:
        worst = max(subjects, key=lambda s: s["negative"])
        lost, worst_lost = total["negative"], worst["negative"]
        share = "all of it" if lost == 1 else "all of them" if worst_lost == lost else f"{worst_lost:g} of them"
        out.append(f"Negative marking cost you {lost:g} mark{'' if lost == 1 else 's'} — {share} in {worst['subject']}. "
                   "Skip a question unless you can rule out at least two options.")
    spent = sum(s["time_sec"] for s in subjects) or 1
    for s in subjects:
        share_time = s["time_sec"] / spent
        share_score = max(0.0, s["score"]) / max(1.0, sum(max(0.0, x["score"]) for x in subjects))
        if share_time - share_score > 0.15 and s["time_sec"] > 600:
            out.append(f"{s['subject']} took {round(100 * share_time)}% of your time but brought {round(100 * share_score)}% "
                       "of your marks — set a time budget per subject next time.")
    slow = sorted((q for q in qs if q["time_sec"] >= 240), key=lambda q: -q["time_sec"])[:3]
    if slow:
        out.append("Slowest questions: " + ", ".join(
            f"Q{qs.index(q) + 1} ({_fmt(q['time_sec'])}, {q['outcome']})" for q in slow) + ".")
    left = total["unattempted"]
    if left and total["accuracy"] >= 80:
        out.append(f"Your accuracy was {total['accuracy']}% — with {left} questions left blank, attempting more would likely raise your score.")
    if not out:
        out.append("Balanced attempt — keep the same strategy and push accuracy on your weakest chapters below.")
    return out


def submit(db: Session, user: User, test: MockTest) -> MockTest:
    if test.status == "submitted":
        return test
    result = grade(db, test)
    test.result, test.score, test.max_score = result, result["total"]["score"], result["total"]["max"]
    test.status, test.submitted_at = "submitted", utcnow()
    # every attempted question feeds the student's analytics; wrong ones go to the redo queue
    by_id = {q.id: q for q in questions(db, test)}
    for row in result["questions"]:
        if row["outcome"] == "unattempted":
            continue
        q = by_id.get(row["id"])
        ok = row["outcome"] == "correct"
        db.add(QuizAttempt(user_id=user.id, topic=row["chapter"], question=(q.question if q else "")[:2000], q_type="mock",
                           correct=ok, score=row["marks"], exam_target=user.exam_target, subject=row["subject"],
                           needs_redo=not ok, confidence=row.get("confidence")))
    db.commit()
    # sure and wrong: a blind spot, which counts double as a weak spot (it leads the plan until a re-check clears it)
    blind = [r for r in result["questions"] if r["outcome"] == "incorrect" and r.get("confidence") == "sure"]
    if blind:
        from app.services import bridge, weak, syllabus

        syl = syllabus.of(user, whole=True)
        counts: dict[str, int] = {}
        for r in blind:
            ch = bridge.chapter_of(user, r["subject"], r["chapter"])
            if ch is not None and syl is not None and ch.id in syl.by_id:
                counts[ch.id] = counts.get(ch.id, 0) + 1
        if counts:
            weak.add_blind_spots(db, user.id, syl, counts, test.title or "Test")
    return test


def finalize_overdue(db: Session, user: User) -> None:
    """Papers left open past their time (browser closed) are submitted with what was saved."""
    for test in db.scalars(select(MockTest).where(MockTest.user_id == user.id, MockTest.status == "in_progress")):
        if overdue(test):
            submit(db, user, test)
