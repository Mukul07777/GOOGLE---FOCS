# Progress (20 Nov 2026): the Google hackathon edition

Focs finds the step, and the year, where a student's understanding broke: it reads their handwritten working, marks
the first wrong step, tells a careless slip from a gap in an idea, traces the gap to the earlier-class idea it rests
on, fixes it in five minutes, and proves the fix with a retest.

## Done on `main`
- **Root cause and the Gap Genome** (ported from Edify): prerequisite chains per chapter, a five-minute lesson and
  a recheck per missing idea, a before/after retest, silent tracing from test mistakes (no quiz needed), class roots
  and a class recap for teachers, and the proof card in Admin. Demo data in `scripts/seed_demo.py`.
- **Check my working:**
  - In practice, mock review and root cause. The student draws on the rough pad (tablet), or photographs their
    working on paper with "Check my paper working" (phone). The photo is shrunk on the phone first.
  - Gemini reads it and returns the steps, the first wrong one, slip or gap, a hint, the corrected step, and the
    root behind it, with a button to fix that root in five minutes. A tutor knows the student's gaps.
  - "How you lose marks" fingerprint. The question's own worked solution is passed as a reference when there is one.
  - Unanswered questions can't be checked.
  - If Gemini hasn't answered within 8 s, a second model is asked too: a check takes 2-6 s, and one call took 80 s.
- **Google first:**
  - Gemini first for text and images. `GOOGLE_ONLY=true` uses nothing else.
  - Cloud Run: `cloudbuild.yaml` and `docs/DEPLOY_GOOGLE.md`.
  - The "roots" edition (`VITE_EDITION=roots`) leads with this story.
- **Also:** Marathi, Bengali, Tamil, Telugu and Gujarati; the dashboard's "Your real gap" card; and everything
  focs.in runs today (enforced CSP, `/api/health/ready`, sharper board reading, the Mumbai database notes).
- **Paused lectures stay open** (the bug students hit: pause 25-30 min, black screen, new session):
  - The lecture tab sends a heartbeat every minute, also while paused, so the 30-minute idle rule no longer
    closes it.
  - A lecture closed anyway reopens as the same session, notes and all, within 12 hours. This covers a slept
    laptop or a tab Chrome unloaded.
  - "Paused for 27 min · Your session stays open" shows for a YouTube lecture or Focs's own Pause. "Your
    lecture looks paused: no change for 6 min" shows for a tab share, but not while the teacher is talking.
  - A stopped share shows a card with "Share the lecture tab again" instead of a black stage. Paused time is not
    lecture time.
  - New `study_sessions` columns (`alive_at`, `ended_by`, `paused_s`, `pause_since`) are added at startup.
  - The browser run of this fix (time fast-forwarded past 30 min) is still in progress.
- **Tools for the pitch numbers:**
  - `scripts/warm_chains.py`: chains for the chapters real students attempt, a free `--dry-run`, and
    `--export/--import`.
  - `scripts/evidence.py`: read-only, totals only, groups under 5 students hidden.
  - `scripts/bench_working.py`: `--init`, `--compare` (with vs without the worked solution), and `--from-fermat`
    for AI4Bharat's public handwritten-maths set.
  - Guides: `docs/ROLLOUT_FOCS_IN.md` ("Get the numbers") and `docs/BENCHMARK.md`.
- **22 root-cause chains** for the top 15 JEE and NEET chapters, built with Gemini, ship in
  `backend/scripts/chains.json`. Load them with `warm_chains.py --import scripts/chains.json`, no AI needed.

## Measured so far
- **First real Gemini run:** 3 of 3 right on generated phone-photo pages labelled before the run (a cos-for-sin
  gap, a 12/2 = 4 slip, a correct solution). It got the step, the slip or gap, and no false alarm, in 2-6 s a check.
  This is a smoke test, not the benchmark: don't quote it as accuracy.

## Next, in order
1. **Real student numbers:** `scripts/evidence.py` against focs.in (read-only).
2. **Benchmark:** 30-50 real photos of students' working (`docs/BENCHMARK.md`), and/or FERMAT (accept its terms on
   Hugging Face first).
3. **Deploy to Cloud Run** (`docs/DEPLOY_GOOGLE.md`).
4. **Roll out to focs.in** (`docs/ROLLOUT_FOCS_IN.md`, database backup first).
5. **Deck and a rehearsed 3-minute demo** built on the real numbers.
6. **Check the rotational-motion chain:** it stops at Class 11 and misses trigonometry and vectors (the torque
   demo's gap).

## Good to know
- `backend/.env` may hold production credentials. Without an explicit `DATABASE_URL`, any local server or script
  uses `SUPABASE_DB_URL`, the live database. For local runs set
  `DATABASE_URL=sqlite:///<scratch file>` (and blank `SUPABASE_DB_URL`). Tests are safe: `tests/conftest.py` forces
  a temporary database and blanks every key.
- Earlier work, still in this app (Oct 2026): pricing by type of student with the launch offer; the Class 1-12
  NCERT syllabus (`tools/school_syllabus/build_school.py`; `tests/test_gate_boards.py` guards a rebuild); the new
  B.Tech branches; GGSIPU and AKTU semester plans.
