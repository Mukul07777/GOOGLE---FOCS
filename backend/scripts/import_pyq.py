"""Import previous-year questions (PYQs) from PDFs in data/pyq/ into the question bank.

    python scripts/import_pyq.py                 # every PDF, every stage (resumable)
    python scripts/import_pyq.py --stage scan    # one stage: scan | read | build | solve | store
    python scripts/import_pyq.py --file "Allen"  # only PDFs whose name contains this

Only genuine past exam questions are imported: a question needs an exam-and-year tag printed with it
([JEE(Main)-2017], [AIEEE-2011], [NEET 2021], [AIPMT 2014]…), or must come from an official paper (a PDF in
data/pyq/official/, where every question is a past question). A coaching book's own practice questions,
explanations and solutions are never copied: every imported question gets a solution written by our model,
and its answer is confirmed against the answer key, or by a second model, before students see it.

Stages (each saves its work under data/pyq/.work/<pdf>/, so re-running never pays twice):
  scan   free local OCR of every page: which pages carry tagged questions or an answer key
  read   a vision model reads just those pages into questions (text + LaTeX, options, tag)
  build  join questions cut across pages, keep the tagged ones, attach answer-key answers
  solve  our own solution, chapter and difficulty for each; answer confirmed by the key or a second model
  reread pages where a solution couldn't reach the official answer are read again at a higher resolution
  store  add confirmed questions to the bank (duplicates across books are skipped); the rest go to review.json

Cost: the cheapest model at every step. Pages are read by gemini flash-lite, the cheapest model that sees images;
the answer key catches its rare misreadings, and only those pages are read again, by the same model at a higher
resolution. Solutions are written by the cheap Groq models (gpt-oss-20b explains a known answer, 120b solves when
there is no key); Gemini never solves, the import waits out Groq's rate limits instead.
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import httpx  # noqa: E402
import pymupdf  # noqa: E402

from app.core.config import settings  # noqa: E402

ROOT = BACKEND.parent / "data" / "pyq"
WORK = ROOT / ".work"
log = logging.getLogger("pyq")

TAG = re.compile(r"(AIEEE|JEE|NEET|AIPMT|IIT|MAIN|ADV|AIIMS|CBSE[- ]?PMT)[^\n]{0,30}(19|20)\d\d", re.I)
KEY = re.compile(r"ANSWER\s*KEY|Que\.?\s*\d+\s+\d+|ANSWERS", re.I)
VISION_MODEL = "gemini-3.1-flash-lite"      # cheapest model that reads images
VISION_BUSY = "gemini-3.5-flash-lite"       # when it answers 503 "high demand" (most of 2026-10-19)
REREAD_DPI = 160                             # the few pages the first read got wrong: same cheap model, sharper image
SUBJECT_WORDS = {"Mathematics": ("math",), "Physics": ("phys",), "Chemistry": ("chem",), "Biology": ("bio", "botany", "zoology")}

READ_PROMPT = """You transcribe one scanned page of an Indian exam-prep book or exam paper (JEE/NEET) into JSON.
Return ONLY a JSON object:
{"chapter": the chapter name in the page header or null,
 "section": the exercise/section heading active on this page (e.g. "EXERCISE : JEE MAIN") or null,
 "subject": the subject heading in force on this page of a paper with several subjects ("PHYSICS", "CHEMISTRY",
            "BOTANY", "ZOOLOGY", "MATHEMATICS"), or null,
 "answer_key": [{"section": "JEE MAIN" or the exercise the key belongs to, "n": "12", "a": "3"}] for every entry of
               any answer-key table on the page, else [],
 "questions": [{"n": "4", "type": "single" | "multi" | "numerical" | "matrix" | "subjective",
                "passage": "the comprehension/paragraph text this question belongs to, if any, else null",
                "text": "...", "options": ["...","...","...","..."] or [],
                "tag": "[JEE (Mains) Offline-2014]" or null,
                "figure": true if a diagram/graph/picture is needed to solve it,
                "cut": true if the question continues on the next page,
                "answer": the answer printed with the question itself ("Answer (3)", "Ans. (B)", "Sol. ... Answer: 4"):
                          the option number 1-4 or the value, else null}]}
