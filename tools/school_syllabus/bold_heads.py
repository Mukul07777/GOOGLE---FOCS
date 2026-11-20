"""Bold section headings of NCERT chapter PDFs whose headings are set in the body size: short lines whose spans are all
bold (or in a heading typeface), not part of a paragraph. Writes ncert/bold/<name>.txt. Usage: bold_heads.py name [...]"""
import collections
import concurrent.futures
import pathlib
import re
import subprocess
import sys
import time

import pymupdf

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).parent / "ncert"
OUT = HERE / "bold"
OUT.mkdir(exist_ok=True)


def read(pdf: pathlib.Path) -> list[str]:
    doc = pymupdf.open(pdf)
    sizes = collections.Counter()
    lines = []
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            blines = block.get("lines", [])
            for line in blines:
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = re.sub(r"\s+", " ", "".join(s["text"] for s in spans)).strip()
                size = max(s["size"] for s in spans)
                bold = all(re.search(r"bold|demi|black|heavy|semibold|-bd|medium", s["font"], re.I) or s["flags"] & 16 for s in spans)
                sizes[round(size)] += len(text)
                lines.append((text, size, bold, len(blines)))
    body = sizes.most_common(1)[0][0] if sizes else 11
    out = []
    for text, size, bold, block_lines in lines:
        if bold and size >= body - 0.5 and 3 < len(text) < 80 and not text.endswith((".", ",", ";")):
            out.append(text)
    return list(dict.fromkeys(out))


def one(name: str) -> str:
    pdf = HERE / f"{name}_b.pdf"
    for attempt in range(4):
        subprocess.run(["curl", "-sS", "-m", "240", "-A", "Mozilla/5.0", "-o", str(pdf), f"https://ncert.nic.in/textbook/pdf/{name}.pdf"],
                       check=False, capture_output=True)
        try:
            found = read(pdf)
            break
        except Exception:  # noqa: BLE001
            time.sleep(3 + 5 * attempt)
    else:
        pdf.unlink(missing_ok=True)
        return f"{name} FAILED"
    pdf.unlink(missing_ok=True)
    (OUT / f"{name}.txt").write_text("\n".join(found), encoding="utf-8")
    return f"{name} {len(found)}"


names = sys.argv[1:]
with concurrent.futures.ThreadPoolExecutor(4) as pool:
    for msg in pool.map(one, names):
        print(msg, flush=True)
