# Startup Buildathon 2026: the submission deck and demo video

| Output | What it is |
| --- | --- |
| `out/Focs-Buildathon-Demo.mp4` | The demo video: 2:44, 1920×1080, Hinglish voiceover (Gemini TTS), subtitles, music |
| `out/Focs-Buildathon-Deck.pdf` | The 14-slide submission deck on the organisers' template sections and branding |

Both are built, not stored in git. Everything below runs from `pitch/` (`npm install` once).

## The story

The root-cause loop of the hackathon edition (`VITE_EDITION=roots`):
1. A torque MCQ is answered *Sure* and wrong.
2. A photo of the paper working is checked by Gemini: step 1, cos θ for sin θ, a gap.
3. The root behind it is traced class by class to Class 11 trigonometry.
4. A five-minute fix in Hinglish follows, then the retest: 1/3 → 3/3.
5. The teacher's root-gap map and the Gap Genome come next, then a tour of the rest of Focs.

## Rebuild

1. **Filming server** (never the live database). Build the roots edition with `VITE_EDITION=roots npx vite build --outDir <scratch>/dist-roots`.
   Then from `backend/`, with `DATABASE_URL=sqlite:///<scratch>/film.db`, `FRONTEND_DIST=<scratch>/dist-roots`, `GOOGLE_ONLY=true`
   and every `SUPABASE_*` variable blank:
   - Import the chains: `scripts/warm_chains.py --import scripts/chains.json --overwrite`.
   - Add three more Rotational Motion MCQs to that database. The retest needs six, and the shipped seed bank has five.
   - Run `scripts/seed_demo.py --reset`.
   - Run `uvicorn app.main:app --port 8017`.
2. **Film**: `node buildathon/film_roots.mjs` → `public/clips/r-*.mp4`. Only the practice question is staged: a fixed torque
   MCQ, so the photographed working (`buildathon/make_paper.py`) matches it. The working check, the trace, the lesson and the
   maps are the real server and real Gemini calls. The tour reuses the earlier clips in `public/clips/`.
3. **Voice**: `python buildathon/make_vo.py [id ...]` reads `buildathon/vo.json` and writes `public/bt/vo/`.
   - Every take is transcribed back by Gemini (`check_vo.py`) and redone if it reads instructions aloud or is slow.
   - The TTS preview models have small daily quotas: `TTS_MODEL=gemini-2.5-flash-preview-tts` switches the model.
4. **Sound**:
   - `python buildathon/make_sfx.py`.
   - `python buildathon/make_music.py <seconds> <drop> <calm>`: the drop lands on "Meet Focs". Use the length that
     `npx remotion compositions buildathon/video/index.ts` prints.
5. **Render**: `npx remotion render buildathon/video/index.ts FocsBuildathon out/Focs-Buildathon-Demo.mp4 --codec=h264 --crf=20`.
   Scene lengths follow the voice lines (`buildathon/video/timeline.ts`).
6. **Deck**: `node buildathon/deck/print.mjs --png` → `out/Focs-Buildathon-Deck.pdf` (and a PNG per slide).

Everyone on screen is a sample account. The music and sound effects are synthesised by the scripts here; nothing is licensed.
