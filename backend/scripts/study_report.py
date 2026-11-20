"""The learning study's results: what the Focs group and the comparison group scored, right after the lecture and the
next day, with the uncertainty and the limitations stated next to the numbers.

    python scripts/study_report.py ../docs/evidence/study_results.csv

The CSV has one row per student: participant, group (focs | control), immediate, next_day (scores out of 6; leave
next_day empty for anyone who missed it). See docs/evidence/LEARNING_STUDY.md for how the study is run.
Plain Python on purpose: anyone can check the arithmetic.
"""
from __future__ import annotations

import csv
import math
import statistics
import sys
from pathlib import Path

MAX_SCORE = 6

# two-sided 95% critical values of Student's t, by degrees of freedom (beyond 30, 1.96 is close enough)
T95 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23, 11: 2.20, 12: 2.18,
       13: 2.16, 14: 2.14, 15: 2.13, 16: 2.12, 17: 2.11, 18: 2.10, 19: 2.09, 20: 2.09, 22: 2.07, 24: 2.06, 26: 2.06,
       28: 2.05, 30: 2.04}


def t95(df: float) -> float:
    if df >= 30:
        return 1.96 if df > 60 else 2.0
    d = max(1, int(df))  # rounding df down is the cautious choice: a wider interval
    while d not in T95:
        d -= 1
    return T95[d]


def load(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if not (r.get("participant") or "").strip():
                continue
            group = (r.get("group") or "").strip().lower()
            if group not in ("focs", "control"):
                raise SystemExit(f"participant {r['participant']}: group must be focs or control, not {group!r}")
            score = lambda k: float(r[k]) if (r.get(k) or "").strip() else None  # noqa: E731
            row = {"participant": r["participant"].strip(), "group": group, "immediate": score("immediate"), "next_day": score("next_day")}
            for k in ("immediate", "next_day"):
                if row[k] is not None and not 0 <= row[k] <= MAX_SCORE:
                    raise SystemExit(f"participant {row['participant']}: {k} {row[k]} is outside 0..{MAX_SCORE}")
            rows.append(row)
    return rows


def compare(focs: list[float], control: list[float]) -> dict | None:
    """Mean difference (Focs minus control) with a Welch 95% interval and Cohen's d. None if a group has under 2."""
    if len(focs) < 2 or len(control) < 2:
        return None
    m1, m2 = statistics.mean(focs), statistics.mean(control)
    v1, v2 = statistics.variance(focs), statistics.variance(control)
    n1, n2 = len(focs), len(control)
    se = math.sqrt(v1 / n1 + v2 / n2)
    df = (v1 / n1 + v2 / n2) ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)) if se else n1 + n2 - 2
    pooled = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    diff = m1 - m2
    half = t95(df) * se
    return {"focs_mean": m1, "control_mean": m2, "focs_sd": math.sqrt(v1), "control_sd": math.sqrt(v2), "n_focs": n1, "n_control": n2,
            "diff": diff, "ci": (diff - half, diff + half), "d": diff / pooled if pooled else None, "df": df}


def limitations(rows: list[dict]) -> list[str]:
    notes = []
    n = len(rows)
    groups = {g: sum(r["group"] == g for r in rows) for g in ("focs", "control")}
    if n < 12:
        notes.append(f"Only {n} students: far too few to generalise; treat this as a pilot.")
    else:
        notes.append(f"{n} students is a small sample: the interval shows how much the result could move.")
    if abs(groups["focs"] - groups["control"]) > 2:
        notes.append(f"The groups are uneven ({groups['focs']} with Focs, {groups['control']} without).")
    missed = sum(r["next_day"] is None for r in rows)
    if missed:
        notes.append(f"{missed} students missed the next-day test; the next-day numbers leave them out.")
    notes.append("One lecture, one topic, one test of 6 questions: it says nothing about other subjects or long-term use.")
    notes.append("Students knew which group they were in, and the Focs group also got novelty; neither can be ruled out.")
    return notes


def report(rows: list[dict]) -> str:
    out = [f"| Learning study ({len(rows)} students, scores out of {MAX_SCORE}) | With Focs | Without | Difference (95% interval) | Effect size d |",
           "|---|---|---|---|---|"]
    for k, label in (("immediate", "Right after the lecture"), ("next_day", "Next day")):
        f = [r[k] for r in rows if r["group"] == "focs" and r[k] is not None]
        c = [r[k] for r in rows if r["group"] == "control" and r[k] is not None]
        res = compare(f, c)
        if res is None:
            out.append(f"| {label} | n={len(f)} | n={len(c)} | not enough students | |")
            continue
        lo, hi = res["ci"]
        d = f"{res['d']:.2f}" if res["d"] is not None else "n/a"
        out.append(f"| {label} | {res['focs_mean']:.2f} ± {res['focs_sd']:.2f} (n={res['n_focs']}) | {res['control_mean']:.2f} ± {res['control_sd']:.2f} "
                   f"(n={res['n_control']}) | {res['diff']:+.2f} ({lo:+.2f} to {hi:+.2f}) | {d} |")
    out.append("")
    out.append("± is the standard deviation. If the interval includes 0, this study can't tell the groups apart.")
    out.append("")
    out.append("Limitations:")
    out.extend(f"- {n}" for n in limitations(rows))
    return "\n".join(out)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print(report(load(Path(sys.argv[1]))))


if __name__ == "__main__":
    main()
