"""How well does "Check my working" find the wrong step? Measured on real handwritten solutions, labelled by a person.

    python scripts/bench_working.py <folder> --init                 # list the pictures in labels.csv, free
    python scripts/bench_working.py <folder> [--exam jee] [--limit N] [--compare]

The folder holds the pictures (photos of paper, or rough-pad pages saved from a tablet: .jpg .jpeg .png .webp) and a
labels.csv written by hand, one row per picture:

    file,question,options,answer,chosen,first_wrong,kind[,solution]
    torque1.jpg,"A 10 N force acts at 30° on a 2 m spanner. Torque?","10 N m|17.3 N m|20 N m|5 N m",A,B,2,gap
    ohm3.png,"Current through 3 Ω and 6 Ω in parallel across 12 V?",,,,3,slip
    proj2.jpg,"Range of a projectile at 15 m/s, 30°?",,,,right,

  question     the question as printed (the checker gets nothing else from you)
  options      optional, separated by |
  answer       optional: the correct option letter (A-D)
  chosen       optional: the option the student picked
  first_wrong  the number of the first wrong step as the student wrote it (1 = first line of working), or "right",
               or "wrong" when the working has a mistake but nobody marked which line (counts only for "caught")
  solution     optional: a correct worked solution (the app passes one when it has it; measure both ways)
  kind         for a wrong solution: "slip" (sign, arithmetic, units, misread) or "gap" (concept, formula, set-up)

Counting steps the way the checker does: one line or one equation of working is one step. Label before you run it,
and don't change labels after seeing the results: that's what makes the number honest.

--init adds one row per new picture to labels.csv (file filled in, the rest blank for you) and never touches rows
that are already there. --compare runs every picture that has a solution twice, with and without it, so you can say
what the reference solution adds: it DOUBLES the API calls for those pictures.

Pictures are checked the way the app checks them: a .png as a page from the tablet rough pad, anything else as a phone
photo of paper (--source pad|photo makes every picture one or the other).

A second, public test set: FERMAT (AI4Bharat, ACL 2025, CC BY 4.0), about 2,200 photos of handwritten maths solutions,
grades 7-12, each with the correct solution. It says whether a solution has a real mistake, not which line, so it
measures "caught the mistake" and "no false alarm", not the exact step. Accept its terms at
huggingface.co/datasets/ai4bharat/FERMAT, download its .parquet files, `pip install pyarrow`, then:

    python scripts/bench_working.py <new folder> --from-fermat <a .parquet file or a folder of them> --sample 100
    python scripts/bench_working.py <new folder> --compare

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


HEADER = ["file", "question", "options", "answer", "chosen", "first_wrong", "kind", "solution"]


def init_labels(folder: Path) -> int:
    """Adds a row for each picture in the folder that labels.csv doesn't list yet. Existing rows are never changed."""
    labels = folder / "labels.csv"
    known, header = set(), HEADER
    if labels.exists():
        with labels.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or HEADER
            known = {(r.get("file") or "").strip() for r in reader}
    new = sorted(p.name for p in folder.iterdir() if p.suffix.lower() in PICTURES and p.name not in known)
    exists = labels.exists() and labels.stat().st_size > 0
    with labels.open("a", newline="", encoding="utf-8") as f:
        if exists:  # make sure the last row ended its line before adding ours
            raw = labels.read_bytes()
            if not raw.endswith(b"\n"):
                f.write("\r\n")
        w = csv.writer(f)
        if not exists:
            w.writerow(header)
        for name in new:
            w.writerow([name if col == "file" else "" for col in header])
    return len(new)


def fermat_to_folder(records, folder: Path, sample: int = 0, seed: int = 7) -> int:
    """FERMAT records (dicts with orig_q, orig_a, image, has_error) → pictures + labels.csv in ``folder``.

    ``has_error`` False means the change made to the solution is only superficial (16 cm vs 16.0 cm): that working is
    right. The image is the dataset's {"bytes": ...} cell or raw bytes. A fixed seed keeps a sample the same each time.
    """
    import random

    records = [r for r in records if r.get("image") and r.get("orig_q")]
    if sample and sample < len(records):
        records = random.Random(seed).sample(records, sample)
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "labels.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for n, r in enumerate(records, 1):
            image = r["image"]["bytes"] if isinstance(r["image"], dict) else r["image"]
            name = f"fermat{n:04d}.jpg"
            (folder / name).write_bytes(vision.to_jpeg(image))
            w.writerow([name, r["orig_q"], "", "", "", "wrong" if r.get("has_error") else "right", "", r.get("orig_a") or ""])
    return len(records)


def _read_fermat(src: Path) -> list[dict]:
    try:
        import pyarrow.parquet as pq
    except ImportError:
        sys.exit("Reading FERMAT needs pyarrow: pip install pyarrow")
    files = sorted(src.rglob("*.parquet")) if src.is_dir() else [src]
    cols = ["orig_q", "orig_a", "image", "has_error"]
    return [row for p in files for row in pq.read_table(p, columns=cols).to_pylist()]


def _source(picture: Path, forced: str | None) -> str:
    return forced or ("pad" if picture.suffix.lower() == ".png" else "photo")


def _check(row: dict, picture: Path, student, options: list[str], source: str = "photo"):
    """One check of one picture. Returns (what the checker read or None, the error text)."""
    try:
        data = vision.read_json([vision.to_jpeg(picture.read_bytes())],
                                working._prompt(student, row["question"], options, _letter(row.get("answer", "")),
                                                _letter(row.get("chosen", "")), [], row.get("solution") or None,
                                                source=source),
                                "working_bench", max_tokens=2400)
        return working._read(data, []), ""
    except (working.WorkingError, LLMUnavailable, ValueError) as exc:
        return None, str(exc)