Rules: copy the question and options exactly; write every formula in LaTeX inside $...$
(e.g. $\\lim_{x\\to 0} \\frac{\\sin x}{x}$); "tag" is the exam/year label printed with the question, verbatim, or null;
drop option labels like (1) (A); a table (Match List-I with List-II, a truth table, data) is a Markdown table,
never LaTeX tabular; a numbered question with no options is "numerical" if it asks for a value;
ignore watermarks, channel names, page numbers, question codes (e.g. LT0107) and scanner logos."""


# ---------------------------------------------------------------- helpers
def pdfs(name_filter: str | None) -> list[Path]:
    files = sorted(ROOT.rglob("*.pdf"))
    return [f for f in files if ".work" not in f.parts and (not name_filter or name_filter.lower() in f.name.lower())]


def workdir(pdf: Path) -> Path:
    d = WORK / re.sub(r"[^\w.-]+", "_", pdf.stem)
    d.mkdir(parents=True, exist_ok=True)
    return d


def official(pdf: Path) -> bool:
    return "official" in {p.lower() for p in pdf.relative_to(ROOT).parts[:-1]}


def subject_of(pdf: Path) -> str | None:
    return subject_in(pdf.name)


def subject_in(text: str | None) -> str | None:
    """The subject a file name or a heading names ("Allen PHYSICS Neet Module", "ZOOLOGY"), if any."""
    name = (text or "").lower()
    return next((s for s, words in SUBJECT_WORDS.items() if any(w in name for w in words)), None)


def load(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path: Path, data: Any) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def page_jpeg(pdf: Path, page: int, dpi: int = 110) -> bytes:
    pix = pymupdf.open(pdf)[page].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    return pix.tobytes("jpg", jpg_quality=72)


# ---------------------------------------------------------------- scan (local OCR, free)
def _scan_page(args: tuple[str, int]) -> tuple[int, dict]:
    pdf, page = args
    doc = pymupdf.open(pdf)
    text = doc[page].get_text()
    if len(text.strip()) < 80:  # a scanned page: read it with our OCR
        import cv2
        import numpy as np

        from app.services.ocr import ocr_engine
        pix = doc[page].get_pixmap(dpi=100, colorspace=pymupdf.csGRAY)
        img = cv2.cvtColor(np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w), cv2.COLOR_GRAY2BGR)
        text = ocr_engine.run(img, "rapid").text
    return page, {"tags": len(TAG.findall(text)), "key": bool(KEY.search(text)), "head": text[:160]}


def scan(pdf: Path, workers: int) -> dict:
    path = workdir(pdf) / "scan.json"
    done: dict[str, dict] = load(path, {})
    todo = [p for p in range(pymupdf.open(pdf).page_count) if str(p) not in done]
    if official(pdf):  # every page of an official paper is read
        for p in todo:
            done[str(p)] = {"tags": 1, "key": True, "head": ""}
        save(path, done)
        return done
    log.info("scan %s: %d pages to go", pdf.name, len(todo))
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, (page, info) in enumerate(ex.map(_scan_page, [(str(pdf), p) for p in todo], chunksize=4)):
            done[str(page)] = info
            if i % 25 == 0:
                save(path, done)
                log.info("  scanned %d/%d", i + 1, len(todo))
    save(path, done)
    return done


def candidates(scan_result: dict) -> list[int]:
    pages = sorted(int(p) for p, info in scan_result.items() if info["tags"] or info["key"])
    return pages


# ---------------------------------------------------------------- read (vision)
_busy: set[str] = set()  # models that answered 503 in this run: straight to VISION_BUSY for the rest of it


def _vision(img: bytes, model: str = VISION_MODEL) -> dict:
    model = VISION_BUSY if model in _busy else model
    body = {"model": model, "temperature": 0, "response_format": {"type": "json_object"},
            **({"reasoning_effort": "low"} if "lite" not in model else {}),
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": READ_PROMPT},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(img).decode()}}]}]}
    key = settings.LLM_FALLBACK_API_KEY or settings.GEMINI_API_KEY
    for attempt in range(6):
        r = httpx.post(settings.LLM_FALLBACK_BASE_URL.rstrip("/") + "/chat/completions", json=body, timeout=240,
                       headers={"Authorization": f"Bearer {key}"})
        if r.status_code == 503 and body["model"] != VISION_BUSY:
            log.warning("vision %s busy (503), reading with %s from now on", body["model"], VISION_BUSY)
            _busy.add(body["model"])
            body["model"] = model = VISION_BUSY
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            wait = float(r.headers.get("retry-after") or 0) or min(120, 10 * 2 ** attempt)
            log.warning("vision %s, waiting %.0fs", r.status_code, wait)
            time.sleep(wait)
            continue
        if r.status_code == 400 and "reasoning_effort" in r.text and "reasoning_effort" in body:
            body.pop("reasoning_effort")
            continue
        r.raise_for_status()
        data = r.json()
        _record_cost(model, data.get("usage"))
        content = data["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:  # LaTeX backslashes the model didn't escape ("\lim"): the app's tolerant parser
            from app.services.llm import parse_json
            parsed = parse_json(content)
        return {**parsed, "_model": model}
    raise RuntimeError("vision model kept failing")


def _record_cost(model: str, usage: dict | None) -> None:
    try:
        from app.services import ledger
        ledger.record("pyq_read", model, usage)
    except Exception:  # noqa: BLE001 - cost tracking must never stop an import
        pass


def read(pdf: Path, pages: list[int], workers: int, model: str = VISION_MODEL, again: bool = False, dpi: int = 110) -> None:
    out = workdir(pdf) / "pages"
    out.mkdir(exist_ok=True)
    todo = [p for p in pages if again or not (out / f"{p:04d}.json").exists()]
    log.info("read %s with %s: %d of %d pages to go", pdf.name, model, len(todo), len(pages))

    def one(p: int) -> int:
        result = _vision(page_jpeg(pdf, p, dpi), model)
        if again:
            result["_reread"] = True
        save(out / f"{p:04d}.json", result)
        return p

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(one, p) for p in todo]
        for i, f in enumerate(as_completed(futures)):
            try:
                f.result()
            except Exception as exc:  # noqa: BLE001 - one bad page shouldn't stop the book
                log.warning("page failed: %s", exc)
            if i % 20 == 0:
                log.info("  read %d/%d", i + 1, len(todo))


# ---------------------------------------------------------------- build
EXAMS = [
    (re.compile(r"neet|aipmt|cbse[- ]?pmt|aiims|pre[- ]?medical", re.I), "neet"),
    (re.compile(r"adv|iit[- ]?jee|jee[- ]?\(?a", re.I), "jee_advanced"),
    (re.compile(r"aieee|jee|main", re.I), "jee_main"),
]


def parse_tag(tag: str | None) -> tuple[str, int, str] | None:
    """[JEE (Mains) Online-2014] → ("jee_main", 2014, "JEE Main 2014 (Online)")."""
    if not tag:
        return None
    m = re.search(r"(19|20)\d\d", tag)
    if not m:
        return None
    year = int(m.group(0))
    exam = next((e for rx, e in EXAMS if rx.search(tag)), None)
    if exam is None:
        return None
    raw = tag.upper()
    if "AIEEE" in raw:
        name = f"AIEEE {year}"
    elif "AIPMT" in raw:
        name = f"AIPMT {year}"
    elif "AIIMS" in raw:
        name = f"AIIMS {year}"
    elif exam == "neet":
        name = f"NEET {year}"
    elif exam == "jee_advanced":
        name = f"JEE Advanced {year}" if year >= 2013 else f"IIT-JEE {year}"
    else:
        name = f"JEE Main {year}"
    for word in ("Online", "Offline", "Jan", "Feb", "April", "Apr", "Sept", "July", "Aug", "Phase", "Re", "Odisha"):
        if re.search(rf"\b{word}", tag, re.I):
            name += f" ({word})"
            break
    return exam, year, name


def build(pdf: Path) -> list[dict]:
    pages_dir = workdir(pdf) / "pages"
    pages = sorted(pages_dir.glob("*.json"))
    is_official = official(pdf)
    keys: dict[tuple[str, str, str], str] = {}  # (chapter, section, n) → answer
    items: list[dict] = []
    chapter, section, subject = "", "", None
    for path in pages:
        page = int(path.stem)
        data = load(path, {})
        header = (data.get("chapter") or "").strip()
        if header and not _generic(header):  # alternate pages carry only the book's name: keep the chapter
            chapter = header
        section = (data.get("section") or section or "").strip()
        subject = subject_in(data.get("subject")) or subject  # a paper's subject heading holds till the next one
        for k in data.get("answer_key") or []:
            keys[(chapter.lower(), _sec(k.get("section") or section), str(k.get("n")).strip())] = _norm_key(k.get("a"))
        for q in data.get("questions") or []:
            text = str(q.get("text") or "").strip()
            if items and items[-1].get("cut") and (not q.get("n") or str(q.get("n")) == items[-1]["n"]):
                prev = items[-1]  # the rest of a question that started on the previous page
                prev["text"] = (prev["text"] + " " + text).strip()
                prev["options"] = prev["options"] or q.get("options") or []
                prev["tag"] = prev["tag"] or q.get("tag")
                prev["cut"] = bool(q.get("cut"))
                continue
            items.append({"pdf": pdf.name, "page": page, "chapter_hint": chapter, "section": section, "subject_hint": subject,
                          "n": str(q.get("n") or "").strip(), "type": q.get("type") or "single", "passage": q.get("passage"),
                          "text": text, "options": [str(o).strip() for o in q.get("options") or []],
                          "tag": q.get("tag"), "figure": bool(q.get("figure")), "cut": bool(q.get("cut")),
                          "printed": q.get("answer")})
    out = []
    default_exam = _official_exam(pdf) if is_official else None
    for it in items:
        parsed = parse_tag(it["tag"]) or default_exam
        if parsed is None:
            continue  # not a past exam question: a coaching book's own practice question
        it["exam"], it["year"], it["paper"] = parsed
        # an answer-key table, else the answer printed under the question (official papers with answers)
        it["key"] = keys.get((it["chapter_hint"].lower(), _sec(it["section"]), it["n"])) or _norm_key(
            None if it.get("printed") is None else str(it["printed"]))
        out.append(it)
    save(workdir(pdf) / "questions.json", out)
    log.info("build %s: %d tagged questions (%d with an answer key) from %d pages", pdf.name, len(out),
             sum(1 for q in out if q["key"]), len(pages))
    return out


GENERIC_WORDS = {"jee", "neet", "main", "advanced", "mathematics", "maths", "math", "physics", "chemistry", "biology",
                 "botany", "zoology", "pre", "medical", "allen", "leader", "module", "aiims", "ug"}


def _generic(header: str) -> bool:
    """A running book/subject title ("JEE- Mathematics", "Pre-Medical") rather than a chapter name."""
    words = re.findall(r"[a-z]+", header.lower())
    return not words or all(w in GENERIC_WORDS for w in words)


def _norm_key(answer: str | None) -> str | None:
    """Answer-key entries as option numbers (A-D → 1-4) or values; multi-answer keys are left as they are."""
    if answer is None:
        return None
    a = str(answer).strip().strip("()").upper()
    if a in ("A", "B", "C", "D"):
        return str("ABCD".index(a) + 1)
    return a or None


def _sec(s: str) -> str:
    s = (s or "").upper()
    return "NEET" if "NEET" in s or "AIPMT" in s else "ADV" if "ADV" in s else "MAIN" if "MAIN" in s else s.strip()


def _official_exam(pdf: Path) -> tuple[str, int, str] | None:
    """data/pyq/official/JEE Main 2024 27 Jan Shift 1.pdf → ("jee_main", 2024, "JEE Main 2024 (27 Jan Shift 1)")."""
    parsed = parse_tag(pdf.stem)
    if parsed is None:
        return None
    exam, year, _ = parsed
    detail = re.sub(r"(?i)\b(jee|main|mains|advanced|adv|neet|ug|paper|question|19\d\d|20\d\d)\b", " ", pdf.stem)
    detail = re.sub(r"[\s_-]+", " ", detail).strip()
    base = {"jee_main": "JEE Main", "jee_advanced": "JEE Advanced", "neet": "NEET"}[exam]
    return exam, year, f"{base} {year}" + (f" ({detail})" if detail else "")


# ---------------------------------------------------------------- solve
SOLVE = """You are a senior {exam} {subject} teacher. Solve this past exam question yourself, independently.
Return JSON: {{"answer": {answer_spec}, "solution": "a clear, concise step-by-step solution in your own words,
markdown with LaTeX in $...$ (at most ~12 lines)", "chapter": the name (before the colon) of the chapter listed whose topics the question is on,
"difficulty": "easy"|"medium"|"hard"}}
Chapters: {chapters}"""
CHECK = """Solve this {exam} {subject} question carefully and independently. Return JSON: {{"answer": {answer_spec}}}"""
EXPLAIN = """You are a senior {exam} {subject} teacher. This past exam question's official answer is {key}.
Write the solution a student needs to reach it. Return JSON: {{"answer": {answer_spec} (the one your solution reaches),
"solution": "a clear, concise step-by-step solution in your own words, markdown with LaTeX in $...$ (at most ~12 lines)",
"chapter": the name (before the colon) of the chapter listed whose topics the question is on,
"difficulty": "easy"|"medium"|"hard"}}
Chapters: {chapters}"""


def _words(text: str) -> set[str]:
    stop = {"and", "of", "the", "in", "to", "a", "its", "their"}
    return {w.rstrip("s") for w in re.findall(r"[a-z]+", text.lower()) if w not in stop and len(w) > 2}


def chapter_from_heading(heading: str, chapters: list[str]) -> str | None:
    """The book's own chapter heading, when it clearly is one of ours ("Limit, Continuity, Differentiability")."""
    h = _words(heading)
    if not h:
        return None
    scored = sorted(((len(h & _words(c)) / len(h | _words(c)), c) for c in chapters), reverse=True)
    return scored[0][1] if scored and scored[0][0] >= 0.5 else None


