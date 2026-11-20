"""Import SSC CGL previous-year papers (PDFs) into the question bank, figures and Hindi included. Free: no paid API.

    python scripts/import_ssc.py --src "<folder of PDFs>"            # every stage, resumable
    python scripts/import_ssc.py --src ... --stage extract --file 1772  # one stage / some PDFs
    python scripts/import_ssc.py --src ... --report                     # what each PDF gave, so far
    python scripts/import_ssc.py --src ... --stage check --remote <url> --key <k> --workers 48 --live
        # check on a rented/free GPU (scripts/kaggle_vllm.ipynb), 100 at a time, each 100 stored as it finishes

The PDFs are the papers SSC publishes (response sheets with the right option ticked), coaching-site copies of them
and memory-based papers. A coaching site's own explanations are never copied: only the question, its options and the
answer. Every question gets our own solution, and its answer is checked by solving it again before students see it.

Stages (each saves its work under data/ssc/.work/<pdf>/, so re-running never repeats work):
  extract  the PDF's text layer, read by code (scripts/ssc_extract.py): one question per marker, its options, the
           answer the paper prints or ticks, the Hindi copy, its figures cut out (watermark cleaned)
  read     the questions the text layer doesn't give whole (maths printed as pictures, an option missing) are read
           from a picture of them by a local vision model (Ollama, qwen2.5vl)
  check    a local model (Ollama, qwen3) solves each question, files it under a syllabus chapter and topic and writes
           our solution; when it disagrees with the paper's answer it thinks again, and a Maths or Reasoning question
           it still disagrees on goes to review.json instead of the bank. General Awareness and English keep the paper's
           answer (a small model's general knowledge is less reliable than the exam's key)
  store    add the checked questions to the bank (a question already there, from any paper, is skipped); figures are
           copied to frontend/public/q/ssc/ so the site serves them

Duplicate PDFs (the same file downloaded twice) are read once, and a question in several PDFs is checked once.
Needs Ollama running with qwen3:8b and qwen2.5vl:3b pulled. Keep the laptop on charge; it can be stopped any time.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402
import pymupdf  # noqa: E402

import ssc_extract  # noqa: E402
from app.services.llm import LLMUnavailable, parse_json  # noqa: E402

ROOT = BACKEND.parent / "data" / "ssc"
WORK = ROOT / ".work"
FIGURES = BACKEND.parent / "frontend" / "public" / "q" / "ssc"
FIGURE_URL = "/q/ssc/"
OLLAMA = "http://localhost:11434"
CHECK_MODEL = "qwen3:8b"
VISION_MODEL = "qwen2.5vl:3b"
CROP_DPI = 200
log = logging.getLogger("ssc")

# what a paper's section heading says → the syllabus subject
SECTIONS = [(re.compile(r"reason|intelligence", re.I), "General Intelligence and Reasoning"),
            (re.compile(r"quant|math|arithmetic", re.I), "Quantitative Aptitude"),
            (re.compile(r"english", re.I), "English Comprehension"),
            (re.compile(r"awareness|general knowledge|\bgk\b|general studies", re.I), "General Awareness"),
            (re.compile(r"computer", re.I), "Computer Knowledge")]
KNOWLEDGE = ("General Awareness", "English Comprehension", "Computer Knowledge")  # the key outranks a small model here
NEEDS_FIGURE = re.compile(r"\b(given|following|below|above|this)\s+(figure|diagram|venn diagram|graph|bar graph|pie chart|"
                          r"chart|dice|cube|image)\b|\bfigure (given|below|above|shown)\b|\bmirror image\b|"
                          r"\bpaper is folded\b|\bshown in the (figure|diagram)\b", re.I)


def unique_pdfs(src: Path, name_filter: str | None) -> list[Path]:
    """Every PDF under src once: a second download of the same file is skipped by its content hash."""
    seen: set[str] = set()
    out = []
    for f in sorted(src.rglob("*.pdf")):
        md5 = hashlib.md5()
        with f.open("rb") as fh:  # in pieces: the whole file at once ran out of memory on a busy laptop
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                md5.update(chunk)
        h = md5.hexdigest()
        if h in seen:
            continue
        seen.add(h)
        if not name_filter or name_filter.lower() in f.name.lower():
            out.append(f)
    return out


def workdir(pdf: Path) -> Path:
    d = WORK / re.sub(r"[^\w.-]+", "_", pdf.stem)
    d.mkdir(parents=True, exist_ok=True)
    return d


def load(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path: Path, data: Any) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def keep_awake() -> None:
    """Hold off Windows sleep while the import runs (the screen may still turn off)."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED


# ---------------------------------------------------------------- the paper a question is from
MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


