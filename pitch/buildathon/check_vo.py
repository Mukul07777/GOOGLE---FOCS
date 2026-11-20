"""Listens back to each voiceover line (Gemini transcribes it) so a take that adds, drops or reads out the style
instructions is caught before it goes in the film.

    python buildathon/check_vo.py [id ...]
"""
import base64
import json
import sys
import urllib.request
import wave
from pathlib import Path

from make_vo import OUT, key

MODEL = "gemini-3.5-flash-lite"


def transcribe(path: Path) -> str:
    body = {"contents": [{"parts": [
        {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(path.read_bytes()).decode()}},
        {"text": "Transcribe this audio exactly, word for word, in Roman script (Hinglish as spoken). Output only the transcript."}]}],
        "generationConfig": {"temperature": 0}}
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key()})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["candidates"][0]["content"]["parts"][0]["text"].strip()


if __name__ == "__main__":
    cfg = json.loads((Path(__file__).parent / "vo.json").read_text(encoding="utf-8"))
    only = set(sys.argv[1:])
    for line in cfg["lines"]:
        p = OUT / f"{line['id']}.wav"
        if not p.exists() or (only and line["id"] not in only):
            continue
        with wave.open(str(p)) as w:
            d = w.getnframes() / w.getframerate()
        words = len(line["text"].split())
        print(f"== {line['id']}  {d:.1f}s  {words} words  ({words / d:.1f} w/s)")
        print("   heard:", transcribe(p))