def _render(q: dict) -> str:
    body = (f"Passage:\n{q['passage']}\n\n" if q.get("passage") else "") + q["text"]
    if q["qtype"] == "mcq":
        body += "\n\nOptions:\n" + "\n".join(f"{i + 1}. {o}" for i, o in enumerate(q["options"]))
    return body


def _answer_spec(q: dict) -> str:
    return "the option number 1-4" if q["qtype"] == "mcq" else "the numerical value"


def _same(q: dict, a: Any, b: Any) -> bool:
    try:
        return abs(float(a) - float(b)) < (1e-6 if q["qtype"] == "mcq" else 1e-2 * max(1.0, abs(float(b))))
    except (TypeError, ValueError):
        return str(a).strip().lower() == str(b).strip().lower()


def solve(pdf: Path, workers: int, limit: int | None = None) -> int:
    """Solve what is still to do (at most ``limit`` questions); returns how many are left after this call."""
    from app.services import llm as llm_mod
    from app.services import syllabus
    from app.services.llm import LLMUnavailable, _models, fix_latex, llm

    gemini = frozenset(_models(settings.LLM_FALLBACK_MODEL))  # never pay Gemini to solve: wait for Groq instead
    strong = gemini | frozenset(_models(settings.LLM_LIGHT_MODEL))  # chapters need the stronger model: wait for it

    path = workdir(pdf) / "solved.json"
    solved: dict[str, dict] = load(path, {})
    questions = load(workdir(pdf) / "questions.json", [])
    subject_default = subject_of(pdf)

    def key_of(q: dict) -> str:
        return f"{q['page']}:{q['n']}:{q['text'][:40]}"

    def one(q: dict) -> tuple[str, dict]:
        k = key_of(q)
        if q.get("key") and "," in str(q["key"]):
            q = dict(q, type="multi")  # a multiple-correct key: the exam screen takes one answer per question
        if q["type"] not in ("single", "numerical") or q["figure"] or q["cut"]:
            return k, {"status": "skipped", "why": "figure" if q["figure"] else q["type"] if q["type"] not in ("single", "numerical") else "cut"}
        q = dict(q, qtype="mcq" if q["type"] == "single" else "numerical")
        if q["qtype"] == "mcq" and len(q["options"]) != 4:
            return k, {"status": "skipped", "why": "options"}
        exam = "neet" if q["exam"] == "neet" else "jee"
        # a subject's book names it; a paper of several subjects names it in its headings (NEET 2020 opens with Biology)
        subject = subject_default or q.get("subject_hint")
        if subject is None:
            return k, {"status": "skipped", "why": "subject"}
        listed = syllabus.get(exam).subject_chapters(subject)
        chapters = [c.name for c in listed]
        # each chapter with its topics: by name alone the cheap model filed a question on drugs (cocaine, heroin)
        # under Biomolecules instead of Human Health and Disease
        menu = "\n" + "\n".join(f"- {c.name}: {', '.join(t.name for t in c.topics)}" for c in listed)
        label = "NEET" if exam == "neet" else "JEE"
        # with the official answer known, the model explains it (accurate even when a weaker model has to step in);
        # without one, it solves independently and a second model must agree
        prompt = (EXPLAIN.format(exam=label, subject=subject, answer_spec=_answer_spec(q), chapters=menu,
                                 key=f"option {q['key']}" if q["qtype"] == "mcq" else q["key"])
                  if q.get("key") else
                  SOLVE.format(exam=label, subject=subject, answer_spec=_answer_spec(q), chapters=menu))
        try:  # the stronger model: the cheap one explained answers well but filed a logic-gate truth table under
            # Current Electricity and d-block magnetism under Chemical Bonding (chapter tests need the right chapter)
            data, model = llm.json_with_model([{"role": "system", "content": prompt}, {"role": "user", "content": _render(q)}],
                                              max_tokens=1400, temperature=0.1, effort="medium", feature="pyq_solve",
                                              tier="standard", patient=True, skip=strong)
        except LLMUnavailable as exc:
            return k, {"status": "retry", "why": str(exc)[:200]}
        answer = data.get("answer")
        chapter = chapter_from_heading(q.get("chapter_hint") or "", chapters) or str(data.get("chapter") or "")
        if chapter not in chapters:
            chapter = next((c for c in chapters if c.lower() in chapter.lower() or chapter.lower() in c.lower()), "")
        result = {"answer": answer, "solution": fix_latex(str(data.get("solution") or "").strip()), "chapter": chapter,
                  "difficulty": data.get("difficulty") if data.get("difficulty") in ("easy", "medium", "hard") else "medium",
                  "subject": subject, "qtype": q["qtype"], "model": model}
        if q.get("key"):
            result["status"] = "ok" if _same(q, answer, q["key"]) else "disagrees_with_key"
            return k, result
        try:  # no key: a second, different model must agree
            check, _ = llm.json_with_model(
                [{"role": "system", "content": CHECK.format(exam=label, subject=subject, answer_spec=_answer_spec(q))},
                 {"role": "user", "content": _render(q)}],
                max_tokens=600, temperature=0.0, effort="medium", skip=frozenset({model}) | gemini, feature="pyq_verify")
            result["status"] = "ok" if _same(q, answer, check.get("answer")) else "models_disagree"
        except LLMUnavailable:
            result["status"] = "unchecked"
        return k, result

    todo = [q for q in questions if solved.get(key_of(q), {}).get("status") in (None, "retry")]
    log.info("solve %s: %d of %d to go", pdf.name, len(todo), len(questions))
    left = len(todo)
    todo = todo[:limit] if limit else todo
    llm_mod.LIGHT_WAIT_S = 30
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, fut in enumerate(as_completed([ex.submit(one, q) for q in todo])):
            k, res = fut.result()
            solved[k] = res
            if i % 10 == 0:
                save(path, solved)
                log.info("  solved %d/%d", i + 1, len(todo))
            if res.get("status") != "retry":
                left -= 1
    save(path, solved)
    return left


