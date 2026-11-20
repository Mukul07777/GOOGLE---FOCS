"""Write backend/app/data/syllabus/school/class_NN.json from school_data.py / school_senior.py: each chapter's topics
are the ones given, else the section headings of NCERT's own chapter PDF (ncert/heads), else the subject's
language topics. Prints what it could not fill. Run with -I from the scratchpad; a headings folder and an output
folder can be given to try new headings without touching the app's data."""
import collections
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import school_data  # noqa: E402
import school_senior  # noqa: E402
from school_topics import FIX, TOPICS  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
DATA = pathlib.Path("C:/Users/HP/Desktop/focs/backend/app/data/syllabus/school")
HEADS = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "ncert" / "heads"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else DATA
NUM = re.compile(r"^(\d{1,2})\.(\d{1,2})(?:\.(\d{1,2}))?\s+(.+)$")
DULL = re.compile(r"^(introduction|summary|exercises?|conclusion|let us recall|points to ponder|keywords?|key words|what have we learnt|glossary|"
                  r"think and reflect|revise, reflect, refine|at a glance|questions|activities|project|the journey beyond|in a nutshell|"
                  r"what we have discussed|let us enhance|let us do|let us think)\b", re.I)
LANGUAGE = {
    "English": ["Reading and understanding the text", "Words and their meanings", "Grammar in context", "Speaking and writing about the text"],
    "Hindi": ["पाठ को पढ़ना और समझना", "शब्द और उनके अर्थ", "व्याकरण", "बोलना और लिखना"],
    "Sanskrit": ["पाठस्य अर्थः भावः च", "शब्दार्थाः", "व्याकरणम्", "अनुवादः लेखनं च"],
}
YOUNG_ENGLISH = ["Let us listen and sing", "Let us speak", "Let us read", "Let us write"]
missing = []


def language_of(subject: str) -> str | None:
    return next((k for k in LANGUAGE if subject.startswith(k)), None)


NOT_HEADING = re.compile(r"^(introduction|summary|exercises?|key ?terms?|keywords?|contents|activity|chapter|unit\b|unit-|the big questions?|after reading|"
                         r"let us|let’s|let's|think|do you know|box|fig|figure|table|source|glossary|questions?|answers?|project|before we|"
                         r"note|teacher|in this chapter|you will|learning objectives|objectives$|reprint|timeline|conclusion|references|"
                         r"suggested|further reading|test yourself|points to|check your|try this|discuss|class \d|part [ivx\d]|section [ivx\d]|"
                         r"the big|noodles|put a|overview|map work|write a short|fast forward|ü|social$|science$|life$|hindu$|production$)", re.I)
JOINERS = ("of", "the", "and", "—", "–", "-", "from", "in", "to", "for", "a", "an", "on", "with", "its", "their", "&", "as", "between", "at", "by", ":")


def plain(text: str) -> str:
    """Text for comparing: lower case, one kind of quote and dash ("India’s" is "India's")."""
    return re.sub(r"\s+", " ", text.lower().translate(str.maketrans("’‘“”–—", "''\"\"--"))).strip()


def big_headings(lines: list[str], chapter_name: str) -> list[str]:
    """Section headings among the lines set in a large font: wrapped ones joined, title fragments and labels dropped."""
    joined: list[str] = []
    for line in (re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\u2022\u25aa\uf0b7]+", "", x)).strip() for x in lines):
        if not line:
            continue
        if joined and (joined[-1].split()[-1].lower() in JOINERS or joined[-1].endswith((",", "—", "–"))):
            joined[-1] = f"{joined[-1]} {line}"
        else:
            joined.append(line)
    title = plain(chapter_name)
    out: list[str] = []
    for h in joined:
        h = h.strip(" .:-–—|")
        low = plain(h)
        if (len(h) < 4 or len(h) > 70 or NOT_HEADING.match(h) or re.search(r"\b\w \w \w\b", h) or not h[0].isupper() or re.search(r"[=×+]|\d{2,}|\.\s", h)
                or low in title or title in low or h.isupper() and len(h.split()) <= 3
                or low in (x.lower() for x in out) or len(h.split()) > 10):
            continue
        out.append(h if not h.isupper() else title_case(h))
    return out[:10]


BOLD = HERE / "ncert" / "bold"
BOLD_NOISE = re.compile(r"^(activity|activiy|do you know|teachers?|exercises?|introduction|summary|key terms|review questions|project ideas|"
                        r"weblinks|pedagogical|after reading|contents|glossary|read a cartoon|let us|note|box|source|fig|table|"
                        r"illustration|example|solution|test your|check your|questions?|answers?|case|chapter|unit)\b", re.I)


