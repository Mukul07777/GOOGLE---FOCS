"""Section headings (and a text sample) of every non-language chapter of the chosen NCERT books, six downloads at a
time, with retries; each PDF is deleted once read. Writes ncert/heads/<code><nn>.txt (or the folder given as the
first argument; a second names a file listing the only chapters to read). Run with -I.

A heading is read a text block at a time, so one the book wraps onto two or three lines comes back whole; text set
twice over itself (the Class 10 books' shadowed headings) is read once, and broken ligatures ("Eﬀ ect") are joined."""
import collections
import concurrent.futures
import json
import pathlib
import re
import subprocess
import sys
import time

import pymupdf

HERE = pathlib.Path(__file__).parent / "ncert"
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "heads"
OUT.mkdir(parents=True, exist_ok=True)
NUM = re.compile(r"^(\d{1,2})\.(\d{1,2})(?:\.\d{1,2})?\s+(\S.{2,140})$")
LANGUAGE = {"English", "Hindi", "Sanskrit", "English Core", "Hindi Core", "Hindi Course A", "Hindi Course B"}
LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}

src = (pathlib.Path(__file__).parent / "ncert_toc.py").read_text(encoding="utf-8")
BOOKS = eval(src.split("BOOKS = ", 1)[1].split("\nMARKS", 1)[0])  # noqa: S307 (our own file)
ranges = {re.search(r"\?([a-z0-9]+)=", b["url"]).group(1): int(b["url"].rsplit("-", 1)[1])
          for b in json.load(open(HERE / "books.json", encoding="utf-8")) if b["url"]}


def clean(text: str) -> str:
    for lig, letters in LIGATURES.items():
        text = re.sub(lig + r"\s?", letters, text)
    return re.sub(r"\s+", " ", text).strip()


def blocks(page) -> list[tuple[str, float, bool]]:
    """The page's text as (text, size, bold) runs: lines in a row set at the same size and weight are one run, so a
    heading wrapped onto two lines is read whole. Each block is rebuilt from its characters, a character printed
    again within a point of itself (a shadow) kept once."""
    out = []
    for block in page.get_text("rawdict")["blocks"]:
        grid: dict[tuple, bool] = {}
        chars = []
        for line in block.get("lines", []):
            for span in line["spans"]:
                bold = "bold" in span["font"].lower() or bool(span["flags"] & 16)
                for ch in span["chars"]:
                    x, y = ch["origin"]
                    cell = (ch["c"], int(x // 2), int(y // 2))
                    if any((cell[0], cell[1] + dx, cell[2] + dy) in grid for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                        continue
                    grid[cell] = True
                    chars.append((y, x, ch["c"], span["size"], bold, ch["bbox"][2]))
        if not any(c[2].strip() for c in chars):
            continue
        chars.sort(key=lambda c: c[0])  # (a stable sort: a ligature's letters, which share a place, stay in order)
        rows: list[list] = []
        for c in chars:
            if rows and c[0] - rows[-1][0][0] <= c[3] * 0.5:
                rows[-1].append(c)
            else:
                rows.append([c])
        lines = []
        for row in rows:
            row.sort(key=lambda c: c[1])
            text = ""
            for prev, c in zip([None, *row], row):  # a gap wider than a fifth of the type is a space the PDF left out
                if prev and prev[2].strip() and c[2].strip() and c[1] - prev[5] > c[3] * 0.2:
                    text += " "
                text += c[2]
            text = clean(text)
            if text:
                inked = [c for c in row if c[2].strip()]
                lines.append((text, max(c[3] for c in inked), any(c[4] for c in inked)))
        run: list | None = None
        for t, s, b in lines:
            if run and abs(s - run[1]) <= 0.6 and b == run[2]:
                run[0] = f"{run[0]} {t}"
            elif run and len(t) <= 3:  # a chapter number set between the lines of its title
                continue
            else:
                if run:
                    out.append(tuple(run))
                run = [t, s, b]
        out.append(tuple(run))
    return out


def read(pdf: pathlib.Path) -> str:
    doc = pymupdf.open(pdf)
    sizes = collections.Counter()
    spans, plain = [], []
    for page in doc:
        plain.append(page.get_text())
        for text, size, bold in blocks(page):
            sizes[round(size)] += len(text)
            spans.append((text, size, bold))
    body = sizes.most_common(1)[0][0] if sizes else 11
    numbered = [t for t, size, bold in spans if NUM.match(t) and (bold or size > body + 0.5)
                and not re.search(r"\b(fig|figure|table|activity|example|exercise)\b", t, re.I)]
    big = [t for t, size, bold in spans if size >= body + 2.5 and 3 < len(t) < 140
           and not re.fullmatch(r"[\d\s.]+|reprint.*|chapter|unit", t, re.I)]
    sample = re.sub(r"\s+", " ", " ".join(plain))[:1800]
    dedup = lambda xs: list(dict.fromkeys(xs))  # noqa: E731
    return "NUMBERED\n" + "\n".join(dedup(numbered)) + "\nBIG\n" + "\n".join(dedup(big)[:80]) + "\nSAMPLE\n" + sample


def one(name: str) -> str:
    out = OUT / f"{name}.txt"
    if out.exists():
        return f"{name} done before"
    pdf = OUT / f"{name}.pdf"
    for attempt in range(4):
        subprocess.run(["curl", "-sS", "-m", "240", "-A", "Mozilla/5.0", "-o", str(pdf), f"https://ncert.nic.in/textbook/pdf/{name}.pdf"],
                       check=False, capture_output=True)
        try:
            text = read(pdf)
            break
        except Exception:  # noqa: BLE001
            time.sleep(3 + 5 * attempt)
    else:
        pdf.unlink(missing_ok=True)
        return f"{name} FAILED"
    pdf.unlink(missing_ok=True)
    out.write_text(text, encoding="utf-8")
    return f"{name} ok"


if __name__ == "__main__":
    jobs = [f"{code}{n:02d}" for cls, subject, book, code in BOOKS if subject not in LANGUAGE for n in range(1, ranges.get(code, 0) + 1)]
    if len(sys.argv) > 2:  # a file naming the only chapters to read ("fecu108" a line)
        only = set(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8").split())
        jobs = [j for j in jobs if j in only]
    print(len(jobs), "chapters", flush=True)
    with concurrent.futures.ProcessPoolExecutor(6) as pool:  # reading a PDF is CPU work: processes, not threads
        for i, msg in enumerate(pool.map(one, jobs)):
            if "FAILED" in msg or i % 25 == 0:
                print(i, msg, flush=True)
    print("all done", flush=True)