# ---------------------------------------------------------------- pacing
_room: tuple[float, int] = (0.0, 0)


def groq_room() -> int:
    """Requests left today on the Groq models, the fewest of them (they also write students' notes and quizzes). A
    free key has 1,000 a day per model, refilled evenly over the day; a paid one reports far more. Probed with a
    one-token request at most every two minutes."""
    global _room
    from app.core.config import settings
    from app.services.llm import _models

    if time.monotonic() - _room[0] < 120:
        return _room[1]
    left = []
    for model in dict.fromkeys(_models(settings.LLM_MODEL)):
        try:
            r = httpx.post(settings.LLM_BASE_URL.rstrip("/") + "/chat/completions", timeout=30,
                           headers={"Authorization": f"Bearer {settings.llm_api_key}", "User-Agent": "focs-bank-import"},
                           json={"model": model, "messages": [{"role": "user", "content": "ok"}], "max_tokens": 1})
            left.append(int(r.headers.get("x-ratelimit-remaining-requests", 10 ** 6)))
        except (httpx.HTTPError, ValueError):
            left.append(0)
    _room = (time.monotonic(), min(left, default=10 ** 6))
    return _room[1]


def solve_paced(pdf: Path, workers: int, reserve: int) -> None:
    """Solve in small rounds, only with what the AI quota has beyond ``reserve`` requests: the students' share of the
    day is never spent on the import. Below it, wait for the quota to refill."""
    before = None
    while True:
        room = groq_room()
        if room < reserve + 10:
            log.info("Groq has %d requests left today, %d kept for students: waiting 20 minutes", room, reserve)
            time.sleep(1200)
            continue
        left = solve(pdf, workers, limit=min(25, room - reserve))
        if left == 0:
            return
        if left == before:  # a round made no progress (rate limits): give the minute's budget time to refill
            time.sleep(90)
        before = left


