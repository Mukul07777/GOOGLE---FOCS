"""Real-student evidence for the pitch, straight from the database: what real students did, and what silent tracing,
root-cause tracing and Check my working found in it. READ-ONLY, and aggregates only.

    python scripts/evidence.py [--chains-from <postgres url>] [--out evidence.md]

Point it at the live database the way the app is (SUPABASE_DB_URL or DATABASE_URL in the environment / backend/.env).
It never writes to it: on Postgres the whole run is one READ ONLY transaction.

Privacy, by construction:
  - only counts and shares leave the database: no name, email, school or answer is ever printed;
  - any group smaller than MIN_GROUP students is not shown (it could point at a person);
  - demo accounts (demo.focs.*), test addresses (@example.com, .invalid), mentors and inactive accounts are left out.

Silent tracing needs each exam chapter's chain (what it rests on). They are the same for every student and hold no
student data. The live database has them once the new code runs there (scripts/warm_chains.py builds the top ones);
until then --chains-from reads them from another database that has them, e.g. the Cloud Run demo one.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, inspect, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import engine  # noqa: E402
from app.models._util import utcnow  # noqa: E402
from app.models.mock import MockTest  # noqa: E402
from app.models.quiz_attempt import QuizAttempt  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.weak import WeakTopic  # noqa: E402
from app.services import gaps, syllabus  # noqa: E402

MIN_GROUP = 5
NOT_REAL = ("demo.focs.%", "%@example.com", "%.invalid")


def _real(db: Session) -> list[User]:
    q = select(User).where(func.coalesce(User.role, "student") == "student", User.is_active.is_not(False))
    for pattern in NOT_REAL:
        q = q.where(User.email.not_like(pattern))
    return list(db.scalars(q))


def _pct(part: int, whole: int) -> str:
    return f"{round(100 * part / whole)}%" if whole else "–"


def _chains(db: Session, url: str | None) -> dict[str, list]:
    """Every stored chain (exam chapter -> what it rests on), from this database or from ``url``."""
    if url:
        if url.startswith(("postgresql://", "postgres://")):
            url = "postgresql+psycopg://" + url.split("://", 1)[1]
        other = create_engine(url)
        with other.connect() as c:
            return {k: v if isinstance(v, list) else json.loads(v or "[]")
                    for k, v in c.execute(text("SELECT key, chain FROM prereq_maps")).all() if v}
    if "prereq_maps" not in inspect(engine).get_table_names():
        return {}
    return {k: (v if isinstance(v, list) else json.loads(v or "[]")) for k, v in db.execute(text("SELECT key, chain FROM prereq_maps")).all() if v}


def report(db: Session, chains_url: str | None = None) -> tuple[list[str], dict]:
    now = utcnow()
    students = _real(db)
    ids = {u.id for u in students}
    by_id = {u.id: u for u in students}
    lines, data = [], {}
    tables = set(inspect(engine).get_table_names())

    # ---- who
    active7 = sum(1 for u in students if u.last_seen_at and u.last_seen_at >= now - timedelta(days=7))
    active30 = sum(1 for u in students if u.last_seen_at and u.last_seen_at >= now - timedelta(days=30))
    exams = Counter((u.exam_target or "other") for u in students)
    shown = {e: n for e, n in exams.items() if n >= MIN_GROUP}
    data["students"] = {"total": len(students), "active_7d": active7, "active_30d": active30, "by_exam": shown}
    lines += ["## Real students", "",
              f"- **{len(students)} real students** signed up; {active30} used Focs in the last 30 days, {active7} in the last 7.",
              "- By exam: " + (", ".join(f"{e.upper()} {n}" for e, n in sorted(shown.items(), key=lambda kv: -kv[1])) or "–")
              + (" (smaller groups not shown)" if len(shown) < len(exams) else ""), ""]

    # ---- what they did
    mocks = db.scalar(select(func.count(MockTest.id)).where(MockTest.status == "submitted", MockTest.user_id.in_(ids))) or 0
    mock_students = db.scalar(select(func.count(func.distinct(MockTest.user_id))).where(MockTest.status == "submitted", MockTest.user_id.in_(ids))) or 0
    answers = db.scalar(select(func.count(QuizAttempt.id)).where(QuizAttempt.user_id.in_(ids))) or 0
    weak_rows = db.execute(select(WeakTopic.user_id, WeakTopic.chapter_id, WeakTopic.misses)
                           .where(WeakTopic.status == "open", WeakTopic.user_id.in_(ids))).all()
    weak: dict[int, Counter[str]] = {}
    for uid, cid, n in weak_rows:
        weak.setdefault(uid, Counter())[cid] += n or 1
    data["activity"] = {"mocks_submitted": mocks, "mock_students": mock_students, "answers": answers,
                        "weak_chapters": sum(len(c) for c in weak.values()), "students_with_weak": len(weak)}
    lines += ["## What they did", "",
              f"- {mocks} full mock tests submitted by {mock_students} students; {answers} practice answers marked.",
              f"- {data['activity']['weak_chapters']} weak chapters recorded across {len(weak)} students "
              f"({sum(1 for c in weak.values() if len(c) >= 2)} of them weak in 2+ chapters).", ""]

    # ---- silent tracing on their real mistakes (no quiz, no AI)
    chains = _chains(db, chains_url)
    covered = sum(1 for c in weak.values() for cid in c if cid in chains)
    total_weak = data["activity"]["weak_chapters"]
    with_suspect, roots, under = 0, Counter(), []
    for uid, misses in weak.items():
        if len(misses) < gaps.SUSPECT_MIN_CHAPTERS:
            continue
        found = gaps.suspects_from(misses, chains, syllabus.of(by_id[uid], whole=True))
        if found:
            with_suspect += 1
            under.append(len(found[0]["because"]))
            for s in found:
                roots[(s["chapter_id"], s["name"], s.get("cls"))] += 1
    top = [(name, cls, n) for (cid, name, cls), n in roots.most_common(8) if n >= MIN_GROUP]
    data["silent_tracing"] = {"chains": len(chains), "weak_covered": covered, "students_with_suspect": with_suspect,
                              "eligible": sum(1 for c in weak.values() if len(c) >= 2), "top_roots": top}
    lines += ["## Silent tracing on real mistakes (no quiz, no AI)", ""]
    if not chains:
        lines += ["- No chains available yet: run scripts/warm_chains.py, or pass --chains-from.", ""]
    else:
        eligible = data["silent_tracing"]["eligible"]
        lines += [f"- {len(chains)} exam chapters have their chain; they cover {_pct(covered, total_weak)} of real weak chapters.",
                  f"- **{with_suspect} of {eligible} students ({_pct(with_suspect, eligible)}) weak in 2+ chapters have one earlier"
                  f" chapter under several of them**: one fix that pays off more than once"
                  + (f" (median {sorted(under)[len(under) // 2]} weak chapters on the top suspect)." if under else "."),
                  "- The earlier chapters most often behind real students' trouble:"]
        lines += [f"  - {name}{f' (Class {cls})' if cls else ''}: {n} students" for name, cls, n in top] or \
                 [f"  - (no single chapter yet behind {MIN_GROUP}+ students)"]
        lines.append("")

    # ---- root-cause tracing, measured (once the new code runs here)
    if {"gap_traces", "prereq_maps"} <= tables:
        p = gaps.proof(db)
        data["tracing"] = p
        if p["traces"]:
            lines += ["## Root-cause tracing, measured", "",
                      f"- {p['students']} students finished {p['traces']} traces; {p['root_rate']}% found an earlier gap.",
                      f"- Five-minute fixes: {p['fixed']} of {p['lessons']} lessons passed their re-check"
                      f" ({p['recheck_pass']}% on the first try); median {p['median_minutes_to_fix']} min from trace to fixed.",
                      (f"- **The stuck topic itself: {p['retest_before']}% right before → {p['retest_after']}% after the fix**"
                       f" ({p['retest_pairs']} students who did both)." if p.get("retest_pairs", 0) >= MIN_GROUP else
                       f"- Before → after: {p.get('retest_pairs', 0)} students so far (shown from {MIN_GROUP})."),
                      f"- {p['reused']}% of traces reused a chain another student had already paid for; AI cost per student"
                      f" ${p['ai_usd_per_student']}." if p["ai_usd_per_student"] is not None else "", ""]

    # ---- Check my working
    if "working_checks" in tables:
        rows = db.execute(text("SELECT user_id, verdict, error_type FROM working_checks")).all()
        rows = [r for r in rows if r[0] in ids]
        wrong = [r for r in rows if r[1] != "right" and r[2]]
        slips = sum(1 for r in wrong if r[2] in ("arithmetic", "sign", "units", "misread"))
        people = len({r[0] for r in rows})
        data["working"] = {"checks": len(rows), "students": people, "mistakes": len(wrong), "slips": slips}
        if people >= MIN_GROUP:
            lines += ["## Check my working", "",
                      f"- {len(rows)} solutions checked from {people} students' rough pads.",
                      f"- **{_pct(slips, len(wrong))} of their mistakes were careless slips** (the idea was right); "
                      f"{_pct(len(wrong) - slips, len(wrong))} were gaps in an idea.", ""]

    head = [f"# Focs: evidence from real students ({now:%d %b %Y, %H:%M} UTC)", "",
            f"Aggregates only, read-only. Groups under {MIN_GROUP} students are not shown. Demo, test and mentor accounts excluded.", ""]
    return head + [ln for ln in lines if ln is not None], data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--chains-from", default=None, help="a database URL to read the chains from (no student data in them)")
    ap.add_argument("--out", type=Path, default=Path("evidence.md"))
    args = ap.parse_args()
    print(f"Reading {engine.url.render_as_string(hide_password=True)}", file=sys.stderr)
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION READ ONLY"))  # a report never writes, even by mistake
        lines, data = report(db, args.chains_from)
        db.rollback()
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    args.out.with_suffix(".json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved {args.out} and {args.out.with_suffix('.json')}", file=sys.stderr)


__all__ = ["MIN_GROUP", "report"]
if __name__ == "__main__":
    main()