def parse_paper(title: str | None) -> dict | None:
    """"SSC CGL Tier-I 14 Jul 2023 Shift 1" → {"year": 2023, "paper": "SSC CGL 2023 Tier-I (14 Jul, Shift 1)", ...}.
    A "similar-based" or "practice" paper is not a past paper: its questions are practice ones."""
    if not title:
        return None
    t = " ".join(title.split())
    low = t.lower()
    similar = "similar" in low or "practice" in low or "mock" in low
    m = re.search(r"(\d{1,2})[\s\-/_.]*(?:th|st|nd|rd)?[\s\-/_.]*([A-Za-z]{3,9}|\d{1,2})[\s,\-/_.]*((?:19|20)\d\d)", t)
    day = month = None
    if m:
        mon = m.group(2).lower()[:3]
        month = MONTHS.get(mon) or (int(m.group(2)) if m.group(2).isdigit() and 1 <= int(m.group(2)) <= 12 else None)
        day = int(m.group(1)) if month else None
        year = int(m.group(3))
    else:
        y = re.search(r"(?:19|20)\d\d", t)
        if not y:
            return None
        year = int(y.group(0))
    tier = "Tier-II" if re.search(r"tier[\s\-]*(ii|2)\b", low) else "Tier-I" if re.search(r"tier[\s\-]*(i|1)\b", low) else None
    shift = re.search(r"shift[\s\-:]*(\d)", low)
    if not shift:  # official response sheets print the start time instead
        hour = re.search(r"\b(\d{1,2}):\d\d\s*(am|pm)", low)
        if hour:
            h = int(hour.group(1)) % 12 + (12 if hour.group(2) == "pm" else 0)
            shift = re.match(r"(\d)", "1" if h < 11 else "2" if h < 14 else "3")
    exam = "SSC CHSL" if "chsl" in low else "SSC CGL"
    when = ", ".join(x for x in (f"{day} {list(MONTHS)[month - 1].title()}" if day and month else None,
                                 f"Shift {shift.group(1)}" if shift else None) if x)
    name = " ".join(x for x in (exam, str(year), tier) if x) + (f" ({when})" if when else "")
    return {"year": year, "paper": name, "similar": similar, "exam": exam, "memory": "memory" in low}


# ---------------------------------------------------------------- figures
def _clean_figure(img):
    """A cropped figure on white: coaching-site watermarks (pale cyan/blue) and light page noise removed."""
    import numpy as np
    from PIL import Image
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    # the watermark is a pale tint; a figure drawn in a strong colour (Testbook draws in cyan) stays
    white = ((b - r > 25) & (g - r > 10) & (r > 140)) | (a.min(axis=2) > 215)
    a[white] = 255
    gray = np.asarray(Image.fromarray(a.astype(np.uint8)).convert("L")).astype(np.int16)
    gray = np.where(gray < 235, np.clip(gray * 0.55, 0, 255), 255)  # coloured lines turn dark grey, readable
    gray = Image.fromarray(gray.astype(np.uint8))
    box = Image.eval(gray, lambda v: 255 - v).getbbox()  # trim the white margin
    return gray.crop(box) if box else gray


def _dhash(img) -> str:
    small = img.convert("L").resize((9, 8))
    px = list(small.tobytes())
    bits = "".join("1" if px[r * 9 + c] > px[r * 9 + c + 1] else "0" for r in range(8) for c in range(8))
    return f"{int(bits, 2):016x}"


def _render(doc: pymupdf.Document, page: int, clip: tuple[float, float, float, float], dpi: int = CROP_DPI):
    from PIL import Image
    pix = doc[page].get_pixmap(dpi=dpi, clip=pymupdf.Rect(*clip))
    return Image.open(io.BytesIO(pix.tobytes("png")))


def crop(doc: pymupdf.Document, page: int, box: tuple) -> dict | None:
    """Cut a picture out of a page into a webp; returns {"file", "hash"} (hash: compares figures across papers)."""
    x0, y0, x1, y1 = box
    c = _clean_figure(_render(doc, page, (x0 - 1, y0 - 1, x1 + 1, y1 + 1)))
    if c.size[0] < 16 or c.size[1] < 16:
        return None
    buf = io.BytesIO()
    c.save(buf, "WEBP", quality=80, method=6)
    data = buf.getvalue()
    name = hashlib.sha1(data).hexdigest()[:16] + ".webp"
    figdir = WORK / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    (figdir / name).write_bytes(data)
    return {"file": name, "hash": _dhash(c)}


