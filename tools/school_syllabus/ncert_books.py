"""Which NCERT books each class and subject has, read from ncert.nic.in/textbook.php (its JavaScript menus)."""
import json
import re
import sys

src = open(sys.argv[1], encoding="utf-8", errors="replace").read()
# drop commented-out lines
lines = [ln for ln in src.splitlines() if not ln.strip().startswith("//")]
src = "\n".join(re.sub(r"/\*.*?\*/", "", ln) for ln in lines)
src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)

books = []
head = re.compile(r'tclass\.value==(\d+)\)\s*&&\s*\(document\.test\.tsubject\.options\[sind\]\.text=="([^"]+)"\)\)')
for m in head.finditer(src):
    cls, subject = int(m.group(1)), m.group(2)
    body = src[m.end(): m.end() + 6000]
    stop = re.search(r"\n\s*(else\s+)?if\s*\(\(document", body)
    if stop:
        body = body[: stop.start()]
    titles = dict(re.findall(r'tbook\.options\[(\d+)\]\.text="([^"]*)"', body))
    values = dict(re.findall(r'tbook\.options\[(\d+)\]\.value="([^"]*)"', body))
    for i, title in titles.items():
        if i != "0" and title and i in values:
            books.append({"class": cls, "subject": subject, "title": title, "url": values[i]})
json.dump(books, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(books), "books")
for b in books:
    print(b["class"], "|", b["subject"], "|", b["title"], "|", b["url"])
