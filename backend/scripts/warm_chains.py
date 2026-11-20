"""Builds the shared root-cause chains for the chapters real students actually work on, before anyone asks.

    python scripts/warm_chains.py --dry-run                      # see the chapters and coverage first: no AI, no cost
    python scripts/warm_chains.py [--exams jee neet] [--top 15]  # build them (costs AI credit)
    python scripts/warm_chains.py --export chains.json           # build, then save every chain to a file
    python scripts/warm_chains.py --import chains.json           # load a file of chains: no AI at all

--by attempts (default) ranks each exam's chapters by what real students did in the last --days (default 60):
weak chapters a test showed (WeakTopic, counted by questions lost), root-cause traces (GapTrace) and checked
solutions (WorkingCheck). Those are the tables that name a syllabus chapter id reliably; QuizAttempt only has a
free-text topic and TopicProgress says what was finished, so neither is used. Demo, test, mentor and inactive
accounts are left out (app/services/real_students.py). With no activity yet, or --by weight, it takes the highest
exam weight first, and says so.

A chain is the same for every student and holds no student data, so it can be built once (on a laptop with a key, or
the Cloud Run demo) with --export, then loaded onto the live server with --import. Import skips chapters that already
have a chain unless --overwrite. Chapters that already have a chain are skipped when building too, and one failing
chapter never stops the rest.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.models.gap import PrereqMap  # noqa: E402
from app.services import gaps, syllabus  # noqa: E402
from app.services.real_students import chapter_activity, real_students  # noqa: E402


def choose(syl, activity, by: str, top: int) -> tuple[list, bool]:
    """The chapters to build for one exam, and whether it fell back to weight (no activity to rank by)."""
    by_weight = sorted(syl.chapters, key=lambda c: -c.weight)
    if by == "attempts":
        active = sorted((c for c in syl.chapters if activity.get(c.id)), key=lambda c: (-activity[c.id], -c.weight))
        if active:
            return active[:top], False
        return by_weight[:top], True
    return by_weight[:top], False


def _is_chain(value) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(link, dict) for link in value)


def import_chains(db, path: Path, overwrite: bool = False) -> tuple[int, int]:
    """Loads a chains file. Returns (added, skipped because already present)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        sys.exit(f"{path} is not a chains file: expected a JSON object of chapter id -> list of links")
    added = skipped = 0
    for key, chain in data.items():
        if not _is_chain(chain):
            print(f"skipped {key}: not a list of links")
            continue
        have = db.get(PrereqMap, key)
        if have and have.chain and not overwrite:
            skipped += 1
            continue
        db.merge(PrereqMap(key=key, chain=chain))
        added += 1
    db.commit()
    return added, skipped


def export_chains(db, path: Path) -> int:
    data = {r.key: r.chain for r in db.query(PrereqMap).order_by(PrereqMap.key) if _is_chain(r.chain)}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(data)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--exams", nargs="+", default=["jee", "neet"])
    ap.add_argument("--top", type=int, default=15, help="chapters per exam")
    ap.add_argument("--by", choices=["attempts", "weight"], default="attempts",
                    help="attempts: what real students did lately; weight: highest exam weight first")
    ap.add_argument("--days", type=int, default=60, help="how far back 'lately' goes (with --by attempts)")
    ap.add_argument("--dry-run", action="store_true", help="list the chapters and coverage, build nothing, no AI")
    ap.add_argument("--export", type=Path, help="after building, save every stored chain to this JSON file")
    ap.add_argument("--import", dest="import_", type=Path, help="load chains from a JSON file instead of building (no AI)")
    ap.add_argument("--overwrite", action="store_true", help="with --import: replace chains already present")
    args = ap.parse_args()

    db = SessionLocal()
    if args.import_:
        added, skipped = import_chains(db, args.import_, args.overwrite)
        print(f"imported {added}, skipped {skipped} already present" + ("" if args.overwrite else " (--overwrite replaces them)"))
        return

    activity = chapter_activity(db, {u.id for u in real_students(db)}, args.days) if args.by == "attempts" else {}
    built = cached = failed = 0
    for exam in args.exams:
        syl = syllabus.get(exam)
        chosen, fell_back = choose(syl, activity, args.by, args.top)
        mine = {c.id for c in syl.chapters}
        total = sum(n for cid, n in activity.items() if cid in mine)
        if args.by == "attempts" and fell_back:
            print(f"\n{exam.upper()}: no real-student activity in the last {args.days} days, so using exam weight instead.")
        elif args.by == "attempts":
            covered = sum(activity[c.id] for c in chosen)
            print(f"\n{exam.upper()}: the top {len(chosen)} chapters cover {100 * covered / total:.0f}% of the chapter-tagged"
                  f" attempts in the last {args.days} days ({total} attempts).")
        else:
            print(f"\n{exam.upper()}: the top {len(chosen)} chapters by exam weight.")
        running = 0
        for ch in chosen:
            running += activity.get(ch.id, 0)
            cover = f"  cumulative {100 * running / total:.0f}%" if total and args.by == "attempts" and not fell_back else ""
            n_att = f"{activity.get(ch.id, 0):4} attempts" if args.by == "attempts" and not fell_back else f"weight {ch.weight:g}"
            have = bool((row := db.get(PrereqMap, ch.id)) and row.chain)
            if have:
                cached += 1
                print(f"{exam:5} {ch.id:55} {n_att}{cover}  cached")
                continue
            if args.dry_run:
                print(f"{exam:5} {ch.id:55} {n_att}{cover}  would build")
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
            print(f"{exam:5} {ch.id:55} {n_att}{cover}  {len(chain)} links, down to class {deepest}, {time.monotonic() - t:.1f}s")
    if args.dry_run:
        print(f"\ndry run: nothing built, no AI called. {cached} chapters already have a chain.")
        return
    print(f"\nbuilt {built}, already cached {cached}, failed {failed}")
    if args.export:
        print(f"exported {export_chains(db, args.export)} chains to {args.export}")


if __name__ == "__main__":
    main()
