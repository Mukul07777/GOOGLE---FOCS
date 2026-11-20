# Benchmark: how well does "Check my working" find the wrong step?

One day, 40 to 60 real handwritten solutions, labelled by a person before anything is run. The result is a number you
can defend, with its uncertainty.

## 1. Collect (morning)

- Ask students (and for minors, their parents) first, in writing: "We will photograph your rough work to test our
  software. No name, no face. You can say no." Keep the consent notes.
- Photograph the **paper**, flat and well lit, one question per picture. No names, faces or school marks in the
  frame; crop them out if they are. Save as .jpg or .png in one folder.
- Aim for a mix: about a third **right**, a third **slips** (sign, arithmetic, units, misread), a third **gaps**
  (wrong formula, concept or set-up). Do not pick only the cases you expect to work.

## 2. Label (before running)

```bash
python scripts/bench_working.py <folder> --init     # free: writes labels.csv, one row per picture
```
Fill in each row (a spreadsheet is fine, save as CSV): `question` (as printed), `first_wrong` (the number of the first
wrong step as written, one line or equation = one step, or `right`), `kind` (`slip` or `gap`, for wrong ones), and
optionally `options`, `answer`, `chosen`, and `solution` (a correct worked solution).

Rules: two people label independently if you can, and settle disagreements before the run. **Never change a label
after seeing the results.** Re-run `--init` any time to add new pictures; existing rows are never touched.

## 3. Run

```bash
python scripts/bench_working.py <folder>             # one check per picture
python scripts/bench_working.py <folder> --compare   # pictures with a solution are checked twice (with and without)
```
Needs `GEMINI_API_KEY` in `backend/.env` and costs real API credit; `--compare` doubles the calls for rows that have
a `solution`. Output: `results.csv` (every picture) and `summary.md` (the numbers).

## 4. Quote it honestly

- Quote the number with its 95% interval exactly as `summary.md` prints it, e.g. "found the exact wrong step on 31 of
  44 wrong solutions (70%, 95% CI 56-81%)". With under 100 pictures the interval is wide: say so.
- Say what the sample is: how many pictures, how many students, which exam, handwriting on paper, labelled by hand
  before the run. Do not call it "accuracy" without saying what was measured.
- Quote "right working called right" (no false alarms) next to it; a checker that flags everything scores well on
  finding errors.
- With `--compare`, the gap between the two lines is what the reference solution adds.
- Report pictures it could not read, and do not drop them from the count.
