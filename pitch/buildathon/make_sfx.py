"""Small sound effects for the film, synthesised here: whoosh, pop, tick, buzz (wrong), ding (right), snap (camera).

    python buildathon/make_sfx.py   -> public/bt/sfx/<name>.wav
"""
import wave
from pathlib import Path

import numpy as np

SR = 44100
OUT = Path(__file__).resolve().parents[1] / "public" / "bt" / "sfx"
rng = np.random.default_rng(11)


def lp(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    from scipy.signal import lfilter
    return lfilter([1 - a], [1, -a], x)


def save(name, x, gain=0.8):
    x = x / (np.abs(x).max() + 1e-9) * gain
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def t(sec):
    return np.arange(int(sec * SR)) / SR


def main():
    # whoosh: band-passed noise sweeping up then down
    n = t(0.55); x = rng.standard_normal(len(n))
    sweep = 400 + 5000 * np.sin(np.pi * n / n[-1]) ** 2
    y = np.zeros_like(x); acc = 0.0
    for i in range(len(x)):
        a = np.exp(-2 * np.pi * sweep[i] / SR); acc = (1 - a) * x[i] + a * acc; y[i] = acc
    y = y - lp(y, 300)
    save("whoosh", y * np.sin(np.pi * n / n[-1]) ** 1.5, 0.55)
    # pop: a quick pitched blip
    n = t(0.12); f = 900 * np.exp(-n * 18) + 300
    save("pop", np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-n * 38), 0.6)
    # tick: a tiny click
    n = t(0.04); save("tick", rng.standard_normal(len(n)) * np.exp(-n * 160), 0.35)
    # buzz: wrong answer, two low square-ish tones
    n = t(0.32); s = np.sign(np.sin(2 * np.pi * 150 * n)) * 0.5 + np.sin(2 * np.pi * 155 * n)
    e = np.exp(-n * 6) * (n < 0.14) + np.exp(-(n - 0.16) * 7) * (n >= 0.16) * 0.9
    save("buzz", lp(s * e, 1800), 0.5)
    # ding: right answer / proof, a bright two-note chime
    n = t(1.2)
    ding = sum(np.sin(2 * np.pi * f0 * k * n) * np.exp(-n * (3 + k * 2)) / k for f0 in (1318.5,) for k in (1, 2, 3))
    ding2 = np.concatenate([np.zeros(int(0.09 * SR)), (sum(np.sin(2 * np.pi * 1760 * k * n) * np.exp(-n * (3 + k * 2)) / k for k in (1, 2, 3)))[: len(n) - int(0.09 * SR)]])
    save("ding", ding + ding2, 0.5)
    # snap: camera shutter
    n = t(0.18); x = rng.standard_normal(len(n))
    s = (x - lp(x, 2000)) * (np.exp(-n * 60) + 0.7 * np.exp(-np.maximum(n - 0.07, 0) * 70) * (n > 0.07))
    save("snap", s, 0.55)
    # rise: a short tension riser into a reveal
    n = t(1.4); x = rng.standard_normal(len(n))
    save("rise", (x - lp(x, 2500)) * (n / n[-1]) ** 2.5, 0.45)
    print("wrote", sorted(p.name for p in OUT.glob("*.wav")))


if __name__ == "__main__":
    main()
