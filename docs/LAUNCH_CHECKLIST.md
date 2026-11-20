# Launch checklist

What's ready, and what still has to happen before Focs goes public. Items marked **(you)** need an account,
a payment, a key or a decision that only the founder can make.

## Ready in the product

- [x] Live lecture capture, FocsOCR, AI notes, pop quizzes, floating window, doubts (5 modes), revision sheets
- [x] Practice sets, flashcards (SM-2), board photos, formula book
- [x] Full JEE Main mocks (30+30+30 and 25+25+25), chapter tests, verified question bank, report-a-question
- [x] Study rooms: synced YouTube (play, seek, speed), live quizzes, doubt board, Ask AI, shared live notes, focus timer
- [x] Leaderboards (room + weekly/all-time) with opt-out
- [x] AI allowance per 5-hour window + weekly cap, Pro 10×, graceful fallback in live lectures
- [x] Account data export and deletion; consent at sign-up (including parent/guardian for under-18s)
- [x] Password reset by email (needs SMTP settings, see 4)
- [x] Privacy Policy and Terms pages (drafts, see Legal below)
- [x] Installable web app (manifest, icons), share image, robots.txt, long-lived caching of built assets
- [x] Error boundary with recovery screen; auto-reload after a new deploy
- [x] Backend tests (`pytest`), LaTeX renderer tests (`npm run test:math`), browser QA of every flow

## Must do before launch

