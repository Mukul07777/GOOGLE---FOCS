from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent
INSECURE_DEFAULT_KEY = "dev-insecure-secret-change-me"


class Settings(BaseSettings):
    """All paths resolve relative to the backend folder, so the app behaves the same
    no matter which directory it is launched from."""

    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), extra="ignore")

    # App
    APP_NAME: str = "Focs"
    APP_VERSION: str = "1.4.0"
    ENV: str = "development"  # development | production
    SENTRY_DSN: str = ""  # error reports (sentry.io, project focs-backend); empty = off
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # the Android app (mobile/): its pages are served from inside the app at one of these, whatever server it talks to
    APP_ORIGINS: list[str] = ["http://localhost", "https://localhost", "capacitor://localhost"]

    # Database: SUPABASE_DB_URL (Postgres) when set, else the local SQLite file.
    # An explicit DATABASE_URL overrides both (used by tests and Docker).
    DATABASE_URL: str = ""
    SQLITE_PATH: Path = BACKEND_DIR / "focs.db"

    # Supabase (database + storage for board snapshots)
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SECRET_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_DB_URL: str = ""
    SUPABASE_BUCKET: str = "board-snapshots"

    # Sign in with Google: the OAuth web client ID from Google Cloud (APIs & Services > Credentials). Empty = no
    # Google button. It isn't secret: the browser shows it to Google
    GOOGLE_CLIENT_ID: str = ""

    # Auth
    SECRET_KEY: str = INSECURE_DEFAULT_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # LLM — any OpenAI-compatible endpoint. Primary: Groq (free tier). Fallback: Gemini (free tier),
    # used automatically when the primary is rate-limited or down.
    GROQ_API_KEY: str = ""
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    # Cheapest first, everywhere: gpt-oss-20b ($0.075/$0.30 per 1M tokens), then 120b only when 20b is busy.
    LLM_MODEL: str = "openai/gpt-oss-20b,openai/gpt-oss-120b"  # comma-separated, tried in order
    # Frequent, simpler jobs (board notes, pop quizzes, checkpoints, flashcards) try this cheaper model first.
    LLM_LIGHT_MODEL: str = "openai/gpt-oss-20b"
    GEMINI_API_KEY: str = ""
    LLM_FALLBACK_API_KEY: str = ""
    LLM_FALLBACK_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    LLM_FALLBACK_MODEL: str = "gemini-3.1-flash-lite"  # last resort when Groq is down; the pricier Gemini models are never used
    LLM_TIMEOUT_SECONDS: float = 45.0
    # Claude: paid, so tried only once Groq and Gemini have both failed (or aren't configured). Empty key switches
    # it off, same as every other provider here. Spends real (Anthropic) credit, so kept to a cheap model.
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-haiku-5-5"
    # Google first: with a GEMINI_API_KEY, Gemini answers everything (notes, root-cause chains, lessons, the tutor,
    # handwriting) and Groq/Claude only step in when every Gemini model is busy. GOOGLE_ONLY leaves them out entirely
    # (the hackathon build: every call is Gemini). Same OpenAI-compatible endpoint as LLM_FALLBACK_BASE_URL.
    GEMINI_FIRST: bool = True
    GOOGLE_ONLY: bool = False
    GEMINI_MODEL: str = "gemini-3.5-flash-lite,gemini-3-flash-preview,gemini-3.1-flash-lite"  # tried in order
    GEMINI_LIGHT_MODEL: str = "gemini-3.1-flash-lite"  # frequent simple jobs (board notes, pop quizzes) try it first
    # List prices in USD per 1M tokens (input, output), for the cost ledger and the admin dashboard.
    # Update when providers change prices; unknown models are costed at the conservative default.
    MODEL_PRICES_USD: dict[str, tuple[float, float]] = {
        "openai/gpt-oss-120b": (0.15, 0.60),
        "openai/gpt-oss-20b": (0.075, 0.30),
        "gemini-3.1-flash-lite": (0.25, 1.50),
        "gemini-3.5-flash-lite": (0.30, 2.50),
        "gemini-3-flash-preview": (0.50, 3.00),
        "qwen/qwen3.8-27b": (0.80, 4.00),
        "claude-haiku-5-5": (0.10, 0.50),
    }
    DEFAULT_PRICE_USD: tuple[float, float] = (1.0, 4.0)
    # Speech to text for spoken answers, on the primary provider (Groq or OpenAI), used only when the browser
    # can't dictate by itself. Empty switches the fallback off.
    # The models that read images (lecture boards, an uploaded test result), comma-separated and tried in order: on
    # the fallback provider (Gemini), or on the primary one with "groq:". Under high demand a Gemini model answers
    # 503 after up to 20 s, and 3.1-flash-lite did so for 3 of 4 real boards on 2026-10-19, so the board went to
    # garbled OCR instead. Qwen on Groq reads boards too (0.9 s, ~Rs 0.12 a board, a 7 once read as 4): a
    # different provider, so it is up when Gemini is busy. Cheapest first: on three recorded lectures (2026-10-20) Qwen
    # read most boards while the Geminis were overloaded, at Rs 0.11-0.16 a board against Rs 0.04-0.09, three quarters
    # of what a lecture hour cost. A board written up in the background (LIVE_WRITE_BEHIND) waits for them instead.
    VISION_MODEL: str = "gemini-3.1-flash-lite,gemini-3.5-flash-lite,groq:qwen/qwen3.8-27b"
    STT_MODEL: str = "whisper-large-v3-turbo"
    STT_PRICE_USD_PER_HOUR: float = 0.04
    USD_INR: float = 88.0

    # Storage
    STORAGE_DIR: Path = BACKEND_DIR / "storage"
    FRONTEND_DIST: Path = REPO_DIR / "frontend" / "dist"

    # OCR / live capture
    OCR_ENGINE: str = "auto"  # auto (ensemble) | focs | rapid
    # CPU threads each OCR model may use. Left to itself ONNX Runtime takes every core, and a laptop running Focs
    # next to the lecture video stuttered on every new board (15 CPU-seconds in 3.5 s on 12 cores).
    OCR_THREADS: int = 2
    # On a server that isn't production (a student's own laptop), run below normal priority so the lecture video
    # and the browser always get the CPU first.
    BACKGROUND_PRIORITY: bool = True
    OCR_MODEL_DIR: Path = BACKEND_DIR / "app" / "assets" / "ocr"
    OCR_MIN_CHARS: int = 12
    OCR_MIN_LINE_CONFIDENCE: float = 0.5
    # Ensemble rule, fitted on the frame benchmark (scripts/benchmark_ocr.py --analyze):
    # pick FocsOCR when conf_focs + margin (+ math bonus) >= conf_ppocr
    OCR_ENSEMBLE_MARGIN: float = 0.0
    OCR_MATH_BONUS: float = 0.08
    FRAME_HASH_THRESHOLD: int = 2        # Hamming distance (of 64) at or below which frames are "the same board"
    TEXT_NOVELTY_THRESHOLD: float = 0.85  # OCR text similarity above which we skip re-generating notes
    # A board's notes are written BOARD_AWAY_S after the lecture moved on from it (unless it came back to it: a PW
    # teacher talks to the camera for half a minute and goes on writing), or once it has been still for
    # BOARD_SETTLE_S. A board the teacher is still writing on gets them BOARD_REFRESH_S after it appeared, and again
    # every BOARD_REFRESH_S while it grows. A new view is a board once it has held for BOARD_MIN_S, and one left
    # sooner (a cut to the teacher's camera, the frame between two slides) gets no notes.
    BOARD_REFRESH_S: int = 300
    BOARD_SETTLE_S: int = 20
    # frames read at once (each uses a CPU core for its image work and OCR); 0 = the server's CPU count. Past that a
    # frame waits FRAME_WAIT_S for a turn, then is answered "busy" and the app sends the screen again next tick
    FRAME_SLOTS: int = 0
    FRAME_WAIT_S: float = 3.0
    BOARD_AWAY_S: int = 60
    BOARD_MIN_S: int = 15
    # Write a board's notes in the background while the lecture goes on (they come back with a later frame), so the
    # board read can wait for the cheap vision models. Off: written while the frame's request waits (the tests).
    LIVE_WRITE_BEHIND: bool = True

    # Email (password reset). Any SMTP provider; leave SMTP_HOST empty to hide email features.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""  # e.g. "Focs <no-reply@your-domain>"
    # two-step sign-in: a password sign-in also needs a 6-digit code sent to the account's email (Google sign-in
    # doesn't: Google checks the person). Only where email is set up: without SMTP nobody could get the code.
    LOGIN_EMAIL_CODE: bool = True
    APP_URL: str = "http://localhost:8000"  # public address used in email links

    # Plans
    ALLOW_DEV_UPGRADE: bool = True  # dev servers: switch plans, and pay with a test button instead of Razorpay
    # ...and only from the machine the server runs on, so a server put online with ENV left at development
    # doesn't hand out Pro to anyone who asks
    DEV_FEATURES_LOCAL_ONLY: bool = True
    # Behind a hosting proxy every visitor arrives from the proxy's address. Set this to how many proxies add an
    # X-Forwarded-For entry (Cloud Run: 1; Cloud Run behind a Google load balancer: 2) so each visitor gets their
    # own rate limits. Entries are counted from the right: the left end is whatever the visitor wrote.
    TRUSTED_PROXY_HOPS: int = 0
    # Student prices (2026-10-20, night). Pro has a price for each kind of student (services/pricing.py says who is
    # which): "exam" for JEE and NEET, "college" for B.Tech and placements, "school" for class 11-12 boards; more kinds
    # come later (until then everyone else pays the exam price). PRO_PRICES_INR are the regular prices of a month,
    # six months (a semester, or the run-up to an exam) and a year; 0 hides a pass. While the launch offer runs, the
    # plans show them struck through and charge PRO_OFFER_PRICES_INR, until PRO_OFFER_PLACES students have paid for Pro
    # at an offer price (0: no offer). Every pass pays for its own AI: a Pro student's AI may cost at most what their
    # pass brings in per 30 days after Razorpay's ~2.4% (services/pricing.py), so no student can cost more than they
    # paid.
    # Measured: three PW lectures replayed through live capture with the real AI cost Rs 2.1-3.4 a lecture hour (on
    # free Groq and Gemini tiers, whose limits push work to dearer models; Rs 1.5-2.1 without), a doubt ~Rs 0.01,
    # captions ~Rs 3.5 per hour of sound. Fair use at LECTURE_HOUR_INR, per 30 days: about 90 lecture hours on the
    # exam offer, 70 on the college one and 50 on the school one; 115, 95 and 80 at the regular prices.
    PRO_PRICES_INR: dict[str, dict[str, int]] = {
        "exam": {"month": 359, "semester": 1899, "year": 3599},
        "college": {"month": 299, "semester": 1599, "year": 2999},
        "school": {"month": 249, "semester": 1299, "year": 2499},
        "ssc": {"month": 399, "semester": 2099, "year": 3999},
    }
    PRO_OFFER_PRICES_INR: dict[str, dict[str, int]] = {
        "exam": {"month": 249, "semester": 1449, "year": 2849},
        "college": {"month": 199, "semester": 1099, "year": 2199},
        "school": {"month": 149, "semester": 799, "year": 1599},
        "ssc": {"month": 299, "semester": 1699, "year": 3299},
    }
    PRO_OFFER_PLACES: int = 200
    PRO_DAYS: int = 30  # what one Pro payment buys
    PRO_SEMESTER_DAYS: int = 180
    PRO_YEAR_DAYS: int = 365
    # Hours of lecture a study day (USAGE_WINDOW_HOURS) gets AI board notes, by plan: the time a student is capturing a
    # lecture, a pause of more than a minute counted as a minute. Past it, the lecture carries on with basic notes. Pro's
    # 7 hours are its whole promise for lectures (no add-ons); what they cost is covered by its price (see
    # AI_CEILING_PRO_INR). 0 = unlimited.
    LECTURE_HOURS_FREE: float = 0.5
    LECTURE_HOURS_PRO: float = 7.0
    LECTURE_HOURS_TEAM: float = 0
    # Lecture captions are the one AI cost that grows with every minute watched (speech to text is paid by the hour),
    # so they have their own weekly allowance. 0 = unlimited.
    CAPTION_MINUTES_FREE_WEEK: int = 30
    CAPTION_MINUTES_PRO_WEEK: int = 180
    # Payments (dashboard.razorpay.com -> API Keys). Empty: no real payments (dev servers use the test button).
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""  # Webhooks -> payment.captured, so a payment counts even if the tab was closed
    # Mentors: private 1:1 calls and master-session seats are paid for at the mentor's price (Focs keeps a share)
    MENTOR_CALL_PRICE_INR: int = 49       # a private call's price until the mentor sets their own
    MENTOR_CALL_PRICE_MAX_INR: int = 2000  # the most a mentor can charge for a call
    SESSION_PRICE_MAX_INR: int = 1999      # the most a mentor can charge for a seat in a master session
    MENTOR_CALL_MINUTES: int = 30
    MENTOR_COMMISSION_PCT: int = 20       # Focs's share of each paid call; the mentor earns the rest
    GROUP_SESSION_MINUTES: int = 60
    GROUP_SESSION_SEATS: int = 25
    # Paid master sessions a Pro student joins each week at no charge. Focs pays the mentor's share of each such seat
    # out of the Pro price, up to SESSION_PRICE_MAX_INR a seat, so it stays 0 until Pro revenue can carry it.
    PRO_GROUP_SESSIONS_PER_WEEK: int = 0
    GROUP_SESSION_PAY_INR: int = 150      # what Focs pays a mentor for each group session held
    CALL_ROOM_BASE: str = "https://meet.jit.si"  # video rooms; a self-hosted Jitsi or JaaS address works the same
    # Admin panel (/admin): its own ID and password, separate from every student account.
    # Set them with set_admin.bat, which stores only a bcrypt hash of the password.
    ADMIN_USERNAME: str = "admin@focs"
    ADMIN_PASSWORD_HASH: str = ""
    ADMIN_SESSION_HOURS: int = 8
    GOAL_CUSTOMERS: int = 200  # the target shown on the admin dashboard

    # AI allowance. Every AI action costs a few units (see services/usage.py): a board's notes 1, a doubt 2.
    # A study day: the window opens with the first AI action and resets USAGE_WINDOW_HOURS later; a weekly cap sits
    # on top. Pro's day is a 10-hour study day: up to 8 lecture hours of board notes (about 20 a lecture hour) plus
    # doubts, quizzes and practice, and its week lets a student study every day. Starter's day is about an hour of
    # lecture. Boards another student already captured are free and count against nothing. 0 = unlimited.
    USAGE_WINDOW_HOURS: float = 24
    USAGE_FREE_WINDOW: int = 30
    USAGE_FREE_WEEKLY: int = 150
    USAGE_PRO_WINDOW: int = 200
    USAGE_PRO_WEEKLY: int = 1200
    USAGE_TEAM_WINDOW: int = 0
    USAGE_TEAM_WEEKLY: int = 0
    # What one student's AI may really cost in any 30 days (the cost ledger's list prices, captions included), in
    # rupees. Units count actions, but an action's cost varies (which vision model answered, how long the doubt was):
    # this is the guarantee behind the prices above. Past it, that student gets the offline fallbacks until older use
    # drops out of the 30 days. 0 = no ceiling.
    # A Pro student's ceiling is what their pass brings in per 30 days (services/pricing.py), never more than
    # AI_CEILING_PRO_INR, which is also the ceiling of Pro given without a payment. Rs 300 is about 120 hours of lecture
    # notes every 30 days at LECTURE_HOUR_INR; Starter's Rs 40 its half hour a day all month.
    AI_CEILING_FREE_INR: float = 40.0
    AI_CEILING_PRO_INR: float = 300.0
    LECTURE_HOUR_INR: float = 2.5  # what an hour of live lecture costs in AI, as measured (for the plans' wording)
    # Free accounts, all together, may spend this much AI a day, plus a share of what Pro passes brought in over the
    # last 30 days: free students are paid for by Pro income, with a small daily amount to get started. Past it, free
    # accounts get the offline fallbacks until the next day (05:30 IST); Pro carries on. Shared work (the question
    # bank) counts here too. Without a ceiling a script making free accounts could spend without end.
    FREE_AI_DAY_FLOOR_INR: float = 50.0
    FREE_AI_REVENUE_SHARE: float = 0.2
    # Full mock tests started per rolling 7 days
    MOCKS_FREE_PER_WEEK: int = 1
    MOCKS_PRO_PER_WEEK: int = 0  # Pro: unlimited (papers come from the question bank, so the AI cost is small)
    MOCKS_TEAM_PER_WEEK: int = 0
    # Full mocks bought one at a time, past the week's own (Starter: Pro and Institute have them unlimited). They never run out with time.
    # A mock is mostly served from the question bank, so its AI cost is small. 0 takes that choice off sale.
    MOCK_PRICE_INR: int = 9
    MOCK_PACK_SIZE: int = 5
    MOCK_PACK_INR: int = 29

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        if self.SUPABASE_DB_URL:
            url = self.SUPABASE_DB_URL
            for prefix in ("postgresql://", "postgres://"):
                if url.startswith(prefix):
                    return "postgresql+psycopg://" + url[len(prefix):]
            return url
        return f"sqlite:///{self.SQLITE_PATH.as_posix()}"

    @property
    def supabase_server_key(self) -> str:
        return self.SUPABASE_SECRET_KEY or self.SUPABASE_SERVICE_ROLE_KEY

    @property
    def use_supabase_storage(self) -> bool:
        return bool(self.SUPABASE_URL and self.supabase_server_key)

    @property
    def llm_api_key(self) -> str:
        return self.LLM_API_KEY or self.GROQ_API_KEY

    @property
    def gemini_api_key(self) -> str:
        return self.LLM_FALLBACK_API_KEY or self.GEMINI_API_KEY

    @property
    def gemini_first(self) -> bool:
        return (self.GEMINI_FIRST or self.GOOGLE_ONLY) and bool(self.gemini_api_key)

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