def bold_headings(name: str, chapter_name: str) -> list[str]:
    """Headings set bold at the body size (older NCERT books): short title-like lines, capitals made title case,
    labels, sentence pieces and words glued together by the PDF left out."""
    path = BOLD / f"{name}.txt"
    if not path.exists():
        return []
    title = chapter_name.lower()
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        h = re.sub(r"\s+", " ", line).strip(" .:-–—|")
        if (len(h) < 4 or len(h) > 70 or BOLD_NOISE.match(h) or not h[0].isupper() or re.search(r"[=×+]|\d{3,}|\.\s|;", h)
                or len(h.split()) > 9 or (h.isupper() and any(len(w) > 13 for w in h.split()))
                or h.lower() in title or title in h.lower() or h.endswith(":")):
            continue
        if h.isupper():
            h = " ".join(w.capitalize() if len(w) > 3 or i == 0 else w.lower() for i, w in enumerate(h.split()))
        if h.lower() not in (x.lower() for x in out):
            out.append(h)
    return out[:10]


CUT = {"of", "the", "and", "from", "in", "to", "for", "a", "an", "on", "with", "its", "their", "as", "between", "at", "by", "or",
       "into", "than", "that", "is", "are"}


def heading(raw: str) -> str | None:
    """A numbered heading's title cleaned, or None for a review section; a page number the PDF ran on is dropped
    ("Rusting 63"), a number the title ends with is kept ("Powers of 10")."""
    title = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\u2022\u25aa\uf0b7]+", "", raw)).strip()
    page = re.search(r"\s+\d{1,3}$", title)
    if page and title[:page.start()].split()[-1].lower() not in CUT:
        title = title[:page.start()]
    title = title.strip(" .:-–—")
    if len(title) < 3 or DULL.match(title) or len(title) > 95:
        return None
    return title[0].upper() + title[1:]


def from_heads(code: str, n: int, chapter_name: str = "") -> list[str] | None:
    """The chapter's numbered sections with their numbered sub-sections ("1.2.1 Combination Reaction") when all of
    them come to ten topics or fewer; otherwise a section with sub-sections gives those instead, the sections with
    the fewest first, as long as the chapter stays at ten."""
    path = HEADS / f"{code}{n:02d}.txt"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    numbered = text.split("BIG", 1)[0].splitlines()[1:]
    rows = [m for m in (NUM.match(line.strip()) for line in numbered) if m]
    if sum(1 for m in rows if not m.group(3)) < 2:
        big = text.split("\nBIG\n", 1)[1].split("\nSAMPLE\n", 1)[0].splitlines() if "\nBIG\n" in text else []
        found = big_headings(big, chapter_name)
        return found if len(found) >= 2 else None
    chapter_no = collections.Counter(m.group(1) for m in rows if not m.group(3)).most_common(1)[0][0]
    tree: dict[str, list[str]] = {}
    section = None
    for m in rows:
        title = heading(m.group(4)) if m.group(1) == chapter_no else None
        if m.group(3):
            if title and section and m.group(2) == section[0]:
                tree[section[1]].append(title)
        elif title and title.lower() not in (t.lower() for t in tree):
            tree[title] = []
            section = (m.group(2), title)
        else:
            section = None
    if len(tree) < 2:
        return None
    if len(tree) + sum(len(subs) for subs in tree.values()) <= 10:
        return list(dict.fromkeys(t for title, subs in tree.items() for t in (title, *subs)))
    total, expand = len(tree), set()
    for title in sorted(tree, key=lambda t: len(tree[t])):
        if len(tree[title]) >= 2 and total - 1 + len(tree[title]) <= 10:
            expand.add(title)
            total += len(tree[title]) - 1
    out = [t for title, subs in tree.items() for t in (subs if title in expand else [title])]
    return list(dict.fromkeys(out))[:10]


SMALL = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on", "or", "the", "to", "with", "vs"}


