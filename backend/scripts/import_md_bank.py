"""Import question banks written as Markdown (### Q<n> blocks: **Question:**, (A)-(D), **Answer:** `(X)`) into the bank.

    python scripts/import_md_bank.py --src "F:\\PYQ"                 # every stage, resumable
    python scripts/import_md_bank.py --src "F:\\PYQ" --stage parse   # just count what's there

The files repeat a few questions thousands of times (a 40,000-question file held 5), so only unique questions are
kept, and their keys are not trusted: every question is checked the way scripts/import_ssc.py checks a paper (a model
solves it from scratch and files it under the syllabus; when it disagrees with the file's key a stronger model
decides; nonsense is dropped). The "PYQ" and shift labels in these files are not trusted either: everything is stored
as practice, not as a past paper. Placeholder files ("Which of the following best describes Topic G?" with options
"Option A".."Option D", as in the School folder) don't match the format and are skipped.

Folders read: JEE/Mains, JEE/Advanced, NEET/<subject>, SSC Questions/<section>. Work is saved in data/pyq_md/.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from import_ssc import CHECK_BATCH, CHECK_MODEL, JUDGE_MODEL, chat, load, save  # noqa: E402

WORK = BACKEND.parent / "data" / "pyq_md"
log = logging.getLogger("md_bank")

BLOCK = re.compile(r"\*\*Question:\*\*\s*(.+?)\n\s*\(A\)\s*(.+?)\n\s*\(B\)\s*(.+?)\n\s*\(C\)\s*(.+?)\n\s*\(D\)\s*(.+?)\n"
                   r".*?\*\*Answer:\*\*\s*`\(([A-D])\)`(?:\s*\*\*Explanation:\*\*\s*(.*?)(?=\n---|\Z))?", re.S)

# bank exam -> (syllabus id, how the prompt names it)
EXAMS = {"jee_main": ("jee", "JEE Main"), "jee_advanced": ("jee", "JEE Advanced"), "neet": ("neet", "NEET"),
         "ssc_cgl": ("ssc_cgl", "SSC CGL")}

CHECK_PROMPT = """You are a senior {name} faculty member checking practice questions before they go into a question
bank for students. For EACH question below:
1. Decide if it is usable: a complete, sensible question with exactly one correct option. Unusable: garbled, missing
   information that cannot be inferred, no correct option, two correct options, or a template with placeholders.
2. Fix small slips (a broken word, a missing bracket, a formula written badly, plain-text maths like "k * R^2")
   WITHOUT changing what it asks or which option is right. Return the fixed text only if you changed something;
   write maths in LaTeX inside $...$.
3. Solve it yourself from scratch and give the 0-based index of the correct option. Do not trust the marked answer.
4. File it under the syllabus below: subject, chapter and topic exactly as written there.
5. Write our own short solution (2-6 lines; LaTeX in $...$; money as ₹ in plain text, never the $ sign).

Syllabus (subject > chapter: topics):
{syllabus}

Questions:
{questions}

Return ONLY JSON: {{"results": [{{"id": "<id>", "usable": true, "why": "if not usable, one line",
 "text": "fixed question or null", "options": ["fixed options"] or null, "answer": 0,
 "subject": "...", "chapter": "...", "topic": "...", "difficulty": "easy|medium|hard", "solution": "..."}}]}}"""

JUDGE_PROMPT = """Two checks of this {name} question disagree about the right option: the answer key says option {key}
(0-based) and a solver chose option {solver}. Solve it carefully yourself, step by step, then decide.

{question}