# ---------------------------------------------------------------- reread
def reread(pdf: Path, workers: int) -> int:
    """Pages where a solution couldn't reach the official answer: most likely the cheap read slipped (a lost
    exponent or sign). Read them again with the stronger model, then those questions are built and solved afresh."""
    solved_path = workdir(pdf) / "solved.json"
    solved = load(solved_path, {})
    pages_dir = workdir(pdf) / "pages"
    pages = sorted({int(k.split(":")[0]) for k, v in solved.items() if v.get("status") == "disagrees_with_key"})
    pages = [p for p in pages if not load(pages_dir / f"{p:04d}.json", {}).get("_reread")]
    if not pages:
        return 0
    read(pdf, pages, workers, again=True, dpi=REREAD_DPI)
    redo = {k for k in solved if int(k.split(":")[0]) in pages}
    save(solved_path, {k: v for k, v in solved.items() if k not in redo})
    log.info("reread %s: %d pages read again, %d questions to solve again", pdf.name, len(pages), len(redo))
    return len(pages)


# ---------------------------------------------------------------- store
TABULAR = re.compile(r"\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}", re.S)


def md_tables(text: str) -> str:
    """A LaTeX tabular (a truth table, Match List-I with List-II) as a Markdown table: KaTeX can't draw tabular, and
    the exam screen renders Markdown. Cells keep their $...$ maths."""
    def table(m: re.Match) -> str:
        rows = [r.replace(r"\hline", "").strip() for r in re.split(r"\\\\", m.group(1))]
        rows = [[c.strip() for c in r.split("&")] for r in rows if r.strip()]
        if not rows:
            return ""
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width] + ["| " + " | ".join(r) + " |" for r in rows[1:]]
        return "\n\n" + "\n".join(lines) + "\n\n"
    text = re.sub(r"\\begin\{center\}|\\end\{center\}", "", text)
    return re.sub(r"\n{3,}", "\n\n", TABULAR.sub(table, text)).strip()


