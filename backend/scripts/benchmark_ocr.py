"""End-to-end OCR benchmark on full lecture frames (detection + recognition).

    python scripts/benchmark_ocr.py [--bench ../ml/data/bench]               synthetic scenes
    python scripts/benchmark_ocr.py --set real --bench ../ml/data/real       real frames and board photos
    python scripts/benchmark_ocr.py --draft ../ml/data/real                  pre-fill labels for a new folder

Synthetic scenes come from `python -m focs_ocr.scenes` (held-out seed); results go to app/assets/ocr/benchmark.json.
A real set (frames from openly licensed lectures, photos of classroom boards) goes to benchmark_<set>.json, so it never
replaces the synthetic numbers, and is reported next to them in the OCR Lab: FocsOCR, PP-OCR and both combined ("auto").

labels.json is a list of {"file", "lines": [...], "style"}; a real set also gives each frame "source" (a URL) and
"licence" (e.g. "CC BY-NC-SA 4.0"), which are counted in the results so anyone can check them. --draft runs the
engines on every image in the folder and writes labels.draft.json: correct every line by hand (it is the OCR's guess,
so scoring against it uncorrected would only measure agreement with itself), then save it as labels.json.

Whitespace is ignored when scoring: spacing inside formulas ("F=ma" vs "F = ma") is ambiguous and not what students
care about.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.services.ocr import ocr_engine  # noqa: E402

FOLD = {"−": "-", "–": "-", "—": "-", "∆": "Δ", "△": "Δ", "µ": "μ", "’": "'", "‘": "'"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    return "".join(FOLD.get(c, c) for c in s if not c.isspace())


def lev(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def analyze(bench: Path, labels: list[dict]) -> None:
    """Per detected line: is FocsOCR right, is PP-OCRv4 right, and with what confidence?
    Grid-search the selection rule on half the scenes; report accuracy on the other half."""
    from app.services.ocr.engine import OcrEngine

    rows = []
    for k, item in enumerate(labels):
        img = np.asarray(Image.open(bench / item["file"]).convert("RGB"))
        gts = [norm(l) for l in item["lines"]]
        res = ocr_engine.run(img, "auto", keep_candidates=True)
        for line in res.lines:
            f, r = line.candidates["focs"], line.candidates["rapid"]
            ref = min(gts, key=lambda g: min(lev(norm(f["text"]), g), lev(norm(r["text"]), g)))
            rows.append((k % 2, f["text"], f["confidence"], norm(f["text"]) == ref, r["text"], r["confidence"], norm(r["text"]) == ref))

    def accuracy(subset, margin, bonus):
        ok = sum((fok if OcrEngine._pick((tf, cf), (tr, cr), margin, bonus)[2] == "focs" else rok)
                 for _, tf, cf, fok, tr, cr, rok in subset)
        return ok / max(1, len(subset))

    fit = [r for r in rows if r[0] == 0]
    held = [r for r in rows if r[0] == 1]
    grid = [(m / 100, b) for m in range(-30, 31, 2) for b in (0.0, 0.04, 0.08, 0.12, 0.2)]
    margin, bonus = max(grid, key=lambda g: accuracy(fit, *g))
    n = max(1, len(held))
    print(f"lines={len(rows)} (fit {len(fit)} / held-out {len(held)})")
    print(f"held-out exact-line accuracy: FocsOCR only {sum(r[3] for r in held) / n:.3f} | "
          f"PP-OCRv4 only {sum(r[6] for r in held) / n:.3f} | oracle {sum(r[3] or r[6] for r in held) / n:.3f}")
    print(f"  current rule  : {accuracy(held, settings.OCR_ENSEMBLE_MARGIN, settings.OCR_MATH_BONUS):.3f}")
    print(f"  fitted rule   : {accuracy(held, margin, bonus):.3f}   (margin={margin:+.2f}, math_bonus={bonus:.2f})")
    print(f"set in backend/.env:  OCR_ENSEMBLE_MARGIN={margin}  OCR_MATH_BONUS={bonus}")


IMAGES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def draft(folder: Path) -> None:
    """A first guess at labels for every image in `folder`, for a person to correct line by line."""
    known = {}
    if (folder / "labels.json").exists():
        known = {item["file"]: item for item in json.loads((folder / "labels.json").read_text(encoding="utf-8"))}
    out = []
    for f in sorted(p for p in folder.rglob("*") if p.suffix.lower() in IMAGES):
        rel = f.relative_to(folder).as_posix()
        if rel in known:
            out.append(known[rel])
            continue
        res = ocr_engine.run(np.asarray(Image.open(f).convert("RGB")), "auto")
        style = "photo" if any(w in rel.lower() for w in ("photo", "camera", "class")) else "screen"
        out.append({"file": rel, "lines": [l.text for l in res.lines], "style": style, "source": "", "licence": "", "checked": False})
    path = folder / "labels.draft.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    todo = sum(1 for item in out if not item.get("checked", True))
    print(f"wrote {path}: {len(out)} images, {todo} to correct by hand (set \"checked\": true on each), then save as labels.json")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default=str(Path(__file__).resolve().parents[2] / "ml" / "data" / "bench"))
    ap.add_argument("--set", default="synthetic", help="name of the frame set: synthetic, or e.g. real (its own results file)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--analyze", action="store_true", help="fit the ensemble selection rule instead of scoring")
    ap.add_argument("--draft", metavar="FOLDER", help="write labels.draft.json for the images in FOLDER and stop")
    ap.add_argument("--out", help="results folder (default: the OCR model folder, which the OCR Lab reads)")
    args = ap.parse_args(argv)
    if args.draft:
        return draft(Path(args.draft))
    bench = Path(args.bench)
    labels = json.loads((bench / "labels.json").read_text(encoding="utf-8"))
    real = args.set != "synthetic"
    if real:
        unchecked = [item["file"] for item in labels if item.get("checked") is False]
        if unchecked:
            sys.exit(f"{len(unchecked)} frames are still the OCR's own draft (checked: false), e.g. {unchecked[0]}. Correct them first.")
        missing = [item["file"] for item in labels if not item.get("licence") or not item.get("source")]
        if missing:
            print(f"warning: {len(missing)} frames have no source or licence, e.g. {missing[0]}")
    if args.limit:
        labels = labels[: args.limit]

    if args.analyze:
        return analyze(bench, labels)

    status = ocr_engine.status()
    engines = status["engines"]
    stats = {e: {"err": 0, "tot": 0, "lines_ok": 0, "lines": 0, "ms": 0.0} for e in engines}
    by_style: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    examples = []

    for k, item in enumerate(labels):
        img = np.asarray(Image.open(bench / item["file"]).convert("RGB"))
        gt_lines = [norm(l) for l in item["lines"]]
        gt = "".join(gt_lines)
        for eng in engines:
            t0 = time.perf_counter()
            res = ocr_engine.run(img, eng)
            stats[eng]["ms"] += (time.perf_counter() - t0) * 1000
            pred_lines = [norm(l.text) for l in res.lines]
            e = lev("".join(pred_lines), gt)
            stats[eng]["err"] += e
            stats[eng]["tot"] += len(gt)
            by_style[item.get("style", "real")][eng][0] += e
            by_style[item.get("style", "real")][eng][1] += len(gt)
            for g in gt_lines:
                stats[eng]["lines"] += 1
                stats[eng]["lines_ok"] += int(g in pred_lines)
            if eng == "auto" and k < 6:
                examples.append({"gt": item["lines"], "pred": [l.text for l in res.lines]})
        if (k + 1) % 40 == 0:
            print(f"  {k + 1}/{len(labels)} frames")

    n = len(labels)
    out = {
        "set": args.set,
        "generated": date.today().isoformat(),
        "images": n,
        "lines": stats[engines[0]]["lines"] if engines else 0,
        "cer_ignores_spaces": True,
        "engines": {e: {"cer": round(s["err"] / max(1, s["tot"]), 4), "line_acc": round(s["lines_ok"] / max(1, s["lines"]), 4),
                        "wer": None, "ms_per_image": round(s["ms"] / max(1, n), 1)} for e, s in stats.items()},
        "by_style": {st: {e: round(v[0] / max(1, v[1]), 4) for e, v in d.items()} for st, d in sorted(by_style.items())},
        "examples": examples,
    }
    if real:
        out["licences"] = dict(Counter(item.get("licence") or "unknown" for item in labels).most_common())
        out["sources"] = len({item.get("source") for item in labels if item.get("source")})
    path = Path(args.out or settings.OCR_MODEL_DIR) / ("benchmark.json" if not real else f"benchmark_{args.set}.json")
    if args.limit:  # partial runs are for quick checks only; never replace the published numbers
        print(json.dumps(out["engines"], indent=2))
        print("(--limit run: benchmark.json left unchanged)")
        return
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({e: v for e, v in out["engines"].items()}, indent=2))
    print(json.dumps(out["by_style"], indent=2))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
