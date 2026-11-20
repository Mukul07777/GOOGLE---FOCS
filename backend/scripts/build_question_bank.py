"""Build the seed question bank shipped with Focs (app/assets/bank/jee_main.json).

    python scripts/build_question_bank.py [--papers 2] [--subject Physics]

Writes AI-generated JEE Main questions spread over the syllabus by chapter weight. Each one is
solved again by a different model and kept only when both agree. Appends to the existing file
(duplicates skipped), saving after every batch so an interrupted run keeps its progress.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import question_bank as qb  # noqa: E402
from app.services.llm import llm  # noqa: E402
from app.services.mock_patterns import PATTERNS, SUBJECTS, chapter_targets  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", type=int, default=2, help="how many full 30+30+30 papers worth of questions")
    ap.add_argument("--subject", choices=SUBJECTS, action="append")
    ap.add_argument("--out", type=Path, default=qb.SEED_FILE)
    ap.add_argument("--patience", type=int, default=4, help="attempts per chapter before moving on")
    ap.add_argument("--wait", type=float, default=90, help="seconds to wait between attempts (rate limits)")
    args = ap.parse_args()
    if not llm.available:
        sys.exit("No LLM configured — add GROQ_API_KEY / GEMINI_API_KEY to backend/.env")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    bank: list[dict] = json.loads(args.out.read_text(encoding="utf-8")) if args.out.exists() else []
    seen = {qb.fingerprint(q["question"]) for q in bank}
    pattern = PATTERNS["jee_main_30"]

    def save() -> None:
        args.out.write_text(json.dumps(bank, ensure_ascii=False, indent=1), encoding="utf-8")

    for subject in args.subject or SUBJECTS:
        for section in pattern.sections:
            want = chapter_targets(subject, section.count * args.papers)
            have: dict[str, int] = {}
            for q in bank:
                if q["subject"] == subject and q["qtype"] == section.qtype:
                    have[q["chapter"]] = have.get(q["chapter"], 0) + 1
            need = {c: k - have.get(c, 0) for c, k in want.items() if k > have.get(c, 0)}
            if not need:
                print(f"{subject} {section.qtype}: complete")
                continue
            print(f"{subject} {section.qtype}: generating {sum(need.values())} …", flush=True)
            t = time.time()
            for chapter, k in need.items():
                added, tries = 0, 0
                while added < k and tries < args.patience:
                    tries += 1
                    for q in qb.generate(subject, section.qtype, {chapter: k - added}, workers=2):
                        fp = qb.fingerprint(q["question"])
                        if fp in seen or not q.get("verified"):
                            continue  # the shipped seed only carries independently verified questions
                        seen.add(fp)
                        bank.append({"exam": "jee_main", **q})
                        added += 1
                    save()
                    if added < k and tries < args.patience:
                        time.sleep(args.wait)  # free tiers: wait for the rate limit instead of skipping the chapter
            got = sum(1 for q in bank if q["subject"] == subject and q["qtype"] == section.qtype)
            print(f"{subject} {section.qtype}: {got} in bank ({time.time() - t:.0f}s)", flush=True)
    print(f"done: {len(bank)} questions in {args.out}")


if __name__ == "__main__":
    main()
