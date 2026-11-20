"""Download open-licensed fonts and a word list used to synthesise OCR training data.

Everything comes from public GitHub repositories:
  * google/fonts                       (SIL OFL / Apache 2.0 fonts)
  * first20hours/google-10000-english  (common English word list)

Usage:  python ml/scripts/download_assets.py
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "data" / "fonts"
CORPUS_DIR = ROOT / "data" / "corpus"

GF = "https://raw.githubusercontent.com/google/fonts/main"

# (category, relative path in google/fonts). Categories steer the renderer:
#   hand  -> chalk / marker / pen-tablet handwriting styles
#   slide -> printed slides, textbooks, screens
FONTS: list[tuple[str, str]] = [
    # Handwriting (Kalam is by the Indian Type Foundry — a natural fit for Indian classroom boards).
    ("hand", "ofl/kalam/Kalam-Regular.ttf"),
    ("hand", "ofl/kalam/Kalam-Bold.ttf"),
    ("hand", "ofl/kalam/Kalam-Light.ttf"),
    ("hand", "ofl/caveat/Caveat%5Bwght%5D.ttf"),
    ("hand", "ofl/patrickhand/PatrickHand-Regular.ttf"),
    ("hand", "ofl/indieflower/IndieFlower-Regular.ttf"),
    ("hand", "ofl/architectsdaughter/ArchitectsDaughter-Regular.ttf"),
    ("hand", "ofl/gochihand/GochiHand-Regular.ttf"),
    ("hand", "ofl/shadowsintolight/ShadowsIntoLight.ttf"),
    ("hand", "apache/permanentmarker/PermanentMarker-Regular.ttf"),
    ("hand", "ofl/handlee/Handlee-Regular.ttf"),
    ("hand", "apache/comingsoon/ComingSoon-Regular.ttf"),
    ("hand", "apache/schoolbell/Schoolbell-Regular.ttf"),
    ("hand", "ofl/itim/Itim-Regular.ttf"),
    ("hand", "ofl/mali/Mali-Regular.ttf"),
    ("hand", "ofl/mali/Mali-Medium.ttf"),
    # Slides / print — these carry Greek + math glyph coverage.
    ("slide", "ofl/notosans/NotoSans%5Bwdth,wght%5D.ttf"),
    ("slide", "ofl/notosansmath/NotoSansMath-Regular.ttf"),
    ("slide", "ofl/stixtwotext/STIXTwoText%5Bwght%5D.ttf"),
    ("slide", "ofl/firasans/FiraSans-Regular.ttf"),
    ("slide", "ofl/firasans/FiraSans-SemiBold.ttf"),
    ("slide", "ofl/roboto/Roboto%5Bwdth,wght%5D.ttf"),
    ("slide", "ofl/opensans/OpenSans%5Bwdth,wght%5D.ttf"),
    ("slide", "ofl/lato/Lato-Regular.ttf"),
    ("slide", "ofl/lato/Lato-Bold.ttf"),
    ("slide", "ofl/poppins/Poppins-Regular.ttf"),
    ("slide", "ofl/poppins/Poppins-SemiBold.ttf"),
    ("slide", "ofl/montserrat/Montserrat%5Bwght%5D.ttf"),
    ("slide", "ufl/ubuntu/Ubuntu-Regular.ttf"),
    ("slide", "ofl/sourcecodepro/SourceCodePro%5Bwght%5D.ttf"),
]

WORDLIST_URL = (
    "https://raw.githubusercontent.com/first20hours/google-10000-english/"
    "master/google-10000-english-no-swears.txt"
)


def fetch(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 1000:
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "focs-asset-fetcher"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return True
    except Exception as exc:  # network hiccups should not abort the whole run
        print(f"  ! failed {url}: {exc}")
        return False


def main() -> int:
    ok = 0
    for category, rel in FONTS:
        name = rel.rsplit("/", 1)[-1].replace("%5B", "[").replace("%5D", "]")
        if fetch(f"{GF}/{rel}", FONT_DIR / category / name):
            ok += 1
    print(f"fonts: {ok}/{len(FONTS)} available in {FONT_DIR}")
    words = fetch(WORDLIST_URL, CORPUS_DIR / "english_words.txt")
    print(f"word list: {'ok' if words else 'missing'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