def region_picture(doc: pymupdf.Document, r: ssc_extract.Region) -> bytes:
    """The whole question as one picture (its part of each page it runs over, stacked), for the vision model."""
    from PIL import Image
    parts = []
    pages = sorted({ln.page for ln in r.lines})
    for p in pages:
        mine = [ln for ln in r.lines if ln.page == p]
        pics = [x for x in r.pictures if x.page == p]
        y0 = min([ln.box[1] for ln in mine] + [x.box[1] for x in pics]) - 6
        y1 = max([ln.box[3] for ln in mine] + [x.box[3] for x in pics]) + 6
        w = doc[p].rect.width
        parts.append(_render(doc, p, (0, max(0, y0), w, y1), dpi=130).convert("L"))
    width = max(im.size[0] for im in parts)
    out = Image.new("L", (width, sum(im.size[1] for im in parts)), 255)
    y = 0
    for im in parts:
        out.paste(im, (0, y))
        y += im.size[1]
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


def _option_band(r: ssc_extract.Region, p: ssc_extract.Picture) -> int | None:
    """Which option a picture is (options given as pictures): the option whose number is level with the picture's
    middle (a response sheet prints the number halfway down the picture), with the picture to its right."""
    opts = ssc_extract.option_lines(r)
    if len(opts) != 4:
        return None
    mid = (p.box[1] + p.box[3]) / 2
    near = [(abs((ln.box[1] + ln.box[3]) / 2 - mid), k) for k, ln in enumerate(opts)
            if ln.page == p.page and p.box[0] >= ln.box[0] - 5]
    if not near:
        return None
    dist, k = min(near)
    return k if dist <= (p.box[3] - p.box[1]) / 2 + 10 else None


# ---------------------------------------------------------------- extract
def fp(q: dict) -> str:
    """Same question, same fingerprint, whichever paper or PDF it came from: its words, options and figures."""
    figs = [f["hash"] for f in q.get("figures") or []] + [f["hash"] for f in q.get("option_figures") or [] if f]
    words = re.sub(r"[^a-z0-9]", "", (q["text"] + "|" + "|".join(q["options"])).lower())
    return hashlib.sha1((words[:600] + "|" + ",".join(figs)).encode()).hexdigest()


def extract(pdf: Path) -> list[dict]:
    path = workdir(pdf) / "questions.json"
    if path.exists():
        return load(path, [])
    doc = pymupdf.open(pdf)
    regions = ssc_extract.regions(doc)
    out: list[dict] = []
    pics_dir = workdir(pdf) / "pictures"
    for i, r in enumerate(regions):
        q = ssc_extract.parse(r)
        tick = ssc_extract.ticked(r)
        how = "printed" if q["answer"] is not None else "tick" if tick is not None else None
        if q["answer"] is None:
            q["answer"] = tick
        figures, option_figures = [], [None] * 4
        for p in r.pictures:
            if p.small:
                continue
            k = _option_band(r, p)
            f = crop(doc, p.page, p.box)
            if f is None:
                continue
            if k is not None and option_figures[k] is None:
                option_figures[k] = f
            else:
                figures.append(f)
        if not any(option_figures):
            option_figures = []
        elif not all(option_figures):  # some options pictures, some not: keep them as the question's figures
            figures += [f for f in option_figures if f]
            option_figures = []
        if option_figures and not all(q["options"]):
            q["options"] = [o or "" for o in q["options"]]
            q["ok"] = q["ok"] or bool(q["text"])
        if not figures and not option_figures and NEEDS_FIGURE.search(q["text"]):
            q["ok"], q["lost_figure"] = False, True  # its figure was drawn, not a picture: not usable without it
        item = {"pdf": pdf.name, "i": i, **q, "answer_from": how, "figures": figures, "option_figures": option_figures,
                **({"paper_info": info} if (info := parse_paper(q["paper"])) else {})}
        if not item["ok"]:  # read again from its picture
            pics_dir.mkdir(exist_ok=True)
            (pics_dir / f"{i:05d}.png").write_bytes(region_picture(doc, r))
        out.append(item)
    for q in out:
        q["fp"] = fp(q)
    save(path, out)
    log.info("extract %s: %d questions, %d whole from the text, %d with the paper's answer, %d with figures, %d Hindi",
             pdf.name, len(out), sum(q["ok"] for q in out), sum(q["answer"] is not None for q in out),
             sum(bool(q["figures"] or q["option_figures"]) for q in out), sum(bool(q["text_hi"]) for q in out))
    return out


# ---------------------------------------------------------------- local models
REMOTE: dict[str, str] = {}  # --remote: an OpenAI-compatible vLLM server serving Qwen3-8B (see scripts/kaggle_vllm.ipynb)