### 0. Security settings for the live server (check each one)
| Setting | Value | If it's wrong |
|---|---|---|
| `ENV` | `production` (the Docker image's default) | Dev shortcuts switch on: test payments, college-email codes shown on screen, the API map at `/api/docs` |
| `SECRET_KEY` | 32+ random characters, new for the live server (`python -c "import secrets; print(secrets.token_urlsafe(48))"`) | Focs refuses to start. A leaked or reused key lets anyone sign in as anyone |
| `TRUSTED_PROXY_HOPS` | `1` behind Caddy, nginx, Cloud Run, Render or Railway; `2` behind a Google load balancer | `0` behind a proxy: every visitor shares one rate limit, so at launch sign-ups and logins start failing with "Too many requests" |
| App port | Reachable only through the HTTPS proxy (`docker-compose.yml` publishes it on 127.0.0.1) | With the port open, people skip HTTPS and can fake their address to dodge rate limits |
| `FREE_AI_DAY_FLOOR_INR`, `FREE_AI_REVENUE_SHARE` | `50` and `0.2` (defaults): free accounts together may spend Rs 50 a day plus 20% of the last 30 days' Pro income | Free accounts cost nothing to make: without a budget a script could spend without end. Past it, free accounts get offline answers until 05:30 IST; Pro carries on. The admin dashboard shows today's spend against it |
| `AI_CEILING_FREE_INR`, `AI_CEILING_PRO_INR` | `40` and `300`: what one student's AI may cost in any 30 days. A Pro student's is what the pass they are on brings in over 30 days, up to `300` (about 120 lecture hours) | This is what makes every pass pay for itself, whatever its price: `tests/test_pricing.py` checks every pass |
| `PRO_PRICES_INR`, `PRO_OFFER_PRICES_INR`, `PRO_OFFER_PLACES` | The defaults: regular and launch-offer prices for JEE / NEET, College and School; the offer runs for the first `200` students who pay | The offer ends by itself when its places are taken (the admin dashboard shows how many are left); `PRO_OFFER_PLACES=0` ends it at once |
| `VISION_MODEL` | Leave the default (`gemini-3.1-flash-lite,gemini-3.5-flash-lite,groq:qwen/qwen3.8-27b`: cheapest first). Turn on billing for the Gemini key: the free tier is the first to get "overloaded" answers | Boards go to Qwen, which costs about twice as much a board: on 20 October it read most of them while the Geminis were overloaded |
| `LIVE_WRITE_BEHIND` | `true` (default): a board's notes are written in the background while the lecture goes on | Off, every board's write-up holds up the student's next frame, and the board read can wait only 8 s per model, so more boards go to the dear model |
| `LECTURE_HOURS_PRO`, `LECTURE_HOURS_FREE` | `7` and `0.5` (defaults): hours of live lecture a study day that get AI notes | These are the plans' promise; the prices are worked out from them (`tests/test_pricing.py`) |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH` | A long admin password (`set_admin.bat --print-hash`) | The admin panel stays closed (safe) |
| `RAZORPAY_WEBHOOK_SECRET` | From the Razorpay webhook page | Payments still work from the browser; a student who closes the tab before returning isn't credited automatically |
| `APP_URL` | `https://your-domain` | Password-reset emails link to localhost |
| Proxy upload size | nginx: `client_max_body_size 64m;` (Caddy has no limit) | nginx's default 1 MB blocks lecture frames, photos and PDFs with "413" |
| Websockets | nginx: `proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; proxy_read_timeout 3600s;` | Study rooms don't connect, or drop every minute |

A minimal Caddy setup (HTTPS certificates are automatic): `your-domain { reverse_proxy 127.0.0.1:8000 }`.

Never commit `backend/.env` (it is git-ignored) or paste keys into chats and screenshots; rotate any key that was.

### 1. Hosting, domain, HTTPS (you)
- Buy a domain and deploy the Docker image (`docker compose up --build`) on a VPS or a container host.
- **HTTPS is required**: browsers only allow screen capture, the floating window and notifications on secure sites.
- In `backend/.env`: `ENV=production`, a fresh `SECRET_KEY`, `CORS_ORIGINS=["https://your-domain"]`.
- Run **one** worker (`uvicorn --workers 1`): study rooms and rate limits live in memory until Redis is added.
- Admin panel sign-in: run `set_admin.bat --print-hash` and set `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` on the
  host. The panel is at `https://your-domain/admin` and stays closed until both are set.

### 2. Payments (you, then code)
- Razorpay account (business KYC, PAN, bank account). Razorpay checks that Terms, Privacy, refund and contact
  details are visible on the site — they are once the legal settings below are filled.
- Code still to write: Razorpay checkout + webhook that sets `user.plan`. Today plans switch only in dev mode
  (automatically disabled when `ENV=production`).

### 3. Legal (you)
- Fill `frontend/.env`: `VITE_LEGAL_NAME`, `VITE_SUPPORT_EMAIL`, `VITE_GRIEVANCE_OFFICER`, rebuild.
- Have a lawyer review `/privacy` and `/terms` — especially the DPDP Act sections for minors, the 7-day refund
  promise, retention ("backups expire within 30 days" must match your Supabase plan) and "encrypted in transit"
  (true only once HTTPS is on).

### 4. Email (you)
- Password reset by email is built (single-use links, 30 minutes, can't be used to log in). It switches on when
  SMTP is configured: pick a provider (Zoho ZeptoMail, Resend, Amazon SES, Brevo), verify your domain with it,
  then set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` and `APP_URL=https://your-domain`
  in `backend/.env`. The "Forgot password?" link appears on the sign-in page automatically.
- Email verification at sign-up is not built yet (optional for launch).

### 5. AI capacity (you)
- Free Groq/Gemini tiers ran out during overnight testing ("all configured models are rate-limited").
  For launch, move Groq to a paid developer tier (and/or Gemini paid) and keep both as fallbacks.
- Tune `USAGE_*` limits to your cost per user once real usage data exists.

### 6. Question bank
- The shipped seed bank has 153 verified questions (Physics and Maths MCQs well covered; Chemistry, and Maths
  numerical questions, still thin).
  Grow it to at least 3 full papers per subject before launch:
  `backend\.venv\Scripts\python scripts\build_question_bank.py --papers 3` (needs a paid AI tier to finish quickly).
- Have a JEE teacher spot-check a sample: two AIs agreeing is a strong filter, not a guarantee.

### 7. Operations
- Error monitoring (Sentry for API and web), an uptime check on `/api/health`.
- Supabase: enable point-in-time recovery or daily backups on a paid plan; keep the service-role key server-side only.
- Rotate any key that was ever shared in chat or screenshots.

## Soon after launch
- Redis for rooms and rate limits → more than one worker
- Teacher / institute dashboards, Devanagari OCR, Play Store listing (PWA → Trusted Web Activity)
- Privacy-friendly analytics (e.g. Plausible) to see which features students actually use
