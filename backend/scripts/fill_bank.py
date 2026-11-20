"""Write questions for every chapter the bank is short on, a few at a time, until each has --per-chapter.

    python scripts/fill_bank.py                               # JEE Physics, Chemistry, Maths and NEET Biology
    python scripts/fill_bank.py --subject Biology --per-chapter 60
    python scripts/fill_bank.py --exam ssc_cgl --exam cbse_10 --exam cbse_12   # SSC CGL and school classes (MCQs)

Counted the way students are served (question_bank.exam_family): a Physics or Chemistry chapter counts JEE Main,
JEE Advanced and NEET questions together, and new ones are written in turn as JEE Main and NEET questions; JEE
subjects also get --numericals per chapter. Chapters are filled level by level (all to 10, then 20, ...), so every
chapter has some before any has many. Each question is written by one model and solved again by another, kept only
when both agree (question_bank.generate, as when a test is prepared). Only Groq quota beyond --reserve requests a day
is used (import_pyq.groq_room), so students never run short. Safe to stop and run again.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import func, select  # noqa: E402

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.models.mock import BankQuestion  # noqa: E402
from app.services import question_bank as qb  # noqa: E402
from app.services.mock_patterns import SYLLABUS  # noqa: E402
from import_pyq import background, groq_room  # noqa: E402

log = logging.getLogger("fill_bank")
PLAN = {"Physics": ("jee", ("mcq", "numerical")), "Chemistry": ("jee", ("mcq", "numerical")),
        "Mathematics": ("jee", ("mcq", "numerical")), "Biology": ("neet", ("mcq",))}
STEP = 10  # chapters are filled this many at a time, level by level
ROUND = 5  # questions written per call (question_bank.BATCH)


def stock(subject: str, qtype: str, exam: str) -> dict[str, dict[str, int]]:
    """Per chapter: usable questions by the bank's exam value, among those this exam's students are served."""
    family = qb.exam_family(exam, subject)
    with SessionLocal() as db:
        rows = db.execute(select(BankQuestion.chapter, BankQuestion.exam, func.count())
                          .where(BankQuestion.subject == subject, BankQuestion.qtype == qtype,
                                 func.coalesce(BankQuestion.reports, 0) < qb.RETIRE_AFTER_REPORTS)
                          .group_by(BankQuestion.chapter, BankQuestion.exam)).all()
    out: dict[str, dict[str, int]] = {}
    for chapter, q_exam, n in rows:
        if (q_exam or "jee_main") in family:
            out.setdefault(chapter, {})[q_exam or "jee_main"] = n
    return out


def other_plan(exams: list[str]) -> list[tuple[str, str, list[str]]]:
    """(subject, bank exam, chapters) for SSC CGL and school classes ("cbse_10"): MCQs only, each its own bank."""
    from app.services import syllabus
    out = []
    for e in exams:
        syl, bank_exam = syllabus.get(e), "cbse" if e.startswith("cbse_") else e
        for subject in dict.fromkeys(c.subject for c in syl.chapters):
            out.append((subject, bank_exam, [c.name for c in syl.chapters if c.subject == subject]))
    return out


def writes_as(subject: str, exam: str, have: dict[str, int]) -> str:
    """Which exam a new question is written for: a shared subject's go to whichever of JEE Main and NEET has fewer."""
    if exam in ("cbse", "ssc_cgl"):
        return exam
    if subject in qb.SHARED_SUBJECTS:
        return "neet" if have.get("neet", 0) < have.get("jee_main", 0) else "jee_main"
    return "neet" if exam == "neet" else "jee_main"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subject", choices=list(PLAN), action="append")
    ap.add_argument("--exam", action="append", help="instead of JEE/NEET: ssc_cgl or a school class (cbse_10)")
    ap.add_argument("--per-chapter", type=int, default=40, help="MCQs each chapter should have")
    ap.add_argument("--numericals", type=int, default=12, help="numerical questions each JEE chapter should have")
    ap.add_argument("--reserve", type=int, default=450, help="Groq requests a day kept for students")
    args = ap.parse_args()
    background()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    for name in ("httpx", "focs.llm", "focs.bank"):
        logging.getLogger(name).setLevel(logging.WARNING)
    init_db()
    if args.exam:
        plan = [(subject, exam, ("mcq",), chapters) for subject, exam, chapters in other_plan(args.exam)]
    else:
        plan = [(subject, *PLAN[subject], list(SYLLABUS[subject])) for subject in args.subject or list(PLAN)]
    top = max(args.per_chapter, args.numericals)
    for level in range(STEP, top + STEP, STEP):
        for subject, exam, qtypes, chapters in plan:
            for qtype in qtypes:
                goal = min(level, args.per_chapter if qtype == "mcq" else args.numericals)
                have = stock(subject, qtype, exam)
                short = [(c, goal - sum(have.get(c, {}).values())) for c in chapters]
                short = [(c, n) for c, n in short if n > 0]
                if short:
                    log.info("level %d: %s %s, %d chapters short of %d", level, subject, qtype, len(short), goal)
                for chapter, need in short:
                    misses = 0
                    while need > 0 and misses < 6:  # a chapter the checker keeps turning down waits for the next level
                        room = groq_room()
                        if room < args.reserve + 10:
                            log.info("Groq has %d requests left today, %d kept for students: waiting 20 minutes", room, args.reserve)
                            time.sleep(1200)
                            continue
                        as_exam = writes_as(subject, exam, stock(subject, qtype, exam).get(chapter, {}))
                        k = min(need, ROUND)
                        written = qb.generate(subject, qtype, {chapter: k}, workers=1, exam=as_exam,
                                              deadline=time.monotonic() + 600)
                        with SessionLocal() as db:
                            added = qb.store(db, written)  # (a few extra are written to cover the checker's rejections)
                        log.info("  %s / %s (%s, %s): +%d", subject, chapter, qtype, as_exam, added)
                        if not added:
                            misses += 1
                            time.sleep(60)  # rate limits, or the checker turned every one down: try again shortly
                        need -= added
    log.info("every chapter has its questions")


if __name__ == "__main__":
    main()
