"""Print just the contents of each saved NCERT prelims PDF, condensed: the page whose heading is "Contents" (or the
Hindi word) and the page after it while it still lists chapters. Usage: toc_show.py code [code...]"""
import pathlib
import re
import sys

import pymupdf

sys.stdout.reconfigure(encoding="utf-8")

HERE = pathlib.Path(__file__).parent / "ncert"
HEADS = ("contents", "content", "अनुक्रम", "विषय-सूची", "विषय सूची", "अनुक्रमणिका", "विषयानुक्रमणिका", "विषयसूची", "पाठ-सूची")
SKIP = re.compile(r"^(reprint|foreword|preface|about (this|the) book|a note for|rationalisation|iii|iv|v|vi|vii|viii|ix|x|xi|xii|xiii|xiv|xv)\b", re.I)


def show(code: str, limit: int = 2600) -> None:
    doc = pymupdf.open(HERE / f"{code}ps.pdf")
    pages = [doc[i].get_text() for i in range(doc.page_count)]
    start = None
    for i, t in enumerate(pages):
        lines = [ln.strip().lower() for ln in t.splitlines() if ln.strip()]
        if any(ln in HEADS or ln.rstrip(":") in HEADS for ln in lines[:6] + lines[-3:]):
            start = i
    if start is None:
        print(f"#### {code}: no contents heading")
        return
    out = []
    for t in pages[start:start + 2]:
        for ln in t.splitlines():
            ln = re.sub(r"\s+", " ", ln).strip()
            if ln and not SKIP.match(ln) and not re.fullmatch(r"[\divxlc]+", ln, re.I):
                out.append(ln)
    text = " | ".join(out)
    print(f"#### {code} (page {start})\n{text[:limit]}\n")


for c in sys.argv[1:]:
    try:
        show(c)
    except Exception as exc:  # noqa: BLE001
        print(f"#### {c}: {exc}")