def remote(prompt: str, think: bool, tokens: int) -> dict:
    """The same check on the remote server: the same model and prompt, the answer parsed the same way."""
    body = {"model": REMOTE["model"], "messages": [{"role": "user", "content": prompt}], "temperature": 0, "stream": True,
            # thinking needs room (4000 ran out on easy ones), but a long answer through the tunnel is the one that drops
            "max_tokens": tokens,
            "chat_template_kwargs": {"enable_thinking": think}}
    headers = {"Authorization": f"Bearer {REMOTE['key']}"}
    bad = 0
    for attempt in range(8):
        try:
            # streamed: a quick tunnel cuts a request that sends nothing for 100 s (Cloudflare 524), and a thinking
            # answer under load takes longer than that
            parts, finish = [], None
            with httpx.stream("POST", f"{REMOTE['url']}/v1/chat/completions", json=body, headers=headers,
                              timeout=httpx.Timeout(900, read=300)) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    for ch in json.loads(line[6:]).get("choices") or []:
                        parts.append((ch.get("delta") or {}).get("content") or "")
                        finish = ch.get("finish_reason") or finish
            text = re.sub(r"<think>.*?</think>", "", "".join(parts), flags=re.S)
            if think and finish == "length" and not text.strip():
                # it thought until the budget ran out: take its answer without the thinking instead of nothing
                body["chat_template_kwargs"] = {"enable_thinking": False}
                body["max_tokens"] = 1500
                think = False
                continue
            return parse_json(text)
        except (ValueError, LLMUnavailable) as exc:
            bad += 1
            if bad >= 3:
                break
            log.warning("remote: %s, retrying", str(exc)[:200])
            # the same prompt at temperature 0 breaks the JSON the same way again: vary it, and without thinking
            # make the server hold the answer to valid JSON
            body["temperature"] = 0.4
            if not think:
                body["response_format"] = {"type": "json_object"}
        except httpx.HTTPError as exc:  # the tunnel blinked or the server is restarting
            log.warning("remote: %s, retrying", str(exc)[:200])
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("the remote model gave no usable answer")


def ollama(model: str, prompt: str, images: list[bytes] | None = None, think: bool = False, tokens: int = 1500) -> dict:
    """One JSON answer from a local Ollama model; waits for Ollama to come back if it was restarted."""
    if REMOTE and model == CHECK_MODEL and not images:
        return remote(prompt, think, tokens)
    msg: dict[str, Any] = {"role": "user", "content": prompt}
    if images:
        msg["images"] = [base64.b64encode(i).decode() for i in images]
    body = {"model": model, "messages": [msg], "stream": False, "format": "json", "think": think,
            "options": {"temperature": 0, "num_ctx": 6144, "num_predict": tokens}, "keep_alive": "30m"}
    bad_json = 0
    for attempt in range(6):
        try:
            r = httpx.post(f"{OLLAMA}/api/chat", json=body, timeout=900)
            if r.status_code == 400 and "think" in r.text and "think" in body:
                body.pop("think")  # a model without a thinking mode
                continue
            r.raise_for_status()
            text = r.json()["message"]["content"]
            if body.get("think") and r.json().get("done_reason") == "length" and not text.strip():
                body["think"] = False  # thought until the budget ran out: its answer without the thinking
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return parse_json(text)
        except (ValueError, LLMUnavailable, httpx.HTTPStatusError) as exc:
            # Ollama answered, but not JSON (a 500 here is its JSON grammar failing on this input): one more try is enough
            bad_json += 1
            if bad_json >= 2:
                break
            log.warning("%s: %s, retrying", model, str(exc)[:200])
        except httpx.HTTPError as exc:  # Ollama down or restarting: wait for it
            log.warning("%s: %s, retrying", model, str(exc)[:200])
            time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"Ollama ({model}) gave no usable answer")


READ_PROMPT = """This picture is one question from an Indian SSC exam paper, with its four options. Transcribe it.
Text found in the PDF for it (pieces may be missing where the paper printed maths or symbols as pictures):
---
{hint}
---
Return ONLY JSON: {{"question": "the full English question", "options": ["opt 1", "opt 2", "opt 3", "opt 4"]}}
Write maths in LaTeX inside $...$ ($\\frac{{3}}{{8}}$, $\\sqrt{{3}}$, $x^2$, $\\theta$). Ignore Hindi text, ticks, crosses,
"Ans", "Question ID", "Status", "Chosen Option". If an option is a picture with no text, give "" for it."""