Return ONLY JSON: {{"answer": <0-based index of the correct option, or null if no option is correct or the question is
ambiguous>, "solution": "the short worked solution for that answer (2-6 lines, LaTeX in $...$)"}}"""


SSC_SUBJECTS = {"01": "Quantitative Aptitude", "02": "General Intelligence and Reasoning", "03": "English Comprehension",
                "04": "General Awareness", "05": "Computer Knowledge"}


def subject_of(parts: tuple[str, ...]) -> str:
    if parts[0] == "SSC Questions":
        return SSC_SUBJECTS.get(parts[1][:2], "")
    return parts[2] if parts[0] == "JEE" else parts[1]


def exam_of(parts: tuple[str, ...]) -> str | None:
    if parts[0] == "JEE":
        return {"Mains": "jee_main", "Advanced": "jee_advanced"}.get(parts[1])
    return {"NEET": "neet", "SSC Questions": "ssc_cgl"}.get(parts[0])


# ---------------------------------------------------------------- parse
def parse(src: Path) -> list[dict]:
    from app.services.question_bank import fingerprint
    out: dict[str, dict] = {}
    blocks = 0
    for f in sorted(src.rglob("*.md")):
        parts = f.relative_to(src).parts
        exam = exam_of(parts)
        if not exam or len(parts) < 3:
            continue
        for chunk in re.split(r"\n### Q\d+", f.read_text(encoding="utf-8", errors="replace"))[1:]:
            m = BLOCK.search(chunk)
            if not m:
                continue
            blocks += 1
            text, *options, key, why = ((s or "").strip() for s in m.groups())
            fp = fingerprint(exam + "|" + text + "|" + "|".join(options))
            out.setdefault(fp, {"fp": fp, "exam": exam, "text": text, "options": options, "answer": "ABCD".index(key),
                                 "subject": subject_of(parts), "solution": re.sub(r"^\*\s*", "", why, flags=re.M)})
    questions = list(out.values())
    log.info("parse: %d question blocks, %d unique: %s", blocks, len(questions), dict(Counter(q["exam"] for q in questions)))
    return questions


# ---------------------------------------------------------------- check
def _render(q: dict, with_key: bool = True) -> str:
    opts = "\n".join(f"  ({j}) {o}" for j, o in enumerate(q["options"]))
    return f"[{q['id']}]\n{q['text']}\n{opts}" + (f"\n  marked answer: {q['answer']}" if with_key else "")


def check(questions: list[dict], workers: int) -> None:
    from app.services import syllabus
    path = WORK / "checked.json"
    done: dict[str, dict] = load(path, {})
    for exam, (syl_id, name) in EXAMS.items():
        syl = syllabus.get(syl_id)
        index = {(c.subject, c.name) for c in syl.chapters}
        sylt = "\n".join(f"{c.subject} > {c.name}: {', '.join(t.name for t in c.topics)}" for c in syl.chapters)
        todo = [q for q in questions if q["exam"] == exam and done.get(q["fp"], {}).get("status", "retry") == "retry"]
        if not todo:
            continue
        log.info("check %s: %d questions to go", exam, len(todo))
        for i, q in enumerate(todo):
            q["id"] = f"q{i}"
        batches = [todo[i:i + CHECK_BATCH] for i in range(0, len(todo), CHECK_BATCH)]

        def one(batch: list[dict]) -> list[tuple[str, dict]]:
            prompt = CHECK_PROMPT.format(name=name, syllabus=sylt, questions="\n\n".join(_render(q) for q in batch))
            results = {str(r.get("id")): r for r in chat(CHECK_MODEL, prompt, "md_check", "low").get("results") or []}
            out = []
            for q in batch:
                r = results.get(q["id"])
                if r is None:
                    continue
                if not r.get("usable", True):
                    out.append((q["fp"], {"status": "dropped", "why": r.get("why") or "unusable"}))
                    continue
                if not (isinstance(r.get("answer"), int) and 0 <= r["answer"] <= 3 and (r.get("subject"), r.get("chapter")) in index):
                    out.append((q["fp"], {"status": "retry"}))
                    continue
                fixed = {**q, "text": r.get("text") or q["text"],
                         "options": r["options"] if isinstance(r.get("options"), list) and len(r["options"]) == 4 else q["options"]}
                answer, solution, how = r["answer"], r.get("solution") or "", "key"
                if answer != q["answer"]:
                    j = chat(JUDGE_MODEL, JUDGE_PROMPT.format(name=name, key=q["answer"], solver=answer,
                                                              question=_render(fixed, False)), "md_check", "medium")
                    if j.get("answer") not in (0, 1, 2, 3):
                        out.append((q["fp"], {"status": "dropped", "why": "no option is clearly right"}))
                        continue
                    answer, solution = j["answer"], j.get("solution") or solution
                    how = "key" if answer == q["answer"] else "corrected"
                out.append((q["fp"], {"status": "ok", "how": how, "answer": answer, "text": fixed["text"],
                                      "options": fixed["options"], "subject": r["subject"], "chapter": r["chapter"],
                                      "topic": r.get("topic"), "difficulty": r.get("difficulty") or "medium",
                                      "solution": solution}))
            return out

        with ThreadPoolExecutor(max_workers=workers) as ex:
            for i, f in enumerate(as_completed([ex.submit(one, b) for b in batches])):
                try:
                    done.update(f.result())
                except Exception as exc:  # noqa: BLE001 - one bad batch shouldn't stop the rest
                    log.warning("check failed: %s", exc)
                if i % 10 == 0:
                    save(path, done)
                    log.info("  %s: %d/%d batches", exam, i + 1, len(batches))
        save(path, done)
    log.info("check: %s", dict(Counter(v["status"] if v["status"] != "ok" else f"ok/{v['how']}" for v in done.values())))


# ---------------------------------------------------------------- trust the key
def _words(text: str) -> set[str]:
    from app.services.topic_notes import _words as words
    return words(text)


def trusted(questions: list[dict]) -> dict[str, dict]:
    """Without the model check: the file's key as given, the subject from the folder, the chapter and topic whose
    words the question shares most (the subject's first chapter when none are shared)."""
    from app.services import syllabus
    out: dict[str, dict] = {}
    for exam, (syl_id, _) in EXAMS.items():
        syl = syllabus.get(syl_id)
        for q in (q for q in questions if q["exam"] == exam):
            chapters = [c for c in syl.chapters if c.subject == q["subject"]]
            if not chapters:
                continue
            words = _words(q["text"] + " " + " ".join(q["options"]))
            best = (-1.0, chapters[0], None)
            for c in chapters:
                for t in c.topics or [None]:
                    names = _words(c.name) | (_words(t.name) if t else set())
                    score = len(words & names) + (0.5 * len(words & _words(t.name)) if t else 0)
                    if score > best[0]:
                        best = (score, c, t)
            out[q["fp"]] = {"status": "ok", "how": "key", "answer": q["answer"], "text": q["text"], "options": q["options"],
                            "subject": q["subject"], "chapter": best[1].name, "topic": best[2].name if best[2] else None,
                            "difficulty": "medium", "solution": ""}
    return out


# ---------------------------------------------------------------- store
def store(questions: list[dict], trust_key: bool = False) -> None:
    from sqlalchemy import select

    from app.core.database import SessionLocal, init_db
    from app.models.mock import BankQuestion
    from app.services.math_text import clean_option

    init_db()
    checked = {**trusted(questions), **load(WORK / "checked.json", {})} if trust_key else load(WORK / "checked.json", {})
    added = skipped = 0
    with SessionLocal() as db:
        known = set(db.scalars(select(BankQuestion.fingerprint)))
        for q in questions:
            c = checked.get(q["fp"])
            if not c or c["status"] != "ok":
                continue
            if q["fp"] in known:
                skipped += 1
                continue
            db.add(BankQuestion(
                exam=q["exam"], subject=c["subject"], chapter=c["chapter"], topic=c.get("topic"), qtype="mcq",
                difficulty=c["difficulty"], question=c["text"], options=[clean_option(o) for o in c["options"]],
                answer=str(c["answer"]), solution=c["solution"] or q.get("solution", ""), verified=True, source="practice", fingerprint=q["fp"]))
            known.add(q["fp"])
            added += 1
        db.commit()
    log.info("store: %d new questions in the bank, %d were already there", added, skipped)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="folder holding JEE/, NEET/ and 'SSC Questions/'")
    ap.add_argument("--stage", choices=("all", "parse", "check", "store"), default="all")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--trust-key", action="store_true",
                    help="skip the model check: store the files' own answers and explanations (questions the check "
                         "already did keep its result)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    for name in ("httpx", "focs.llm"):
        logging.getLogger(name).setLevel(logging.WARNING)
    WORK.mkdir(parents=True, exist_ok=True)
    questions = parse(Path(args.src))
    save(WORK / "questions.json", questions)
    if args.stage in ("all", "check") and not args.trust_key:
        check(questions, args.workers)
    if args.stage in ("all", "store"):
        store(questions, args.trust_key)
    try:
        from app.services import ledger
        ledger.flush()
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
