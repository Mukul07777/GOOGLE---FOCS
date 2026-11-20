"""An original, light, upbeat bed for the film, synthesised here (no samples, nothing licensed).

    python buildathon/make_music.py <seconds> <drop seconds> [calm-from seconds]  -> public/bt/music.wav

Am - F - C - G at 116 BPM: a soft pulse and plucked arpeggio in the intro, the full groove from the drop
(the "Meet Focs" moment), thinned out again for the close.
"""
import sys
import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 116
BEAT = 60 / BPM
OUT = Path(__file__).resolve().parents[1] / "public" / "bt" / "music.wav"
rng = np.random.default_rng(3)

CHORDS = [  # (root midi, triad)
    (57, [57, 60, 64]),  # Am
    (53, [53, 57, 60]),  # F
    (48, [48, 52, 55]),  # C
    (55, [55, 59, 62]),  # G
]
hz = lambda m: 440 * 2 ** ((m - 69) / 12)


def env(n, a=0.005, d=0.2, s=0.0, r=0.05):
    t = np.arange(n) / SR
    e = np.where(t < a, t / a, np.exp(-(t - a) / max(d, 1e-4)) * (1 - s) + s)
    tail = int(r * SR)
    if tail and n > tail:
        e[-tail:] *= np.linspace(1, 0, tail)
    return e


def saw(f, n, detune=0.0):
    t = np.arange(n) / SR
    out = np.zeros(n)
    for dt in ([-detune, 0, detune] if detune else [0]):
        ph = (t * f * (1 + dt)) % 1
        out += 2 * ph - 1
    return out / (3 if detune else 1)


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    try:
        from scipy.signal import lfilter
        return lfilter([1 - a], [1, -a], x)
    except ImportError:
        pass
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):  # one-pole: fine for these short notes
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def add(buf, x, at):
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(x))
    buf[i:j] += x[: j - i]


def kick():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 48 + 90 * np.exp(-t * 32)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) * 0.9


def hat(open_=False):
    n = int((0.16 if open_ else 0.05) * SR)
    x = rng.standard_normal(n)
    x = x - lowpass(x, 7000)
    return x * env(n, 0.001, 0.05 if open_ else 0.012) * 0.22


def clap():
    n = int(0.22 * SR)
    x = rng.standard_normal(n)
    x = lowpass(x - lowpass(x, 900), 5000)
    e = env(n, 0.002, 0.07)
    for k in (0.011, 0.022):
        e[int(k * SR):] += env(n - int(k * SR), 0.001, 0.02) * 0.6
    return x * e * 0.35


def pluck(m, dur=0.22):
    n = int(dur * SR)
    x = saw(hz(m), n, 0.004)
    return lowpass(x, 2600) * env(n, 0.003, 0.12, 0.0, 0.03) * 0.16


def pad(notes, dur):
    n = int(dur * SR)
    x = sum(saw(hz(m), n, 0.006) for m in notes) / len(notes)
    x = lowpass(lowpass(x, 1300), 1300)
    a = np.minimum(1, np.arange(n) / (0.4 * SR)) * np.minimum(1, (n - np.arange(n)) / (0.4 * SR))
    return x * a * 0.11


def bass(m, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * hz(m - 12) * t) + 0.25 * np.sin(4 * np.pi * hz(m - 12) * t)
    return x * env(n, 0.004, 0.25, 0.55, 0.04) * 0.30


def main():
    total = float(sys.argv[1])
    drop = float(sys.argv[2])
    calm = float(sys.argv[3]) if len(sys.argv) > 3 else total - 10
    n = int((total + 2) * SR)
    L = np.zeros(n); R = np.zeros(n)
    bar = 4 * BEAT
    k, h, ho, c = kick(), hat(), hat(True), clap()
    side = np.ones(n)  # pumping under the kick
    b = 0
    while b * bar < total + 1:
        t0 = b * bar
        root, triad = CHORDS[b % 4]
        full = drop <= t0 < calm
        intro = t0 < drop
        p = pad([m + 12 for m in triad], bar + 0.4)
        add(L, p, t0); add(R, p * 0.9, t0)
        arp = [triad[0] + 12, triad[1] + 12, triad[2] + 12, triad[1] + 24]
        for s in range(8):
            ts = t0 + s * BEAT / 2
            pl = pluck(arp[s % 4] if (s % 3) else arp[(s + 1) % 4])
            gain = 0.75 if intro else 1.0
            add(L, pl * gain * (0.8 if s % 2 else 1.1), ts); add(R, pl * gain * (1.1 if s % 2 else 0.8), ts + 0.012)
        for q in range(4):
            tb = t0 + q * BEAT
            if full or (intro and t0 >= drop - 2 * bar):
                add(L, k, tb); add(R, k, tb)
                i = int(tb * SR); m = int(0.22 * SR)
                if i < n:
                    side[i:i + m] = np.minimum(side[i:i + m], 0.45 + 0.55 * np.linspace(0, 1, len(side[i:i + m])))
            if full:
                add(L, bass(root, BEAT * 0.45), tb + BEAT / 2); add(R, bass(root, BEAT * 0.45), tb + BEAT / 2)
                add(L, h * 0.9, tb + BEAT / 2); add(R, h, tb + BEAT / 2 + 0.004)
                add(L, h * 0.5, tb + BEAT / 4); add(R, h * 0.5, tb + 3 * BEAT / 4)
                if q in (1, 3):
                    add(L, c, tb); add(R, c, tb + 0.006)
                if q == 3 and b % 4 == 3:
                    add(L, ho, tb + BEAT / 2); add(R, ho, tb + BEAT / 2)
            elif not intro:  # the close: pulse only
                add(L, h * 0.5, tb + BEAT / 2); add(R, h * 0.5, tb + BEAT / 2)
        b += 1
    # a riser into the drop
    rn = int(2 * bar * SR)
    x = rng.standard_normal(rn)
    rise = (x - lowpass(x, 1500)) * np.linspace(0, 1, rn) ** 2.2 * 0.18
    add(L, rise, drop - 2 * bar); add(R, rise, drop - 2 * bar)
    # pads and plucks pump with the kick; kick and claps are already in, so pump only the tonal parts would need
    # separate buses: a gentle overall pump is close enough
    L *= side; R *= side
    mix = np.stack([L, R], 1)[: int(total * SR)]
    fade = int(3 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    mix[: int(0.5 * SR)] *= np.linspace(0, 1, int(0.5 * SR))[:, None]
    mix /= np.abs(mix).max() / 0.85
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    print("wrote", OUT, f"{total:.1f}s")


if __name__ == "__main__":
    main()