def read(pdf: Path) -> None:
    """The questions the text layer didn't give whole, read from their pictures by the local vision model."""
    path = workdir(pdf) / "questions.json"
    questions = load(path, [])
    todo = [q for q in questions if not q["ok"] and not q.get("read") and not q.get("lost_figure")]
    log.info("read %s: %d questions to read from their pictures", pdf.name, len(todo))
    for n, q in enumerate(todo, 1):
        pic = workdir(pdf) / "pictures" / f"{q['i']:05d}.png"
        if not pic.exists():
            q["read"] = "no picture"
            continue
        hint = q["text"] + "\n" + "\n".join(f"{k + 1}. {o}" for k, o in enumerate(q["options"]))
        try:
            got = ollama(VISION_MODEL, READ_PROMPT.format(hint=hint[:1500]), [pic.read_bytes()], tokens=900)
        except RuntimeError as exc:  # one unreadable picture shouldn't stop the run; retried next time
            log.warning("read failed: %s", exc)
            continue
        opts = got.get("options")
        if isinstance(got.get("question"), str) and isinstance(opts, list) and len(opts) == 4:
            q["text"] = got["question"].strip() or q["text"]
            q["options"] = [str(o).strip() for o in opts]
            q["ok"] = bool(q["text"]) and (all(q["options"]) or bool(q["option_figures"]))
        q["read"] = "vision"
        q["fp"] = fp(q)
        if n % 10 == 0:
            save(path, questions)
            log.info("  read %d/%d", n, len(todo))
    save(path, questions)


# ---------------------------------------------------------------- check
CHECK_PROMPT = """You are an SSC CGL teacher checking a previous-year question before it goes to students.

{question}

Syllabus chapters and topics for this question's subject:
{syllabus}

Do this:
1. "work": solve it yourself, briefly and step by step (do not trust any answer you may know from the paper).
2. "answer": the 0-based index (0-3) of the correct option by your working.
3. "usable": false only if the question is garbled, incomplete, or has no correct option.
4. "chapter" and "topic": from the syllabus above, copied exactly.
5. "difficulty": easy, medium or hard (for an SSC candidate).
6. "solution": a short explanation for students, 2-5 lines, built from your working (every step you state must be
   true for this question: check it against the options), the quick SSC method if there is one. Maths in LaTeX
   inside $...$; money as ₹ in plain text.
Return ONLY JSON: {{"work": "...", "answer": 0, "usable": true, "subject": "{subject}", "chapter": "...",
"topic": "...", "difficulty": "medium", "solution": "..."}}"""

FIGURE_PROMPT = """You are an SSC CGL teacher filing a previous-year {subject} question that needs a figure, table or
graph (not shown to you). Its answer is option {key} (0-based).

{question}

Syllabus chapters and topics (the chapter and topic must be copied exactly from this list):
{syllabus}

Return ONLY JSON: {{"subject": "{subject}", "chapter": "...", "topic": "...", "difficulty": "easy|medium|hard",
"solution": "1-3 lines on how to see the answer, for a student looking at the figure"}}"""


def _subject_of(q: dict) -> str | None:
    sec = q.get("section") or ""
    return next((s for rx, s in SECTIONS if rx.search(sec)), None)


def _syllabus(subject: str | None) -> tuple[str, dict]:
    from app.services import syllabus
    syl = syllabus.get("ssc_cgl")
    chapters = [c for c in syl.chapters if subject is None or c.subject == subject]
    text = "\n".join(f"- [{c.subject}] {c.name}: {', '.join(t.name for t in c.topics)}" for c in chapters)
    return text, {(c.subject, c.name): c for c in syl.chapters}


def _show(q: dict) -> str:
    opts = "\n".join(f"({k}) {o or '[a picture]'}" for k, o in enumerate(q["options"]))
    return f"Question: {q['text']}\nOptions:\n{opts}"


def _chapter(r: dict, index: dict, subject: str | None) -> tuple[str, str, str | None] | None:
    """(subject, chapter, topic) from a model's answer, matched to the syllabus (case and spacing forgiven)."""
    norm = lambda s: re.sub(r"[^a-z]", "", str(s or "").lower())  # noqa: E731
    want = norm(r.get("chapter"))
    hits = [k for k in index if norm(k[1]) == want and (subject is None or k[0] == subject)]
    if not hits:
        hits = [k for k in index if want and (want in norm(k[1]) or norm(k[1]) in want) and (subject is None or k[0] == subject)]
    if not hits and r.get("topic") and r.get("topic") != r.get("chapter"):
        # a small model often writes one level up: the subject as the chapter and the chapter as the topic
        shifted = _chapter({"chapter": r["topic"], "topic": None}, index, subject)
        if shifted:
            return shifted
        want_t = norm(r["topic"])  # or the right topic under a wrong chapter name: the chapter that has it
        for k, c in index.items():
            if subject in (None, k[0]):
                for t in c.topics:
                    if norm(t.name) == want_t:
                        return k[0], k[1], t.name
    if not hits:
        return None
    subj, chap = hits[0]
    topics = {norm(t.name): t.name for t in index[hits[0]].topics}
    return subj, chap, topics.get(norm(r.get("topic")))


