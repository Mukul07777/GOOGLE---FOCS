"""Import free, openly licensed question sets into the question bank.

    python scripts/import_open_banks.py                    # every set, every stage (resumable)
    python scripts/import_open_banks.py --set neet-bio     # one set: neet-bio | neet-papers | jee-adv
    python scripts/import_open_banks.py --stage solve      # one stage: fetch | read | solve | store

The sets (each MIT-licensed, which allows commercial use; attributions in app/assets/bank/OPEN_SOURCES.md):
  neet-bio     sweatSmile/neet-biology-qa: 793 NEET Biology MCQs with answers. Not past questions: stored as "open".
  neet-papers  Reja1/jee-neet-benchmark: the NEET 2024 (T3), 2025 (45) and 2026 papers, one image per question,
               with the official answers.
  jee-adv      the same benchmark's JEE Advanced 2024-2026 papers (images), and daman1209arora/jeebench: JEE
               Advanced 2016-2023 (text).

Every question goes through import_pyq's solve and store stages: our own solution, chapter and difficulty, the answer
confirmed against the set's key (a solution that reaches another answer is set aside in review.json, never stored),
and questions with several correct answers or that need a figure are left out (the bank holds text only). A question
image is read into text first by Gemini flash-lite, about Rs 0.03 an image. Work is kept under
data/pyq/.work/open_<set>_<subject>/, so re-running never pays twice. Solutions are written by the stronger Groq model
(the cheap one filed questions under the wrong chapter), only with the quota beyond --reserve requests a day, so
students never run short: on a free key the import runs at the pace the quota refills, on a paid one at full speed.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_pyq as pyq  # noqa: E402

log = logging.getLogger("open_banks")

HF = "https://huggingface.co/datasets"
ROWS = "https://datasets-server.huggingface.co/rows"
BENCH = "Reja1/jee-neet-benchmark"
SETS = ("neet-bio", "neet-papers", "jee-adv")
SUBJECTS = {"physics": "Physics", "phy": "Physics", "chemistry": "Chemistry", "chem": "Chemistry", "math": "Mathematics",
            "mathematics": "Mathematics", "biology": "Biology", "botany": "Biology", "zoology": "Biology"}
SINGLE = {"MCQ_SINGLE_CORRECT", "MCQ_MATCHING", "MCQ"}  # a matching question has four options and one is right
NUMERIC = {"INTEGER", "INTEGER_2", "NUMERICAL", "Integer", "Numeric"}
SOURCE_DIR = pyq.WORK / "open_sources"


def part(set_name: str, subject: str) -> Path:
    """The stand-in "PDF" import_pyq keys a work folder and a subject on (its name says the subject)."""
    return pyq.ROOT / f"open {set_name} {subject}.pdf"


def _get(url: str, **params) -> httpx.Response:
    for attempt in range(5):
        try:
            r = httpx.get(url, params=params or None, timeout=120, follow_redirects=True, headers={"User-Agent": "focs-bank-import"})
            if r.status_code < 500 and r.status_code != 429:
                r.raise_for_status()
                return r
        except httpx.TransportError as exc:
            log.warning("download failed (%s), again", exc)
        time.sleep(5 * 2 ** attempt)
    raise RuntimeError(f"could not download {url}")


def _cached(name: str, url: str) -> bytes:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    path = SOURCE_DIR / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_get(url).content)
    return path.read_bytes()


def _item(n: str, page: int, text: str, options: list[str], qtype: str, key: str | None, exam: str, *,
          year: int | None = None, paper: str | None = None, source: str = "pyq", figure: bool = False,
          passage: str | None = None) -> dict:
    """A question in the shape import_pyq's build stage writes."""
    return {"pdf": "", "page": page, "chapter_hint": "", "section": "", "n": n, "type": qtype, "passage": passage,
            "text": text.strip(), "options": [str(o).strip() for o in options], "tag": None, "figure": figure, "cut": False,
            "exam": exam, "year": year, "paper": paper, "key": key, "source": source}


