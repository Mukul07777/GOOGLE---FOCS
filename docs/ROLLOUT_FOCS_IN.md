# Putting root cause, the Gap Genome and Check my working on focs.in

focs.in's real students are the evidence: once the new code runs there, their traces, fixes and checked working fill
**Admin → Root-cause tracing, measured** and `scripts/evidence.py`. This is the safe way to do it. About 30 minutes,
done by whoever holds the server key (`keys/focs-key.pem`).

## What changes for students, and what doesn't

- **Additive only.** Three new tables (`prereq_maps`, `gap_traces`, `working_checks`) are created on start-up. No
  existing table or column changes, so the old code still runs on the same database if you roll back.
- New in the menu: Root cause, Gap Genome. New under questions: Check my working (after answering). Everything else is
  unchanged.
- **Build the full app, not the hackathon build.** Real students need every screen: leave `VITE_EDITION` empty here.
  The `roots` build is only for the Cloud Run demo.

## Decide first: which AI answers

The new code tries **Gemini first** whenever `GEMINI_API_KEY` is set (`GEMINI_FIRST=true` by default). On focs.in that
changes the provider and the cost of every AI call. Pick one and put it in `/etc/focs.env`:

| Setting | What happens | Cost |
|---|---|---|
| `GEMINI_FIRST=false` | Exactly as today (Groq first, Gemini as backup). Handwriting and boards were already Gemini. | Same as today |
| `GEMINI_FIRST=true` | Gemini answers first, Groq steps in when it's busy. "Runs on Gemini" is true for the pitch. | Gemini flash-lite is a little dearer per token than gpt-oss-20b; each student's AI cap still applies |
| `GOOGLE_ONLY=true` | Only Gemini, ever. | As above, and no fallback when Gemini is busy |

## Steps

1. **Back up the database first.** Supabase → Database → Backups → make sure today's exists (or `pg_dump` it).
2. **Give the server read access to the new repo.** The server pulls from Study_Platform today. In GitHub,
   GOOGLE---FOCS → Settings → Deploy keys → Add: paste the server's `~/.ssh/focs_deploy.pub`, read-only. Then on the
   server:
   ```bash
   cd ~/focs
   git remote add google git@github.com:Mukul07777/GOOGLE---FOCS.git
   git fetch google
   git rev-parse HEAD > ~/focs-before-roots.txt     # where to come back to
   git checkout -B live google/main                 # the histories are unrelated; checkout, not pull
   ```
3. **Settings:** add your choice from the table above to `/etc/focs.env` (no quotes).
4. **Build and swap** (the usual 7h steps; the old container serves while it builds):
   ```bash
   sudo docker build --build-arg VITE_SENTRY_DSN='<as before>' -t focs .
   sudo docker rm -f focs
   sudo docker run -d --name focs --restart unless-stopped --env-file /etc/focs.env -p 127.0.0.1:8000:8000 \
     --log-opt max-size=20m --log-opt max-file=3 focs
   curl -s https://focs.in/api/health
   ```
5. **Build the shared chains** for the top JEE and NEET chapters, so real students' first traces are instant and
   "Focs noticed" can work from their past mock tests straight away (costs a few rupees of AI, once):
   ```bash
   sudo docker exec focs python scripts/warm_chains.py --top 25
   ```
6. **Check, as a test student:** Root cause opens; a trace finds a root; Practice → answer → Rough → write →
   Check my working reads it on a phone and on a tablet. Admin shows "Root-cause tracing, measured".
7. **Evidence for the pitch,** any time after (read-only, aggregates only, groups under 5 hidden):
   ```bash
   sudo docker exec focs python scripts/evidence.py --out /tmp/evidence.md && sudo docker exec focs cat /tmp/evidence.md
   ```

## Get the numbers (pitch evidence)

Run these in order on the server. All are safe on production: the first and third never write, the second only adds
shared chains (no student data in them).

```bash
# 1. See which chapters real students actually attempt, and what they cover. No AI, no cost.
sudo docker exec focs python scripts/warm_chains.py --dry-run --top 25

# 2. Load the 22 chains already built with Gemini for the top 15 JEE and NEET chapters (in the image; no AI)...
sudo docker exec focs python scripts/warm_chains.py --import scripts/chains.json    # --overwrite replaces existing ones
#    ...then build the rest of what step 1 listed (only missing ones; a few rupees of AI, once)
sudo docker exec focs python scripts/warm_chains.py --top 25
#    (no AI on the server? build them elsewhere with "--top 25 --export chains.json", then
#     sudo docker cp chains.json focs:/tmp/chains.json and --import /tmp/chains.json)

# 3. The evidence report (read-only, aggregates only, groups under 5 students hidden)
sudo docker exec focs python scripts/evidence.py --out /tmp/evidence.md

# 4. Copy it off the server (run this on your own computer)
scp <user>@<server>:/tmp/evidence.md . 
```
If `evidence.md` is in the container rather than on the host, first run
`sudo docker cp focs:/tmp/evidence.md /tmp/evidence.md` on the server, then `scp` it. `evidence.json` sits next to it.
The report says how much of real students' chapter-tagged attempts (last 60 days) have a chain; run step 2 again with
a larger `--top` if that share is low. For the handwriting accuracy number, see BENCHMARK.md.

## Roll back (2 minutes)

```bash
cd ~/focs && git checkout "$(cat ~/focs-before-roots.txt)"
sudo docker build --build-arg VITE_SENTRY_DSN='<as before>' -t focs . && sudo docker rm -f focs && sudo docker run ...  # as in step 4
```
The new tables stay in the database, unused, and do no harm.

## Tell students (this is what fills the numbers)

The dashboard's "Your real gap" card and the mock result page point students at the loop. A short message helps too
(WhatsApp or the in-app bell): *"New on Focs: write your working on the rough pad and Focs finds the exact step that
went wrong, then the Class 9-10 idea behind it. Fix it in 5 minutes."*

## Privacy

Check my working sends the rough-pad page to Google's Gemini to be read, the same way Snap already sends photos. Only
what was read is kept, never the drawing. Make sure the privacy page's AI section still matches (it names the AI
providers used).
