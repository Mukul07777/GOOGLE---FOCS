"""Read SSC papers' questions straight from the PDF's text layer (no AI): the first stage of import_ssc.py.

Every line of a page is taken with its position, lines at the same height are joined left to right (some coaching
PDFs store an option's number after its text), and the stream is cut into one region per question at the question
markers the PDF uses ("Q.12", "Que. 12", "QID : 12 -", "Question 12.", "12.From..."). A region keeps its lines and the
pictures that sit inside it; pictures decide the right option on an official response sheet (a green tick next to
it, a red cross next to the others) and are the figures of a reasoning question.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pymupdf

MARKERS = {
    "q": re.compile(r"^Q\.?\s?(\d{1,3})\.?(?=\s|$)"),          # official response sheets: "Q.12", "Q18."
    "que": re.compile(r"^Que\.\s?(\d{1,3})\b"),                 # Testbook: "Que. 12"
    "qid": re.compile(r"^QID\s*:\s*(\d{1,6})\s*-?"),            # "QID : 12 - From...", "QID : 30741 - In..."
    "question": re.compile(r"^Question\s?(\d{1,3})\.?"),        # "Question 18.I, II, III & IV..."
    "num": re.compile(r"^(\d{1,3})\.(?=[A-Za-z(\"'])"),         # "7.From the given options..."
}
# a paper's title: where one paper (shift) ends and the next begins
TITLE = re.compile(r"\bshift\b|held on|exam date|previous\s*year\s*paper|memory\s*based|similar[\s-]*based|"
                   r"combined graduate level|exam paper", re.I)
YEAR = re.compile(r"(?:19|20)\d\d")
NOISE = re.compile(r"testbook\.com|play\.google|link\.testbook|^https?://|^page\s*[-–:]?\s*\d+\s*$|unlock live|"
                   r"enroll|subscription|^useful links|click to print|^logout|adda247|^\s*$", re.I)
# lines a coaching PDF adds to a question that are not part of it
DROP = re.compile(r"^(question id|status|chosen option|candidate answer)\s*:|^options\s*:?$|^testbook solution\s*$", re.I)
# where a coaching site's own explanation starts: nothing after it is ours to copy
SOLUTION = re.compile(r"^(solution|sol\.|explanation|testbook solution)\b(?!.*correct option)", re.I)


@dataclass
class Line:
    page: int
    box: tuple[float, float, float, float]
    text: str


@dataclass
class Picture:
    page: int
    box: tuple[float, float, float, float]
    digest: str
    small: bool   # a tick, a cross or an inline symbol rather than a figure


@dataclass
class Region:
    n: str
    paper: str | None
    section: str | None = None
    lines: list[Line] = field(default_factory=list)
    pictures: list[Picture] = field(default_factory=list)


def page_lines(page: pymupdf.Page, pno: int) -> list[Line]:
    raw = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for ln in b["lines"]:
            t = "".join(s["text"] for s in ln["spans"]).replace(" ", " ").strip()
            if t and not NOISE.search(t):
                raw.append((tuple(ln["bbox"]), t))
    raw.sort(key=lambda r: (r[0][1], r[0][0]))
    out: list[Line] = []
    for box, t in raw:  # one line per height: pieces whose middles are within a few points join, left to right
        mid = (box[1] + box[3]) / 2
        if out and out[-1].page == pno and abs((out[-1].box[1] + out[-1].box[3]) / 2 - mid) < 3.5:
            prev = out[-1]
            parts = sorted([(prev.box, prev.text), (box, t)], key=lambda p: p[0][0])
            prev.text = " ".join(p[1] for p in parts)
            prev.box = (min(prev.box[0], box[0]), min(prev.box[1], box[1]), max(prev.box[2], box[2]), max(prev.box[3], box[3]))
            continue
        out.append(Line(pno, box, t))
    return out


def page_pictures(page: pymupdf.Page, pno: int) -> list[Picture]:
    area = page.rect.width * page.rect.height
    out = []
    try:
        infos = page.get_image_info(hashes=True)
    except Exception:  # noqa: BLE001 - a huge picture can't be decoded for its hash: tell pictures apart by xref
        infos = [{**i, "digest": f"xref{i.get('xref')}"} for i in page.get_image_info(xrefs=True)]
    for info in infos:
        r = pymupdf.Rect(info["bbox"])
        a = r.width * r.height
        if a <= 0 or a > 0.4 * area:  # a full-page banner or watermark
            continue
        out.append(Picture(pno, tuple(r), info.get("digest", b"").hex() if isinstance(info.get("digest"), bytes) else str(info.get("digest")),
                           a < 0.0012 * area))
    return out


def family(doc: pymupdf.Document) -> str:
    """Which question marker this PDF uses: the one that starts the most lines (a sample of pages is enough)."""
    counts = dict.fromkeys(MARKERS, 0)
    step = max(1, doc.page_count // 40)
    for pno in range(0, doc.page_count, step):
        for ln in page_lines(doc[pno], pno):
            for k, rx in MARKERS.items():
                if rx.match(ln.text):
                    counts[k] += 1
    return max(counts, key=counts.get)


def _title_at(lines: list[Line], i: int) -> str | None:
    """The paper title starting at line i, if there is one: a short line naming a shift or a date, a year nearby."""
    t = lines[i].text
    if len(t) > 90 or not TITLE.search(t) or re.search(r"correct (answer|option)", t, re.I):
        return None
    window = " ".join(ln.text for ln in lines[max(0, i - 2): i + 3])
    return window if YEAR.search(window) else None


def regions(doc: pymupdf.Document) -> list[Region]:
    fam = family(doc)
    # numbered questions ("7.From..."): a number alone on its line also starts one, its text on the next line
    marker = re.compile(r"^(\d{1,3})\.(?=[A-Za-z(\"']|$)") if fam == "num" else MARKERS[fam]
    lines: list[Line] = []
    pics: list[Picture] = []
    for pno in range(doc.page_count):
        lines += page_lines(doc[pno], pno)
        pics += page_pictures(doc[pno], pno)
    # a big picture printed on several pages is the site's banner, logo or watermark, not a question's figure (a
    # figure belongs to one question); ticks and crosses repeat and stay
    pages_of: dict[str, set[int]] = {}
    for p in pics:
        pages_of.setdefault(p.digest, set()).add(p.page)
    pics = [p for p in pics if p.small or len(pages_of[p.digest]) < 3]
    out: list[Region] = []
    # the PDF's own title until a paper title inside it says otherwise
    paper: str | None = next((t for i in range(min(len(lines), 25)) if (t := _title_at(lines, i))), None)
    cur: Region | None = None
    section: str | None = None
    in_solution = False
    for i, ln in enumerate(lines):
        title = _title_at(lines, i) if not marker.match(ln.text) else None
        if title:
            paper, cur, in_solution = title, None, False
            continue
        m = marker.match(ln.text)
        if m:
            n = m.group(1)
            if cur is not None and cur.n == n:  # the number printed again over the Hindi copy: same question
                rest = ln.text[m.end():].strip()
                if rest:
                    cur.lines.append(Line(ln.page, ln.box, rest))
                continue
            cur = Region(n, paper, section)
            out.append(cur)
            in_solution = False
            rest = ln.text[m.end():].strip(" .-:")
            cur.lines.append(Line(ln.page, ln.box, rest) if rest else Line(ln.page, ln.box, ""))
            continue
        sec = re.match(r"^section\s*:\s*(.+)$", ln.text, re.I)
        if sec:
            section = sec.group(1).strip()
            continue
        if cur is None:
            continue
        if SOLUTION.match(ln.text):
            in_solution = True
        if in_solution and not re.search(r"correct (option|answer)|^answer\b", ln.text, re.I):
            continue
        if DROP.match(ln.text) or re.match(r"^section\s*:", ln.text, re.I):
            continue
        cur.lines.append(ln)
    # each picture goes to the region it sits in: from the region's first line to the next region's first line
    out = [r for r in out if r.lines]
    starts = [(r.lines[0].page, r.lines[0].box[1] - 4) for r in out]
    import bisect
    for p in pics:
        pos = (p.page, (p.box[1] + p.box[3]) / 2)
        i = bisect.bisect_right(starts, pos) - 1
        if i >= 0:
            out[i].pictures.append(p)
    return [r for r in out if r.lines]


# ---------------------------------------------------------------- one region → a question
OPT = re.compile(r"^(?:ans\s+)?\(?([1-4]|[A-Da-d])[.)]\s*(.*)$", re.I)       # "1. 17", "1) NAMES", "(a) x", "Ans 1. QDS"
LABEL = re.compile(r"^\(?([1-6]|[A-Fa-f])[.)]\s*(.*)$")                     # an option or a list item
OPT_AFTER = re.compile(r"^(.*?)\s+([1-4])\.$")                                  # "JFN 3." (number printed after)
TWO_OPTS = re.compile(r"\s(?=[B-D]\)\s)")                                       # "A) 54.2 years B) 38.6 years"
KEY = [re.compile(r"correct option\s*[-:–]\s*([1-4])", re.I),
       re.compile(r"correct answer\s*[:\-]\s*(.+)$", re.I),
       re.compile(r"\banswer\s*\|+\s*([A-Da-d1-4])\b", re.I)]
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
# letters a broken Hindi font turns Devanagari into (Ǒ, ǒ, ǔ...) or scripts no SSC paper uses
GARBLED = re.compile(r"[Ā-ɏက-႟ᄀ-ᇿ㄰-㆏가-힯一-鿿-Ͱ-ϿЀ-ӿ]")


def _hindi(text: str) -> bool:
    return len(DEVANAGARI.findall(text)) > max(2, len(re.findall(r"[A-Za-z]", text)) // 2)


def _key(lines: list[str]) -> tuple[str | None, list[str]]:
    """The answer the paper prints ("Correct Option - 2", "Correct Answer: NAMES", "Answer ||| B") and the lines
    without it."""
    key, rest = None, []
    for t in lines:
        for rx in KEY:
            m = rx.search(t)
            if m:
                key = key or m.group(1).strip()
                t = (t[:m.start()] + t[m.end():]).strip() if rx is KEY[0] else t[:m.start()].strip()  # a solution may follow
                break
        if t:
            rest.append(t)
    return key, rest


def parse(r: Region) -> dict:
    """Question text, four options, the paper's answer and the Hindi version, as far as the text layer gives them.
    ``ok`` is False when it doesn't (an option missing or empty, maths that was a picture): such a question is read
    again from its picture by a vision model."""
    texts = [ln.text for ln in r.lines]
    key, texts = _key(texts)
    split: list[str] = []
    for t in texts:
        split += TWO_OPTS.split(t) if re.match(r"^\(?[A-D]\)", t) else [t]
    # A paper may print the question twice, in English and then in Hindi (or the other way round), each with its
    # options: one block per copy. A paper that prints both languages line by line has one block.
    # A numbered list inside the question ("1. Petitionary ... 5. Petitioned", statements "A. ... D.") looks like
    # options; it is folded back into the question when a fifth item follows, when "Ans" (a response sheet's options)
    # follows, or when a 1-4 run follows an A-D one.
    blocks: list[dict] = [{"q": [], "opts": [], "raw": [], "kind": None}]

    def fold(b: dict) -> None:
        b["q"] += [ln for raw in b["raw"] for ln in raw]
        b["opts"], b["raw"], b["kind"] = [], [], None

    for t in split:
        cur = blocks[-1]
        ans = re.match(r"^ans\b\s*", t, re.I)
        if ans:  # a response sheet: the options start here, whatever numbered lines came before
            if cur["opts"]:
                fold(cur)
            t = t[ans.end():]
            if not t:
                continue
        m = LABEL.match(t)
        label = None
        body = ""
        if m:
            label, body = m.group(1), m.group(2).strip()
        else:
            m2 = OPT_AFTER.match(t)
            if m2 and not _hindi(t):
                label, body = m2.group(2), m2.group(1).strip()
        if label is not None:
            kind = "digit" if label.isdigit() else "letter"
            idx = int(label) - 1 if kind == "digit" else "abcdef".index(label.lower())
            n = len(cur["opts"])
            if idx == n and n < 4 and (n == 0 or kind == cur["kind"]):  # the next option in order: 1, 2, 3, 4
                cur["opts"].append([body] if body else [])
                cur["raw"].append([t])
                cur["kind"] = kind
                continue
            if idx >= 4 and idx == n and kind == cur["kind"]:  # a fifth item: it was a list in the question
                fold(cur)
                cur["q"].append(t)
                continue
            if idx == 0 and n == 4 and kind != cur["kind"] and cur["kind"] == "letter":  # statements A-D, then 1-4
                fold(cur)
                cur["opts"], cur["raw"], cur["kind"] = [[body] if body else []], [[t]], kind
                continue
            if idx == 0 and n == 4:  # the options again: the other language's copy
                blocks.append({"q": [], "opts": [[body] if body else []], "raw": [[t]], "kind": kind})
                continue
        if not cur["opts"]:
            cur["q"].append(t)
        elif len(cur["opts"]) == 4 and cur["q"] and _hindi(t) != _hindi(" ".join(cur["q"])):
            blocks.append({"q": [t], "opts": [], "raw": [], "kind": None})  # the question again, other language
        else:
            cur["opts"][-1].append(t)
            cur["raw"][-1].append(t)
    q_en = [t for b in blocks for t in b["q"] if not _hindi(t)]
    q_hi = [t for b in blocks for t in b["q"] if _hindi(t)]
    whole = [b for b in blocks if len(b["opts"]) == 4]
    en = next((b for b in whole if any(not _hindi(" ".join(o)) and o for o in b["opts"])), whole[0] if whole else None)
    hi = next((b for b in whole if any(_hindi(" ".join(o)) for o in b["opts"])), None)
    options = [" ".join(x for x in o if not _hindi(x)).strip() for o in en["opts"]] if en else []
    # a Hindi option is its Devanagari text, or (a number, a name in Latin letters) what the English copy shows
    options_hi = ([" ".join(x for x in o if _hindi(x)).strip() or options[i] if i < len(options) else ""
                   for i, o in enumerate(hi["opts"])] if hi else [])
    if hi is None and en is not None and any(_hindi(x) for o in en["opts"] for x in o):  # both languages per line
        options_hi = [" ".join(x for x in o if _hindi(x)).strip() or options[i] for i, o in enumerate(en["opts"])]
    text = "\n".join(q_en).strip()
    hindi = "\n".join(q_hi).strip()
    if GARBLED.search(hindi + " ".join(options_hi)):
        hindi, options_hi = "", []  # a broken Hindi font: keep the English only
    answer = _answer(key, options) if key else None
    figures = [p for p in r.pictures if not p.small]
    # small pictures not standing in front of an option: maths or a symbol printed as a picture inside the text
    inline = [p for p in r.pictures if p.small and not _at_option(p, r)]
    ok = len(options) == 4 and (all(options) or bool(figures)) and bool(text or figures) and not inline
    return {"n": r.n, "paper": r.paper, "text": text, "options": options + [""] * (4 - len(options)),
            "text_hi": hindi or None, "options_hi": options_hi if len(options_hi) == 4 and all(options_hi) else None,
            "key": key, "answer": answer, "ok": ok, "inline_pictures": len(inline), "section": r.section}


def _answer(key: str, options: list[str]) -> int | None:
    """The 0-based option a printed key names: a number, a letter, or the option's own text."""
    k = key.strip().strip("().").strip()
    if re.fullmatch(r"[1-4]", k):
        return int(k) - 1
    if re.fullmatch(r"[A-Da-d]", k):
        return "abcd".index(k.lower())
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())  # noqa: E731
    hits = [i for i, o in enumerate(options) if o and norm(o) == norm(k)]
    return hits[0] if len(hits) == 1 else None