# ---------------------------------------------------------------- neet-bio (text)
def fetch_neet_bio() -> dict[str, list[dict]]:
    rows: list[dict] = []
    while True:
        cached = SOURCE_DIR / "neet-bio" / f"rows_{len(rows)}.json"
        if not cached.exists():
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(_get(ROWS, dataset="sweatSmile/neet-biology-qa", config="default", split="train",
                                   offset=len(rows), length=100).text, encoding="utf-8")
        page = [r["row"] for r in json.loads(cached.read_text(encoding="utf-8"))["rows"]]
        rows += page
        if len(page) < 100:
            break
    items = []
    for i, r in enumerate(rows):
        answer = str(r.get("answer") or "").strip().upper()
        if len(r.get("choices") or []) != 4 or answer not in ("A", "B", "C", "D"):
            continue
        items.append(_item(str(i + 1), i, r["question"], r["choices"], "single", pyq._norm_key(answer), "neet", source="open"))
    log.info("neet-bio: %d questions", len(items))
    return {"Biology": items}


# ---------------------------------------------------------------- jeebench (text)
OPTION = re.compile(r"\(\s*([A-D])\s*\)")


def _split_options(text: str) -> tuple[str, list[str]] | None:
    """'... is\\n\\n(A) x\\n\\n(B) y ...' -> ('... is', ['x', 'y', 'z', 'w']), when the four are there in order."""
    marks = list(OPTION.finditer(text))
    if [m.group(1) for m in marks[-4:]] != ["A", "B", "C", "D"]:
        return None
    marks = marks[-4:]
    stem = text[:marks[0].start()].strip()
    options = [text[m.end():(marks[i + 1].start() if i < 3 else len(text))].strip() for i, m in enumerate(marks)]
    return (stem, options) if stem and all(options) else None


def fetch_jeebench() -> dict[str, list[dict]]:
    data = json.loads(_cached("jeebench/test.json", f"{HF}/daman1209arora/jeebench/resolve/main/test.json"))
    out: dict[str, list[dict]] = {}
    for q in data:
        if q["type"] not in ("MCQ", "Integer", "Numeric"):
            continue  # several answers: the exam screen takes one (a LaTeX table is redrawn in Markdown when stored)
        m = re.search(r"(20\d\d) Paper (\d)", q["description"])
        year, paper = (int(m.group(1)), f"JEE Advanced {m.group(1)} (Paper {m.group(2)})") if m else (None, "JEE Advanced")
        subject = SUBJECTS[q["subject"]]
        n = f"jb{q['index']}"
        if q["type"] == "MCQ":
            split = _split_options(q["question"])
            if not split:
                continue
            stem, options = split
            item = _item(n, q["index"], stem, options, "single", pyq._norm_key(q["gold"]), "jee_advanced", year=year, paper=paper)
        else:
            item = _item(n, q["index"], q["question"], [], "numerical", str(q["gold"]).strip(), "jee_advanced", year=year, paper=paper)
        out.setdefault(subject, []).append(item)
    log.info("jeebench: %s", {s: len(v) for s, v in out.items()})
    return out


# ---------------------------------------------------------------- the benchmark's papers (images)
def _bench_rows(exam: str) -> list[dict]:
    rows = [json.loads(line) for line in _cached("bench/metadata.jsonl", f"{HF}/{BENCH}/resolve/main/images/metadata.jsonl")
            .decode("utf-8").splitlines() if line.strip()]
    return [r for r in rows if r["exam_name"] == exam]


def _jpeg(png: bytes) -> bytes:
    import cv2
    import numpy as np

    img = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()