def store(pdf: Path) -> tuple[int, int]:
    from sqlalchemy import select

    from app.core.database import SessionLocal, init_db
    from app.models.mock import BankQuestion
    from app.services.question_bank import fingerprint

    init_db()
    questions = load(workdir(pdf) / "questions.json", [])
    solved = load(workdir(pdf) / "solved.json", {})
    review = []
    added = 0
    with SessionLocal() as db:
        known = set(db.scalars(select(BankQuestion.fingerprint)))
        for q in questions:
            s = solved.get(f"{q['page']}:{q['n']}:{q['text'][:40]}")
            if not s or s.get("status") in ("skipped", "retry"):
                continue  # not for students (multi-answer, needs a figure) / not solved yet: the next run picks it up
            if s["status"] != "ok" or not s.get("chapter"):
                review.append({**q, **s})
                continue
            text = md_tables((f"{q['passage']}\n\n" if q.get("passage") else "") + q["text"])
            fp = fingerprint(text)
            if fp in known:
                continue
            if s["qtype"] == "mcq":
                answer = str(int(float(q.get("key") or s["answer"])) - 1)
            else:
                answer = str(q.get("key") or s["answer"])
            db.add(BankQuestion(exam=q["exam"], subject=s["subject"], chapter=s["chapter"], qtype=s["qtype"],
                                difficulty=s["difficulty"], question=text,
                                options=[md_tables(o) for o in q["options"]] if s["qtype"] == "mcq" else None,
                                answer=answer, solution=s["solution"], verified=True, source=q.get("source") or "pyq",
                                fingerprint=fp, year=q.get("year"), paper=q.get("paper")))
            known.add(fp)
            added += 1
        db.commit()
    save(workdir(pdf) / "review.json", review)
    log.info("store %s: %d new questions in the bank, %d set aside for review", pdf.name, added, len(review))
    return added, len(review)


