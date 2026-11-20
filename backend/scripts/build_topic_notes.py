"""Pre-make the notes library: detailed notes for every syllabus topic and a last-day capsule for every chapter.

    python scripts/build_topic_notes.py --exam jee [--subject Physics] [--chapter Kinematics] [--limit 20]
                                        [--capsules | --asked] [--no-export]
    (--asked: every chapter's most-asked topics, which last-day revision puts first; a few requests for a whole exam)
    python scripts/build_topic_notes.py --exam college_cse --semester 3      (a B.Tech branch: one semester's courses,
                                        or with no --semester every course in its plan; notes are shared by all branches)

Notes are written with the AI (cheapest model first) into the database Focs runs on, skipping everything the library
already has, so an interrupted run simply carries on where it stopped. Afterwards the library is exported to
app/assets/notes/<exam>.json, which ships with Focs: a fresh install (or the cloud database) starts with these
notes instead of writing them again. Without this script the library still fills itself, one topic at a time, the
first time a student asks for a topic.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.services import ledger, likely, syllabus, topic_notes  # noqa: E402
from app.services.llm import LLMUnavailable, llm  # noqa: E402


def rank_chapters(db, syl: syllabus.Syllabus, chapters: list, wait: float, patience: int) -> tuple[int, int]:
    """Rank the most-asked topics of every chapter the library hasn't ranked, likely.AT_ONCE chapters a request,
    waiting out rate limits. Returns (chapters ranked, chapters skipped)."""
    have = likely.known(db, syl.library, [c.id for c in chapters])
    todo = [c for c in chapters if c.id not in have and len(c.topics) >= likely.FEWEST]
    print(f"{syl.library.upper()} most-asked topics: {len(have)} chapters ranked, {len(todo)} to rank")
    ranked = skipped = 0
    for i in range(0, len(todo), likely.AT_ONCE):
        batch = todo[i:i + likely.AT_ONCE]
        for attempt in range(patience):
            likely._rest_until = 0.0  # this script waits for itself
            got = [c for c in batch if c.id in likely.rank(db, syl, batch)]
            if got:
                ranked += len(got)
                print(f"  [{ranked}/{len(todo)}] {', '.join(c.name for c in got[:4])}{' …' if len(got) > 4 else ''}")
                break
            if attempt == patience - 1:
                skipped += len(batch)
                print(f"  skipped {len(batch)} chapters: no model answered")
            else:
                time.sleep(wait)
    return ranked, skipped


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--exam", choices=syllabus.EXAMS, required=True)
    ap.add_argument("--subject", action="append", help="only this subject (repeatable)")
    ap.add_argument("--semester", type=int, choices=syllabus.SEMESTERS, help="a B.Tech branch: only this semester's courses")
    ap.add_argument("--chapter", action="append", help="only this chapter, by name (repeatable)")
    ap.add_argument("--limit", type=int, default=0, help="stop after writing this many notes (0 = all)")
    ap.add_argument("--capsules", action="store_true", help="write the chapters' last-day capsules instead of topic notes")
    ap.add_argument("--asked", action="store_true", help="rank every chapter's most-asked topics instead of writing notes")
    ap.add_argument("--wait", type=float, default=45, help="seconds to wait when every model is rate-limited")
    ap.add_argument("--patience", type=int, default=6, help="waits before giving up on a note and moving on")
    ap.add_argument("--no-export", action="store_true", help="don't refresh app/assets/notes/<exam>.json")
    args = ap.parse_args()
    if not llm.available:
        sys.exit("No LLM configured: add GROQ_API_KEY / GEMINI_API_KEY to backend/.env")

    init_db()
    syl = syllabus.get(args.exam)
    lib = syl.library  # every B.Tech branch reads and writes the one "college" library
    planned = {s for n, subjects in syl.semesters for s in subjects if not args.semester or n == args.semester}
    chapters = [c for c in syl.chapters if (c.subject in args.subject if args.subject else not syl.is_college or c.subject in planned)
                and (not args.chapter or c.name in args.chapter)]
    if not chapters:
        sys.exit("No chapter matches. Check --subject / --chapter against the syllabus.")
    kind = "capsule" if args.capsules else "detailed"
    written = failed = 0
    with SessionLocal() as db:
        if args.asked:
            written, failed = rank_chapters(db, syl, chapters, args.wait, args.patience)
            todo, total = [], 0
        else:
            have = topic_notes.ready(db, lib, kind)
            todo = ([(c, None) for c in chapters if c.id not in have] if args.capsules else
                    [(c, t) for c in chapters for t in c.topics if t.id not in have and not t.notes])
            total = len(todo) if not args.limit else min(len(todo), args.limit)
            print(f"{lib.upper()} {kind} notes: {len(have)} in the library, {len(todo)} to write"
                  + (f" (this run: {total})" if args.limit else ""))
        for chapter, topic in todo:
            if args.limit and written >= args.limit:
                break
            label = f"{chapter.subject} › {chapter.name}" + (f" › {topic.name}" if topic else "")
            for attempt in range(args.patience):
                try:
                    if topic is None:
                        topic_notes.capsule(db, lib, chapter)
                    else:
                        topic_notes.topic_note(db, lib, chapter, topic)
                    written += 1
                    print(f"  [{written}/{total}] {label}")
                    break
                except LLMUnavailable as exc:
                    if attempt == args.patience - 1:
                        failed += 1
                        print(f"  skipped {label}: {exc}")
                    else:
                        time.sleep(args.wait)
        ledger.flush()
        if not args.no_export:
            topic_notes.SEED_DIR.mkdir(parents=True, exist_ok=True)
            out = topic_notes.SEED_DIR / f"{lib}.json"
            notes = topic_notes.export(db, lib)
            out.write_text(json.dumps(notes, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"Exported {len(notes)} notes to {out}")
    print(f"Done: {written} written, {failed} skipped.")


if __name__ == "__main__":
    main()