def check(pdf: Path, seen: dict, live: list[Path] | None = None) -> None:
    """Solve, file and explain every question of a PDF. ``seen``: fingerprint → the PDF that has it first (a
    question repeated in another PDF is checked there only)."""
    questions = load(workdir(pdf) / "questions.json", [])
    path = workdir(pdf) / "checked.json"
    done: dict[str, dict] = load(path, {})
    for q in questions:
        seen.setdefault(q["fp"], pdf.name)
    todo = [q for q in questions if q["ok"] and q["fp"] not in done and seen[q["fp"]] == pdf.name]
    log.info("check %s: %d of %d questions to go", pdf.name, len(todo), len(questions))
    for n, q in enumerate(todo, 1):
        try:
            done[q["fp"]] = _check_one(q)
        except Exception as exc:  # noqa: BLE001 - one question shouldn't stop the paper
            log.warning("check failed: %s", exc)
        if n % 10 == 0:
            save(path, done)
            stats: dict[str, int] = {}
            for v in done.values():
                stats[v["status"]] = stats.get(v["status"], 0) + 1
            log.info("  checked %d/%d %s", n, len(todo), stats)
        if live and n % 100 == 0:  # --live: every 100 checked go into the bank straight away
            try:
                store(live)
            except Exception:  # noqa: BLE001 - the database being away shouldn't stop the checking
                log.exception("store failed; tried again after the next 100")
    save(path, done)
    if live and todo:
        store(live)


def share(files: list[Path], spec: str) -> list[Path]:
    """The PDFs in shares ``a-b/n`` of n, dealt so each share gets about the same number of questions."""
    rng, n = spec.split("/")
    a, _, b = rng.partition("-")
    want = set(range(int(a), int(b or a) + 1))
    sizes = sorted(((len(load(workdir(f) / "questions.json", [])), f) for f in files), key=lambda x: -x[0])
    loads, owner = [0] * int(n), {}
    for size, f in sizes:  # biggest first, each to the lightest share
        k = loads.index(min(loads))
        loads[k] += size
        owner[f] = k + 1
    return [f for f in files if owner[f] in want]


