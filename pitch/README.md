# The pitch: deck and demo film

Shark Tank order: the deck's opening (slides 1–5), the film (slide 6, silent, about 3:48: talk over it), then the close
(slides 7–12). Speaker notes on every slide carry the script.

| File | What it is |
| --- | --- |
| `out/Focs-Pitch.pptx` | The deck, with the film embedded on slide 6 (click it to play) |
| `out/Focs-Demo.mp4` | The film on its own (1920×1080, 30 fps, no sound) |

Both are built, not stored in git. Before the pitch, fill in the ask on slide 11 (`₹ [amount]` for `[x]%`) and say your
names on slide 1.

## Rebuild

From `pitch/` (Node 20+; `npm install` once):

1. **Filming server** on port 8017 with its own SQLite file (never your real database), then the demo data:
   `backend/scripts/seed_demo.py`, `shoot/tidy_db.py <db>` and `node shoot/seed.mjs` (sample students, three approved
   mentors, a waiting application, master sessions, a mentorship with a check-in). Set `VISION_MODEL=` on that server so
   boards are read by FocsOCR (Gemini's vision model was overloaded on 18 Oct).
2. **Film**: `node shoot/film.mjs [scene ...]` drives the real app in Chrome and records each scene into
   `public/clips/<scene>.mp4` with timing marks in `.json`. Needs `FOCS_DB` (the filming .db) and `FOCS_PY` (a Python)
   for the test scene. The live-lecture scene shares a fake lecture tab (`shoot/lecture-stream.js`: a chalkboard drawn on
   a canvas plus the teacher's voice from `shoot/make_voice.py`); everything Focs does with it is the real server.
3. **Edit**: the cut is data in `video/shots.json` (clips, speeds, callouts, zooms); `npm run studio` previews it.
   `npx remotion render video/index.ts FocsDemo out/Focs-Demo.mp4 --codec=h264 --crf=18 --muted`.
4. **Deck**: `node deck/build.cjs` (embeds the film if `out/Focs-Demo.mp4` exists).

Everyone on screen is a sample account (the film says so in its corner): Riya, Aman, Kabir, Neha, Arjun, and the
mentors Aditya, Sneha, Ananya, Meera and Rohan. Their proof images are marked "sample".

Remotion is free for individuals and companies of up to three people; a bigger team needs a Remotion company licence.
