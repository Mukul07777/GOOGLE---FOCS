# Evidence: three real numbers

The pitch should claim only what has been measured. Three measurements back it, and each has a tool in this repo.
Measure on the same build you demo, write down the date, and paste the tables the tools print as they are.

| Number | Tool | Needs |
|---|---|---|
| 1. How well Focs reads **real** boards | `backend/scripts/benchmark_ocr.py --set real` | 60–100 labelled frames (below) |
| 2. Whether students **learn more** with it | `backend/scripts/study_report.py` | 12–20 students, one afternoon and the next day ([LEARNING_STUDY.md](LEARNING_STUDY.md)) |
| 3. How fast and how cheap the **demo** is | `backend/scripts/demo_metrics.py drive` and `cost` | a running Focs with the demo's AI key |

## 1. Real-board OCR benchmark

The published benchmark uses synthetic frames. These steps measure real ones.

1. **Collect** 60–100 frames from openly licensed lectures, plus 20–30 photos of real classroom boards.
   - Lectures: NPTEL and MIT OpenCourseWare publish under Creative Commons. Check each video's licence and keep its URL.
   - Board photos: only boards you may photograph, with no students' faces in the frame.
   - Put them in `ml/data/real/`, in sub-folders such as `screen/` and `photo/`. Images stay out of git.
2. **Draft the labels:**
   ```
   cd backend
   .venv\Scripts\python scripts\benchmark_ocr.py --draft ..\ml\data\real
   ```
   This writes `labels.draft.json`, with Focs's own guess at every line.
3. **Correct every line by hand.**
   - Type exactly what is on the board.
   - Fill in `source` (URL) and `licence`, then set `"checked": true`.
   - Save the file as `labels.json`.
   - The benchmark refuses to score frames still marked `"checked": false`. Scored uncorrected, the OCR would only be agreeing with itself.
4. **Score:**
   ```
   .venv\Scripts\python scripts\benchmark_ocr.py --set real --bench ..\ml\data\real
   ```
   This writes `app/assets/ocr/benchmark_real.json`. The OCR Lab shows it as "Real boards", next to the synthetic results.
   - It reports FocsOCR, PP-OCR and both combined (`auto`), broken down by style (screen or photo).
   - It also lists how many frames come under each licence.
5. **Report honestly.**
   - If FocsOCR loses to PP-OCR on real boards, say so. Focs uses both combined by default.
   - Then retrain with `ml/focs_ocr/train.py` on real plus synthetic data. Keep a held-out part of the real frames out of training, and report the before and after numbers.

## 2. Learning study

See [LEARNING_STUDY.md](LEARNING_STUDY.md) for the protocol, consent text, test template and analysis.

## 3. Demo numbers

Run these on the hosted demo with its real AI key, after a rehearsal:

```
cd backend
.venv\Scripts\python scripts\demo_metrics.py drive --url https://your-demo-host --boards 6 --audio teacher-25s.webm
.venv\Scripts\python scripts\demo_metrics.py cost --days 7
```

- **`drive`** plays a scripted lecture the way the browser does: a frame every 5 s, and a settle once the board is still. It times:
  - a new board to its notes;
  - the teacher's last line to the final notes. This includes the deliberate wait for the board to settle (20 s by default), which saves most AI calls.
  - with `--audio`, the teacher speaking to the caption.
- **`cost`** reads the cost ledger and divides what the AI calls cost during real live lectures by those lectures' hours. Only lectures of 5 minutes or more are counted. Run some real lectures first.

Measured locally on 2026-10-18 with the AI off (offline notes, OCR only), as a floor:
- a new board to its notes: median 2.6 s;
- the last line to the final notes: 25.5 s (20 s of that is the settle wait).

Re-measure with the AI on before quoting any number.
