# Focs — every lecture, understood

[![CI](https://github.com/Mukul07777/Study_Platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Mukul07777/Study_Platform/actions/workflows/ci.yml)

**Focs carries the lecture to the student, and the confusion back to the teacher.**

> Picking up the project? Start with [HANDOVER.md](HANDOVER.md): how to run it, what's built, and what's left.

### The gap

A lecture moves at the teacher's speed, in the teacher's language. The student who can't keep up falls behind
quietly: they don't raise a hand, and the teacher never finds out which board lost them.

### The two sides

| Teacher | Student |
| --- | --- |
| Board and voice, at their speed, in their language | Needs their own pace, their own language, their own way of reading |
| Can't see who is lost, or where | Won't say they're lost |

### The bridge: four lanes

| Lane | Direction | What it does | Status |
| --- | --- | --- | --- |
| Speed | teacher → student | The board, read by Focs's own OCR model, and the teacher's voice become live notes and captions (after the lecture, a summary of what the teacher said, the exact words a tap away): from a lecture tab, or in a real classroom from a phone on the desk (its four marked corners straighten the board before it's read) | Built |
| Language and ability | teacher → student | Notes, quizzes, flashcards, revision sheets and doubts in Hindi or Hinglish, every formula checked unchanged | Built, with read-aloud (formulas said as words), an accessibility mode, and the bridge screens (menu, live lecture, confidence, "I'm lost", waits, Ask a senior) in Hindi or Hinglish too |
| Understanding | teacher → student | Every answer locked in as Sure or Guessing; blind spots (sure and wrong) lead the summary, weak spots (counted double) and the plan | Built |
| Return | student → teacher | Anonymous "I'm lost" taps, wrong answers and doubts, each pinned to the board on screen, reach the host live; after, a confusion map ranks the boards and offers a recap or a check on any of them | Built |

After the lecture, the bridge reaches students who have done the course: in *Ask a senior* a junior's question gets
an AI draft at once, labelled as one, and a senior (a B.Tech student who confirmed their college email, so the badge
means something) checks or corrects it. JEE and NEET aspirants ask B.Tech students the same way. Seniors hear about
new questions in the bell, and an answer the asker marks as the one that settled it counts on the leaderboard.

Waiting is part of the bridge too: whenever the AI is working (a doubt, a practice set, a revision sheet, a
note written for the first time, a translation, a test result being read) Focs says what it's doing and hands the
student one thing from their own material meanwhile: a flashcard that's due, a question they got wrong before, or
a formula to say aloud. That needs no AI, so it works exactly when the AI is busy.

### The evidence

- FocsOCR reads 240 held-out lecture frames at a 0.48% character error rate, against 7.27% for PP-OCRv4 on the
  same frames ([details](#focsocr--the-model)). Those frames are synthetic, which flatters any model. A benchmark on real,
  openly licensed lecture frames and classroom photos (`benchmark_ocr.py --set real`, hand-checked labels) is being collected.
- Board-to-note delay, caption delay and cost per lecture hour are measured by `scripts/demo_metrics.py`. With the AI
  off (OCR only, a floor), a new board gets its notes in a median 2.6 s; the hosted demo with its AI key is measured
  before any number is quoted.
- A small learning study (12–20 students, with and without Focs, tested straight after and the next day) has its protocol
  and analysis ready; results are reported with their interval and limitations. See [docs/evidence](docs/evidence/README.md).
- Accessibility: axe (WCAG 2.1 A and AA) finds no serious or critical problem on the main pages, signed out and in,
  in both themes; CI checks it on every push (`npm run test:a11y`).

The event build (`VITE_EDITION=bridge npm run build`, or `docker build --build-arg VITE_EDITION=bridge .`) opens on
this story and shows only the screens on the bridge; everything else still works by URL. `scripts/seed_demo.py` makes
labelled demo accounts with everything the demo opens written in advance; [docs/DEMO.md](docs/DEMO.md) covers hosting,
rehearsal and the 5-minute script.

---

Focs is an AI study companion for Indian exam aspirants (JEE, NEET, UPSC, GATE, CA, boards,
college). While a student watches any lecture in a browser tab, Focs **reads the board with its
own OCR model**, writes exam-ready notes, **pops quick quizzes during the lecture**,
answers doubts in context, and turns every lecture into a revision sheet, practice sets and
spaced-repetition flashcards.

---

## Quick start (Windows)

Double-click **`run.bat`**. That's it.

The first run sets everything up (≈3–5 minutes), later runs start in seconds:

1. creates `backend/.venv` and installs the Python packages
2. creates `backend/.env` with a random secret key
3. builds the web app once (needs Node.js 20+ the first time only)
4. starts the server and opens **http://localhost:8000**

Requirements: **Python 3.11 or 3.12** and **Node.js 20+**.

> **Turn on AI notes (recommended, free):** get a key at <https://console.groq.com/keys>, put it in
> `backend/.env` as `GROQ_API_KEY=...`, and restart `run.bat`. Without a key Focs runs in
> **offline mode** — OCR, organised notes, cloze quizzes and flashcards all still work.

| Script | What it does |
| --- | --- |
| `run.bat` | Set up (first time) and launch. `run.bat rebuild` forces a fresh web build. |
| `dev.bat` | Development: API with auto-reload on :8000 + Vite hot reload on :5173. |
| `train_ocr.bat` | Re-train FocsOCR on your GPU, export it into the backend, benchmark it. |

---

## What's inside

| | Feature | How it works |
| --- | --- | --- |
| 🧭 | **Personal mentor plan** | Two-minute onboarding (exam, class, exam date, rank goal, dream college, daily hours, what's covered) → a realistic plan month by month, week by week and for every day: learn, practise, revise (after a week, a month, three months), chapter tests and full mocks. Reality checks for time and goal, "days behind/ahead", and priority mode (most marks per hour) when time is short. Rebuilt from progress every time; no AI cost. |
| ✏️ | **An editable plan** | *Edit plan* on the plan page: hours as two numbers or day by day (with rest days), exam date, goal. *Change the order*: take any chapter next or leave one out (and bring it back). Today's list takes your own tasks, and a planned task can be taken off for today without losing it. |
| ⏳ | **Last-day revision** | One day before the exam, a subject test or a class test. The student picks the syllabus first (all of it, one subject, or chosen chapters and the topics of each that are coming) and gets everything important in it, most marks first: weightage, their own test accuracy, weak spots and how long since they looked decide the order and the minutes. Every chapter lists its most-asked topics first (the AI's reading of past papers, judged once per chapter and shared by everyone); a chapter not studied yet gets a short block for those topics only, or, with "only what I've studied", waits under "leave these today". A revision capsule per chapter, the redo queue / formulas / flashcards first, chapters added to or taken off the list, a night-before checklist, and at the end a final test on exactly the day's list: its chapters, and in a chapter revised in part only its listed topics, timed and marked like the student's exam. |
| 🎯 | **Weak spots (tests taken anywhere)** | Attach the result of a coaching or school test (screenshots, photos or a PDF of the score report or marked paper). Focs reads the marks and every wrong question, places each in its chapter and topic, and the student corrects the list before it is saved. Each weak topic then gets its notes and questions, leads the daily plan one a day, moves up last-day revision, and stays until a re-check clears it: 70% on a practice set of the topic or on a Focs chapter test. Miss it again in the next test and it comes back with more weight. |
| 🗂️ | **Prep Hub** | The whole JEE (58 chapters, 347 topics) and NEET (71 chapters, 425 topics) syllabus by unit and chapter, with class, weightage and study hours. Tick topics, log revisions, start a chapter test, open a topic for its lecture, detailed notes and your own captured notes, practise it or explain it back. |
| 🎓 | **College (B.Tech), by semester** | Six branches (CSE, IT, ECE, EE, ME, Civil) on one library of 115 courses (631 chapters, 2,900+ topics). A student picks their college, semester and subjects: IIT Delhi, IIIT-Delhi, DTU and NSUT have their own semester plans where the scheme was checked, any other college gets a typical AICTE-style plan, and every list can be edited (drop a course, add any other one). Everything above then runs on that semester: the Prep Hub, a plan up to the mid-sem or end-sem exams with a grade goal, notes written at university level, subject and chapter tests (MCQs, no negative marking), weak spots and last-day revision for one subject's paper. |
| 🎯 | **GATE and Class 11-12** | GATE papers CS, DA, EC, EE, ME and CE are built from the same course library (so notes and questions are shared with B.Tech), with each subject weighted by the marks it usually carries, a plan up to the February exam, and a full paper: 65 questions, 100 marks, 3 hours, negative marking. Class 11 and 12 students pick their science subjects and get the NCERT chapters of their class, a plan up to their exams, and board-level chapter tests. |
| 💼 | **Placements** | The *Placements* target follows a syllabus of what campus drives for software roles test: two coding-pattern courses, Data Structures, Algorithms, aptitude, DBMS, OS, OOP, networks, system design basics and interview skills (resume, projects, HR). A plan to the date drives open, notes on every topic and subject tests. The weight of each subject is our estimate, not an official split. |
| 📸 | **Ask with a photo** | Photograph a question from a book, a paper or a screen: the idea behind it, every step and the answer, saved with your doubts. Or photograph an answer you wrote by hand: marks as an examiner would give them, where they were lost, and an answer worth full marks. Needs the AI that reads images. |
| 🏫 | **Campus** | For B.Tech, GATE and placement students: past papers and notes shared by students of the same courses, a shelf per college. Open a file, mark what helped, report what should not be there (two reports hide it). A paper's questions are read out of it once and each can be explained. Files are students' own uploads and are not checked by Focs. |
| 👩‍🏫 | **Classes and the parent link** | A teacher makes a class and gives out its code; students who join share their week with that teacher: study time day by day, syllabus done, last test, weak chapters, and the chapters most of the class is stuck on. A student can also make a private read-only link for a parent (`/p/…`), and turn it off at any time. Neither shows notes or doubts. |
| 📱 | **Android app** | `mobile\build_apk.bat` builds an APK ([mobile/README.md](mobile/README.md)). The app is a thin shell: it learns where your Focs server is, then shows that server's own pages, so it has the same account and data as the web and is never a version behind. `mobile\serve_for_phone.bat` starts Focs so a phone on the same Wi-Fi can reach it. |
| ✨ | **Midnight and Ivory** | A premium look with one futuristic thread. Midnight (dark, the first look) is deep navy-black under a soft aurora; Ivory (light) is warm porcelain. On both: glass cards with hairline edges and a lit rim, Geist set tight with one italic Instrument Serif word where a headline turns, a luminous gold for the next thing to do, and Focs's AI layer in electric periwinkle: focus brackets that lock onto whatever you point at, mono read-outs, formulas the OCR picks out in the margins, a lens that turns behind the headline, light running along the bridge between teacher and student. All of it stands still for anyone who asks their device for less motion. |
| 📖 | **Detailed notes library** | Every syllabus topic has a pre-made detailed note (core ideas, formulas, a worked example, common mistakes, how the exam asks it), given when the student asks. Written once, checked by a second model that re-does the worked example, then shared by everyone. Notes come with real past questions on the topic from the question bank (the newest one is solved as the note's worked example; the others can be tried, then opened), and open in a reader built for reading: one wide column, a bar to jump between sections, adjustable text size, print. Every board note keeps its short write-up and gains optional *Detailed notes* from the same library. |
| 🎙️ | **Speak or write** | Written answers can be typed, spoken or both (English, Hindi, Hinglish). *Explain it back*: say a topic in your own words and get it checked against what was taught; offered on every topic and as an alternative to the checkpoint question in a live lecture. |
| 🎥 | **Live lecture capture** | Shares a *browser tab* (never your tabs/URL bar), crop to the board, frames sampled every 3–8 s. An on-device change detector skips idle boards, so nothing is sent while the teacher talks. |
| 🔎 | **FocsOCR** | Our own line recogniser (CNN + BiLSTM + CTC) trained on synthetic chalkboards, whiteboards, pen-tablet and slide lectures, with Greek letters, sub/superscripts and math operators. Runs on CPU via ONNX Runtime. |
| 🤝 | **OCR ensemble** | PP-OCRv4's detector finds the lines; FocsOCR and PP-OCRv4 both read every line and the better reading wins (math-aware tie-breaking). |
| 📝 | **Notes that grow** | When the teacher keeps writing on the same board, the existing note is updated instead of duplicated. Markdown + LaTeX, rendered with KaTeX. |
| 🎯 | **Pop quizzes & checkpoints** | A quick MCQ every 5 or 10 minutes of lecture (or on demand), plus one whenever the topic shifts. Wrong answers go to the redo queue. |
| 🪟 | **Float over lecture** | A small always-on-top Focs window (Document Picture-in-Picture) shows live status and pops quizzes right over the video you're watching. |
| 💬 | **Doubt solver** | Context-aware tutor: *Explain*, *Step-by-step*, *Simple*, *Hint only* and *Hinglish*; ask about the whole lecture or one board. Wide tables slide sideways inside the answer, and any answer opens in a full view. |
| 📚 | **Revision sheet** | End a lecture → overview, key concepts, formula sheet, common mistakes, plus 6–10 flashcards. |
| 🧠 | **Flashcards (SM-2)** | Anki-style spaced repetition with interval previews; keyboard-first review. |
| ✍️ | **Practice** | Exam-pattern MCQ / true-false / written-or-spoken questions from any lecture, any syllabus topic or pasted material; AI grading of written and spoken answers. |
| ⏱️ | **Full JEE Main mocks** | 30+30+30 or the current 25+25+25 pattern, 3-hour server-side timer, NTA-style screen (palette, Save & Next, mark for review, "any 5 of 10"), autosave, +4/−1 grading, subject / chapter / time analysis, solutions, report-a-question. |
| 🧩 | **Chapter tests** | Pick chapters, 10–25 questions, same exam screen and analysis. |
| ✅ | **Verified question bank** | AI-written questions are kept only when a second model, solving independently, gets the same answer; reported questions retire themselves. |
| Σ | **Formula book** | Every formula from your notes, grouped by subject and topic, searchable and printable. |
| 📷 | **Board photos** | Offline classes: snap the board or a notebook page, get notes. |
| 👥 | **Study rooms** | YouTube lectures in sync (play, seek and speed), live MCQ battles, a doubt board (me-too votes, answers, accepted answers earn points), Ask AI for the room, shared live board notes, focus timer. |
| 🏆 | **Leaderboards** | Room points plus a weekly / all-time board from every answered question (opt-out in Settings). |
| ⚖️ | **Fair-use AI allowance** | Like Claude: units per 5-hour window plus a weekly cap; Pro gets 10×. Live lectures fall back to basic notes instead of stopping. |
| 📊 | **Admin dashboard** | Growth, active students, expected revenue vs the customer goal, and the real AI cost per feature, model and student. |
| 🔐 | **Your data** | Download everything as JSON or delete the account in one step (DPDP Act). |
| 📈 | **Dashboard** | Today's plan, streaks with weekly freezes, focus time, a year-long study heatmap, weekly minutes vs accuracy, weak topics. |
| 🔬 | **OCR Lab** | Drop any image, compare engines line by line, read the model card and benchmark. |

Every AI feature has a deterministic **offline fallback**, so the product never hard-fails when the
LLM is unreachable. The LLM layer speaks the OpenAI-compatible API: Groq (default), OpenAI,
Together or a local **Ollama** all work by changing `LLM_BASE_URL` / `LLM_MODEL`.

---

## Syllabus, lectures and notes (Prep Hub)

The syllabus lives in `backend/app/data/syllabus/jee.json` and `neet.json`: subjects → units → chapters → topics.
Each chapter has its class (11/12), weightage (approximate share of questions) and self-study hours (lectures plus
practice). NEET Physics and Chemistry reuse the JEE chapters (same NMC/NTA units) at NEET depth and weightage, and
JEE chapter names match the question bank, so "Chapter test" works from any chapter.

College is a second kind of syllabus, in `backend/app/data/syllabus/college/`. The course files (`common.json`,
`computing.json`, `electronics.json`, `electrical.json`, `mechanical.json`, `civil.json`) are the library: a course
is a subject and its units are the chapters. `branches.json` says which courses a branch studies in which semester:
a typical plan for every branch, and a college's own where its scheme was read (the `source` line of each plan says
from what; IIT Delhi's is its Courses of Study 2023-24, DTU's its published schemes, IIIT-Delhi's its programme
pages, and NSUT's CSE plan comes from a students' index, not an official document). To add a college or correct a
plan, edit `branches.json`; course names must be names from the library. A branch shares every course's notes and
questions with the other branches (they are stored once, under "college").

A topic can be a plain name or carry its lecture and notes, which then show on its page in the Prep Hub:

```json
{"name": "Projectile motion", "video": "https://www.youtube.com/watch?v=…", "notes": "## Projectile motion\n…markdown + LaTeX…"}
```

Progress is stored against topic IDs built from the names (`physics.kinematics.projectile-motion`), so renaming a
topic starts its progress afresh. The mentor plan (`services/planner.py`) reads the same file.

### The notes library

Topics without hand-written `notes` get theirs from the notes library (`services/topic_notes.py`, table
`topic_notes`): one detailed note per topic and one last-day capsule per chapter, per exam. A note is written by
the AI the first time any student asks for it, checked by a second model (formulas, and the worked example solved
again from its data), corrected if needed, and then served to everyone from the database. Opening a note that is
already in the library is free; the student who triggers the writing pays 2 units of allowance. Three different
students reporting a mistake retires a note, and it is written again on the next request.

To pre-make the library instead of letting it fill itself:

```
build_notes.bat --exam jee                      every JEE topic (safe to stop and resume)
build_notes.bat --exam neet --subject Biology   one subject
build_notes.bat --exam jee --capsules           the chapters' last-day capsules
```

It writes into the database Focs runs on and exports `backend/app/assets/notes/<exam>.json`, which is loaded at
start-up: commit that file and every install (and the cloud database) starts with the notes already made.

Board notes link into the same library: a board whose title matches a syllabus topic opens that topic's note under
*Detailed notes*; any other board gets a detailed write-up of its own, stored with the board.

## Question bank (mock tests and chapter tests)

Mock tests are assembled from a shared bank of JEE Main questions. The bank ships with Focs
(`backend/app/assets/bank/jee_main.json`, loaded into the database on start) and grows automatically
whenever a paper needs questions it doesn't have yet.

**What's in the shipped bank today — 153 questions**

| Subject | MCQ (single correct) | Numerical (integer answer) | Total | Chapters covered | Easy / medium / hard |
| --- | ---: | ---: | ---: | ---: | --- |
| Physics | 47 | 28 | **75** | 19 / 19 | 31 / 31 / 13 |
| Mathematics | 45 | 5 | **50** | 18 / 19 | 25 / 20 / 5 |
| Chemistry | 15 | 13 | **28** | 14 / 20 | 13 / 10 / 5 |
| **All** | **107** | **46** | **153** | 51 / 58 | 69 / 61 / 23 |

**How many questions a paper takes**

| Paper | Per subject | Whole paper | Time | Marks |
| --- | --- | --- | --- | --- |
| JEE Main 30 + 30 + 30 | 20 MCQ + 10 numerical (answer any 5) | 90 questions | 3 h | 300 |
| JEE Main 25 + 25 + 25 (current NTA) | 20 MCQ + 5 numerical | 75 questions | 3 h | 300 |
| Chapter test | ~70 % MCQ, rest numerical, chosen chapters only | 10 / 15 / 20 / 25 | 2 min per question | 4 per question |

What that means right now: Physics alone could fill two full papers; Chemistry MCQs (15 of 20) and
Mathematics numericals (5 of 10) are short of one paper. So every full mock currently writes the missing
questions first — the student sees "Preparing your paper…" for a few minutes — and those questions stay in
the bank for everyone after them. Chapter tests on well-stocked chapters (marked ⚡ in the app) start instantly.
A student never gets the same question twice while unseen ones remain.

**How a question gets in, and out**

1. The large model writes a batch for specific chapters, solving each one before fixing its answer.
2. A *different* model solves every question from scratch; only questions where both answers agree are kept
   ("verified"). Solutions that "think aloud" ("wait…", "let's verify…") are rejected.
3. Students can report a question from the review screen; two reports retire it from new papers.

Grow the bank before launch (a paid AI tier makes this fast; free tiers hit rate limits):

```bat
cd backend
.venv\Scripts\python scripts\build_question_bank.py --papers 3 --subject Chemistry --subject Mathematics
```

The script only adds what's missing, saves after every batch, and waits out rate limits.
Two AIs agreeing is a strong filter, not a guarantee — have a JEE teacher spot-check a sample before launch.

## AI cost — and should we train our own model?

**Where the money goes.** Only the AI text model costs money per use. Board reading (FocsOCR), flashcard
scheduling, the formula book, leaderboards, rooms and grading of mock tests run on our own server at no
per-use cost. The AI is called for: notes for each *new* board (unchanged boards are skipped on the device),
pop quizzes, doubts, practice sets, revision sheets, flashcard sets, answer grading, and writing new bank
questions. The AI allowance (`USAGE_*`, about 60 units per 5 hours on the free plan) caps what one student
can spend.

**Already in place to keep costs low**
- Questions are written once and reused by every student (the bank), instead of per test.
- Idle boards cost nothing: the device only sends a frame when the writing changes.
- Every AI feature has an offline fallback, so running out never breaks the app.
- Free-tier models are tried first (Groq → Gemini), and each student's usage is capped.
- Board notes always use the cheap model (`LLM_LIGHT_MODEL`). If it is briefly rate-limited, a background
  write-up waits up to 25 s for it instead of paying for a bigger model; a student pressing a button never waits.
- A board the teacher is still writing on is written up once it settles (`BOARD_SETTLE_S`, 20 s still), or at
  most every `BOARD_REFRESH_S` (45 s), instead of after every new line. A heading alone waits for the first lines.
- Notes are shared between students: the same board of a popular lecture is written up by the AI once
  (`shared_notes`: exact match, or near match for longer boards read with OCR noise). Later captures are free
  and use no allowance.
- Measured on a simulated 4-board lecture written line by line: 23 AI calls before, 8 now, and 0 for the
  next student watching the same lecture.

**Training our own model — honest answer**

| Option | Cost | Verdict |
| --- | --- | --- |
| Train an LLM from scratch | crores of rupees of GPU time | Not realistic for a startup |
| Fine-tune a small open model (1.5–4 B parameters) for our most frequent job — turning board text into notes — using notes the big model already wrote as training data | a few days of work; trains on the RTX 4050 with 4-bit LoRA | **Worth it later** |
| Serve that model ourselves | a GPU server, roughly ₹15,000–40,000 a month, whether students use it or not | Cheaper than the API only at high, steady usage |

Today, with few students, paying per call on Groq/Gemini is cheaper than renting a GPU that sits idle.
The sensible path: keep collecting (board text → notes) pairs as students use Focs, then distil them into a
small notes model once board-notes volume is high. It can run on a modest GPU and take over the
highest-volume call. Doubts, quizzes and question writing stay on the big models, where quality matters
most. We already did the same for board reading: FocsOCR is our own 3.1 M-parameter model, trained on the
RTX 4050, that runs on the server's CPU with no per-use cost.

## Architecture

```
 Browser (React 19 + Vite + Tailwind 4)                    FastAPI (Python 3.12)
 ┌──────────────────────────────────────┐   JPEG frame   ┌───────────────────────────────────────────┐
 │ getDisplayMedia(tab) → crop → 48×27  │ ─────────────▶ │ /api/capture/{id}/frame                   │
 │ luminance signature (skip idle)      │                │  ├ pHash dedupe                           │
 │                                      │ ◀───────────── │  ├ OCR: DBNet det → FocsOCR ⨉ PP-OCRv4    │
 │ Notes · Ask · Checkpoint · Summary   │  note + OCR +  │  ├ growing-board merge / duplicate skip   │
 │ Practice · Flashcards · Rooms (WS)   │  checkpoint    │  ├ LLM notes (JSON mode) | offline notes  │
 └──────────────────────────────────────┘                │  └ topic shift → checkpoint MCQ           │
                                                         │ SQLite (WAL) · local snapshot storage     │
                                                         └───────────────────────────────────────────┘
```

---

## FocsOCR — the model

| | |
| --- | --- |
| Architecture | Residual CNN (4 stages) → 2-layer BiLSTM (192) → CTC, 3.1 M parameters |
| Input | 48 px high grayscale line, polarity-normalised (chalk and ink look the same to the model) |
| Charset | 191 symbols: ASCII + Greek + `∫ ∑ √ ≤ ≥ ≠ ≈ ± × ÷ → ⇒ ∂ ∇ ∝ ∞ ∪ ∩` + super/subscripts + ½ ¼ ¾ |
| Training data | 1.76 M synthetic lines rendered on the fly: 6 board styles, 61 fonts (22 handwriting fonts, e.g. Kalam by the Indian Type Foundry), formulas, chemistry, exam phrasing, Hinglish |
| Degradations | capture down-scaling, JPEG/video compression, blur, noise, rotation/shear, lighting, imperfect detector crops |
| Hardware | ~1 h on an RTX 4050 laptop GPU (fp16, width-bucketed batches) |
| Runtime | ONNX Runtime on CPU — no PyTorch needed to serve |

| Result | FocsOCR | PP-OCRv4 |
| --- | --- | --- |
| Validation lines (2,000) — CER / exact lines | **1.43 % / 91.2 %** | – |
| 240 held-out lecture frames, end-to-end — CER | **0.48 %** | 7.27 % |
| … exact lines | **96.9 %** | 63.3 % |

Both test sets are synthetic (held-out seeds); real handwriting is harder. Details, per-style numbers
and caveats: [`ml/README.md`](ml/README.md). Everything is also visible live in the app's **OCR Lab**.

---

## Project layout

```
focs/
├─ run.bat · dev.bat · train_ocr.bat       one-click launch / dev / training
├─ backend/
│  ├─ main.py                               entry (uvicorn main:app)
│  ├─ app/
│  │  ├─ api/          auth, sessions, capture, notes, companion, quiz, flashcards, mock,
│  │  │                analytics, rooms (WebSocket), leaderboard, usage, ocr, billing, courses
│  │  ├─ core/         settings, database (+ additive auto-migrations), security, rate limits
│  │  ├─ models/       SQLAlchemy 2 models      schemas/  Pydantic API contracts
│  │  ├─ services/     live pipeline, ai (+ offline fallbacks), llm client, srs (SM-2), usage,
│  │  │                mock (+ patterns, question_bank), formulas, account,
│  │  │                ocr/ (detector, FocsOCR recogniser, ensemble engine), storage
│  │  └─ assets/       ocr/ (focsocr.onnx, charset, model card, benchmark) · bank/jee_main.json (seed questions)
│  ├─ scripts/         launch.py, benchmark_ocr.py, build_question_bank.py
│  └─ tests/           end-to-end API tests (offline mode) + unit tests
├─ frontend/           React 19 · TypeScript · Tailwind 4 · TanStack Query · Motion · Recharts · KaTeX
│  └─ src/pages/       Landing, Auth, Dashboard, Studio (live), Library, SessionView, FormulaBook, Practice,
│                      MockTests, MockView, MockExam, Flashcards, Rooms, RoomView, Leaderboard, OcrLab,
│                      Settings, Privacy, Terms
└─ ml/                 FocsOCR training: charset, corpus, synthetic renderer, model, train, export, scenes
```

---

## Configuration (`backend/.env`)

Just paste keys after the `=` and restart `run.bat`:

| Key | What it switches on |
| --- | --- |
| `GROQ_API_KEY` | AI notes, tutor, quizzes, summaries. Cheapest first: `gpt-oss-20b`, then `gpt-oss-120b` when 20b is busy, then Gemini `flash-lite` (with `GEMINI_API_KEY`) only if Groq is down. The PYQ importer reads pages with `flash-lite` and solves with the gpt-oss models only |
| `GEMINI_API_KEY` | Automatic backup AI when Groq's free limits are used up. Also the model that sees images (`VISION_MODEL`, Gemini `flash-lite`, the cheapest one): it reads an uploaded test result, and each new lecture board before its notes are written, because line-by-line OCR splits a fraction over two lines and drops the sign between two fractions. Without it both are read from local OCR text instead |
| `SUPABASE_URL`, `SUPABASE_SECRET_KEY` | Board snapshots in a private Supabase Storage bucket |
| `SUPABASE_DB_URL` | Cloud Postgres database. On first start your local `focs.db` is copied over automatically (once, all-or-nothing); the local file is kept as a backup |
| `SECRET_KEY` | Signs login tokens — generated by `run.bat`, never share or reuse it |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `APP_URL` | Password-reset emails through any SMTP provider; the "Forgot password?" link appears once these are set |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH` | The admin panel's own sign-in at `/admin`, separate from student accounts: sign-ups, active students, expected revenue, the 200-customer goal, AI cost by feature/model/student. Set them by double-clicking `set_admin.bat` (stores only a bcrypt hash; a new password signs every admin session out). On a host, run `set_admin.bat --print-hash` and paste both values into its environment settings. `GOAL_CUSTOMERS` tunes the dashboard |
| `LLM_LIGHT_MODEL`, `MODEL_PRICES_USD`, `USD_INR` | Board notes, pop quizzes, checkpoints and flashcards try the cheaper model first; every AI call is recorded with its tokens and list-price cost |
| `STT_MODEL` | Speech to text for spoken answers in browsers that can't dictate themselves (Firefox, Brave). Uses the Groq key above with `whisper-large-v3-turbo`; set it empty to switch the fallback off. Chrome, Edge and Safari dictate on their own, for free |
| `USAGE_*`, `MOCKS_*` | AI allowance per plan (`USAGE_FREE_WINDOW=60`, `USAGE_PRO_WINDOW=600`, weekly caps, `USAGE_WINDOW_HOURS=5`) and full mocks per week; 0 = unlimited |

Frontend (`frontend/.env`): `VITE_LEGAL_NAME`, `VITE_SUPPORT_EMAIL`, `VITE_GRIEVANCE_OFFICER` fill in the Privacy Policy and Terms.

Without any keys Focs runs fully offline (local SQLite, local snapshots, offline AI fallbacks).
Advanced overrides (model lists, `HOST`, `PORT`, `OCR_ENGINE`, `DATABASE_URL`) are documented in
`backend/app/core/config.py`.

## Development

```bat
dev.bat                                      :: hot reload for API and web
backend\.venv\Scripts\python -m pytest -q    :: backend tests (run from backend\)
cd frontend && npm run typecheck             :: TypeScript
cd frontend && npm run test:math             :: LaTeX repair tests (renderer)
backend\.venv\Scripts\python scripts\build_question_bank.py --papers 2   :: grow the verified seed bank (run from backend\)
```

API docs: <http://localhost:8000/api/docs>

## Deploy

```bash
docker compose up --build        # one container: API + web app on :8000, data in a volume
```

For production set `ENV=production`, a strong `SECRET_KEY`, and preferably a PostgreSQL
`DATABASE_URL`. Room state and rate limits are in-process; move them to Redis before running
multiple workers.

## Roadmap

Live Razorpay keys and automatic mentor payouts · teacher dashboards for institutes · Devanagari (Hindi) OCR ·
detector fine-tuning on real board frames · diagram capture · mobile app. See [docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md).