def read_bench(exam: str, workers: int) -> None:
    """Read each question image into text (import_pyq's page reader: the image is a one-question page)."""
    out = pyq.WORK / f"open_bench_{exam.lower()}"
    out.mkdir(parents=True, exist_ok=True)
    rows = [r for r in _bench_rows(exam) if not (out / f"{r['question_id']}.json").exists()]
    log.info("read %s: %d question images to go", exam, len(rows))

    def one(r: dict) -> str:
        png = _cached(f"bench/{r['file_name']}", f"{HF}/{BENCH}/resolve/main/images/{r['file_name']}")
        pyq.save(out / f"{r['question_id']}.json", pyq._vision(_jpeg(png)))
        return r["question_id"]

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, f in enumerate(as_completed([ex.submit(one, r) for r in rows])):
            try:
                f.result()
            except Exception as exc:  # noqa: BLE001 - one bad image shouldn't stop the paper
                log.warning("image failed: %s", exc)
            if i % 25 == 0:
                log.info("  read %d/%d", i + 1, len(rows))


def fetch_bench(exam: str) -> dict[str, list[dict]]:
    """The questions read so far, with the benchmark's official answers."""
    folder = pyq.WORK / f"open_bench_{exam.lower()}"
    out: dict[str, list[dict]] = {}
    for i, r in enumerate(_bench_rows(exam)):
        read = pyq.load(folder / f"{r['question_id']}.json", None)
        if not read or not read.get("questions"):
            continue
        q = read["questions"][0]
        answers = json.loads(r["correct_answer"]) if isinstance(r["correct_answer"], str) else r["correct_answer"]
        qtype = ("multi" if len(answers) != 1 else "single" if r["question_type"] in SINGLE
                 else "numerical" if r["question_type"] in NUMERIC else "other")
        year = int(r["exam_year"])
        paper = f"NEET {year}" if exam == "NEET" else f"JEE Advanced {year}"
        item = _item(r["question_id"], i, str(q.get("text") or ""), q.get("options") or [], qtype,
                     pyq._norm_key(str(answers[0])) if answers else None, "neet" if exam == "NEET" else "jee_advanced",
                     year=year, paper=paper, figure=bool(q.get("figure")), passage=q.get("passage"))
        out.setdefault(SUBJECTS[r["subject"].lower()], []).append(item)
    return out


# ---------------------------------------------------------------- main
def gather(set_name: str, stage: str, workers: int) -> dict[str, list[dict]]:
    if set_name == "neet-bio":
        return fetch_neet_bio()
    exam = "NEET" if set_name == "neet-papers" else "JEE_ADVANCED"
    if stage in ("all", "read"):
        read_bench(exam, workers)
    found = fetch_bench(exam)
    if set_name == "jee-adv":
        for subject, items in fetch_jeebench().items():
            found.setdefault(subject, []).extend(items)
    return found


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", choices=SETS, action="append")
    ap.add_argument("--stage", choices=("all", "fetch", "read", "solve", "store"), default="all")
    ap.add_argument("--read-workers", type=int, default=4)
    ap.add_argument("--solve-workers", type=int, default=2)
    ap.add_argument("--reserve", type=int, default=450,
                    help="Groq requests a day kept for students (free tier: 1,000); the import waits below it")
    args = ap.parse_args()
    pyq.background()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    for name in ("httpx", "focs.llm", "focs.ocr"):
        logging.getLogger(name).setLevel(logging.WARNING)
    from app.core.database import init_db
    init_db()
    for set_name in args.set or SETS:
        log.info("=== %s", set_name)
        for subject, items in gather(set_name, args.stage, args.read_workers).items():
            pdf = part(set_name, subject)
            if args.stage in ("all", "fetch", "read"):
                pyq.save(pyq.workdir(pdf) / "questions.json", items)
                log.info("%s %s: %d questions ready to solve", set_name, subject, len(items))
            if args.stage in ("all", "solve"):
                pyq.solve_paced(pdf, args.solve_workers, args.reserve)
            if args.stage in ("all", "store"):
                pyq.store(pdf)
    try:
        from app.services import ledger
        ledger.flush()
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