def option_lines(r: Region) -> list[Line]:
    """The line each option starts on, in order (for ticks and option pictures): on a response sheet the run after
    "Ans" (a numbered list in the question comes before it)."""
    lines = r.lines
    start = next((i for i, ln in enumerate(lines) if re.match(r"^ans\b", ln.text, re.I)), 0)
    found: list[Line] = []
    for ln in lines[start:]:
        m = OPT.match(ln.text)
        if m and len(found) < 4:
            label = m.group(1)
            idx = int(label) - 1 if label.isdigit() else "abcd".index(label.lower())
            if idx == len(found):
                found.append(ln)
    return found


def _at_option(p: Picture, r: Region) -> bool:
    mid = (p.box[1] + p.box[3]) / 2
    return any(ln.page == p.page and ln.box[1] - 6 <= mid <= ln.box[3] + 6 and p.box[0] <= ln.box[0] + 60
               for ln in option_lines(r))


def ticked(r: Region) -> int | None:
    """The option a response sheet marks right: of the four marks in front of the options, the one that differs (a
    green tick among red crosses)."""
    marks: list[str | None] = []
    for ln in option_lines(r):
        mid = (ln.box[1] + ln.box[3]) / 2
        near = [p for p in r.pictures if p.small and p.page == ln.page and abs((p.box[1] + p.box[3]) / 2 - mid) < 8
                and p.box[0] <= ln.box[0] + 60]
        marks.append(near[0].digest if near else None)
    if len(marks) != 4 or None in marks:
        return None
    odd = [i for i, d in enumerate(marks) if marks.count(d) == 1]
    return odd[0] if len(odd) == 1 and len(set(marks)) == 2 else None
