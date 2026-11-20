"""Make the bank's own (non-PYQ) questions read less like a direct, one-step lookup, the way a real entrance paper does.

A model rewrites the question around the same concept (a situation, data given indirectly, one more step); a second
pass solves the rewrite cold and it is kept only when that solve agrees with the rewrite's own key. PYQs are never
touched. The rewrite may change the numbers, so the key moves with it; the originals go into data/reframe/backup.json
before anything is written.

  python scripts/reframe_bank.py --remote <URL> --key <KEY> --sample 8            # print before/after, write nothing
  python scripts/reframe_bank.py --remote <URL> --key <KEY> --apply --workers 12  # rewrite the bank
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_ssc as ssc  # the same remote() call, retries and JSON repair as the check

log = logging.getLogger("reframe")
OUT = Path(__file__).resolve().parents[2] / "data" / "reframe"
RECALL = ("General Awareness", "English Comprehension", "Computer Knowledge", "Biology")  # a fact has nothing to hide

REFRAME = """You turn an entrance-exam practice question into one that does not read as a direct, one-step lookup.
Keep the same concept and chapter. Make it the way a real {exam} paper asks it:
- give the data indirectly (a ratio, a percentage, a relation, a graph described in words) instead of the plain number, or
- hide what is asked one step away (ask for the quantity that leads to the original answer, or the odd one out), or
- put one more step in front of the original calculation or deduction.
It must need at least one more reasoning step than the original, and it must not be answerable by recalling one formula.
Wording alone is not enough: a paraphrase of the same question is a failure. Do not make it vague or leave out data the
solver needs. You may change numbers and options; then the correct option and the solution change with them.

Rules:
- Exactly 4 options, one correct, the other three the wrong answers a student actually reaches by a slip.
- Keep the formatting of the original (plain text, or LaTeX in $...$ if it used it).
- The solution walks through the new question step by step, short.
- "answer" is the 0-based position of the correct option.

Original question: {question}
Options: {options}
Correct option (0-3): {answer}
Original solution: {solution}

Return only JSON: {{"question": "...", "options": ["...", "...", "...", "..."], "answer": <0-3>, "solution": "..."}}"""

SOLVE = """Solve this question and pick the correct option.

Question: {question}
Options: {options}

Return only JSON: {{"answer": <0, 1, 2 or 3>}}"""


def ask(prompt: str, think: bool, tokens: int) -> dict:
    """The Kaggle server when --remote is given, otherwise the laptop's Ollama."""
    if ssc.REMOTE:
        return ssc.remote(prompt, think=think, tokens=tokens)
    return ssc.ollama(ssc.CHECK_MODEL, prompt, think=think, tokens=tokens)


def reframe(row: dict) -> dict:
    """One question: the rewrite (it may change the numbers), then a cold solve of it. {"status": "ok", ...} only when the
    solve lands on the option the rewrite names as correct."""
    r = ask(REFRAME.format(exam=row["exam"].replace("_", " ").upper(), question=row["question"], answer=int(row["answer"]),
                           options=json.dumps(row["options"], ensure_ascii=False), solution=row["solution"] or ""),
            think=True, tokens=3500)
    opts, new = r.get("options"), r.get("answer")
    if not (isinstance(opts, list) and len(opts) == 4 and r.get("question") and new in (0, 1, 2, 3))             or len(set(map(str, opts))) < 4 or r["question"].strip() == row["question"].strip():
        return {"status": "skipped", "why": "no usable rewrite"}
    got = ask(SOLVE.format(question=r["question"], options=json.dumps(opts, ensure_ascii=False)), think=True, tokens=2500)
    if got.get("answer") != new:
        return {"status": "skipped", "why": f"the solve said {got.get('answer')}, the rewrite says {new}"}
    return {"status": "ok", "question": r["question"].strip(), "options": [str(o).strip() for o in opts], "answer": str(new),
            "solution": (r.get("solution") or row["solution"] or "").strip()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--remote", help="the Kaggle server URL; without it the laptop's Ollama is used (slow)")
    ap.add_argument("--key")
    ap.add_argument("--model", default="Qwen/Qwen3-8B-AWQ")
    ap.add_argument("--exam", action="append", help="only these exams (default: all)")
    ap.add_argument("--sample", type=int, default=0, help="print N before/after pairs and write nothing")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    if args.remote:
        ssc.REMOTE.update(url=args.remote.rstrip("/"), key=args.key, model=args.model)

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.mock import BankQuestion

    OUT.mkdir(parents=True, exist_ok=True)
    done_path, backup_path = OUT / "done.json", OUT / "backup.json"
    done = set(json.loads(done_path.read_text(encoding="utf-8"))) if done_path.exists() else set()
    backup = json.loads(backup_path.read_text(encoding="utf-8")) if backup_path.exists() else {}

    with SessionLocal() as db:
        q = select(BankQuestion).where(BankQuestion.source != "pyq", BankQuestion.difficulty != "hard",
                                       BankQuestion.subject.notin_(RECALL))
        if args.exam:
            q = q.where(BankQuestion.exam.in_(args.exam))
        rows = [r for r in db.execute(q).scalars() if r.id not in done and isinstance(r.options, list) and len(r.options) == 4
                and str(r.answer).isdigit()]
        if args.sample:  # a few from each exam, so the look can be judged across subjects
            by: dict[str, list] = {}
            for r in rows:
                by.setdefault(r.exam, []).append(r)
            rows = [r for i in range(args.sample) for lst in by.values() for r in lst[i:i + 1]][:args.sample]
        log.info("%d questions to reframe%s", len(rows), " (sample: nothing is written)" if args.sample else "")
        data = {r.id: {"exam": r.exam, "question": r.question, "options": r.options, "answer": r.answer, "solution": r.solution}
                for r in rows}
        stats = {"ok": 0, "skipped": 0}
        with ThreadPoolExecutor(args.workers) as pool:
            futs = {pool.submit(reframe, data[i]): i for i in data}
            for n, f in enumerate(as_completed(futs), 1):
                qid = futs[f]
                try:
                    res = f.result()
                except Exception as exc:  # one bad question must not stop the rest
                    res = {"status": "skipped", "why": str(exc)[:120]}
                stats[res["status"]] += 1
                if args.sample:
                    print(f"\n--- {data[qid]['exam']} #{qid}: {res['status']} {res.get('why', '')}")
                    print("BEFORE:", data[qid]["question"], data[qid]["options"], "->", data[qid]["answer"])
                    if res["status"] == "ok":
                        print("AFTER: ", res["question"], res["options"])
                    continue
                if res["status"] == "ok" and args.apply:
                    row = db.get(BankQuestion, qid)
                    backup[str(qid)] = data[qid]
                    row.question, row.options, row.answer, row.solution = res["question"], res["options"], res["answer"], res["solution"]
                    done.add(qid)
                if n % 50 == 0 or n == len(futs):
                    if args.apply:
                        db.commit()
                        backup_path.write_text(json.dumps(backup, ensure_ascii=False), encoding="utf-8")
                        done_path.write_text(json.dumps(sorted(done)), encoding="utf-8")
                    log.info("%d/%d: %s", n, len(futs), stats)
        if args.apply:
            db.commit()
    log.info("done: %s", stats)


if __name__ == "__main__":
    main()
