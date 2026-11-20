"""Voices for the pitch, made with Microsoft's neural voices (edge-tts):

    python make_voice.py teacher   -> public/audio/teacher.mp3 (+ .json): the lecture's teacher, lines at fixed times
    python make_voice.py vo        -> public/audio/vo/<id>.mp3 (+ vo.json): the video's voiceover, one file per line

Needs `pip install edge-tts` and an internet connection. ffmpeg/ffprobe come with Remotion (node_modules).
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "public" / "audio"
BIN = ROOT / "node_modules" / "@remotion" / "compositor-win32-x64-msvc"
FFMPEG, FFPROBE = str(BIN / "ffmpeg.exe"), str(BIN / "ffprobe.exe")

# the lecture being "shared" in the live-lecture shot: (start second, text); the boards in shoot/film.mjs follow it
TEACHER_VOICE = "en-IN-NeerjaNeural"
TEACHER = [
    (1.2, "Chalo, let's start rotational motion. Torque is r cross F. And just like F equals m a, here torque equals I alpha. "
          "For a ring, the moment of inertia is M R squared. Samjhe? Write this down."),
    (49.0, "Next, rolling without slipping. The condition is v equals omega R. The total kinetic energy is half M v squared, "
           "plus half I omega squared. And remember, static friction does no work here. Yeh JEE mein har saal aata hai."),
]
TEACHER_LENGTH = 120.0


def duration(path: Path) -> float:
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


async def say(text: str, voice: str, path: Path, rate: str = "+0%", pitch: str = "+0Hz") -> float:
    path.parent.mkdir(parents=True, exist_ok=True)
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(path))
    return duration(path)


async def teacher() -> None:
    parts, speech = [], []
    for i, (start, text) in enumerate(TEACHER):
        p = AUDIO / "parts" / f"teacher-{i}.mp3"
        d = await say(text, TEACHER_VOICE, p, rate="-4%")
        parts.append((start, p))
        speech.append([start, round(start + d, 2)])
        print(f"  teacher line {i}: {start:.1f}s + {d:.1f}s")
    args = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
    for _, p in parts:
        args += ["-i", str(p)]
    chains = [f"[{i}:a]adelay={int(s * 1000)}|{int(s * 1000)}[a{i}]" for i, (s, _) in enumerate(parts)]
    mix = "".join(f"[a{i}]" for i in range(len(parts)))
    graph = ";".join(chains) + f";{mix}amix=inputs={len(parts)}:normalize=0,apad=whole_dur={TEACHER_LENGTH}[out]"
    out = AUDIO / "teacher.mp3"
    subprocess.run(args + ["-filter_complex", graph, "-map", "[out]", "-t", str(TEACHER_LENGTH), "-ar", "48000", "-b:a", "160k", str(out)], check=True)
    (AUDIO / "teacher.json").write_text(json.dumps({"speech": speech, "length": TEACHER_LENGTH}, indent=2))
    print("  wrote", out)


async def vo() -> None:
    from vo_script import VOICE, LINES  # the voiceover's words live next to the video's timeline

    meta = {}
    for key, text in LINES.items():
        d = await say(text, VOICE, AUDIO / "vo" / f"{key}.mp3", rate="+6%")
        meta[key] = round(d, 2)
        print(f"  {key}: {d:.1f}s")
    (AUDIO / "vo.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "teacher"
    asyncio.run(teacher() if which == "teacher" else vo())
