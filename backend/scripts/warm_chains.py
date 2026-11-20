"""Builds the shared root-cause chains for the chapters students get stuck on most, before any student asks.

    python scripts/warm_chains.py [--exams jee neet] [--top 15]

A chain is the same for every student (see app/services/gaps.py), so building it ahead means the first trace on
a chapter is instant and free, the same as every later one. Chapters that already have a chain are skipped.
Prints one line per chapter: how many links, the deepest class reached, and how long the AI took.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.models.gap import PrereqMap  # noqa: E402
from app.services import gaps, syllabus  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exams", nargs="+", default=["jee", "neet"])
    ap.add_argument("--top", type=int, default=15, help="chapters per exam, highest exam weight first")
    args = ap.parse_args()

    db = SessionLocal()
    built = cached = failed = 0
    for exam in args.exams:
        syl = syllabus.get(exam)
        for ch in sorted(syl.chapters, key=lambda c: -c.weight)[: args.top]:
            if db.get(PrereqMap, ch.id):
                cached += 1
                print(f"{exam:5} {ch.id:55} cached")
                continue
            t = time.monotonic()
            try:
                chain, _ = gaps.prereq_chain(db, syl, ch, None, None)
            except Exception as exc:  # one bad chapter never stops the rest
                db.rollback()
                failed += 1
                print(f"{exam:5} {ch.id:55} FAILED: {exc}")
                continue
            built += 1
            deepest = min((link["cls"] for link in chain if link.get("cls")), default=None)
            print(f"{exam:5} {ch.id:55} {len(chain)} links, down to class {deepest}, {time.monotonic() - t:.1f}s")
    print(f"\nbuilt {built}, already cached {cached}, failed {failed}")


if __name__ == "__main__":
    main()