def _said(read) -> str:
    return "unreadable" if read is None else ("right" if read["first_wrong"] is None else str(read["first_wrong"] + 1))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("folder", type=Path)
    ap.add_argument("--exam", default="jee")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--init", action="store_true", help="write/extend labels.csv with the pictures found, then stop (free)")
    ap.add_argument("--compare", action="store_true",
                    help="run rows that have a solution twice, with and without it (double the API cost for them)")
    ap.add_argument("--source", choices=["pad", "photo"], default=None,
                    help="check every picture as a rough-pad page or a paper photo (default: .png = pad, else photo)")
    ap.add_argument("--from-fermat", type=Path, default=None, metavar="PARQUET",
                    help="turn FERMAT .parquet file(s) into pictures + labels.csv in the folder, then stop (free)")
    ap.add_argument("--sample", type=int, default=0, help="with --from-fermat: keep this many, picked at random (fixed seed)")
    args = ap.parse_args()
    if args.from_fermat:
        n = fermat_to_folder(_read_fermat(args.from_fermat), args.folder, args.sample)
        print(f"{n} FERMAT solutions written to {args.folder}. Now run the benchmark on that folder.")
        return
    if args.init:
        if not args.folder.is_dir():
            sys.exit(f"{args.folder} is not a folder")
        print(f"labels.csv: {init_labels(args.folder)} new pictures added. Fill in the blanks before running the benchmark.")
        return
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
        if not (row.get("question") or "").strip() or not (row.get("first_wrong") or "").strip():
            print(f"[{n}/{len(rows)}] {row['file']}: question or first_wrong not filled in, skipped")
            continue
        options = [o.strip() for o in (row.get("options") or "").split("|") if o.strip()]
        truth = (row.get("first_wrong") or "").strip().lower()
        kind = (row.get("kind") or "").strip().lower()
        start = time.perf_counter()
        source = _source(picture, args.source)
        read, error = _check(row, picture, student, options, source)
        seconds.append(time.perf_counter() - start)
        said = _said(read)
        said_kind = "" if not read or not read["error_type"] else ("slip" if read["error_type"] in working.CARELESS else "gap")
        rec = {"file": row["file"], "truth": truth, "said": said, "truth_kind": kind, "said_kind": said_kind,
               "verdict_ok": int(read is not None and (truth == "right") == (read["first_wrong"] is None)),
               "step_exact": int(said == truth), "step_within_1": int(said.isdigit() and truth.isdigit() and abs(int(said) - int(truth)) <= 1),
               "kind_ok": int(bool(kind) and kind == said_kind), "steps_read": len(read["steps"]) if read else 0,
               "seconds": round(seconds[-1], 1), "error": error}
        if args.compare and (row.get("solution") or "").strip():
            bare, _ = _check({**row, "solution": ""}, picture, student, options, source)  # the same picture, no solution
            rec["said_no_solution"] = _said(bare)
            rec["step_exact_no_solution"] = int(_said(bare) == truth)
            rec["verdict_ok_no_solution"] = int(bare is not None and (truth == "right") == (bare["first_wrong"] is None))
        out.append(rec)
        print(f"[{n}/{len(rows)}] {row['file']}: truth {truth or '?'} / said {said}"
              f"{' ✓' if rec['step_exact'] else ''}  {kind or ''}{'/' + said_kind if said_kind else ''}  {rec['seconds']}s")

    if not out:
        sys.exit("Nothing was checked.")
    with (args.folder / "results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in out for k in r)), restval="")
        w.writeheader()
        w.writerows(out)
    wrong = [r for r in out if r["truth"].isdigit()]
    mistakes = [r for r in out if r["truth"].isdigit() or r["truth"] == "wrong"]
    right = [r for r in out if r["truth"] == "right"]
    kinds = [r for r in wrong if r["truth_kind"] in ("slip", "gap")]
    both = [r for r in wrong if "step_exact_no_solution" in r]
    both_m = [r for r in mistakes if "verdict_ok_no_solution" in r]
    compare = ([f"- With a reference solution vs without, on the {len(both)} wrong pictures that have one: exact wrong step "
                f"{_share(sum(r['step_exact'] for r in both), len(both))} with, "
                f"{_share(sum(r['step_exact_no_solution'] for r in both), len(both))} without"] if both else []) + (
               [f"- Same, caught that the working has a mistake ({len(both_m)} pictures): "
                f"{_share(sum(r['verdict_ok'] for r in both_m), len(both_m))} with, "
                f"{_share(sum(r['verdict_ok_no_solution'] for r in both_m), len(both_m))} without"] if both_m else [])
    lines = [
        f"# Check my working: measured on {len(out)} real handwritten solutions",
        "",
        f"- **Found the exact wrong step:** {_share(sum(r['step_exact'] for r in wrong), len(wrong))}",
        f"- Within one step: {_share(sum(r['step_within_1'] for r in wrong), len(wrong))}",
        f"- Caught that the working has a mistake: {_share(sum(r['verdict_ok'] for r in mistakes), len(mistakes))}",
        f"- Right working called right (no false alarm): {_share(sum(r['verdict_ok'] for r in right), len(right))}",
        f"- Slip told apart from a gap in an idea: {_share(sum(r['kind_ok'] for r in kinds), len(kinds))}",
        f"- Couldn't read the page: {sum(1 for r in out if r['said'] == 'unreadable')} of {len(out)}",
        *compare,
        f"- Time per check: median {statistics.median(seconds):.1f} s, slowest {max(seconds):.1f} s",
        "",
        "Labels were written by hand before the run. Model: the image models in backend/.env, in order: "
        + ", ".join(vision.models()) + ".",
    ]
    (args.folder / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