def check_batches(files: list[Path], seen: dict, workers: int, size: int, live: bool) -> None:
    """The check stage on the remote server: every PDF's questions in batches, ``workers`` at a time. Each batch is
    saved when it finishes and, with ``live``, goes into the bank straight away, so students see questions while the
    rest are still being checked."""
    from concurrent.futures import ThreadPoolExecutor

    done = {pdf: load(workdir(pdf) / "checked.json", {}) for pdf in files}
    todo = [(pdf, q) for pdf in files for q in load(workdir(pdf) / "questions.json", [])
            if q["ok"] and q["fp"] not in done[pdf] and seen.get(q["fp"]) == pdf.name]
    log.info("check (remote, %d at a time): %d questions in %d batches", workers, len(todo), -(-len(todo) // size))

    def one(item):
        try:
            return item, _check_one(item[1])
        except Exception as exc:  # noqa: BLE001 - one question shouldn't stop the batch
            log.warning("check failed: %s", exc)
            return item, None

    # always ``workers`` in flight (a batch no longer waits for its slowest question with the GPU idle); every
    # ``size`` answers are saved and, with ``live``, stored
    from concurrent.futures import as_completed

    start, stats, n, touched = time.time(), {}, 0, set()
    with ThreadPoolExecutor(workers) as pool:
        for fut in as_completed([pool.submit(one, item) for item in todo]):
            (pdf, q), res = fut.result()
            n += 1
            if res is not None:
                done[pdf][q["fp"]] = res
                touched.add(pdf)
                stats[res["status"]] = stats.get(res["status"], 0) + 1
            if n % size == 0 or n == len(todo):
                for p in touched:
                    save(workdir(p) / "checked.json", done[p])
                touched.clear()
                log.info("batch %d/%d: %s in %.0f s", -(-n // size), -(-len(todo) // size), stats, time.time() - start)
                start, stats = time.time(), {}
                if live:
                    try:
                        store(files)
                    except Exception:  # noqa: BLE001 - the database being away shouldn't stop the checking
                        log.exception("store failed; the next batch tries again")


def _check_one(q: dict) -> dict:
    subject = _subject_of(q)
    sylt, index = _syllabus(subject)
    key = q["answer"]
    if q["figures"] or q["option_figures"]:  # the model can't see the figure: file it, the paper's key stands
        if key is None:
            return {"status": "dropped", "why": "a figure question without the paper's answer"}
        r = ollama(CHECK_MODEL, FIGURE_PROMPT.format(key=key, question=_show(q), syllabus=sylt,
                                                   subject=subject or "SSC CGL"), tokens=500)
        place = _chapter(r, index, subject)
        if place is None:
            return {"status": "review", "why": "no chapter"}
        return {"status": "ok", "how": "key", "answer": key, "subject": place[0], "chapter": place[1], "topic": place[2],
                "difficulty": r.get("difficulty") or "medium", "solution": r.get("solution") or ""}
    prompt = CHECK_PROMPT.format(question=_show(q), syllabus=sylt, subject=subject or "the subject it belongs to")
    r = ollama(CHECK_MODEL, prompt, tokens=1200)
    place = _chapter(r, index, subject)
    if place is None:  # a wrong chapter name: once more
        r = ollama(CHECK_MODEL, prompt, tokens=1200)
        place = _chapter(r, index, subject)
        if place is None:
            return {"status": "review", "why": "no chapter"}
    out = {"subject": place[0], "chapter": place[1], "topic": place[2], "difficulty": r.get("difficulty") or "medium",
           "solution": r.get("solution") or ""}
    mine = r.get("answer")
    if r.get("usable") is False and key is None:
        return {"status": "dropped", "why": "the checker found it unusable"}
    if key is not None and mine == key:
        return {**out, "status": "ok", "how": "agreed", "answer": key}
    if key is not None and place[0] in KNOWLEDGE:
        return {**out, "status": "ok", "how": "key", "answer": key}  # the exam's key stands anyway: no second pass
    # disagreement, or no key: think it through
    t = ollama(CHECK_MODEL, prompt, think=True, tokens=2500)  # a short think: a long one costs a T4 minutes
    second = t.get("answer")
    if key is None:
        if second == mine and isinstance(mine, int) and 0 <= mine <= 3:
            return {**out, "status": "ok", "how": "solved", "answer": mine}
        return {**out, "status": "review", "why": "no key and the checks disagree", "answer": second}
    if second == key:
        return {**out, "status": "ok", "how": "agreed", "answer": key, "solution": t.get("solution") or out["solution"]}
    if place[0] in KNOWLEDGE:
        return {**out, "status": "ok", "how": "key", "answer": key}  # facts and usage: the exam's key
    return {**out, "status": "review", "why": f"the paper says {key}, the checker says {second}", "answer": key,
            "checker": second, "checker_solution": t.get("solution")}


# ---------------------------------------------------------------- store
def _no_nul(x):
    """Postgres text can't hold a NUL byte, and some PDFs leave one in the text."""
    if isinstance(x, str):
        return x.replace("\x00", "")
    if isinstance(x, list):
        return [_no_nul(i) for i in x]
    if isinstance(x, dict):
        return {k: _no_nul(v) for k, v in x.items()}
    return x


def store(pdfs_: list[Path]) -> None:
    """Every checked question into the bank, once; figures into the site's public folder; the rest listed in
    data/ssc/review.json for a person to look at."""
    import shutil

    from sqlalchemy import select

    from app.core.database import SessionLocal, init_db
    from app.models.mock import BankQuestion
    from app.services.math_text import clean_option

    init_db()
    FIGURES.mkdir(parents=True, exist_ok=True)
    checked: dict[str, dict] = {}
    for other in WORK.glob("*/checked.json"):  # a repeat is checked where it was first seen
        checked.update(load(other, {}))
    added = skipped = 0
    review = []
    with SessionLocal() as db:
        known = set(db.scalars(select(BankQuestion.fingerprint)))
        for pdf in pdfs_:
            for q in load(workdir(pdf) / "questions.json", []):
                c = checked.get(q["fp"])
                if not c:
                    continue
                if c["status"] == "review":
                    review.append({"pdf": q["pdf"], "paper": q.get("paper"), "question": q["text"], "options": q["options"],
                                   "figures": [f["file"] for f in q["figures"]], **c})
                    continue
                if c["status"] != "ok":
                    continue
                if q["fp"] in known:
                    skipped += 1
                    continue
                for f in q["figures"] + [f for f in q["option_figures"] if f]:
                    target = FIGURES / f["file"]
                    if not target.exists():
                        shutil.copyfile(WORK / "figures" / f["file"], target)
                media = None
                if q["figures"] or q["option_figures"]:
                    media = {"figures": [FIGURE_URL + f["file"] for f in q["figures"]],
                             "options": [FIGURE_URL + f["file"] if f else None for f in q["option_figures"]] or None}
                hindi = None
                if q.get("text_hi"):
                    hindi = {"question": q["text_hi"], "options": q["options_hi"] if q.get("options_hi") and len(q["options_hi"]) == 4 else None}
                info = q.get("paper_info") or {}
                past = bool(info) and not info.get("similar") and info.get("exam") == "SSC CGL"
                db.add(BankQuestion(
                    exam="ssc_cgl", subject=c["subject"], chapter=c["chapter"], topic=c.get("topic"), qtype="mcq",
                    difficulty=c["difficulty"], question=_no_nul(q["text"]), options=_no_nul([clean_option(o) for o in q["options"]]),
                    answer=str(c["answer"]), solution=_no_nul(c["solution"]), verified=True, source="pyq" if past else "practice",
                    year=info.get("year") if past else None,
                    paper=(info["paper"] + (" · memory-based" if info.get("memory") else "")) if past else None,
                    fingerprint=q["fp"], media=media, hindi=_no_nul(hindi)))
                known.add(q["fp"])
                added += 1
            db.commit()
    save(ROOT / "review.json", review)
    log.info("store: %d new questions in the bank, %d were already there, %d for review (data/ssc/review.json)",
             added, skipped, len(review))


def report(pdfs_: list[Path]) -> None:
    checked: dict[str, dict] = {}
    for other in WORK.glob("*/checked.json"):
        checked.update(load(other, {}))
    seen: set[str] = set()
    total: dict[str, int] = {}
    for pdf in pdfs_:
        qs = load(workdir(pdf) / "questions.json", [])
        row: dict[str, int] = {"questions": len(qs)}
        for q in qs:
            if q["fp"] in seen:
                row["repeat"] = row.get("repeat", 0) + 1
                continue
            seen.add(q["fp"])
            st = (checked.get(q["fp"]) or {}).get("status") or ("unreadable" if not q["ok"] else "to check")
            row[st] = row.get(st, 0) + 1
        for k, v in row.items():
            total[k] = total.get(k, 0) + v
        print(f"{pdf.name[:44]:44s} " + " ".join(f"{k}={v}" for k, v in row.items()))
    print("TOTAL " + " ".join(f"{k}={v}" for k, v in total.items()))


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="folder holding the SSC PDFs")
    ap.add_argument("--stage", choices=("all", "extract", "read", "check", "store"), default="all")
    ap.add_argument("--file", help="only PDFs whose name contains this")
    ap.add_argument("--report", action="store_true", help="print what each PDF gave so far, and stop")
    ap.add_argument("--remote", help="check on this OpenAI-compatible vLLM server instead of Ollama")
    ap.add_argument("--key", help="the remote server's API key")
    ap.add_argument("--model", default="Qwen/Qwen3-8B-AWQ", help="the remote server's model name")
    ap.add_argument("--workers", type=int, default=48, help="questions sent to the remote server at once")
    ap.add_argument("--batch", type=int, default=100, help="questions per batch (each batch saved, and stored with --live)")
    ap.add_argument("--share", help="check only this share of the PDFs, e.g. 1-1/5 (the first fifth) or 2-5/5 (the "
                    "other four): the laptop and a remote GPU can work side by side without touching the same PDF")
    ap.add_argument("--small", type=int, help="check only PDFs with at most this many questions (the laptop's part)")
    ap.add_argument("--big", type=int, help="check only PDFs with more than this many questions (the remote GPU's part)")
    ap.add_argument("--live", action="store_true", help="store each batch in the bank as soon as it is checked")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    for name in ("httpx", "focs.llm"):
        logging.getLogger(name).setLevel(logging.WARNING)
    pymupdf.TOOLS.mupdf_display_errors(False)  # some coaching PDFs miss a graphics-state resource on every page
    files = unique_pdfs(Path(args.src), args.file)
    if not files:
        sys.exit(f"No PDFs found in {args.src}")
    if args.report:
        report(files)
        return
    keep_awake()
    if args.stage in ("all", "extract"):
        for pdf in files:
            try:
                extract(pdf)
            except Exception:  # noqa: BLE001 - one broken PDF shouldn't stop the rest
                log.exception("extract %s failed", pdf.name)
    if args.stage in ("all", "read"):
        for pdf in files:
            read(pdf)
    if args.stage in ("all", "check"):
        seen: dict[str, str] = {}
        for pdf in unique_pdfs(Path(args.src), None):  # first-seen order over every PDF, whatever --file says
            for q in load(workdir(pdf) / "questions.json", []):
                seen.setdefault(q["fp"], pdf.name)
        if args.share:
            files = share(files, args.share)
        size = lambda f: len(load(workdir(f) / "questions.json", []))  # noqa: E731
        if args.small is not None:
            files = [f for f in files if size(f) <= args.small]
        if args.big is not None:
            files = [f for f in files if size(f) > args.big]
        if args.remote:
            REMOTE.update(url=args.remote.rstrip("/"), key=args.key or "", model=args.model)
            check_batches(files, seen, args.workers, args.batch, args.live)
        else:
            for pdf in files:
                check(pdf, seen, files if args.live else None)
    if args.stage in ("all", "store"):
        store(files)


if __name__ == "__main__":
    main()
