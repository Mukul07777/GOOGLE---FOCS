# Handover: where Focs stands and how to carry on

*Updated 2026-10-23. Each day's changes after the plan are in section 7: 18 October in 7, 19 October in 7b, 20 October in 7c and 7d, 21 and 22 October in 7e, 22 (evening) and 23 October in 7f, 27 October (pre-handover fixes) in 7g, the live deployment (26 and 27 October) in 7h, the retest fixes (27 October) in 7j, and pop quizzes, full practice sets and photo answers (28 October) in 7k. Before deploying, read 7f's deploy-day list: it replaces 7e's.*

> ## Deployed on 2026-11-10 (01:50 to 01:55 IST), commit `eea705a`
> focs.in now runs everything below, including the SSC figures. Done: `git pull`, docker build, container swap (about 1 minute down), `/api/health` ok, https://focs.in 200, sitemap lists `https://` links, HSTS and the report-only CSP are sent, an SSC figure loads. **Still for a person:** checks 3 to 7 below (the real ₹9 payment, a real phone, a tablet with a stylus, the `csp would block` log, the AI cost for the week).
> **To log in next time:** the key is `keys/focs-key.pem` (not `keysocs-key.pem`; git-ignored). SSH (port 22) is open only to the IPs in the security group's SSH rule: add your current IP (`curl checkip.amazonaws.com`) with Add rule, SSH, My IP, or use EC2 Instance Connect. Never open it to 0.0.0.0/0.
>
> *Original deploy note, kept for the steps:* everything below was on `main` and tested locally (backend tests, typecheck and lint pass).
>
> **Deploy:** on the server, `cd ~/focs && git pull`, then the usual steps 3 to 5 of section 7h (docker build with `VITE_SENTRY_DSN`, `docker rm -f focs`, `docker run ...`). Nothing in `/etc/focs.env` or the Caddyfile has to change.
>
> **What goes live:**
> - **Mocks:** Pro gets unlimited full mocks. Starter can buy 5 for ₹29 or 1 for ₹9 once the free weekly one is used.
> - **Lecture focus mode** on phones and tablets: notes, doubts and quiz settings are hidden and open as a bottom sheet.
> - **Rough pad** under mock and practice questions (pen, eraser, undo, a page per question, palm rejection with a stylus).
> - **Server fixes:** `https` behind Caddy (sitemap URLs), no `Server: uvicorn` header, HSTS includes subdomains, a script allow-list in report-only mode, lint in CI.
> - **Earlier changes not yet live:** Home shows only the student's own subjects with no install offer, the SSC NUL fix, papers weighted away from easy questions.
>
> **After deploying, please check:**
> 1. `curl -s localhost:8000/api/health` and that https://focs.in opens.
> 2. `curl -s https://focs.in/sitemap.xml` lists `https://` links.
> 3. As a Starter test student who has used the free mock, **buy 1 mock for ₹9 with a real UPI payment** and start it. The badge should show the bought mock.
> 4. On a real phone: open a lecture by link. Focus mode should be on, with Notes opening from the bottom and Back closing it.
> 5. On a tablet with a stylus, if you have one: Rough in a mock, write, go to Next and Back, reload. The writing should still be there.
> 6. For a few days, run `sudo docker logs focs 2>&1 | grep "csp would block"`, including after a real payment. If it stays empty, rename `Content-Security-Policy-Report-Only` to `Content-Security-Policy` in `backend/app/main.py` to start enforcing it.
> 7. Watch AI cost in the admin panel for the first week (Pro mocks are now unlimited).
>
> **Score (founder's audit, 10 Nov):** 74/100 on `main`, about 68 on focs.in until deployed. Features 88, phone and tablet 82, code and tests 80, accessibility 80, security 78, pricing 75, speed 60, deployment 55, SEO 40 (skipped on purpose for now), evidence 30.
> **Next for the most points:** deploy (+6); move Supabase to Mumbai `ap-south-1` (+5; the database is in Tokyo, which costs 2-5 s a page); a real phone, tablet and payment check (+4); measure one real number (+4). Details are in the three 2026-11-10 sections at the end of this file.

This file is for the teammate taking over from here.

**The short version:**
- All the code work in the "Bridge the Gap" 9+ plan (W1–W12) is built, tested and on `main`.
- What's left is the work code can't do:
  - collecting real data;
  - running a small study with students;
  - buying an AI key;
  - hosting the app on HTTPS;
  - rehearsing the demo.

Sections 4, 5 and 6 are the to-do list.

---

## 1. Get it running (about 10 minutes the first time)

1. **Pull:** `git pull origin main`
2. **Python 3.12** (or 3.11).
   - `run.bat` looks for `py -3.12` first.
   - Since 21 October it also accepts 3.10, 3.13 and 3.14, and installs with `--ignore-requires-python`. Some packages (`onnxruntime` among them) may still have no builds for 3.13 or 3.14. If the install fails there, install 3.12 alongside from python.org.
3. **Node 20+** for the web app.
4. **Double-click `run.bat`.**
   - The first time, it creates `backend/.venv`, installs everything, builds the web app, writes `backend/.env` with a fresh `SECRET_KEY`, and opens http://127.0.0.1:8000.
   - Run `run.bat rebuild` to force a fresh web build after pulling frontend changes.
5. **For development, use `dev.bat`:** the API on :8000 reloads on save, and the web app on :5173 hot-reloads.

`backend/.env` is **not in git** (it holds secrets). Without any keys the app still runs fully offline:
- notes are written from the OCR text;
- the waiting screens show their study tasks;
- tests pass.

To turn the AI on, add `GROQ_API_KEY=...` and `GEMINI_API_KEY=...` to `backend/.env`. Gemini is the backup AI and also reads each new board off the frame (without it, stacked fractions come out wrong). The README's configuration table lists every setting.
- **The file must be `backend/.env`, with the dot.** A file called `env` is ignored: that is why the AI was off on 18 October.
- **`run.bat` makes a blank `backend/.env` whenever the file is missing.** On 21 October it went missing, and the AI and the Supabase connection silently switched off. Keep a copy of your keys in a password manager. Since 21 October the server logs a warning at start-up when no AI key is set.
- **Since 21 October the local app uses Supabase.** `backend/.env` has `SUPABASE_DB_URL`, so the app reads and writes the shared online database, not `backend/focs.db`. To work on a local database instead, comment out `SUPABASE_DB_URL`. For throwaway tests, set `DATABASE_URL=sqlite:///<some path>`, which overrides both.
- **After changing keys, close the old Focs window first.** If an older Focs is still on port 8000, `run.bat` only opens the browser at it.

## 2. Check that everything works

Run all of these before every push. CI runs the same checks (`.github/workflows/`): backend, frontend, accessibility and docker.

```
cd backend
.venv\Scripts\python -m pytest -q            # ~370 tests, about 5-10 minutes (OCR runs for real)

cd ..\frontend
npm run typecheck
npm run lint                                 # ESLint (since 22 October): must stay at 0 problems
npm run test:math                            # LaTeX repair, read-aloud, and the Hindi/Hinglish strings
npm run build
```

**Accessibility check** (axe, WCAG 2.1 AA, both themes, signed out and in), run from `frontend` against a running app:
```
set A11Y_CHANNEL=msedge
node scripts\a11y.mjs http://127.0.0.1:8000
```
`A11Y_CHANNEL=msedge` uses your installed Edge. Playwright's own Chromium download often fails on Windows. The script doesn't visit a lecture page (`/app/library/<id>`): check that by hand after changing it. It visits last-day revision (`/app/revise`), which ranks the most-asked topics of its chapters with the AI the first time anyone opens them.

**Memory errors** (`OpenBLAS ... Memory allocation still failed`, or Node/esbuild dying mid-build) mean the PC is out of memory, not that the code is broken. On the HP OMEN laptop the audio helpers (`audiodg.exe`, `HP.OMEN.VadRedirectHelper`) leaked over 15 GB. Restart, then run again; `set OPENBLAS_NUM_THREADS=1` makes the tests lighter.

## 3. What was built (the 12 items of the plan)

The plan and the strict rating behind it (5.1/10 at the start) are in the doc that was shared with you. Each item below is one commit; `git show <commit>` shows the whole change.

| Item | Commit | What it is | Main files |
|---|---|---|---|
| W1 One story | `9782258` | README opens on the bridge. `VITE_EDITION=bridge` builds the event edition: no pricing, only the bridge screens in the menu | `frontend/src/lib/site.ts` |
| W2 Voice lane | `2e28451` | The lecture tab's sound goes in ~25 s pieces and comes back as captions; the audio is never stored | `backend/app/services/voice.py`, `speech.py`, `frontend/src/lib/audio.ts` |
| W3 Language | `df81bd7`, `a0d28ef` | Notes, quizzes and doubts in Hindi or Hinglish (formulas checked), and now the interface too | `frontend/src/lib/i18n.ts`, `backend/app/services/translate.py` |
| W4 Return lane | `bac3a31` | Anonymous "I'm lost" taps, wrong answers and doubts reach the teacher live. After class, a confusion map ranks the boards | `backend/app/services/confusion.py`, `frontend/src/pages/RoomReport.tsx`, `RoomView.tsx` |
| W5 Confidence | `ed9cf25` | Every answer is locked in as Sure or Guessing. Blind spots (sure and wrong) lead the summary | `backend/app/services/calibration.py`, `ConfidenceLock.tsx` |
| W6 Classroom mode | `6d82761` | A phone on the desk films the board; four marked corners straighten it before OCR | `backend/app/services/perspective.py`, `frontend/src/lib/capture.ts`, `pages/Studio.tsx` |
| W7 Accessibility | `e972791` | Read aloud (formulas said as words), an accessibility mode, and axe in CI | `frontend/src/lib/readAloud.ts`, `stores/a11y.ts`, `scripts/a11y.mjs` |
| W8 Ask a senior | `0d139f8` | College-email verification, AI draft then senior check, notifications bell | `backend/app/api/seniors.py`, `services/seniority.py`, `components/CampusAsk.tsx` |
| W9 No dead waiting | `b9557f1` | Every AI wait shows what's happening, plus a due flashcard, a question to redo or a formula | `backend/app/api/wait.py`, `components/WaitBridge.tsx` |
| W10 Evidence | `9411f8a` | Tools for the three numbers: real-board OCR benchmark, learning-study kit, delay and cost measurement | `backend/scripts/benchmark_ocr.py`, `demo_metrics.py`, `study_report.py`, `docs/evidence/` |
| W11 Demo | `e1bd323` | `seed_demo.py` makes labelled demo accounts with everything written in advance. `docs/DEMO.md` covers hosting and the script | `backend/scripts/seed_demo.py`, `docs/DEMO.md`, `Dockerfile` |
| W12 Cleanup | `58810cd` | Dead code out, exact versions pinned, Docker runs as a non-root user with a health check, CI builds the image | `backend/requirements.txt`, `Dockerfile` |

## 4. What's left: W10, evidence (needs people; start first)

The plan's bar is "the pitch has three real numbers". None of the three is measured yet, so this matters most. The full steps are in [docs/evidence/README.md](docs/evidence/README.md).

1. **OCR on real boards.**
   - Collect 60–100 frames from openly licensed lectures (NPTEL and MIT OCW are Creative Commons; check each licence and keep its URL), plus 20–30 photos of real classroom boards.
   - Put them in `ml/data/real/`. The images are git-ignored and only `labels.json` is shared.
   - Run `benchmark_ocr.py --draft ..\ml\data\real` to pre-fill the labels.
   - **Correct every line by hand.** Fill in `source` and `licence`, set `"checked": true`, and save the file as `labels.json`.
   - Score with `benchmark_ocr.py --set real --bench ..\ml\data\real`. The OCR Lab then shows "Real boards" next to the synthetic results.
   - If FocsOCR loses on real boards, say so, and retrain with `ml/focs_ocr/train.py` (`train_ocr.bat`) on real plus synthetic data, keeping some real frames out of training.
2. **Learning study.** 12–20 students, one 15-minute Hinglish lecture, half with Focs, and the same 6-question test straight after and the next day.
   - The protocol, consent text and test template are in [docs/evidence/LEARNING_STUDY.md](docs/evidence/LEARNING_STUDY.md).
   - Enter the scores in `docs/evidence/study_results.csv` (copy the template).
   - `study_report.py` prints the table, with its 95% interval and limitations.
3. **Delay and cost.** Once the app is hosted with the AI key (section 5):
   - run `demo_metrics.py drive --url https://<host>` to time board-to-note (and captions with `--audio`);
   - run `demo_metrics.py cost` after a few real lectures.
   - The only number so far is with the AI off: a median 2.6 s from a new board to its notes. That's a floor, so don't quote it as the demo number.

Each time you get a number, update "The evidence" section near the top of `README.md`.

## 5. What's left: W11, demo and hosting (needs money and accounts)

Everything is in [docs/DEMO.md](docs/DEMO.md), including the 5-minute script. In order:

1. **AI keys:** a paid Groq key, plus a Gemini key as backup. Free tiers run out with a room of judges.
2. **HTTPS hosting.** Screen capture, the camera and the microphone don't work on plain `http://`.
   - **Since 23 October the pilot is going on AWS EC2 in Mumbai at `https://focs.in`**: see 7f. The Cloud Run notes below still hold if the team moves.
   - `docs/DEMO.md` has the exact `docker build` and `gcloud run deploy` commands, and why each setting matters:
     - one instance, because live classes live in memory;
     - a 3600 s timeout, for the class websocket;
     - Postgres through `SUPABASE_DB_URL`, because Cloud Run wipes its disk;
     - `TRUSTED_PROXY_HOPS=1`;
     - `ENV=production`, a `SECRET_KEY` of 32+ characters, and `ALLOW_DEV_UPGRADE=false`.
   - Check `https://<host>/api/health` afterwards.
3. **Seed:** `seed_demo.py --password <pw>`, run with the demo's key and database in `backend/.env`.
   - It writes two students' lectures (Hinglish and Hindi), a teacher's class with a confusion map, and a verified senior on Ask a senior.
   - All of it is marked "Demo". Run it again with `--reset` to start clean.
4. **Rehearse once with the AI keys removed.** That's the fallback if the venue internet fails.
5. **At the venue:** hand judges the demo accounts rather than asking them to sign up, because sign-ups are limited per address on shared Wi-Fi. Keep a phone hotspot as backup.

## 6. What's left: mentors, calls and Pro (built before the plan, not in its tracker)

These work on a dev server, where a test button stands in for paying. No real money has moved yet.

| What | Commit | Main files |
|---|---|---|
| **Mentor accounts.** Mentors are a separate kind of account (`User.role` is `"student"` or `"mentor"`). They sign up at `/mentor/signup` and work from their own dashboard at `/mentor`: overview, seekers, calls, master sessions, earnings and profile. Each side's endpoints refuse the other (`require_mentor` and `require_student` in `core/deps.py`) | — | `frontend/src/components/MentorShell.tsx`, `pages/mentor/*`, `backend/app/core/deps.py` |
| **Mentors** for each exam (IITians for JEE, rankers for UPSC, and so on). A mentor applies with what they cleared, their qualification, experience, current college or company, phone (only the admin sees it), call price and proof. The admin approves them at `/admin`, the proof is then deleted, and the mentor is notified. A mentorship carries on, with a check-in each week. Contacts are hidden and chats can be reported, because students may be under 18 | `1c0d35d` | `backend/app/api/mentors.py`, `frontend/src/components/MentorApplyForm.tsx`, `pages/Mentors.tsx` (the student side), `MentorChat.tsx`, `components/MentorAdmin.tsx` |
| **1:1 calls and Pro.** A 30-minute video call (Jitsi) at the price each mentor sets (₹0 makes it free and booked at once); Focs keeps 20%. Pro is bought for a month, 6 months or a year at the price for the student's kind (see "Prices worked out from the measured cost" below; 0 hides a pass) | `dd4c655`, `20b7822` | `backend/app/api/calls.py`, `api/billing.py`, `services/payments.py`, `frontend/src/lib/checkout.ts` |
| **Master sessions.** A mentor posts a live class with a title, description, length, seats and a price per seat (₹0 for free). Students register: a paid seat is held while they pay. With `PRO_GROUP_SESSIONS_PER_WEEK` set, Pro includes that many paid sessions a week and Focs pays the mentor's share; it is 0 since 19 October, because that share comes out of the Pro price. Cancelling refunds paid seats | `355212f` | `backend/app/api/group_sessions.py`, `frontend/src/components/GroupSessions.tsx` |

Prices and shares are settings in `backend/app/core/config.py`: `MENTOR_CALL_PRICE_INR` (the starting price on the application form), `MENTOR_CALL_PRICE_MAX_INR`, `SESSION_PRICE_MAX_INR`, `MENTOR_COMMISSION_PCT`, `GROUP_SESSION_PAY_INR` (only for sessions made before per-seat prices), `PRO_PRICE_INR`, `PRO_SEMESTER_PRICE_INR` / `PRO_SEMESTER_DAYS`, `PRO_GROUP_SESSIONS_PER_WEEK`, and the weekly caption minutes `CAPTION_MINUTES_FREE_WEEK` (60) and `CAPTION_MINUTES_PRO_WEEK` (360): captions are paid by the minute (about ₹3.5 an hour), so they have their own allowance. The landing page and Settings read prices from `/api/billing/plans`, so a price changes in one place. A mentor deleting their account marks every payment for a call or seat still to come as "refund due" and notifies the students.

To do:
1. **Razorpay keys.**
   - `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` are still empty.
   - In the Razorpay dashboard, also add a webhook for `payment.captured` at `https://<host>/api/billing/webhook`, and put its secret in `RAZORPAY_WEBHOOK_SECRET`. The webhook makes a payment count even if the student closed the tab.
2. **Money is moved by hand.**
   - Mentor pay: the admin panel shows what each mentor is owed. Pay them yourself, then record the payout there.
   - Refunds: a cancelled call or seat is marked "refund due". Send the refund from the Razorpay dashboard, then mark it refunded in the admin panel.
   - Pro doesn't renew by itself.
3. **Real mentors.** Recruit a few: they sign up at `/mentor/signup`, and you approve them in the admin panel. `seed_demo.py` doesn't create a mentor.
4. **The event build hides Mentors.** The `VITE_EDITION=bridge` menu shows only the five bridge screens (`BRIDGE_NAV` in `frontend/src/components/AppShell.tsx`). If the team wants judges to see mentors, add `"/app/mentors"` there.

## 7. Changed on 18 October (after the plan)

| What | Commit | Main files |
|---|---|---|
| **Boards read from the frame.** Line-by-line OCR split stacked fractions and lost the sign between them, so the notes answered a different question. With `GEMINI_API_KEY`, each new board is read off the frame image first and the notes are written from that reading, which the note keeps as its board text. OCR still decides "same board" and is the fallback. About 2–8 s more per new board | `6ca71f4` | `backend/app/services/vision.py` (`read_board`), `services/live.py` |
| **A summary of what the teacher said.** The lecture page's transcript card opens on a short summary; the exact words are behind a link. Written once and kept on the lecture; written again only after more speech | `eef5fb9` | `services/voice.py` (`summary`), `services/ai.py` (`talk_summary`), `frontend/src/components/Transcript.tsx` |
| **Last-day revision counts lectures and weak spots.** It counted only Prep Hub ticks (half a chapter), so a student who learns from lectures saw nothing to revise. Each captured board is placed in a chapter once (by name, else one AI call) and kept in `notes.chapter_ref`. Any chapter under "Leave these today" can be tapped to add it | `88b5e1d` | `services/lastday.py`, `api/prep.py` (`_lecture_chapters`), `frontend/src/pages/LastDay.tsx` |
| **Deletes take the transcript too.** Deleting a lecture or an account left `lecture_segments` behind, which would also block the delete on Postgres. Account deletion now also forgets live lecture state and detaches "I'm lost" taps | `552a2a5` | `services/account.py`, `api/sessions.py` |
| **Last-day revision covers the whole syllabus and ends with a test.** The student picks the syllabus first. By default every chapter that carries marks is on the list, studied or not; "Only what I've studied" is the old behaviour. Each chapter's most-asked topics come first, ranked once per chapter by the AI and shared (library kind `asked`); a chapter not studied yet gets 15 minutes for those topics only. The final test at the end of the list asks only about the day's chapters, and in a chapter revised in part only its listed topics | `dea49ff` | `services/lastday.py`, `services/likely.py`, `services/mock_patterns.py` (`revision_pattern`), `services/question_bank.py` (`on_topics`), `api/prep.py`, `frontend/src/pages/LastDay.tsx` |

Worth knowing:
- **New columns** (`study_sessions.talk_summary`, `talk_summary_pieces`, `notes.chapter_ref`, `bank_questions.topic`) are added on startup; nothing to run. To place a lecture again, set its `chapter_ref` to NULL.
- **Most-asked topics** are asked of `gpt-oss-120b`, never the light `gpt-oss-20b`: asked this, the light model just picked each chapter's first four topics. The ranking isn't charged to the student: it is written once per chapter for everyone (every syllabus in Focs comes to about 60 requests of 16 chapters), and logged in the cost ledger as `lastday_asked`. `build_notes.bat --exam jee --asked` ranks a whole exam ahead of time and exports it with the notes; until then the first student to open a chapter waits a few seconds.
- **The final test is a short test** (`pattern "chapter"`, `config.kind "revision"`), so it doesn't count towards the weekly full-mock limit. Questions the bank lacks are written first, on the same allowance as a chapter test's. A question written for one topic keeps it in `bank_questions.topic`; an older question counts for a topic when it shares most of the topic's distinctive words.
- **Boards captured before `6ca71f4` keep their old OCR text**, such as the Rational Inequality lecture's three boards. The summary uses board text as context, so it may get those lectures' questions wrong.
- **The summary uses the cheap model** (`gpt-oss-20b`). It sometimes adds general advice the teacher didn't give, but with the board text it gets the question right. The bigger model invented a wrong answer in testing, so it isn't used for this.
- **Ask a senior, open gaps:**
  - No verified seniors exist yet, so every question gets only the AI draft and nobody is notified.
  - A live server needs email (SMTP) set up before college-email codes can be sent.
  - The page says seniors "cleared JEE", but only a college email is checked.
  - NEET Biology questions never reach a senior: only Physics, Chemistry and Maths count.

## 7b. Changed on 19 October (launch audit, prices, lag, board notes)

| What | Main files |
|---|---|
| **Student prices.** Pro ₹99 for 30 days, or a ₹399 semester pass (150 days). Captions have their own weekly minutes (60 free, 360 Pro): speech to text is paid by the minute, about ₹3.5 a lecture hour. Pro includes no paid master-session seat for now (`PRO_GROUP_SESSIONS_PER_WEEK = 0`), because Focs paid the mentor's share of it. The landing page and Settings read prices from `/api/billing/plans` | `core/config.py`, `api/billing.py`, `services/usage.py` |
| **The lecture no longer stutters on a laptop running Focs.** Each new board used to cost 15 CPU-seconds: two OCR models on every core. Now: 2 threads per model (`OCR_THREADS`), below-normal priority when not in production (`BACKGROUND_PRIORITY`), a warm-up read at start, and FocsOCR alone on live frames while a vision model reads the board (the full ensemble runs again only if the vision read fails). Measured with a lecture video in the front tab: 518 → 27 server CPU-seconds for the same lecture | `services/ocr/*`, `services/live.py` (`_live_engine`), `main.py` |
| **Boards are read reliably.** `gemini-3.1-flash-lite` answered 503 for 3 of 4 real boards. `VISION_MODEL` is now a chain, `gemini-3.5-flash-lite,groq:qwen/qwen3.8-27b,gemini-3.1-flash-lite`, tried in order with 8 s each, and never in JSON mode (it deletes LaTeX backslashes) | `services/vision.py` |
| **Notes don't invent maths.** With a board reading, its text goes into the notes word for word under "On the board", and the model writes only context, key ideas, formulas and the exam tip: asked to copy the board's working, both gpt-oss models still added sign charts of their own, wrong in up to three intervals. Board notes use `gpt-oss-120b`, never the light model (it called a clear board "not a lecture"); a board the vision model read is never dropped | `services/ai.py` (`generate_notes`, `with_board`) |
| **Shared notes keep their signs.** Boards were compared on letters and digits only, so `x^2 - 5x + 6` and `x^2 - 5x - 6`, or `> 0` and `< 0`, shared one set of notes. Signs and relations now count, and a near match must have identical numbers and signs | `services/shared_notes.py`, `services/text_utils.py` |
| **JSON retries keep LaTeX.** An answer that isn't valid JSON goes to the next model first; provider JSON mode is the last resort (it turned `\ge`, `\cup`, `\infty` into `ge`, `cup`, `infty`) | `services/llm.py` (`json_with_model`) |
| **Hinglish doubts stay Hinglish**, tables included (the language is repeated after the question), and doubts don't invent formulas | `services/ai.py` (`companion`) |
| **Each student gets their own exam's content only.** A paper short of questions is written for that exam, never topped up with another exam's on the same chapter (a JEE paper used to take NEET or Class 11-12 questions); a topic's exam questions likewise. UPSC, CA and "Other" have no syllabus here: they get no mock (they were offered JEE Main ones), no old JEE plan, and the menu hides the syllabus pages | `services/question_bank.py` (`pick`), `services/topic_notes.py`, `api/mock.py`, `api/prep.py` (`_goal`), `AppShell.tsx` |
| **A paper left "preparing" by a restart is picked up again** when the student opens it or the list (a deploy used to leave it stuck for ever, and asking again returned the same stuck paper). Messages students see when the AI is busy no longer mention `backend/.env`. Postgres pool 10 + 20 | `services/mock.py` (`resume`), `services/offline.py`, `core/database.py` |
| **Physics and Chemistry questions serve both JEE and NEET** (the student's own exam's first; NEET never gets JEE Advanced ones). **More questions:** `scripts/import_open_banks.py` imports MIT-licensed sets (793 NEET Biology MCQs; NEET 2024-2026 and JEE Advanced 2016-2026 papers; attributions in `app/assets/bank/OPEN_SOURCES.md`), `import_pyq.py` also reads official papers in `data/pyq/official/` (NEET 2020-2023 from Aakash's free PDFs: the subject comes from each page's heading, an answer printed under a question counts as the key), and `scripts/fill_bank.py` writes and cross-checks questions until every chapter has 40 MCQs (12 numericals for JEE). All three solve with `gpt-oss-120b` (the 20b filed questions under the wrong chapter) and only spend Groq quota above `--reserve` (450 a day), so students never run short | `services/question_bank.py` (`exam_family`), `scripts/import_*.py`, `scripts/fill_bank.py` |

Notes written before 19 October keep their old OCR-based text; the October Physics Wallah boards in the database are examples.

## 7c. Changed on 20 October (launch day: security, mentor photos, prices that pay for the AI)

| What | Main files |
|---|---|
| **Security for going live.** Upload and image-bomb limits, a websocket that no longer puts the login in its URL, a cap on room spam, production defaults in the Docker image. The settings the live server needs are in `docs/LAUNCH_CHECKLIST.md`, section 0 | `main.py`, `services/images.py`, `api/rooms.py`, `Dockerfile`, `docker-compose.yml` |
| **Photos of verified mentors.** A mentor adds one on their profile; students see it only after the admin approves it ("New photos" in the admin panel; approving an application approves its photo) | `api/mentors.py`, `pages/mentor/MentorProfilePage.tsx`, `components/MentorAdmin.tsx` |
| **Prices that pay for the AI they include.** Pro ₹199 a month, ₹999 for 6 months, ₹1,799 a year. The allowance is a study day (24 h) instead of 5 hours (Pro 200 units, Starter 30). Lectures another student already captured are free and use no allowance. Under that, each student's real AI cost over 30 days is capped (₹140 Pro, ₹15 Starter), below what even the year pass brings in per 30 days after Razorpay's fee, so no student can cost more than they paid. Free accounts together may spend ₹50 a day plus 20% of the last 30 days' Pro income. `tests/test_pricing.py` fails if a price change breaks this | `core/config.py`, `services/usage.py`, `services/ledger.py`, `api/billing.py` |

**Measured on 20 October, and the reason the plans promise no lecture hours:** two PW one-shot lectures on YouTube, sent through live capture as a student would (480p, no crop), cost ₹21 and ₹45 per lecture hour: 60-220 "boards" an hour, each a vision read plus notes (~₹0.1). Two fixes the same day halved it (₹11 and ₹30): one board read by OCR in a different order or with a few characters changed is no longer a new board (`text_utils.same_board`, tested on the lecture's real OCR in `tests/test_board_matching.py`), and a frame the AI called "not a board" (the teacher's camera) isn't sent to the AI again. Groq's free tier also pushed most notes to Gemini at twice the price. Until a lecture hour costs far less, the ₹140 30-day ceiling covers only a few hours of brand-new lectures a month for a Pro student.

## 7d. Changed on 20 October, evening (a lecture hour for a few rupees; Pro's 7-hour day)

| What | Main files |
|---|---|
| **Which board a frame shows comes from its strokes, not its OCR text.** On a PW lecture the teacher's handwriting OCRs as junk that changes every frame (and Hindi not at all), so nearly every frame was a "new board". Now a top-hat filter keeps the pen strokes and drops the teacher standing in front; a coarse grid finds how far the page scrolled, and the strokes, pixel for pixel, decide. A new view becomes a board only once it holds for 15 s, so the teacher walking up to the camera never does. A frame that shows two known boards merges them; going back to an earlier board continues it | `services/ocr/ink.py`, `services/live.py` |
| **Each board is written up once, when the lecture moves on** (a minute later, in case it comes back), when the screen is still, at Capture now or at the end; a board still being written gets its notes so far every 5 minutes. The first board of a lecture is written at once. Write-ups run in the background, so the board read can wait for the cheap Gemini models instead of handing over to Qwen | `services/live.py`, `services/vision.py` |
| **Lecture notes are counted in hours, not units.** Pro: AI notes for up to 7 hours of lecture a study day, Starter half an hour; past that, basic notes (a lecture never stops). No add-ons. Units are now only for doubts, quizzes and practice | `services/usage.py`, `api/billing.py`, `pages/Settings.tsx`, `components/UsageMeter.tsx` |
| **Prices worked out from the measured cost, for each kind of student.** Launch offer (the regular price struck through) for the first 200 students who pay, then the regular price by itself: JEE / NEET ₹249 ~~₹359~~ a month, ₹1,449 ~~₹1,899~~ for 6 months, ₹2,849 ~~₹3,599~~ a year; College (B.Tech, placements) ₹199 ~~₹299~~, ₹1,099 ~~₹1,599~~, ₹2,199 ~~₹2,999~~; School (class 11-12) ₹149 ~~₹249~~, ₹799 ~~₹1,299~~, ₹1,599 ~~₹2,499~~. GATE, UPSC, CA and Other pay the JEE / NEET price until they get their own. A student pays the price for their own exam, whatever the page showed. Each Pro student's AI may cost, in any 30 days, what the pass they are on brings in over 30 days after Razorpay's fee (at most ₹300), so no student can cost more than they paid: about 90 lecture hours on the JEE / NEET offer, 70 college, 50 school. `tests/test_pricing.py` checks every pass of every kind | `core/config.py` (`PRO_PRICES_INR`, `PRO_OFFER_PRICES_INR`, `PRO_OFFER_PLACES`), `services/pricing.py`, `pages/Landing.tsx` |

**Measured** by recording three PW lectures as the web app sends them (physics, maths on a scrolling pen tablet, a Hindi NEET zoology board with slides; about 25 minutes each) and replaying the frames through the pipeline. On the same frames the old pipeline made 125, 186 and 483 write-ups a lecture hour; the new one makes 21-33, one for each real board or slide (checked frame by frame on contact sheets). Replayed with the real AI, a lecture hour cost ₹2.1-3.4 (it was ₹11-30 in the morning), with the account's free Groq and Gemini tiers sending some boards to dearer models; about ₹1.5-2.1 without that. **Turn on paid tiers for the Groq and Gemini keys before charging for Pro**: on free tiers Groq stopped answering for minutes at a time after a day of use and Gemini was often overloaded. To measure again: record a lecture's frames with Playwright the way `lib/capture.ts` samples the video, then post them to `/api/capture/{id}/frame` in order with `live.time` swapped for a clock set to each frame's video time.

## 7e. Changed on 21 and 22 October (school and college syllabi; testing before launch)

**Mukul, 21 October:**

| What | Main files |
|---|---|
| **School syllabus, Class 1 to 12**, from the NCERT books (2026-27 reprints). Classes 9-12 follow the CBSE 2026-27 curriculum, with marks per unit and dropped chapters left out. A school student's ticked topics count in their plan, and school chapter tests stay inside the book (in Hindi or Sanskrit for those subjects) | `data/syllabus/school/class_*.json` (built by `tools/school_syllabus/`), `services/syllabus.py`, `services/question_bank.py`, `api/prep.py`, `tests/test_gate_boards.py` |
| **New B.Tech branches:** AI & Data Science / AI-ML, Chemical, Biotechnology. 43 new library courses with typical AICTE 8-semester plans | `data/syllabus/college/` (`ai_data.json`, `chemical.json`, `biotech.json`, `branches.json`), `tests/test_college.py` |
| **GGSIPU and AKTU semester plans** from their official schemes, in the college pickers | `data/syllabus/college/branches.json`, `services/syllabus.py`, `components/CollegeSetup.tsx` |
| **Boards and photo questions are filed under the student's own subjects** (their class, GATE paper, branch or placement courses), not the JEE list | `services/ai.py`, `api/snap.py`, `tests/test_gate_boards.py` |
| **The sign-in token is refreshed only once it is 12 hours old.** Quick reloads used to hit the rate limit. A school student who opens Campus gets an explanation and a link to their Prep Hub, not an error | `components/AppShell.tsx`, `pages/Campus.tsx` |
| **Wording for every kind of student:** the School price says "Class 1 to 12 (CBSE)", and the examples fit the student's class | `services/pricing.py`, `pages/Landing.tsx`, `pages/Mentors.tsx`, `pages/OnboardingSimple.tsx`, `pages/PrepHub.tsx` |

**Ashpreet, 21-22 October:**

| What | Main files |
|---|---|
| **Guided tour for new students.** It runs once per account on each device. It highlights each control the student actually has (sidebar or phone tabs, search, notifications, theme, allowance, profile), and the **?** button in the top bar or "Take the tour" in Ctrl+K replays it. To change what a section says, edit `NAV_HELP` | `components/GuidedTour.tsx`, `components/AppShell.tsx` (`data-tour` attributes) |
| **Keys:** `backend/env` (no dot) was merged into `backend/.env` and deleted, and `.dockerignore` excludes it in case it comes back. It had been about to be copied into the Docker image. The server warns at start-up when no AI key is set | `.dockerignore`, `main.py` |
| **Launchers:** `npm.cmd` instead of `npm` (works when PowerShell blocks `npm`), UTF-8 console output, Python 3.10-3.14 accepted | `run.bat`, `dev.bat`, `scripts/launch.py` |
| **Shared board notes keep the vision model's reading of the board.** FocsOCR reads "D > 0" as "D ≥ 0" on some boards (it reads "x > 3" fine). The notes were right, since they're written from the Gemini reading, but the second student on a board saw them beside the OCR text, with the wrong sign. New column `shared_notes.board` | `models/shared_note.py`, `services/shared_notes.py`, `tests/test_cost_cuts.py` |
| **Quiz answers are worked out before the answer is chosen.** The pop quiz (the cheapest model) marked a wrong option about 1 in 8 times, for example D = 1 for 2x² − 7x + 3. The pop quiz, checkpoint and practice prompts now ask for the working first, then `answer_index`. The pop quiz runs at temperature 0.4 (was 0.6). Afterwards, 0 wrong in 12 checked by the bigger model: a small sample | `services/ai.py` |
| **Students name their lectures.** A title typed at the start, or set with the new pencil button on the lecture page (and on the live page), is never replaced when the lecture ends. It used to be, when it matched the first board's topic. An untitled lecture is still named from its boards. New column `study_sessions.title_locked` | `api/sessions.py`, `models/session.py`, `pages/SessionView.tsx`, `pages/Studio.tsx`, `tests/test_lecture_title.py` |
| **Smaller first load.** The first page downloaded ~322 KB gzipped, because the logo shared `common.tsx` with the markdown/LaTeX renderer, so every page pulled in 130 KB of markdown libraries. Now ~175 KB: the renderer is in `components/Markdown.tsx`, the signed-in shell loads lazily, and libraries (react, motion, icons, vendor, charts, markdown) are separate long-cached files. A redeploy makes students re-download only the ~16 KB app entry | `vite.config.ts`, `App.tsx`, `components/Markdown.tsx` |
| **ESLint works:** `npm run lint` (JS, TypeScript and React hooks rules). It found 0 errors. Of its 9 warnings, two were real bugs: the Ctrl+K test label kept the old exam after a change, and the mock exam's clock effect could re-run on every render. All fixed | `eslint.config.js`, `package.json` |

**Tested on 21 October** with the AI on, against a throwaway database: the whole student flow (capture, pop quiz, end and revision sheet, export, quizzes, flashcards, photo doubt, plan, last-day, tests, weak spots, Ask a senior), bad input (other students' data, broken and huge uploads, wrong passwords), and all 21 pages in Edge. Nothing crashed, and the slowest call was 8.5 s. The two maths bugs above were the only real errors.

**Before deploying (still to do):**
1. **AI rate limits are the biggest risk.** Testing alone hit Groq's free per-minute limit several times. Limits apply per Groq *account*, not per key, so several keys on one account don't help. Several accounts to get around the limits breaks Groq's terms, and the accounts can be suspended. Instead: Groq's paid Developer tier, a second provider (Cerebras or OpenRouter) in the `llm.py` chain, and a load test with 50-100 students.
2. **Keys and settings as server environment variables, not a file:** `ENV=production`, a 64-character `SECRET_KEY`, `SUPABASE_DB_URL`, the AI keys.
3. **Error monitoring: done on 22 October.** Sentry (sentry.io, free plan, EU region): project `focs-backend` gets every server error and every `log.error`, and `focs-frontend` every crash screen and uncaught error in the browser. Both DSNs are in `backend/.env` (`SENTRY_DSN`, `VITE_SENTRY_DSN`). On the server, set `SENTRY_DSN` as an environment variable and pass `--build-arg VITE_SENTRY_DSN=...` to `docker build`. No personal data is sent (`core/monitoring.py`, `lib/monitoring.ts`). Errors are tagged `development` or `production`, so filter by environment in Sentry. Empty DSNs turn it off, and tests never send.
4. **Supabase backups** turned on.
5. **The free allowance:** two short test lectures with one quiz, flashcards and a photo doubt used 18 of a Starter student's 30 daily units. Decide whether that's the intended size.
6. **Deploy at quiet hours.** Live lecture state (the board being written, rate limits) is in memory in one process, so a redeploy drops each live student's half-written board. Moving that state to Redis would allow more than one server, but isn't needed for launch.

## 7f. Changed on 22 (evening) and 23 October (load, Hindi, Google sign-in, the server)

**Ashpreet:**

| What | Commit | Main files |
|---|---|---|
| **Many students capturing at once.** From 25 students sending a changed board every 5 s, frames failed with 500s (the database pool ran out: each frame held a connection through its image work) and the slowest took 35-44 s. Now a frame hands its connection back before the image work; pools are SQLite 20+40, Postgres 10+50; `FRAME_SLOTS` frames are read at once (default: CPU count) and past that a frame waits up to `FRAME_WAIT_S` (3 s), then is answered "busy" and the app sends it again 5 s later; keep-alive is 75 s. On 2 CPUs, 25 and 50 students: 0 errors, slowest frame 8.6 s. About 15-20 students capturing fast-changing boards per 2 CPUs; past that frames are skipped, not failed | `1f385bd` | `services/live.py`, `api/capture.py`, `core/database.py`, `core/config.py` |
| **Hindi and Hinglish notes are really translated.** The cheap model often handed the English back, which kept every formula and passed the check. `translate.in_language` now refuses an answer that isn't in the language (Hindi mostly Devanagari; Hinglish with a good share of words changed); translation has its own instruction, said again after the notes, and a token budget that fits Devanagari | `50f2023` | `services/translate.py` |
| **Photo doubts in Hindi and Hinglish.** The solution is still worked out in English, then an English / Hinglish / हिंदी switch says it again in the student's language with the maths untouched; written once per language and kept (new column `doubts.explained`) | `8838b72` | `api/snap.py`, `services/ai.py` (`explain_in`) |
| **Server login keys never reach git:** `*.pem`, `*.ppk` and `keys/` are ignored. The EC2 key lives in `Study_Platform/keys/` on Ashpreet's laptop only | `c00352d` | `.gitignore` |
| **Continue with Google** on sign-in and sign-up (Google's own button, Google Identity Services). The server checks the ID token against Google's published keys: signed by Google, issued for our client ID, in date, verified email. An email that has an account signs in to it (its password keeps working). A new email gets a student account only from sign-up, after the exam is picked and the Terms ticked (the button is dimmed until then); from sign-in it's sent to sign-up. Not on mentor sign-up or inside the app shell. Off until `GOOGLE_CLIENT_ID` is set; the web app reads the ID from `/api/health` | `05a8b7c` | `services/google_auth.py`, `api/auth.py` (`/auth/google`), `components/GoogleButton.tsx`, `pages/Auth.tsx`, `tests/test_google_signin.py` |
| **A waiting student's first board in 2-6 s (was 12-26 s).** `gemini-3.1-flash-lite`, first in `VISION_MODEL`, took 4-30 s on first boards while the next two models answered in 0.3-1.7 s. When a student is waiting, the next model is now asked too once the first has had `BOARD_HEAD_START_S` (3 s), and the first good answer wins. The slower call still finishes and is costed to the same student. Background reads are unchanged (they wait for the cheap model) | `a12ded8` | `services/vision.py` (`_staggered`) |
| **Two-step sign-in.** With email (SMTP) set up, the right password alone no longer signs in: a 6-digit code goes to the account's email (`/auth/login` answers `code_required` with a challenge; `/auth/login/verify` takes the code; `/auth/login/resend` after 30 s). The code is kept only as a hash, works 10 minutes, five wrong tries end the sign-in, and a password change in between ends it too. Continue with Google skips it. Without SMTP (local development) or with `LOGIN_EMAIL_CODE=false`, the password signs in straight away | — | `services/login_code.py`, `api/auth.py`, `core/security.py` (`create_login_challenge`), `pages/Auth.tsx` (`LoginCodeStep`), `tests/test_login_code.py` |
| **Role-based access.** Every account is a `student` or a `mentor` (`User.role`, set at sign-up; no endpoint can change it), and the admin panel has its own sign-in. Which role may use which part of the API is set in one place, `app/api/__init__.py`: the study and AI areas (`STUDENT_AREAS`) refuse mentor accounts with 403 (until now a mentor could use every student feature, and its AI); the shared areas (account, notifications, payments, mentoring) mark their one-sided endpoints with `require_student` / `require_mentor`. Study-room sockets refuse mentors too, and buying Pro is for students. `tests/test_access.py` calls **every route** signed out, as a student, as a mentor and on the admin panel, so a new route is checked the day it's added | — | `core/deps.py` (`require_role`, `only_role`), `api/__init__.py`, `tests/test_access.py` |
| **Hinglish in a teacher's tone.** "The way Indian students talk" gave a photo doubt that opened "Yo, ek simple problem hai". Hinglish rules now ask for a respectful teacher's voice with no slang | `a12ded8` | `services/ai.py` (`HINGLISH_TONE`), `services/translate.py` |

Note: 7b lists the old `VISION_MODEL` order. The default is now `gemini-3.1-flash-lite,gemini-3.5-flash-lite,groq:qwen/qwen3.8-27b`.

**Tested on 23 October** from a fresh clone in production mode with the real AI: 22 of 22 server checks (AI and OCR loaded, no secrets in `/api/health`, API docs hidden, security headers, forged / `alg=none` / dev-key / expired tokens refused, dev Pro upgrade blocked, a fake Google token refused, a full lecture with revision sheet and export), all 21 pages in Edge with 0 errors, and every backend test. The server process uses about 950 MB after several lectures.

**The server (pilot: about 10 students for a week, to learn the real AI cost):**
- AWS EC2 `c7i-flex.large` (2 vCPU, 4 GB) in **Mumbai (`ap-south-1`)**, Ubuntu, paid from the AWS credits ($120, which expire about 32 days after 22 October). A budget alert emails `admin@focs.in`.
- Elastic IP `65.1.163.26`. GoDaddy DNS: `focs.in` and `www.focs.in` point there.
- Docker and Caddy are installed. Caddy gets the HTTPS certificate by itself and passes requests to the app container on port 8000.
- SSH key: `keys/focs-key.pem` on Ashpreet's laptop (git-ignored). Lose it and you can't log in, so keep a copy somewhere safe.
- The repo is private, so cloning on the server needs a GitHub token with `repo` scope. Use it once; don't leave it on the server.
- Settings go in `/etc/focs.env` (readable by root only), passed with `docker run --env-file`.

**Deploy-day list** (each of these breaks something if missed):
1. **`APP_URL=https://focs.in`.** Otherwise password-reset emails link to `localhost`.
2. **Email (SMTP), and test it before telling students.** Password sign-ins now need the emailed code: if SMTP is set but wrong (bad password, blocked port), nobody can sign in with a password (Google sign-in still works). After deploying, use Forgot password on your own account and check the email arrives.  Without it, forgot-password is hidden and seniors can't verify their college email. GoDaddy's mailbox works: `SMTP_HOST=smtpout.secureserver.net`, `SMTP_PORT=465`, `SMTP_USER=admin@focs.in`, `SMTP_PASSWORD=...`, `SMTP_FROM=Focs <admin@focs.in>`. The SPF record already allows GoDaddy.
3. **Google sign-in.** In Google Cloud Console: OAuth consent screen External, scopes email / profile / openid only, then **Publish app** (in "Testing" only listed users can sign in). Create a Web OAuth client with authorised JavaScript origins `https://focs.in`, `https://www.focs.in`, `http://localhost:8000`, `http://localhost:5173` (no redirect URIs). Put its client ID in `GOOGLE_CLIENT_ID`.
4. **No quotes in the env file.** Docker keeps them: `ADMIN_PASSWORD_HASH` copied with its `'...'` from `backend/.env` makes admin login fail.
5. **The rest of the settings:** `ENV=production`, a 64-character `SECRET_KEY`, `SUPABASE_DB_URL`, the AI keys, `SENTRY_DSN`, `TRUSTED_PROXY_HOPS=1` (otherwise every student shares one rate limit), `ALLOW_DEV_UPGRADE=false`. Pass `--build-arg VITE_SENTRY_DSN=...` to `docker build`.
6. **2 GB of swap** before the first build: building while the app runs can run out of memory on 4 GB.
7. **Docker log rotation:** `--log-opt max-size=20m --log-opt max-file=3` on `docker run`, or the logs slowly fill the disk.
8. **Payments say "not set up"** until the Razorpay keys are added (section 6). For the pilot, upgrade testers by hand in the admin panel.
9. **Check afterwards:** `https://focs.in/api/health` shows `status`, whether the AI is on, and `google_client_id`. Since 27 October the versions, providers, AI models and OCR engines are only at `/api/health/details` (signed in; Settings shows them). Then sign up, capture a board, end a lecture.

## 7g. Changed on 27 October (fixes from the pre-handover test)

Two test passes found the problems below: one of the public site, one of the signed-in app. All are fixed except where noted. The tests are in `backend/tests/test_prehandover_fixes.py`.

**Public site**
- **Institute "Talk to us"** now opens an email to `SITE.supportEmail`, and the address shows under the button. The footer has a Contact link.
- **Unknown URLs return a real 404** (the app still draws its "blank board" page). The list of the app's routes is `_APP_ROUTES` in `backend/app/main.py`. **Add any new route in `App.tsx` there too**, or it will answer 404 to search engines. `/sitemap.xml` is served and `robots.txt` points to it.
- **`/api/health` is minimal** (see deploy step 9 above).
- **Headers:** `Permissions-Policy` (camera, microphone and screen capture on our own pages only) and `form-action 'self'` in the CSP. A full script allow-list is still not set: it needs testing with Razorpay and YouTube first.
- **Signup accessibility:** name, email and password have real labels, and the exam buttons and the terms checkbox have names. The landing page's smallest text is 11 px, and footer links are 44 px tall.
- **"200 places left"** was never hard-coded: it is one pool for every course, read from the database. It now says "shared across all courses", and "every place still open" until the first is taken.
- **Not fixed: following an online lecture on a phone.** Phones can't share a tab. Fixing it means a new feature (for example the server reading a YouTube link's frames). Classroom mode and board photos still work on phones.

**Inside the app**
- **Practice questions are checked before they're shown.** A second model solves every MCQ, lists *every* correct option, and judges the explanation. A question is dropped unless exactly the keyed option is correct and the explanation is sound. With no second model, questions are shown with `checked: false`. Mock-bank checking (`question_bank.only_correct`) now also rejects questions with two correct options.
- **Abandoned lectures end by themselves** after 30 minutes with no frame and no new board (`close_idle_sessions` in `api/_common.py`). They end at their last board, so a tab left open overnight adds no time. On any day with focus heartbeats, focus time is the heartbeat minutes only, so the dashboard total and its breakdown always match.
- **Notes:** an unmatched `$$` is dropped before saving, and a sign chart's row of signs keeps its spacing (`ai.tidy_math`, `ai._sign_row`).
- **Sharing a tab or the camera that doesn't start** now says why, both in a toast and on the page (`shareFailure` in `lib/capture.ts`).
- **AI allowance:** practice sets and doubts say what they will cost before you send them (`CostHint`). Costs themselves are unchanged.
- **Search (Ctrl K)** finds notes too, not only commands.
- **Rooms need a name**, in the browser and on the server.
- **Last-day revision** says what it's doing while it loads, offers a retry if it fails, and keeps a plan for 10 minutes.
- **Flashcards:** never-reviewed cards count as "New", not "Learning". The counts move as soon as you rate a card.
- **Wide tables** in answers have an "open it full width" button.
- **Generate** (practice) says why it is greyed out.

**Weak or no connection** (`frontend/src/lib/offline.ts`)
- What a student has opened is saved on the device for their account, and shows at once on the next visit, offline too. Signing out deletes it. Live data (usage, notifications, rooms, mocks in progress) is never saved.
- `public/sw.js` keeps the app's own files, so the app opens offline. It never touches `/api`. It only runs in production builds. The server sends it with `no-cache` so a fixed version reaches browsers on the next visit.
- Reads time out after 25 s and retry with growing gaps. Errors say "you're offline" or "too slow" instead of "is the server running?". A banner shows while offline, and anything sent then is sent on reconnect.
- On 2G or data-saver connections, live capture sends smaller frames every 8 s instead of every 5 s.

## 7h. Deployed on 26 and 27 October (focs.in is live)

**What runs where.** `https://focs.in` and `https://www.focs.in` are served by Caddy (HTTPS certificate from Let's Encrypt, renewed by itself; `/etc/caddy/Caddyfile` sends both names to `localhost:8000`). Behind it, one Docker container named `focs` runs the app (`--restart unless-stopped`, port 8000 on the server's loopback only, logs rotated at 20 MB x 3). Settings are in `/etc/focs.env` (root only, no quotes). The server has 2 GB of swap (`/swapfile`, in `/etc/fstab`).

**Log in to the server:** `ssh -i keysocs-key.pem ubuntu@65.1.163.26` from `Study_Platform` (the `.pem` is git-ignored; keep a second copy). Without the key: AWS Console, EC2, Connect, EC2 Instance Connect, user `ubuntu`.

**Redeploy a new version** (do it when no one is mid-lecture: the live board state is in memory, and the site is down for 1 to 2 minutes):
1. Push to `main`.
2. On the server: `cd ~/focs && git pull` (the repo is cloned over SSH with a read-only **Deploy Key**, `~/.ssh/focs_deploy`, added in GitHub under the repo's Settings, Deploy keys. No token is needed.)
3. `sudo docker build --build-arg VITE_SENTRY_DSN='<the VITE_SENTRY_DSN from backend/.env>' -t focs .` (5 to 10 minutes; the old container keeps serving meanwhile).
4. `sudo docker rm -f focs`, then `sudo docker run -d --name focs --restart unless-stopped --env-file /etc/focs.env -p 127.0.0.1:8000:8000 --log-opt max-size=20m --log-opt max-file=3 focs`.
5. `curl -s localhost:8000/api/health`, then open `https://focs.in`. `sudo docker logs focs --tail 40` shows errors.

**Email (GoDaddy SMTP).** `SMTP_HOST=smtpout.secureserver.net`, port 465, user `admin@focs.in`. For a while the server logged `email ... failed: Connection unexpectedly closed`: GoDaddy accepted the connection and dropped it at login, from the server and from a laptop alike. The mailbox's password was wrong; resetting it in GoDaddy fixed it. **If sign-in codes or reset links stop arriving, test the login first** (`smtplib` from the server with the values in `/etc/focs.env`), then read the docker logs. The `admin@focs.in` password was pasted in a chat: change it in GoDaddy, then update `SMTP_PASSWORD` in `/etc/focs.env` and recreate the container (a changed env file needs `docker rm -f` and `docker run`, not a restart).

**Sign-up now needs the emailed code too** (`api/auth.py`, `register`). With email set up, creating an account with a password sends a 6-digit code and returns `code_required`; the account opens only when the code is typed (`/auth/login/verify`), so every account's email is proven. Google sign-up skips it. Without SMTP it signs in straight away, as before. While email is broken **nobody can create or sign in to a password account** (Google still works). Tests: `tests/test_login_code.py`.

**Google sign-in.** The OAuth app is published ("In production"). It is not verified yet, so students see "Google hasn't verified this app" (Advanced, Go to focs.in). To verify: add `focs.in` as a Domain property in Search Console (a TXT record in GoDaddy DNS), then submit the app in Google's verification centre (scopes: email, profile, openid only). **An email that already has a Focs account signs in to it**, so a Google address used earlier in testing never sees the "pick your exam" step. The database is the same Supabase one used in development, so test accounts are in it.

**A black shared tab (picture-in-picture).** Chrome and Edge move a playing video into its own small window when you switch tabs ("automatic picture-in-picture"), so the shared YouTube tab shows a black box with "Playing in picture-in-picture". Focs can't close another tab's window. Instead, live capture now spots a tab whose middle is black (`looksBlank` in `lib/capture.ts`): it sends no frames (no AI spent on black), and after two looks in a row tells the student to close the small window and block the setting at `chrome://settings/content/autoPictureInPicture` (Edge: `edge://...`). Capture carries on by itself once the video is back (`Studio.tsx`, `blank`).

**Not done yet**
- Search Console domain verification and the Google verification request.
- ~~A `support@focs.in` mailbox~~ Done 2026-10-31: its own GoDaddy mailbox (webmail), mail from Gmail arrives. Aliases cost extra on this plan, so none are set up.
- Razorpay keys: payments say "not set up"; for the pilot, upgrade testers by hand in the admin panel.
- Supabase is in Tokyo and the server is in Mumbai, so every query pays for the distance. Moving the database to Mumbai (`ap-south-1`) would make pages faster.
- No load test on the server itself (50 to 100 students at once). Start the pilot with 10 to 20 students; the AI provider's rate limit is the main risk.

## 7i. Hard test of 27 October (focs.in, then every kind of student)

**How it was tested.** On focs.in, with a B.Tech CSE account and a JEE test account (`mukul06499+jee@gmail.com`; Gmail's `+` gives a separate Focs account in the same inbox): three papers through the real exam screen, every read endpoint, about 40 actions (plan, notes, practice, flashcards, Ask AI, photo doubt, rooms, classes, lecture start/end, last-day, parent link, export, Hindi), security probes, and 30 pages at laptop and phone width. Then, on a local copy with the same code (QA server on :8017, real AI, no email code), 43 kinds of student: NEET, Class 1 to 12, all 9 B.Tech branches, the 6 colleges, the 6 GATE papers, placements, JEE, UPSC, CA, other. Each: sign-up, 20 endpoints, a chapter test made, taken and marked, and every page in a phone-size browser. Full papers: NEET 180, JEE 75, GATE CS. A UPSC/CA/other student only gets 404s from syllabus pages opened by URL (their menu hides them), by design.

**Found and fixed** (commits `ad9be51` and the one after it):
- **JEE 90-question mock stuck at Q26 to 30 of every subject.** Its Section B allowed "any 5 of 10" and Save & Next refused to move once 5 were answered, with a toast that piled up. Save & Next now always moves on (the extra answer isn't kept; one toast says why, `MockExam.tsx`), and the JEE default is the current NTA 75-question paper; the 90-question one is labelled pre-2025.
- **The right MCQ answer was first or second about 70% of the time, fourth about 3%** (AI-written questions for every exam, and the JEE seed set). Always picking option 1 scored 44% on a NEET mock. Each paper now shows every MCQ's options in its own fixed order (`mock.option_order`, `shown_answer`; marked through the same order). Papers made before keep the stored order (`mock_tests.shuffled` is empty for them; the column is added by itself at start-up). Questions whose options point at each other ("both (a) and (b)", "all of the above") or whose solution names an option stay as written (about 6%). Over 2,000 simulated papers each position is right 25% of the time.
- **Sign-in code and password reset emails put the user's name in as raw HTML.** Anyone could sign up with someone else's email and a name holding a link. The greeting now uses only the letters of the first name (`mailer.greeting_name`; Hindi names keep their matras).
- **The guided tour opened over a test's instructions** on any new device. It now opens by itself only for an account made in the last 3 days, only on the dashboard (`AppShell.tsx`).
- **"Upgrade to Pro" while payments aren't set up**: the Tests page button and the limit messages pointed at a Pro nobody can buy. Both now show only when Razorpay keys are set.
- The allowance meter says "% used" (it read like "% left").
- The "not for your exam" messages named only JEE, NEET and B.Tech; they now list school, GATE and placements too. Sign-up says UPSC, CA and Other get lecture notes and doubts but no tests yet.

**Found, still open**
- Payments: Razorpay keys on the server (see 7h).
- Slow pages (2 to 4 s; last-day 4 s, its first-ever load per syllabus up to 14 s while the AI ranks chapters once for everyone): the Tokyo database (see 7h). One query from Mumbai costs about 0.15 to 0.35 s, and last-day needs about 22.
- The free AI allowance (30 units a day) covers about two 30-question tests; a 90-question mock uses 17.
- Many papers at once hit the free Groq limit: 17 written together took up to 10 minutes (GATE CS full). Expect waits when a class starts papers together.
- Not tested on focs.in itself: NEET and school accounts (each needs an emailed code; tested on the local copy instead), Buy Pro with real keys, Live Lecture with a real shared tab.
- Test accounts left on focs.in: id 15 (`qa.hardtest.*@example.com`, never verified), id 16 (`mukul06499+jee@gmail.com`, one used mock, a "QA question please ignore" post in Ask a senior, a parent link).

## 7j. Fixes from the retest of the live site (27 October)

A second retest of focs.in (71/100) found 15 problems; all but payments are fixed.

- **Wrong AI answers.** Pop quizzes and checkpoints are now solved by a second model before a student sees them (`ai._sound_question`, which reuses `_checked_mcqs`); a rejected question is written again once, and a pop quiz that still fails returns "try again" rather than a wrong key. Flashcards (`_checked_cards`) and true/false statements (`_checked_statements`) get the same second-model check. Practice sets top up the questions the checker dropped, once.
- **False claims in notes and sheets.** The board-notes and revision-sheet prompts now forbid describing diagrams or number lines, inventing numbers, and any claim about the exam (syllabus, "asked in 2023").
- **Options that did not render.** `services/math_text.py` (`clean_option`) puts back brackets written as LaTeX delimiters, adds missing dollars and falls back to plain text when the maths is unbalanced. Used for practice, checkpoint, pop-quiz and mock options.
- **Practice shortfall.** `/quiz/generate` returns a `notice` ("Only N of 5 ... could be written, and why"); `Practice.tsx` shows it.
- **Gap map.** Chapters are judged on questions answered; fewer than 2 answered is level `untried` ("Too few"), and blanks are shown separately (`attempted` on each row).
- **Studio.** Pausing freezes the last frame; if the share ended meanwhile the button becomes "Share again"; the counter says "boards saved" (saved notes, not frames read).
- **Smaller fixes.** `<br>` in answers (table cell becomes " · "), mock duration as "3h 20m" and the question count once, friendly validation messages (`validationMessage` in `lib/api.ts`), "Coming soon" instead of the Pro offer when payments are off, an empty-mentors state pointing to Ask a senior, copy that named the wrong exam, and the "Database: Supabase" badge removed from Settings.
- **Not changed:** the AI allowance cost model. A pop quiz now makes one extra (checker) call, which does not count against a student's allowance but adds to Groq's rate-limit load.
- Tests: `backend/tests/test_content_safety.py`; the whole backend suite, `tsc`, `vite build` and `npm run test:math` pass.

## 7k. Pop quizzes, full practice sets and photographed answers (28 October)

- **Disputed answers are settled, not dropped.** The checker (`CHECK_QUIZ`) now returns its own working. When it names a different single option than the key, a third model breaks the tie (`_checked_mcqs`, `_check_round`); the question keeps whichever key two of the three agree on, with that working as the explanation. No correct option, several, or no agreement: dropped. True/false statements work the same way (`CHECK_TF`, `_checked_statements`).
- **Pop quizzes always arrive.** `room_question` tries up to 3 times, then falls back to a question built from the notes instead of a 503. (Dropping every disputed question had made "Quiz me now" fail repeatedly.)
- **Practice sets come back full.** Missing MCQs and true/false statements are topped up, up to two rounds. A live run on the integer-inequality lecture returned all 5 + 3 + 1 with correct keys.
- **Photo of a written answer.** `POST /quiz/evaluate-photo` (multipart: question, key_points as JSON, model_answer, files). The vision model copies the handwriting as written (`READ_ANSWER`), and `ai.evaluate_answer` grades it like a typed answer; the copy comes back as `read_answer`. In Practice the button is "Photo of my answer" (opens the camera on phones). It uses the same vision models as photo doubts, so the server needs no new setting.
- Tests: `backend/tests/test_content_safety.py` (re-keying, tie-break, true/false flip, photo grading).

## 7l. Hard test of 28 October (four testers: Class 1-8, Class 9-12, JEE, NEET). Found, nothing fixed yet

- **Live sign-in was blocked.** focs.in emails a 6-digit code before an account opens, and test addresses at example.com never receive it. Only the public pages were tested live. JEE and Class 1-8 were run on local copies of HEAD (:8017/:8018, email code off). NEET and Class 9-12 were not tested behind login at all. Unverified live test accounts to delete: user ids 18-23 (`qa+…@example.com`). Live serves `index-Dkr09579.js`; a HEAD build gives `index-DI5SZqS5.js`, so live may be behind main.
- **Open: major**
  - Offline fallback turns prompt headers into questions ("Fill in the blank: Syllabus topic: ___ Numbers"; table rows as true/false), `services/offline.py:73-106` fed by `api/quiz.py:34-36`. Ask AI also saves its "can't answer" text as a doubt.
  - Wrong mock key: JEE mock 1 Q28, Kp = e^13.33 = 6.1×10⁵, not 1.2×10⁵. Two correct options: glucose Q39 and projectile T vs h. Mock questions skip the second-model check.
  - The same question appears twice in one chapter test (Class 6, Class 8).
  - Content above class level: scientific notation in Class 5, Diophantine equations in Class 8 notes. Questions reference figures that don't exist. Class 1 questions are long sentences.
  - Explanations number options from 0 ("option 0 matches").
  - Practice card clipped at 390px (`Practice.tsx:84-96`, needs `min-w-0`).
  - Onboarding defaults to 34 h a week for Class 1 (`OnboardingSimple.tsx:39`, `planner.py:74-78`). Goal copy mentions JEE for Class 1-8 (`planner.py:77`).
  - Results page after a test with nothing answered: filter defaults to WRONG (empty), and the advice says "every chapter held up".
  - No stream choice for Class 11/12 at sign-up; the default subjects are Science.
  - No JEE Advanced paper, though sign-up promises it (`mock_patterns.py:95-121`).
- **Open: minor**
  - `^` inside `\text{}` in question stems shows red (Q5 `m/s^2`, Q9 `mol^{-1}`).
  - Answers from the last 0.7 s are lost on tab close (`MockExam.tsx:155-161`). Stale "Not saved" toast.
  - Register takes 8-9 s because the email is sent inside the request (`auth.py:109-115`).
  - Chapter names show "(Class 6)"-style tags.
  - Photo marking gives 2/5 for "7 + 5 = 12" (`snap.py:138-146`, no class level).
  - Last-day revision is slow (up to 9.6 s), and its "past papers" copy is wrong for primary classes. Starter lists "full mock a week" but Class 1 has no mocks.
  - Sign-up card subtitles are cut off at 390px.
  - /pricing is a 404.
  - Repeated questions across tests (small bank).
- **Fixed on 28 October (same day).** Tests: `backend/tests/test_hard_test_fixes.py` and two new `test:math` cases. The full backend suite, `tsc` and `vite build` pass. Not yet re-tested in a browser.
  - Offline practice is built only from fact lines (`offline._fact_lines`), and the "can't answer" fallback is no longer saved as a doubt.
  - Near-copies are skipped within one paper (`question_bank.near_duplicate`, word overlap of 90% or more).
  - `scripts/reverify_bank.py` re-solves unverified AI bank questions and retires the ones the checker rejects. **Run it on the server** to catch keys like Q28.
  - Practice and notes prompts are held to the school class (`ai._level`, `topic_notes._school_level`). Explanations name options by their text, and questions never mention figures.
  - Smaller fixes:
    - Practice card fits at 390px.
    - Answers are saved on tab hide and 250 ms after a change, and the Section B toast clears when the subject changes.
    - Blank papers open on all solutions and get "answer more questions" advice.
    - Hours are scaled by class (`planner.school_hours_share`, mirrored in onboarding), and the JEE line is gone from school goals.
    - Chapter names show without "(Class N)" (`shownName`, display only: stored names unchanged).
    - Photo marking takes the class into account and gives full marks to one-step answers.
    - Last-day revision copy is fixed, and the Starter/Pro test lines are clarified.
    - Sign-up card hints wrap, and /pricing goes to /#pricing.
  - The sign-in code email is sent in a background thread (`login_code.send_in_background`), so a mail failure no longer shows a 502. The student uses Resend.
  - Class 11/12 get stream presets (PCM, PCB, Commerce, Humanities) in the subjects step.
  - New paper `jee_advanced` (Advanced-style: 8 MCQs at +3/−1 and 8 numericals at +4/0 per subject), written at bank level `jee_advanced` and never padded with JEE Main questions. The first papers will be slow while the bank fills.
  - Still open:
    - The live NEET and Class 9-12 run behind login (needs a test inbox or bypass).
    - The sign-up page background colour change below 840px.
    - Deleting test accounts 18-23 on live.
    - The bank is still small, so questions repeat across papers.
- **Passed:** exam engine and +4/-1 marking. JEE keys 72 of 73 checked by hand, with the Q28 slip above. Q26-30 navigation. Option shuffle. NCERT chapter lists for Classes 1, 3, 5, 6, 8 and 10-12. Lecture flow, Ask AI and photo doubt/grading. 19-20 pages per student with no console errors. Live prices ₹249/₹1449/₹2849 (JEE/NEET) and ₹149 (school).

## 7m. Room notes keep going (28 October)

- Switching from the Notes tab to Chat or Doubts no longer stops the board capture. `RoomNotes` stays mounted and is only hidden (`RoomView.tsx`).
- The note taker can **Pause / Resume** without un-sharing the tab. On resume, the board on screen is read afresh.
- When the host closes a room, every member's "room closed" screen offers **Save notes to my library**, and the host gets a Save toast. `POST /rooms/{code}/notes/save` now works on a closed room too, and `test_rooms_v3` covers it.

## 7n. Phone fixes: lecture by link, classroom orientation, phone layout (28 October)

- **Lecture by link** (`services/link_lecture.py`, `POST /capture/{id}/clip`, `components/LinkStudio.tsx`). Sessions with `source="link"` play the YouTube video inside Focs.
  - Every ~150 s actually watched, the browser sends that stretch. Gemini (native `generateContent`, `file_data` set to the YouTube URL with `video_metadata` offsets, `MEDIA_RESOLUTION_LOW`, about 10.5k tokens per 2 min) writes one note from the board and the voice.
  - If Gemini fails, the stretch is written from YouTube captions through `ai.speech_notes`.
  - Rewatched stretches are skipped (`_State.clips`). The note counts as lecture time and `board_note`.
  - This is the phone path: phones can't share a tab. Tests are in `test_link_lecture.py`.
- **Classroom camera:** the preview takes the camera's own aspect ratio, so a portrait picture is no longer a sliver. A Portrait / Landscape switch goes full screen and locks landscape where the browser allows it.
- **Phone layout:**
  - `Segmented` is `max-w-full overflow-x-auto`. Its no-wrap buttons used to push cards past the screen, as in the mock card.
  - Text columns in `flex-wrap` rows got `basis-48`. They were squeezed to one word per line, as in the mock record.
  - Mock pattern labels are fixed: JEE Advanced was shown as "current NTA".
  - A Playwright audit at 360 and 390 px over 26 pages with the demo seed found nothing left after the fixes.

## 8. Things worth knowing before you change code

- **No migrations.** On startup, `backend/app/core/database.py` runs `create_all` plus `_add_missing_columns()`.
  - A new nullable column on an existing model is added automatically.
  - Anything more (a rename, a type change) needs a hand-written step there.
- **Tests share one app and one database for the whole run.** The `client` and `auth` fixtures are session-scoped. A new test should register its own user with a unique email instead of relying on `auth`'s data, or tests will collide.
- **Endpoints are plain `def` on purpose.** FastAPI runs them in a thread pool, so OCR and AI calls don't block the websockets.
- **AI calls go through** `backend/app/services/llm.py` and `ai.py`. Each one checks the allowance (`services/usage.py`) and is written to the cost ledger (`services/ledger.py`, table `llm_calls`). Keep both when adding a feature.
- **Who may call an endpoint:** a new router goes in `STUDENT_AREAS` or `SHARED_AREAS` in `app/api/__init__.py`. In a shared router, an endpoint for one side uses `Depends(require_student)` or `Depends(require_mentor)`; an admin one `Depends(require_admin)`. A new public endpoint (no sign-in) must also be added to `PUBLIC` in `tests/test_access.py`, or that test fails.
- **Rate limits:** `Depends(limit("bucket", per_minute))`. They count per signed-in user, otherwise per address.
- **Language:** `user.language` is `en`, `hinglish` or `hi`.
  - Server text uses `language_rule()`. A formula that changes in translation is rejected and the English is kept.
  - Interface text: wrap it in `t("...")` from `useT()` (`frontend/src/lib/i18n.ts`) and add the English → [Hindi, Hinglish] pair there. `npm run test:math` fails if a Hindi entry isn't Devanagari or a Hinglish one isn't Latin script.
- **Accessibility:** `<Switch>` needs a `label`, dialogs trap focus, and icon-only buttons need `aria-label`. CI's axe job fails on any serious violation.
- **Markdown:** import it from `@/components/Markdown`, not `@/components/common`. Keeping it out of `common.tsx` is what keeps the markdown libraries off the first page. A new library big enough to matter belongs in its own chunk in `vite.config.ts`.
- **The guided tour points at `data-tour="..."` attributes.** Keep them when you restyle the sidebar or top bar. A new sidebar section gets a `NAV_HELP` line in `GuidedTour.tsx`.
- **Quiz prompts:** keep `explanation` before `answer_index` in the JSON the model is asked for. The model then works the answer out before choosing it.
- **Line endings:** git warns "LF will be replaced by CRLF" on Windows. That's harmless.

## 9. How we've been working

- Commit straight to `main`, one commit per finished item. Before pushing, run section 2 and then:
  ```
  git pull --rebase origin main
  git push origin main
  ```
- Commit messages say what changed for the student or teacher in the first line (for example, "W6: classroom mode, a phone on the desk reads a real board"), then the details.
- The plan tracker is in the shared doc. Mark items there as you finish them.

## 10. Open questions for the team

- **Hosting after the pilot:** the AWS credits run out in about a month. Stay on EC2 (paid), or move to another host? Who pays, and for the Groq key?
- **The study:** which school or batch? Who handles consent, including guardians for under-18s?
- **Who gives the 5-minute demo?** Rehearse it at least twice, once with the AI off.
- **The event rules:** does Devlympics accept a project that existed before the event? Check before submitting.
- **Mentors in the demo?** They're hidden in the event build for now (section 6, point 4).
- **AI budget for launch:** Groq's paid tier, and which second provider? Who holds those accounts?
- **Starter allowance:** is 30 units a day right, given one short lecture with a quiz and a few extras used 18?

## Mobile layout fix (2026-10-28)
- Found: at phone width (390px) the Rooms page's "Start a lecture room" card and the whole room view (video, topic bar, timer) ran off the right edge. Cause: responsive grids without a base column (`grid gap-4 xl:grid-cols-…`) size their one implicit column to the widest content. The segmented tab switcher also overflowed on Practice, Mentors and the room chat panel.
- Fixed: `grid-cols-1` base added to every such grid (31 files); the segmented control now scrolls sideways inside its own box.
- Checked: overflow sweep at 390px of Home, Plan, Practice, Mocks, Flashcards, Library, Settings, Leaderboard, Mentors, Classes, Last day, Studio, Rooms, room view, confusion map: nothing sticks out. Not checked: admin/mentor-only pages, the Android APK itself (it shows the same pages).
- Tablet pass (same day): swept 36 pages at 360/390/768/1024px (student, mentor, public). Fixed: room header now puts the title on its own line with buttons below on tablets (was a cramped button column beside a cut-off title); Rooms page goes two-column only at xl (the create form was squeezed at 1024 next to the sidebar); MentorChat grid got the single-column base. Open: room chat sits below the video on tablets (side-by-side only at xl), long tab rows scroll sideways with no fade hint.

## Mobile + tablet hard test, 4 parallel agents (2026-10-28 night)
Every page at 360/390/768/1024, light and dark, every function clicked through (two-user rooms, a full practice set and chapter test, mentor apply->approve->chat->call, admin).
Fixed:
- Rooms: Doubt / Ask AI on Enter was sent as plain chat (Segmented tabs inside the form were submit buttons). Segmented, Switch and dialog close are now type="button" app-wide.
- Settings: changing the password signed the student out (usage refresh used the revoked token). changePassword stores the new token at once; a 401 from a stale token retries once with the new one.
- Shell: notifications panel cut off at 360, cramped search list, tight header; toasts stuck out past the right edge on phones; icon buttons 40px on touch.
- Segmented: 36px on touch, edge fade when more tabs are off-screen, selected tab scrolls into view.
- Mock exam: action-bar labels cut at 360 (now 2-col grid, short labels below xl), submit summary table clipped on phones (now per-subject blocks), bigger palette / Sure-Guessing targets. Practice header wrap, keyboard hints hidden on phones, Last-day chips 36-40px, chapter-test chips bigger.
- Mentor/admin: hamburger 40px, admin header at 360, students table scrolls in its card, applications tabs on their own row, mentor chat shows the conversation before calls on phones, call-hours slots as a grid.
- Onboarding steps open at the top. OCR Lab and LinkStudio grids got the single-column base.
Then fixed (same night): a pop quiz with no topic, video title or captions now answers 422 "Set the room's topic first" (before any AI call or quota) instead of quizzing on the room name; question writers and both checkers (practice ai.py, mock question_bank.py) now treat the same value in another notation (1 C/s vs 1 C.s^-1, 0.5 vs 1/2) as a second correct option, so such questions are rewritten or dropped; written-answer score reads "out of 10" (was a bare "/ 10"; marking out of 10 is intended); master-session form clears date and repeat after posting (keeps seats/price/length); login/signup links, show-password eye (40px) and consent checkbox got bigger tap areas.
Open: the equivalent-option rule is prompt-only, not proven on a live batch. Not tested: real Studio capture, a library lecture with data, real payments, live call rooms, notch padding on a device, dark theme on tablets.

## The never-tested items, tested (2026-10-28 late night)
- Live lecture, end to end on a 390px phone (Chrome fake camera = a generated chalkboard y4m that changes board at 60 s, fake mic = SAPI teacher voice): classroom mode -> board read -> captions every ~20 s -> notes per board -> End -> revision sheet -> Library lecture page (overview, key concepts, formula table, common mistakes, memory tricks, self-check, practice, "What the teacher said"). All rendered cleanly. Fixed: the last voice piece was posted after /end (409, lost from the transcript summary): End now stops the voice lane and waits up to ~8 s for pieces in flight. Re-run: no 409.
- Mentor call + master session: approved mentor, live call and live session seeded in a scratch DB; Join on student chat, student Master sessions, mentor chat, mentor Calls and mentor Sessions all open the same meet.jit.si room per call/session. FOUND: meet.jit.si won't start a room until a host signs in ("no moderators have yet arrived ... please log-in"), and on phones it pushes its app first. Added RoomTip under every Join (mentor: sign in once, Google works; student: waiting = mentor not in yet, pick "Join in browser"). OPEN DECISION: stay on meet.jit.si (free, host must sign in), JaaS (8x8, JWT, free to 25 MAU), self-hosted Jitsi (small VPS, no sign-in), or Daily.co (API key, free minutes). CALL_ROOM_BASE in config.py.
- Notch: tested by building a copy with env(safe-area-inset-*) replaced by 47/34 px. App/mentor shells were already right; full-screen pages weren't: landing, auth, onboarding x3, password reset, admin + login, legal, parent link, 404, error screen, exam, offline banner, toasts now pad for it. Still not on a physical phone.
- Landing header never stayed pinned (overflow-x-hidden on the root breaks sticky): now overflow-x-clip.
- Glass bars (app header, bottom nav, landing header) had NO blur in Chrome/Android: Tailwind/Lightning CSS merged our backdrop-filter + -webkit-backdrop-filter pair and kept only the prefixed one. Now only the unprefixed rule is written; the build adds the prefix.
- Dark theme at 768/1024: every page checked, consistent, no overflow.

## What each age group gets, and SSC CGL on the site (2026-10-30)
- **Timed tests only in the board years.** `syllabus.has_tests()` / `hasTests()`: school Classes 1-9 and 11 have no Tests page, no chapter or last-day tests and no tests in their plan (the API answers 403). Class 10 and 12 keep chapter tests and get a **Mock board exam**: Tests page, pick a subject, 50 MCQs over every chapter in 90 min (`board: true` on `POST /api/mock`, `BOARD_MOCK_*` in `mock_patterns.py`). It is objective only: the written half of a board paper stays under Practice.
- **Subjects** (`tools/school_syllabus/extra_subjects.py`, run after `build_school.py`): Class 6-8 add French, German and Spanish beside Sanskrit (the third language; the subject picker asks for one). Class 9-10 add Information Technology (402) and Computer Applications (165); IT is in the default set. Class 10 Social Science is already History, Geography, Political Science and Economics. Class 9's new NCERT book (Understanding Society) is one combined book, so it stays as one subject. Foreign-language chapters are CBSE's themes by level (A1 to A2), not a textbook.
- **Class 11-12 streams**: onboarding asks the stream first (PCM, PCB, PCMB, Commerce with Maths, Commerce without Maths with Informatics Practices, Arts), then the subjects can be adjusted. `STREAMS` in `lib/utils.ts`.
- **Sign-up**: UPSC, GATE and CA are gone from the exam tiles (`SIGNUP_EXAMS`); SSC CGL is in. Old accounts keep theirs (Settings still shows their own tile). Landing strip updated.
- **SSC CGL** (no AI key needed for any of this): onboarding uses the simple flow (Tier-I / Tier-II dates, approximate; goals in `planner.TARGETS["ssc_cgl"]`), the plan, Prep Hub, mocks (Tier-I and Tier-II patterns), an English / हिंदी switch on the exam and review screens (`components/QuestionMedia.tsx`, remembered per device), figures and picture options shown from `media`, and SSC CGL as a mentor exam. "Ask a senior" is not on for SSC: the seniors there are B.Tech students; SSC guidance goes through Mentors.
- Still open: the SSC question bank fills only when `scripts/import_ssc.py` runs on the PDFs (needs the Gemini key; `data/ssc/` is git-ignored). Until then SSC mocks need the AI to write questions.

## Question banks from F:\PYQ (2026-10-30)
- `F:\PYQ` held 4,247 Markdown "banks" (961,500 question blocks), but they repeat a few questions thousands of times (JEE Main Physics: 40,000 = 5 questions, every key (A)). School folder is placeholders ("best describes Topic G", options "Option A".."D"): skipped.
- `scripts/import_md_bank.py` keeps the unique ones: **1,475** (SSC CGL 1,430: Quant 1,103, Reasoning 147, GA 70, English 60, Computer 50; JEE Main, JEE Advanced and NEET 15 each). Stored as `source="practice"`, not as PYQs (the shift/year labels can't be trusted).
- Added with `--trust-key` (the files' own answers and explanations, chapter by keyword match) into the database in `SUPABASE_DB_URL`, i.e. live. The Gemini check (default mode) was stopped: the free key gave 429s, 6 questions in 8 min.
- Open: the keys were not re-solved. Chapters by keyword are rough (Quant leans on Profit/Loss 407 and Number System 296). The model check can still be run later (`python scripts/import_md_bank.py --src F:\PYQ --stage check`), but store skips questions already in the bank, so fixes would need an update step.
- On this PC Smart App Control blocks SQLAlchemy's compiled `*_cy.pyd`; scripts ran through a wrapper that loads the pure-Python `*_cy.py` instead.
- Same day, later: `reverify_bank.py --source practice --all` re-solves the imported questions (Groq second model) and retires the ones it disagrees with. Trial on 12: 10 kept, 2 retired (one rightly: two correct options; one a correct question the checker got wrong). `fill_bank.py --exam ssc_cgl --exam cbse_10 ...` now fills SSC CGL and school-class chapters too (MCQs, written by one model and kept only when a second agrees), within the Groq reserve for students. Running in the background into the live bank, logs in `data/pyq_md/*.log`.

### Question bank fill: where it stopped (2026-10-30, paused on request)
- Imported from F:\PYQ: 1,475; the second-model re-check kept 1,319 and retired 156 (wrong key, two right options, or broken; a few good ones are lost to a strict checker).
- New AI questions (written by one model, kept only when another agrees): **345** = JEE Main Physics 105, NEET Physics 159, SSC Quant 53, SSC Reasoning 28. About 1,660 usable questions added today, all in the live bank (SUPABASE_DB_URL).
- Two free lanes ran side by side: Groq (`fill_bank.py --exam ssc_cgl --exam cbse_10 --exam cbse_12`, keeps the 450-request student reserve) and Gemini (same script with env `LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai`, `LLM_MODEL=gemini-3.1-flash-lite,gemini-3.5-flash-lite`, `LLM_API_KEY=<GEMINI_API_KEY>`, `--reserve 0`). Gemma 4 on the Gemini key fails JSON mode (500), gemini-2.5-flash-lite is 404. No paid keys: the founder can't spend on API calls.
- **To resume** (safe to re-run, fills only what's short, level by level), from backend/: Groq lane `fill_bank.py --exam ssc_cgl --exam cbse_10 --exam cbse_12 --per-chapter 40`, then `--exam cbse_9 --exam cbse_11 --exam cbse_8 --exam cbse_7 --exam cbse_6 --per-chapter 30`; Gemini lane `fill_bank.py --per-chapter 40` (JEE/NEET) with the env above. On this PC run them through the pure-Python SQLAlchemy wrapper (Smart App Control). Logs in data/pyq_md/.
- Next idea: the founder may supply PDFs (PYQs, MCQ books, study material). PYQ PDFs: `import_pyq.py` (data/pyq/) and `import_ssc.py` (data/ssc/). Practice-MCQ books need a small change (import_pyq keeps only tagged past questions); study material isn't wired to anything yet. Never copy a coaching book's own solutions.
- The pendrive F: dropped off mid-session and Windows offered to format it: don't; nothing needs it (already imported).

## SSC CGL PYQs from the founder's PDFs, free (2026-10-30)
- Source: 42 PDFs (28 different; the rest are the same file downloaded twice) in the founder's `FOCS docs\ssc-cgl` folder: official SSC response sheets (green tick on the right option), Testbook/Adda copies, memory-based and "similar-based" papers, 2016-2026, Tier-I and Tier-II. Not in the repo (copyrighted coaching PDFs); the work folder `data/ssc/` is git-ignored.
- No paid API (the Gemini key is free tier: 20 requests a day on flash). So: `backend/scripts/ssc_extract.py` reads the PDF's text layer with pymupdf (no AI), cuts it at the question markers each PDF uses (`Q.12`, `Que. 12`, `QID : 30741 -`, `Question 18.`, `7.From`), takes the options, the printed answer or the ticked option (a response sheet's tick is a small picture: the one mark that differs from the other three), the Hindi copy (dropped when the PDF's Hindi font is broken), and cuts figures out of the page (coaching banners skipped: a big picture on 3+ pages is an ad; pale watermark removed, Testbook's cyan figure lines kept and darkened).
- `backend/scripts/import_ssc.py` (rewritten, Gemini removed): `extract` → `read` (the ~2% whose text is incomplete, read from a picture by **qwen2.5vl:3b** in Ollama) → `check` (**qwen3:8b**: solves it, files it under the SSC syllabus chapter/topic, writes our solution; a disagreement with the paper gets a second, thinking pass; Maths/Reasoning still disagreeing goes to `data/ssc/review.json`, General Awareness/English keep the paper's key) → `store` (bank as `source=pyq` with year and paper, or `practice` for similar-based/CHSL; figures copied to `frontend/public/q/ssc/`, which then needs a commit and deploy). `--report` prints the counts per PDF.
- Extracted: 19,802 questions, **17,390 different** to check, 1,991 repeats across PDFs, 421 to read from pictures. A question whose figure was drawn (not a picture) is dropped rather than shown without it.
- Running on the founder's laptop (RTX 4050): `data\ssc\run_import.cmd` (read, then check, then `data\ssc\report.txt`). About 15-25 s a question: two to four days. Resumable: run the .cmd again after a restart. Keep the laptop on charge.
- When it finishes: `python scripts/import_ssc.py --src "<folder>" --stage store`, commit `frontend/public/q/ssc/`, deploy. Look through `data/ssc/review.json` (paper answer vs checker answer) before deciding on those.
- 30 October, 14:50: the first run stopped at once (read: the vision model once gave no JSON; check: `MemoryError` hashing the PDFs while the laptop had ~2.5 GB free). Fixed in `import_ssc.py`: a bad answer is retried and then skipped (tried again on the next run), PDFs are hashed in 1 MB pieces. Restarted with `data\ssc\run_import.cmd`; progress in `data\ssc\read.log` and `check.log`.
- **Check on Kaggle's free GPU (30 October, evening):** `backend/scripts/kaggle_vllm.ipynb` serves Qwen3-8B-AWQ with vLLM on Kaggle's 2×T4 and prints a temporary Cloudflare link and key. Then, from `backend/`: `python scripts/import_ssc.py --src "<folder>" --stage check --remote <URL> --key <KEY> --workers 48 --live`. Same prompts and rules as the laptop check, 48 questions at a time, in batches of 100; with `--live` each batch goes into the live bank as it finishes. Questions with figures need `frontend/public/q/ssc/` committed and deployed before their pictures show. A Kaggle session lasts up to 12 hours: when it ends, run the notebook again and restart the command with the new URL and key (it carries on where it stopped).
- **31 October:** `--workers 16` (`data/ssc/run_remote.cmd <URL> <KEY>`): 28-48 at a time overfilled the T4s' memory (vLLM kept restarting answers) and hit Cloudflare's 100 s limit. The thinking pass is capped at 2,500 tokens. A batch of 100 takes 20-40 minutes (Maths/Reasoning think on disagreements), ~150 batches left. Progress at 17:35: 4,361 checked (4,146 ok, 196 review, 19 dropped), ~14,190 to go. Plan: the founder's Kaggle until the weekly ~30 GPU hours run out, then a friend's own Kaggle account runs the same notebook and the laptop points at its URL. Figures pushed as they come; push `frontend/public/q/ssc/` again at the end.

## Hard test and fixes before the Razorpay deploy (2026-10-31)

Tested on localhost (latest code) with throwaway accounts, which were deleted afterwards. Note that localhost uses the **live Supabase database**, so test accounts made there are real rows.

| Fix | Where |
|---|---|
| **Sign-up needs the Terms**: the API took `accepted_terms: false` (only the page's checkbox enforced it). Sign-up is also **closed for UPSC, GATE and CA**, by email and by Google; students already on them keep working | `api/auth.py` (`CLOSED_SIGNUP_EXAMS`) |
| **Deleting an account failed** for anyone who had ever opened a Pro checkout (`payments` pointed at the user). Unpaid checkouts are deleted now; a paid one is kept for the accounts, on a row with no name, email or password | `services/account.py`, `tests/test_account.py` |
| **SSC papers take real PYQs first** (they carry figures and, where the PDF had it, Hindi); before, a paper could be mostly AI-written practice | `services/question_bank.py` (`pick`) |
| **Figures under `/q/` are cached for a year** (named by a hash of the picture) | `main.py` |
| All 2,176 SSC figures committed (were on the laptop only, so they 404'd once deployed) | `frontend/public/q/ssc/` |
| `/app/mock` for a class without tests (6-9, 11) showed an empty page; it now explains | `MockTests.tsx` |
| Choosing हिंदी on a question with no Hindi says so | `MockExam.tsx` |
| Landing top strip now reads "Focs — Focus on Cognitive Studies", centred on phones | `Landing.tsx` |
| Tests no longer pick up the real Razorpay keys from `backend/.env`; launcher reads the minimal `/api/health` | `tests/conftest.py`, `scripts/launch.py` |

**Still open.** Only 492 of 19,802 extracted SSC questions have Hindi: most PDFs carry none as text, so the toggle rarely has anything to switch to (translating at import would fix it). A first board mock takes about 3 minutes while the AI writes it (free-tier rate limits); later students get it from the bank at once. The Kaggle check runs about 33 minutes a batch of 155, too slow to finish. Nine older QA accounts from 27-28 October are still in the database.

## Phones, tablets and latency (2026-10-31, later)

`frontend/scripts/responsive.mjs` opens every page at 375, 412, 768 and 1024 px wide (signed out, and as a Class 10, a Class 7 and an SSC student), fails on a page wider than the screen, a script error or a failing API call, lists small tap targets and slow loads, and deletes its accounts at the end: `RESP_CHANNEL=chrome node scripts/responsive.mjs`. Result: no page overflows on any size and no errors (the Google button's 403 on `127.0.0.1` is local only: that origin isn't in the OAuth client).

Fixed: the landing header on phones and tablets (logo was off-centre; **Sign in was missing on phones**, now an icon), the top strip's theme button was a 24x17 tap target.

**Latency.** The Supabase database is in **Tokyo** (`ap-northeast-1`); the server is in Mumbai. Every query is a ~125-150 ms round trip, and a page makes 10-20, so the dashboard takes 2-5 s and Revise 4 s however fast the code is. Code changes: no `pool_pre_ping` (a round trip per request; TCP keepalives and a 240 s recycle instead), and the user is read once per request, not twice (the routers' role check passes it on to `get_current_user`). **The fix that matters is moving the database to Mumbai (`ap-south-1`)**: a new Supabase project there, `pg_dump`/`pg_restore`, then the new `SUPABASE_*` values in `/etc/focs.env`. Round trips drop to ~1 ms and every page to well under a second.

## Phone hard test, four auditors (2026-10-31, night)

Tested on throwaway local copies (sqlite), never on the live database. `responsive.mjs` now also runs NEET and JEE students.

| Fixed | Where |
|---|---|
| **NEET, JEE and SSC were offered Economics, Commerce and Computer Science** in Live Lecture's subject list, and a board could be filed under them by the AI or the keyword guess. Every exam with a syllabus now picks from its own subjects, and whatever comes back is checked against them | `pages/Studio.tsx`, `services/ai.py` (`fit_subject`), `live.py`, `link_lecture.py`, `api/sessions.py`, `api/notes.py` |
| Chapter test card said 30 min for 15 NEET questions (real: 17; SSC 9) | `ChapterTestCard.tsx` |
| Practice promised the exam's pattern but gave JEE/NEET/SSC True/False and written questions by default | `Practice.tsx` |
| Score trend had no Biology or SSC lines; `/pricing` answered 404; search offered a JEE mock to UPSC/CA/Other | `MockTests.tsx`, `main.py`, `AppShell.tsx` |
| Mentors sent school and SSC students to Ask a senior, a dead end for them; the notifications empty state talked about juniors to everyone | `Mentors.tsx`, `NotificationBell.tsx` |
| iOS zoom on every field (now 16 px on touch screens); Flashcards delete was hover-only; bottom bar ran off screen at 360 px with large text; onboarding "Done" clipped at 360 px; sign-up button was disabled with no reason given; exam header cut off | `index.css`, `Flashcards.tsx`, `AppShell.tsx`, `Onboarding*.tsx`, `Auth.tsx`, `MockExam.tsx` |
| Smaller: cut-off names now wrap, "1 chapters", "Full JEE Main mocks" on the landing page, "ssc students", jargon (SM-2, FocsOCR, Mature), shorter phone landing page, `dvh` for phone toolbars | `PrepHub.tsx`, `LastDay.tsx`, `Landing.tsx`, `Dashboard.tsx`, `dialog.tsx` |

**Open.** (1) Lectures saved before this fix keep their old subject; nobody has counted them in the live database yet. (2) `neet.json` and `jee.json` have no Experimental Skills or Practical Chemistry unit: check against the official NMC and NTA syllabus before adding, because it changes plans and question banks. (3) `api/concept_check.py` is not mounted and nothing calls it: dead code. (4) Not tested on a real iPhone or Android.

Round two: a score script (all pages at 360 and 768 px, six kinds of student) took cut-off text from 31 to 0 and tap targets on touch screens to 40 px (small buttons, chips, range sliders, text links, Revise, Mentors, Library). NEET skips the one-option first onboarding step. Solutions in a mock review open for wrong answers only. The yearly activity chart's cells stay small on purpose.

## Notes that fit what was studied (2026-10-31, night)

Before: every board used one template, the revision sheet had EXACTLY the same sections for 5 minutes or 3 hours, and it read only the first 9,000 characters, so the end of a long lecture never reached it.

- **Board notes** (`ai.NOTES_SYSTEM`): the board decides the shape: Definition, Key ideas, Formulas, Derivation, Steps, Compare, Worked example, Exam tip, only those it earns, and a line or two on the board gets a line or two. All the grounding rules stayed.
- **Revision sheet** (`ai.SHEET_SHAPES`, `sheet_size`): Quick recap (up to 3 boards and under 350 words), Revision sheet, or Full lecture guide (14+ boards or 2,200+ words: lecture map, one section a part, 5-8 questions, 10-14 cards). A subject of words gets Key terms in place of formulas. `lecture_material` gives every board its share of the 9,000 characters. A sheet with no sections is retried once.
- **Look** (`NoteBlocks.tsx`, `RevisionSheet.tsx`, end of `index.css`): each kind of content has its own form, numbered sections, section jumps, a tappable lecture map, read time, self-check progress; formula tables become small cards on phones. Works on notes already saved. Long lectures get a list of all boards.
- A model sometimes drops a table's |---| line, which showed raw pipes; the app repairs it (`math.ts` `repairTables`, in `test:math`).

Checked with real AI output on all three sizes, light and dark, at 390 px.

## Phone experience (2026-10-31, night)

- **Back button**: closes an open sheet, drawer, search or photo zoom and stays on the page (`lib/overlay.ts`, `useBackClose`).
- **Sheets** drag down by their handle; **a new page starts at its top**, Back returns to where you were; tapping the current tab goes to the top.
- **Share a YouTube video into Focs** (installed web app: `share_target` in the manifest; Studio fills in the link) and a **Paste** button on the link box. The Android shell has no share intent yet.
- **Export** on a phone opens the share sheet.
- **Slow connections** see a logo and a moving bar instead of a blank page (`index.html`).
- Fixed: mentor sign-up was 330 px wide on a 320 px phone. Hindi notes keep their formula and example forms, revealed answers no longer print twice, the offline line stays out of the formula panel.

## Hard test rounds, final state (2026-10-31, night)

Five rounds with eleven auditors, on local copies only. Last results: `frontend/scripts/phone-score.mjs` 455 issues down to 3 (230 page views: cut-off text 0, wider than the screen 0), `responsive.mjs` every page fits every screen with no script or API errors, backend tests and `test:math` pass. Onboarding reaches a built plan for NEET, JEE, SSC, Class 12 and B.Tech. Mock marks checked on NEET, JEE, SSC and a board paper; timers, resume and auto-submit work.

Round five caught two of tonight's own bugs, now fixed: signing out from the menu left a blank page (the Back handling raced the redirect), and a closing menu could stay on top. Keep `overlay.ts`'s deferred `history.back()`.

**Open, needs a person.**
- Deploy: none of tonight's work is live until the server is updated.
- Check on a real iPhone and Android phone: real keyboard, share from YouTube, install, real tab capture. All testing was Chrome's phone emulation.
- Lectures saved before tonight keep their old subject (could still show Economics for a NEET student); the count on the live database has not been run, and fixing them is a one-off change to live data.
- `neet.json` and `jee.json` have no Experimental Skills or Practical Chemistry unit: check the official NMC and NTA syllabus.
- Hindi covers the main reading path; long help text, toasts and strings with numbers are still English. The Android shell has no share intent yet. AI grading of written answers was tested with fake replies.

## Founder's phone check (2026-11-01)

- Removed the add-to-home-screen bar: the founder doesn't want an install offer (the browser's own banner is held back too, in `main.tsx`).
- Home's Subjects list and weak topics follow the student's field (`api/analytics.py`): their own subjects, then other courses of their branch they have work in. Physics, Chemistry and the like from an exam they used to prepare for, and General, no longer show; those lectures stay in the Library.

## Papers weighted away from easy questions (2026-11-07)
Students said the questions read too straight-forward. `services/question_bank.py` (`pick`) now shuffles with `DIFFICULTY_WEIGHT` (easy 0.4, hard 2.0, medium 1): a bank that is a quarter easy gives about 13% easy in a paper (was 25%), 45% easy gives 26%. Applies to every exam. Real PYQs are untouched. Note the bank's difficulty tags come from a small model and are mostly "medium" (SSC PYQs: 1,829 easy, 16 hard of 7,558), so the effect is mild; the tags are not a measured difficulty. Next: rewriting the bank's own (non-PYQ) questions less directly, `backend/scripts/reframe_bank.py`: Qwen3-8B alone is not good enough (a 12-question sample gave 2 good rewrites and one wrong question that its own check passed), so the writer must be a bigger model with Qwen only checking, and nothing is applied without a person reading a sample.

## Audit of focs.in and the repo (2026-11-10)
Checked without logging in, so no real accounts were created. Backend pytest passes (~425), typecheck passes, test:math passes, lint has 1 warning, npm audit finds 4 low.
**Found, not fixed:**
- focs.in runs an Oct 31 build (it still has the install offer). The Nov 1 Home change, the SSC NUL fix and the weighted papers are not live.
- The sitemap lists `http://` URLs because uvicorn behind Caddy ignores X-Forwarded-Proto (add `--proxy-headers --forwarded-allow-ips`). Anything else built from `request.base_url` comes out as `http://` too.
- www.focs.in serves a copy of the site instead of redirecting to focs.in. Every page has the same `<title>`. og:image is a relative path. The landing page is a client-side app with no prerendered text.
- On a phone, /pricing shows a blank screen: it scrolls to the section before the fade-in runs. axe on /pricing: color-contrast (17 on desktop, 5 on a phone) from the half-faded reveal. link-in-text-block on /signup and /mentor/signup.
- Responses carry `Server: uvicorn` as well as Caddy. HSTS has no includeSubDomains. The CSP has no script-src.
- CI does not run lint. `api/concept_check.py` is still dead code. The git pack is 243 MB.

## Fixes from the audit, ready to deploy (2026-11-10)
**For Ashpreet:** pull, then do the usual redeploy (section 7h, steps 2 to 5). Nothing in `/etc/focs.env` or the Caddyfile has to change.

| Fix | Where |
|---|---|
| uvicorn trusts forwarded headers from Caddy only (loopback and Docker's bridge, `172.16.0.0/12`), so the app sees `https` and the sitemap lists `https://` URLs. A visitor can't fake their address: the client is the rightmost address that isn't a proxy | `Dockerfile` CMD |
| `Server: uvicorn` is no longer sent (Caddy still adds its own: `header -Server` in the Caddyfile removes that too, optional) | `Dockerfile` |
| HSTS has `includeSubDomains` | `main.py` |
| **Script allow-list, report-only**: `Content-Security-Policy-Report-Only`. Our files, the inline theme script (by hash, read from the build), Google sign-in, YouTube, Razorpay (`'unsafe-eval'`: checkout.js calls `new Function`). What it would block is logged as `csp would block` (`POST /api/csp-report`). Checked locally: no reports on the landing, sign-in and app pages, nor while loading Google, YouTube and Razorpay checkout; an injected script was reported. **After deploying:** `sudo docker logs focs 2>&1 \| grep "csp would block"` for a few days, including one real payment. If it stays quiet, rename the header to `Content-Security-Policy` in `main.py` to enforce it | `main.py` (`_script_policy`) |
| CI runs ESLint with zero warnings allowed; the one warning is fixed | `.github/workflows`, `Onboarding.tsx` |
| Removed the dead `api/concept_check.py` | |
| Terms, Privacy and "Create a student account" links are underlined (axe: link-in-text-block) | `Auth.tsx` |

**Not problems after all:** /pricing on a phone is fine (the blank screenshot was taken mid-scroll), and so is its contrast warning (text caught mid fade-in). Sentry already loads after the first page draws.
**Left on purpose:** SEO (www redirect, page titles, og:image, prerendering), skipped at the founder's request. Moving the database to Mumbai (a Supabase job). Splitting big files. Shrinking the repo.

## Buy full mocks without Pro (2026-11-10)
A student who has used the week's free mock can buy one (₹9) or a pack of 5 (₹29); prices changed the same day, see below. Bought mocks never expire, and the week's free one is always used first. Prices are `MOCK_PRICE_INR`, `MOCK_PACK_SIZE` and `MOCK_PACK_INR` in `config.py` (or `/etc/focs.env`); setting a price to 0 takes it off sale.
- Payments use purpose `mocks`, with `ref_id` holding how many were bought. A mock started on a bought credit is marked `config.paid`, and credits = bought − started paid ones (`services/mock.py`, `credits`/`quota`). The endpoint is `POST /billing/mocks?pack=one|pack`.
- Mock sales count toward the free-AI budget (like Pro income) and show in the admin's revenue line.
- On the page: "Buy 1 mock · ₹19", "5 mocks · ₹79" and "Or get Pro" replace the Pro-only button once the free mock is used. The badge shows how many bought mocks are left (`MockTests.tsx`).
- Test: `test_full_mocks_bought_without_pro`. Checked in a browser with a dev test payment at 390 and 1280 px. Not yet tested with real Razorpay: **after deploying, buy one ₹19 mock to check**. No database change is needed.

## Pro mocks unlimited, cheaper packs, lecture focus mode, rough pad (2026-11-10, later)
- **Pro has unlimited full mocks** (`MOCKS_PRO_PER_WEEK=0`). Starter can buy **5 for ₹29 or 1 for ₹9** (`MOCK_PACK_INR`, `MOCK_PRICE_INR`). Pro and Institute are never offered packs. The plan text, landing page and the out-of-mocks message all say this. Risk: a Pro student's papers come from the question bank, and the AI writes only what the bank lacks, so watch the AI cost in admin.
- **Lecture focus mode** (`components/LectureFocus.tsx`, used by `LinkStudio.tsx` and `Studio.tsx`): on screens under 1280 px it is on by default (the choice is remembered in `focs-lecture-focus`). The lecture stays pinned at the top. Notes, doubts and quiz settings are hidden, and new-note pop-ups are silenced (a dot appears on Notes instead). A slim bar under the video has Notes, Doubt and Quiz me, plus an icon to show everything. Notes open as a sheet from the bottom while the video plays on, and Back closes it. Desktop is unchanged. Pop quizzes still appear.
- **Rough pad** (`components/RoughPad.tsx`): a **Rough** button in the exam screen (next to Questions) and on Practice opens a pad under the question. It has pen (pressure-sensitive with a stylus), eraser (also a stylus's eraser end), undo, clear and a bigger size. Each question gets its own page, about 2.4 screens tall and scrollable. Once a stylus is seen, fingers scroll instead of drawing (palm rejection). Pages are kept in sessionStorage per test, so a reload keeps them; nothing goes to the server.
- **Checked:** in Chrome at 390 px and on an 820x1180 tablet: drawing, a clean page on the next question, the drawing back on Back, kept after a reload, no page wider than the screen. Focus mode at 390 px and 1440 px: sheet opens, Back closes it, leaving focus shows everything. Backend tests pass.
- **Not checked:** a real stylus (Apple Pencil, Android S-Pen) on a real tablet, the rough pad on Practice (it needs the AI to write a set; same component), and focus mode with the camera on a real phone.

- **SSC figures (2026-11-10):** the Kaggle check has put about 10,000 SSC questions in the live bank so far; their pictures (`frontend/public/q/ssc/`, 4,257 files) are committed and need a deploy to show. About 8,500 questions are still unchecked (`data/ssc/run_remote.cmd <URL> <KEY>`); the figures of the rest need one more commit at the end.
