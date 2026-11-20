# Demo day

A 5-minute demo that can't be stalled by a slow AI, a rate limit or the venue Wi-Fi. Each step says who does it;
**(you)** marks the steps that need an account, a key or a card.

## A week before

### 1. AI (you)
- Get a paid Groq key (`GROQ_API_KEY`) and a Gemini key (`GEMINI_API_KEY`) as the fallback. Free tiers hit their limits with a room of judges.
- Put both on the host (step 2) and in `backend/.env` for the seed (step 3).

### 2. HTTPS hosting (you)
Screen capture, the camera and the microphone only work on `https://` (or on `localhost`), so a phone or a judge's laptop needs a real host.
The image is ready: build it as the event edition, push it, and run it on Cloud Run.

```
docker build --build-arg VITE_EDITION=bridge -t REGION-docker.pkg.dev/PROJECT/focs/focs:demo .
docker push REGION-docker.pkg.dev/PROJECT/focs/focs:demo
gcloud run deploy focs --image REGION-docker.pkg.dev/PROJECT/focs/focs:demo --port 8000 \
  --max-instances 1 --timeout 3600 --memory 2Gi --cpu 2 --no-cpu-throttling --allow-unauthenticated \
  --set-env-vars ENV=production,ALLOW_DEV_UPGRADE=false,TRUSTED_PROXY_HOPS=1,CORS_ORIGINS='["https://YOUR-URL"]' \
  --set-secrets SECRET_KEY=focs-secret:latest,GROQ_API_KEY=groq:latest,GEMINI_API_KEY=gemini:latest,SUPABASE_DB_URL=supabase-db:latest
```

Why each setting:

| Setting | Why |
|---|---|
| `--max-instances 1` | Live classes and rate limits live in one server's memory. A second instance would split a class in two. |
| `--timeout 3600` | A live class is one long websocket. The default 5 minutes would drop everyone mid-lecture. |
| `--no-cpu-throttling`, 2 CPUs, 2 GiB | OCR runs on the server. Throttled CPU between requests makes every board slow. |
| `SUPABASE_DB_URL` (Postgres) | Cloud Run's disk is wiped on every restart, so SQLite would lose the demo. |
| `TRUSTED_PROXY_HOPS=1` | Behind Cloud Run every visitor arrives from Google's proxy. Without this, all judges share one rate limit. |
| `ENV=production`, `SECRET_KEY` (32+ characters), `ALLOW_DEV_UPGRADE=false` | The server refuses to start in production with the default key. The dev "upgrade" button must be off. |

- Uploaded board photos go to Supabase Storage when `SUPABASE_URL` and `SUPABASE_SECRET_KEY` are set. Otherwise they are lost on a restart, though the notes stay.
- Open `https://YOUR-URL/api/health` to check. It should show `"database": "supabase"`, the AI model and the OCR engines.

### 3. Seed the demo (you run it; it takes a few minutes)

Run this with the demo's AI key and database in `backend/.env`:

```
cd backend
.venv\Scripts\python scripts\seed_demo.py --password <a password for the demo accounts>
```

The seed writes everything the demo opens, with the AI, now, and keeps it:

- **Two students, each with a finished lecture.** One reads in Hinglish, the other in Hindi. Each lecture has its boards, notes in that student's language, a revision sheet and flashcards.
- **A teacher's live class with a confusion map.** It records "I'm lost" taps, a quiz, wrong answers marked as sure, and doubts. The second board is the one that lost the room.
- **A verified B.Tech senior.** A student's question carries Focs's AI draft, checked by the senior, plus the senior's own answer, accepted by the student.

Every account is named "Demo …" and every post starts with "[Demo]". Run the seed again with `--reset` to start clean.

### 4. Measure (see [evidence](evidence/README.md))
```
.venv\Scripts\python scripts\demo_metrics.py drive --url https://YOUR-URL --boards 6
```
Only put numbers in the slides that this printed on the real host.

## The day before

- **Rehearse once with the AI switched off.** Remove the two keys on the host, or run locally without them, and run the whole script.
  - Notes fall back to offline mode, the waits show their study tasks, and everything seeded is still there.
  - If the venue's internet fails, this is the demo you'll give.
- Sign in to every demo account on the demo laptop and phone, so nobody types passwords on stage.
- Charge the phone. Bring a stand for classroom mode, and a printed board or a whiteboard marker.

## At the venue

- **Wi-Fi:** everyone at the event shares one public address.
  - Signed-in requests are rate-limited per account, not per address, so judges using the demo accounts don't block each other.
  - Sign-ups are limited per address. Hand out the demo accounts instead of asking judges to sign up.
- **A phone hotspot as backup.** Test it before your slot.
- **Open in tabs before you start:** the student's lecture, the teacher's confusion map, and Ask a senior.

## The 5 minutes

1. **The gap (20 s).** The teacher moves at the speed of the board. Students need their own pace and language. And the teacher can't see who is lost.
2. **Teacher → student (90 s).**
   - Share a lecture tab in Live lecture. A board appears and its notes follow within seconds; the captions follow the teacher.
   - Switch the student to Hindi: the notes, the menu and the buttons change language, and the formulas stay exact.
   - Press *Read aloud*.
3. **Understanding (40 s).**
   - A pop quiz: pick an answer and lock it in as *Sure* or *Guessing*.
   - Being sure and wrong is a blind spot, and blind spots lead the summary.
4. **Student → teacher (60 s).**
   - In the live class, a student taps *I'm lost*, and the teacher's meter moves.
   - Open the confusion map: the second board lost the room.
   - Press *Recap* on it, and the explanation goes back to the class.
5. **In a real classroom (30 s).** Put the phone on the desk and mark the board's four corners. The board is straightened and read.
6. **After class (30 s).** In Ask a senior, Focs drafts an answer at once, and a verified senior checks it.
7. **Evidence (30 s).** Show the measured numbers: OCR on real boards, delay and cost per hour, and the learning study with its interval.

If something breaks on stage, go to the seeded version of the same screen. It's all there already.