def background() -> None:
    """Run at the lowest priority: an import may run while a student watches a lecture on the same laptop."""
    try:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)  # IDLE_PRIORITY_CLASS
        else:
            os.nice(19)
    except Exception:  # noqa: BLE001 - priority is a courtesy, never a reason to stop
        pass


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=("all", "scan", "read", "build", "solve", "reread", "store"), default="all")
    ap.add_argument("--file", help="only PDFs whose name contains this")
    ap.add_argument("--ocr-workers", type=int, default=3)
    ap.add_argument("--read-workers", type=int, default=4)
    ap.add_argument("--solve-workers", type=int, default=2)
    ap.add_argument("--reserve", type=int, default=450,
                    help="Groq requests a day kept for students (free tier: 1,000); solving waits below it")
    ap.add_argument("--no-scan", action="store_true",
                    help="read only pages the scan has already found (while scan_pyq_gpu.py is still running)")
    ap.add_argument("--pages", help="read just these pages (0-based), e.g. 298-309, skipping the scan (for trials)")
    args = ap.parse_args()
    background()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    for name in ("httpx", "focs.llm", "focs.ocr"):
        logging.getLogger(name).setLevel(logging.WARNING)
    files = pdfs(args.file)
    if not files:
        sys.exit(f"No PDFs found in {ROOT}")
    from app.core.database import init_db
    init_db()  # the bank's tables (and the cost ledger's) exist before anything is written
    for pdf in files:
        log.info("=== %s", pdf.name)
        if args.pages and args.stage in ("all", "read"):
            a, _, b = args.pages.partition("-")
            read(pdf, list(range(int(a), int(b or a) + 1)), args.read_workers)
        elif args.stage in ("all", "scan", "read"):
            result = load(workdir(pdf) / "scan.json", {}) if args.no_scan else scan(pdf, args.ocr_workers)
            pages = candidates(result)
            log.info("%s: %d of %d pages carry tagged questions or keys", pdf.name, len(pages), len(result))
            if args.stage in ("all", "read"):
                read(pdf, pages, args.read_workers)
        if args.stage in ("all", "build"):
            build(pdf)
        if args.stage in ("all", "solve"):
            solve_paced(pdf, args.solve_workers, args.reserve)
        if args.stage in ("all", "reread") and reread(pdf, args.read_workers):
            build(pdf)
            solve_paced(pdf, args.solve_workers, args.reserve)
        if args.stage in ("all", "store"):
            store(pdf)
    try:
        from app.services import ledger
        ledger.flush()
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