def title_case(text: str) -> str:
    words = text.lower().split()
    return " ".join(w if (i and w in SMALL) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def tidy(topics: list[str]) -> list[str]:
    """Headings as read from a PDF, cleaned: capitals made title case, a large first letter set apart joined back
    ("O bserve"), pieces that only begin another heading and decorative title art ("Oney And And C") left out,
    review sections dropped."""
    out = []
    for t in topics:
        t = re.sub(r"\s+,", ",", re.sub(r"\s+", " ", t)).strip(" .:-–—|;,")
        t = re.sub(r"^([B-HJ-Z]) (?=[a-z])", r"\1", t)
        t = re.sub(r"̒\s*", "‘", t).replace("̓", "’")  # combining commas set as quotes ("the ̒ food factories̓")
        if re.search(r"\b(\w+) \1\b", t, re.I) or re.fullmatch(r"(review questions|questions|exercises?|summary|keywords?|key terms)", t, re.I):
            continue
        letters = [ch for ch in t if ch.isalpha()]
        if letters and sum(ch.isupper() for ch in letters) / len(letters) > 0.8 and len(t) > 4:
            t = title_case(t)
        out.append(t)
    keep = [t for t in out if not any(o != t and o.lower().startswith(t.lower()) for o in out)]
    return list(dict.fromkeys(keep))


def chapter(cls: int, subject: str, book: str, code: str, n: int, raw) -> dict | None:
    item = {"name": raw} if isinstance(raw, str) else dict(raw)
    if item["name"].startswith("-"):
        return None  # in the book, not in this year's CBSE syllabus
    out = {"name": item["name"], "book": item.get("book", book)}
    if item.get("marks") is not None:
        out["marks"] = item["marks"]
    topics = item.get("topics")
    lang = language_of(subject)
    if not topics and not lang:
        topics = TOPICS.get((cls, subject, out["book"], item["name"])) or TOPICS.get((cls, subject, item["name"])) or from_heads(code, n, item["name"])
    if topics and not item.get("topics"):
        topics = tidy(topics) or topics
        name = plain(item["name"])  # the chapter's own title, or its first part, set large again inside it
        echo = lambda t: plain(re.sub(r"\s+\d{1,2}$", "", t))  # noqa: E731 (with its number: "India’s Long Road 2")
        topics = [FIX.get((item["name"], t), FIX.get(t, t)) for t in topics if not (echo(t) == name or len(t) >= 15 and name.startswith(echo(t)))]
        topics = [t for t in topics if t]
    if not topics and lang:
        topics = YOUNG_ENGLISH if lang == "English" and cls <= 5 else LANGUAGE[lang]
    if not topics:
        missing.append(f"class {cls} {subject}: {item['name']} ({code}{n:02d})")
        topics = [item["name"]]
    out["topics"] = topics
    return out


def build(cls: int, data: dict, keep: dict | None = None) -> dict:
    subjects = []
    for name in data.get("keep", []):
        subjects.append(next(s for s in keep["subjects"] if s["name"] == name))
    for subject, units in data["subjects"]:
        merged: dict[str, dict] = {}
        for unit_name, book, code, first, marks, chapters in units:
            unit = merged.setdefault(unit_name, {"name": unit_name, "chapters": []})
            kept = []
            pdf = first  # the chapter's PDF number in its book (a chapter only CBSE has, "nopdf", has none)
            for raw in chapters:
                c = chapter(cls, subject, book, code, pdf, raw)
                if not (isinstance(raw, dict) and raw.get("nopdf")):
                    pdf += 1
                if c:
                    kept.append(c)
            if marks is not None and kept:
                for c in kept:
                    c.setdefault("marks", round(marks / len(kept), 2))
            unit["chapters"] += kept
        subjects.append({"name": subject, "units": [u for u in merged.values() if u["chapters"]]})
    return {"class": cls, "default": data.get("default"), "subjects": subjects}


def unique_names(classes: dict[int, dict]) -> None:
    """Chapter names are what questions are filed under, so within a subject each must be unique across the classes:
    two books of one class with the same chapter name get the book's place ("(India)"), the same name in two
    classes gets the class ("Probability (Class 11)")."""
    for built in classes.values():
        for subject in built["subjects"]:
            seen: set[str] = set()
            for unit in subject["units"]:
                for c in unit["chapters"]:
                    if c["name"] in seen:
                        c["name"] += " (India)" if c["book"].startswith("India") else f" ({c['book']})"
                    seen.add(c["name"])
    where: dict[tuple[str, str], list[int]] = collections.defaultdict(list)
    for n, built in classes.items():
        for subject in built["subjects"]:
            for unit in subject["units"]:
                for c in unit["chapters"]:
                    where[(subject["name"], re.sub(r" \(Class \d+\)$", "", c["name"]))].append(n)
    for n, built in classes.items():
        for subject in built["subjects"]:
            for unit in subject["units"]:
                for c in unit["chapters"]:
                    base = re.sub(r" \(Class \d+\)$", "", c["name"])
                    if len(set(where[(subject["name"], base)])) > 1:
                        c["name"] = f"{base} (Class {n})"


OUT.mkdir(parents=True, exist_ok=True)
plan = {n: getattr(school_data, f"C{n}") for n in range(1, 11)}
plan[11], plan[12] = school_senior.C11, school_senior.C12
built_all = {}
for n, data in plan.items():
    path = DATA / f"class_{n:02d}.json"
    keep = json.loads(path.read_text(encoding="utf-8")) if data.get("keep") else None
    built_all[n] = build(n, data, keep)
unique_names(built_all)
for n, built in built_all.items():
    path = OUT / f"class_{n:02d}.json"
    path.write_text(json.dumps(built, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    chapters = sum(len(u["chapters"]) for s in built["subjects"] for u in s["units"])
    print(f"class {n}: {len(built['subjects'])} subjects, {chapters} chapters")
print("unfilled:", len(missing))
for m in missing:
    print("  ", m)
