"""How well does "Check my working" find the wrong step? Measured on real handwritten solutions, labelled by a person.

    python scripts/bench_working.py <folder> [--exam jee] [--limit N]

The folder holds the pictures (photos of paper, or rough-pad pages saved from a tablet: .jpg .jpeg .png .webp) and a
labels.csv written by hand, one row per picture:

    file,question,options,answer,chosen,first_wrong,kind
    torque1.jpg,"A 10 N force acts at 30° on a 2 m spanner. Torque?","10 N m|17.3 N m|20 N m|5 N m",A,B,2,gap
    ohm3.png,"Current through 3 Ω and 6 Ω in parallel across 12 V?",,,,3,slip
    proj2.jpg,"Range of a projectile at 15 m/s, 30°?",,,,right,

  question     the question as printed (the checker gets nothing else from you)
  options      optional, separated by |
  answer       optional: the correct option letter (A-D)
  chosen       optional: the option the student picked
  first_wrong  the number of the first wrong step as the student wrote it (1 = first line of working), or "right"
  kind         for a wrong solution: "slip" (sign, arithmetic, units, misread) or "gap" (concept, formula, set-up)

Counting steps the way the checker does: one line or one equation of working is one step. Label before you run it,
and don't change labels after seeing the results: that's what makes the number honest.

Writes results.csv (every picture: what the checker said, right or not) and summary.md (the numbers for the pitch) in
the same folder. Uses the image models in backend/.env (GOOGLE_ONLY / VISION_MODEL), and costs real API credit.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import vision, working  # noqa: E402
from app.services.llm import LLMUnavailable  # noqa: E402

PICTURES = (".jpg", ".jpeg", ".png", ".webp")


def _letter(value: str) -> int | None:
    v = (value or "").strip().upper()
    return "ABCDEF".index(v) if len(v) == 1 and v in "ABCDEF" else None


def _wilson(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% interval for a share, honest at small n (Wilson score)."""
    if not n:
        return 0.0, 0.0
    p = hits / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def _share(hits: int, n: int) -> str:
    if not n:
        return "–"
    lo, hi = _wilson(hits, n)
    return f"{hits}/{n} = {100 * hits / n:.0f}% (95% CI {100 * lo:.0f}–{100 * hi:.0f}%)"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("folder", type=Path)
    ap.add_argument("--exam", default="jee")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    labels = args.folder / "labels.csv"
    if not labels.exists():
        sys.exit(f"No {labels}: see the top of this script for its columns.")
    if not vision.available():
        sys.exit("No image model: set GEMINI_API_KEY in backend/.env")
    rows = list(csv.DictReader(labels.open(encoding="utf-8-sig")))
    if args.limit:
        rows = rows[: args.limit]
    student = SimpleNamespace(exam_target=args.exam)
    out, seconds = [], []
    for n, row in enumerate(rows, 1):
        picture = args.folder / row["file"].strip()
        if picture.suffix.lower() not in PICTURES or not picture.exists():
            print(f"[{n}/{len(rows)}] {row['file']}: missing or not a picture, skipped")
            continue
        options = [o.strip() for o in (row.get("options") or "").split("|") if o.strip()]
        truth = (row.get("first_wrong") or "").strip().lower()
        kind = (row.get("kind") or "").strip().lower()
        start = time.perf_counter()
        try:
            data = vision.read_json([vision.to_jpeg(picture.read_bytes())],
                                    working._prompt(student, row["question"], options, _letter(row.get("answer", "")),
                                                    _letter(row.get("chosen", "")), []),
                                    "working_bench", max_tokens=2400)
            read = working._read(data, [])
            error = ""
        except (working.WorkingError, LLMUnavailable, ValueError) as exc:
            read, error = None, str(exc)
        seconds.append(time.perf_counter() - start)
        said = "unreadable" if read is None else ("right" if read["first_wrong"] is None else str(read["first_wrong"] + 1))
        said_kind = "" if not read or not read["error_type"] else ("slip" if read["error_type"] in working.CARELESS else "gap")
        rec = {"file": row["file"], "truth": truth, "said": said, "truth_kind": kind, "said_kind": said_kind,
               "verdict_ok": int(read is not None and (truth == "right") == (read["first_wrong"] is None)),
               "step_exact": int(said == truth), "step_within_1": int(said.isdigit() and truth.isdigit() and abs(int(said) - int(truth)) <= 1),
               "kind_ok": int(bool(kind) and kind == said_kind), "steps_read": len(read["steps"]) if read else 0,
               "seconds": round(seconds[-1], 1), "error": error}
        out.append(rec)
        print(f"[{n}/{len(rows)}] {row['file']}: truth {truth or '?'} / said {said}"
              f"{' ✓' if rec['step_exact'] else ''}  {kind or ''}{'/' + said_kind if said_kind else ''}  {rec['seconds']}s")

    if not out:
        sys.exit("Nothing was checked.")
    with (args.folder / "results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    wrong = [r for r in out if r["truth"].isdigit()]
    right = [r for r in out if r["truth"] == "right"]
    kinds = [r for r in wrong if r["truth_kind"] in ("slip", "gap")]
    lines = [
        f"# Check my working: measured on {len(out)} real handwritten solutions",
        "",
        f"- **Found the exact wrong step:** {_share(sum(r['step_exact'] for r in wrong), len(wrong))}",
        f"- Within one step: {_share(sum(r['step_within_1'] for r in wrong), len(wrong))}",
        f"- Right working called right (no false alarm): {_share(sum(r['verdict_ok'] for r in right), len(right))}",
        f"- Slip told apart from a gap in an idea: {_share(sum(r['kind_ok'] for r in kinds), len(kinds))}",
        f"- Couldn't read the page: {sum(1 for r in out if r['said'] == 'unreadable')} of {len(out)}",
        f"- Time per check: median {statistics.median(seconds):.1f} s, slowest {max(seconds):.1f} s",
        "",
        "Labels were written by hand before the run. Model: the image models in backend/.env, in order: "
        + ", ".join(vision.models()) + ".",
    ]
    (args.folder / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
