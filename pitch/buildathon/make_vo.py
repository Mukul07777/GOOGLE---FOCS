"""The film's Hinglish voiceover, spoken by Gemini TTS, one file per line.

    python buildathon/make_vo.py [id ...]     -> public/bt/vo/<id>.wav and public/bt/vo.json (seconds per line)

Reads GEMINI_API_KEY from backend/.env. Long pauses are shortened and the take is sped up a little (pitch kept),
so the delivery stays fast and punchy. Lines already made are kept unless named on the command line.
"""
import base64
import os
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "public" / "bt" / "vo"
ENV = ROOT.parent / "backend" / ".env"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SR = 24000
TEMPO = 1.13          # faster, pitch kept
MAX_GAP = 0.16        # no pause longer than this (seconds)


def key() -> str:
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("GEMINI_API_KEY is not in backend/.env")


def speak(text: str, cfg: dict) -> np.ndarray:
    body = {
        "contents": [{"parts": [{"text": f"{cfg['style']}: {text}" if cfg["style"] else text}]}],
        "generationConfig": {"responseModalities": ["AUDIO"],
                             "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": cfg["voice"]}}}},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{os.environ.get('TTS_MODEL') or cfg['model']}:generateContent"
    for attempt in range(8):
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json", "x-goog-api-key": key()})
            with urllib.request.urlopen(req, timeout=240) as r:
                d = json.load(r)
            raw = base64.b64decode(d["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
            if raw[:4] == b"RIFF":
                raw = raw[44:]
            return np.frombuffer(raw[: len(raw) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768
        except (urllib.error.URLError, KeyError, TimeoutError) as e:
            wait = 65 if "429" in str(e) else 5 * (attempt + 1)  # the TTS preview allows a few calls a minute
            print(f"    retry {attempt + 1} in {wait}s: {e}")
            time.sleep(wait)
    raise SystemExit("TTS failed")


def words(s: str) -> list[str]:
    return [w for w in "".join(c.lower() if c.isalnum() else " " for c in s).split() if w]


def good_take(path: Path, text: str, seconds: float) -> tuple[bool, str]:
    """Heard back: it must start and end with the script's words (no instructions read out) and be quick enough."""
    from check_vo import transcribe
    try:
        heard = transcribe(path)
    except Exception as e:  # noqa: BLE001 - the listen-back is a guard, not a reason to stop
        return True, f"(not checked: {e})"
    want, got = words(text), words(heard)
    leak = any(w in got for w in ("founder", "accent", "energy", "hinglish")) and not any(w in want for w in ("founder", "accent"))
    rate = len(want) / seconds
    ok = not leak and rate >= 2.9 and len(got) <= len(want) * 1.25
    return ok, f"{rate:.1f} w/s{' LEAK' if leak else ''}: {heard[:90]}"


def tighten(a: np.ndarray) -> np.ndarray:
    """Trim the ends and shorten every pause to MAX_GAP."""
    w = int(SR * 0.02)
    n = len(a) // w
    env = np.sqrt((a[: n * w].reshape(n, w) ** 2).mean(axis=1))
    loud = env > max(env.max() * 0.035, 1e-4)
    idx = np.flatnonzero(loud)
    if not len(idx):
        return a
    keep, gap = [], 0
    for i in range(idx[0], idx[-1] + 1):
        if loud[i]:
            gap = 0
            keep.append(i)
        else:
            gap += 1
            if gap * 0.02 <= MAX_GAP:
                keep.append(i)
    out = np.concatenate([a[i * w:(i + 1) * w] for i in keep])
    pad = np.zeros(int(SR * 0.05), dtype=np.float32)
    return np.concatenate([pad, out, pad])


def save(a: np.ndarray, path: Path) -> float:
    tmp = path.with_suffix(".raw.wav")
    with wave.open(str(tmp), "wb") as wv:
        wv.setnchannels(1); wv.setsampwidth(2); wv.setframerate(SR)
        wv.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(tmp),
                    "-af", f"atempo={TEMPO},highpass=f=70,acompressor=threshold=-18dB:ratio=3:attack=5:release=80,loudnorm=I=-15:TP=-1.5:LRA=7",
                    "-ar", "48000", "-ac", "1", str(path)], check=True)
    tmp.unlink()
    with wave.open(str(path)) as wv:
        return wv.getnframes() / wv.getframerate()


def main() -> None:
    cfg = json.loads((HERE / "vo.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    meta_path = OUT.parent / "vo.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    only = set(sys.argv[1:])
    for line in cfg["lines"]:
        path = OUT / f"{line['id']}.wav"
        if path.exists() and line["id"] in meta and (only and line["id"] not in only or not only and meta.get(line["id"] + "#text") == line["text"]):
            continue
        best = None
        for take in range(5):
            a = tighten(speak(line["text"], cfg))
            trial = path.with_name(f"{line['id']}.take{take}.wav")
            secs = save(a, trial)
            ok, note = good_take(trial, line["text"], secs)
            print(f"  {line['id']} take {take}: {secs:.2f}s {'OK' if ok else 'redo'} · {note}")
            rate = len(words(line["text"])) / secs
            if best is None or (ok and not best[0]) or (ok == best[0] and rate > best[2]):
                if best:
                    best[1].unlink(missing_ok=True)
                best = (ok, trial, rate, secs)
            else:
                trial.unlink(missing_ok=True)
            if ok:
                break
        best[1].replace(path)
        meta[line["id"]] = round(best[3], 3)
        meta[line["id"] + "#text"] = line["text"]
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    total = sum(v for k, v in meta.items() if "#" not in k)
    print(f"  total speech {total:.1f}s")


if __name__ == "__main__":
    main()
