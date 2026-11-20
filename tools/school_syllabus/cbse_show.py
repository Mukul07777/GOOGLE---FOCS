"""Print a stretch of a CBSE curriculum text, condensed: from the n-th match of START up to END (or LIMIT chars).
Usage: cbse_show.py file.txt START END [nth] [limit]"""
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
name, start, end = sys.argv[1:4]
nth = int(sys.argv[4]) if len(sys.argv) > 4 else 1
limit = int(sys.argv[5]) if len(sys.argv) > 5 else 9000
text = open(f"cbse/{name}", encoding="utf-8").read()
text = re.sub(r"[ \t]+", " ", text)
hits = [m.start() for m in re.finditer(start, text, re.I)]
if len(hits) < nth:
    print("no start", hits)
    sys.exit()
s = hits[nth - 1]
e = re.search(end, text[s + 10:], re.I)
chunk = text[s: s + 10 + e.start()] if e else text[s: s + limit]
chunk = re.sub(r"\n\s*\n+", "\n", chunk[:limit])
print(re.sub(r"\s*\n\s*", " | ", chunk))
