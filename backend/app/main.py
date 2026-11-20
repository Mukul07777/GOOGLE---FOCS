import logging
import mimetypes
import os
import re
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.core.config import INSECURE_DEFAULT_KEY, settings
from app.core.buildinfo import fingerprint
from sqlalchemy import text

from app.core.database import engine, init_db
from app.core.deps import get_current_user
from app.core.security import decode_token
from app.core.migrate import migrate_local_to_postgres_if_needed
from app.core.logging import setup_logging
from app.core.monitoring import init_monitoring, report
from app.services.llm import llm, providers as llm_providers
from app.services.maintenance import backfill_legacy
from app.services import ledger, mailer, storage
from app.services.ocr import ocr_engine

setup_logging()
BUILD = fingerprint()  # what this process is running; the launcher compares it
init_monitoring(BUILD)
log = logging.getLogger("focs")


def _below_normal_priority() -> None:
    """Focs on a student's own laptop shares the CPU with the lecture it reads: let the video and browser go first.
    (A busy CPU still gives this process all the time nobody else wants.)"""
    try:
        if os.name == "nt":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL_PRIORITY_CLASS
        else:
            os.nice(5)
    except Exception:  # noqa: BLE001 - priority is a courtesy, never a reason not to start
        log.debug("could not lower the process priority", exc_info=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    weak = settings.SECRET_KEY in (INSECURE_DEFAULT_KEY, "change-me") or len(settings.SECRET_KEY) < 32
    if settings.is_production and weak:  # it signs every login: a guessable one lets anyone sign in as anyone
        raise RuntimeError("Set a random SECRET_KEY of 32+ characters in backend/.env before running in production.")
    if not (settings.gemini_api_key or settings.llm_api_key):  # notes, summaries and tests go offline-only: say so loudly
        log.warning("No AI key: set GEMINI_API_KEY in backend/.env or the server's environment")
    else:
        log.info("AI: %s", ", ".join(p.name for p in llm_providers()) or "none usable")
    if settings.is_production and settings.LOGIN_EMAIL_CODE and not mailer.configured():
        log.warning("Email (SMTP) isn't set up: password sign-ins skip the emailed code, and forgot-password is off")
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, 7):  # a short internet/DNS blip at start-up shouldn't stop Focs: retry for ~30 s
        try:
            init_db()
            break
        except Exception as exc:
            where = "Supabase (check your internet and SUPABASE_DB_URL in backend/.env)" if engine.dialect.name == "postgresql" else "the database"
            if attempt == 6 or engine.dialect.name != "postgresql":
                raise RuntimeError(f"Focs could not connect to {where}: {exc}") from exc
            log.warning("Can't reach %s yet (attempt %d of 6), retrying in 5 s…", where.split(" (")[0], attempt)
            time.sleep(5)
    copied = migrate_local_to_postgres_if_needed(engine, settings.SQLITE_PATH)
    if copied:
        _upload_existing_snapshots()
    storage.ensure_bucket()
    backfill_legacy()
    _load_question_bank()
    if settings.BACKGROUND_PRIORITY and not settings.is_production:
        _below_normal_priority()
    # Load OCR models (and read one line) in the background so the first captured frame isn't slow.
    threading.Thread(target=ocr_engine.warm_up, name="ocr-warmup", daemon=True).start()
    log.info("Focs %s ready — LLM %s", settings.APP_VERSION,
             f"on ({' -> '.join(llm.models)})" if llm.available else "OFF (offline mode: add GEMINI_API_KEY to backend/.env)")
    yield
    ledger.flush()  # AI calls still queued for the cost ledger


def _load_question_bank() -> None:
    from app.core.database import SessionLocal
    from app.services import question_bank, topic_notes

    with SessionLocal() as db:
        question_bank.load_seed(db)
        topic_notes.load_seed(db)  # detailed notes shipped with Focs


def _upload_existing_snapshots() -> None:
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.note import Note

    with SessionLocal() as db:
        paths = [p for p in db.scalars(select(Note.image_path).where(Note.image_path.is_not(None)))]
    if paths:
        log.info("uploaded %d existing board snapshots", storage.upload_local_snapshots(paths))


MAX_UPLOAD_BODY = 64 * 1024 * 1024  # the biggest real upload: a test result of 6 files of 10 MB
MAX_BODY = 2 * 1024 * 1024          # everything else is a form or JSON


class BodyLimit:
    """Turns away a request body over the limit as it arrives. Each upload checks its own size, but only after
    Starlette has saved the whole body to disk: without this, one request of a few gigabytes could fill the disk."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        cap = MAX_UPLOAD_BODY if headers.get(b"content-type", b"").startswith(b"multipart/") else MAX_BODY
        declared = headers.get(b"content-length", b"")
        if declared.isdigit() and int(declared) > cap:
            response = JSONResponse(status_code=413, content={"detail": "That upload is too big."})
            return await response(scope, receive, send)
        received = 0

        async def counted():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > cap:  # a body sent without a length, or longer than it said
                    raise HTTPException(status_code=413, detail="That upload is too big.")
            return message

        await self.app(scope, counted, send)


class HeadAsGet:
    """Answers HEAD like GET minus the body, so uptime monitors and link checkers (which probe with HEAD) don't see a
    405 and report a healthy site as down."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "HEAD":
            return await self.app(scope, receive, send)

        async def no_body(message):
            if message["type"] == "http.response.body":
                message = {"type": "http.response.body", "body": b"", "more_body": message.get("more_body", False)}
            await send(message)
        await self.app({**scope, "method": "GET"}, receive, no_body)


def create_app() -> FastAPI:
    docs = not settings.is_production  # the API map stays on dev servers: no need to hand it to strangers
    app = FastAPI(title=f"{settings.APP_NAME} API", version=settings.APP_VERSION, lifespan=lifespan,
                  docs_url="/api/docs" if docs else None, redoc_url=None, openapi_url="/api/openapi.json" if docs else None)
    app.add_middleware(BodyLimit)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(CORSMiddleware, allow_origins=[*settings.CORS_ORIGINS, *settings.APP_ORIGINS], allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(HeadAsGet)  # last added = outermost

    @app.middleware("http")
    async def headers_and_timing(request: Request, call_next):
        start = time.perf_counter()
        # who the AI calls in this request are for (cost ledger); a bad or missing token just means "nobody"
        auth = request.headers.get("authorization", "")
        payload = decode_token(auth[7:]) if auth.lower().startswith("bearer ") else None
        sub = str((payload or {}).get("sub", ""))
        ledger.current_user.set(int(sub) if sub.isdigit() else None)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        # Only rules that can't break a page: no <base> tag rewriting links, no framing by other sites. (A script
        # allow-list would stop injected scripts too, but needs testing with Razorpay and YouTube first; object-src
        # stays open because shared PDFs open as blob: pages that inherit this policy and need the PDF viewer.)
        response.headers["Content-Security-Policy"] = (
            "base-uri 'self'; frame-ancestors 'none'; form-action 'self'; " + _script_policy())
        # The script allow-list is now enforced (merged above). Violations still go to /api/csp-report. To roll back,
        # send _script_policy() as Content-Security-Policy-Report-Only again. Razorpay's checkout.js needs 'unsafe-eval'.
        # The lecture tools need the camera, microphone and screen capture on our own pages, nothing else does.
        response.headers["Permissions-Policy"] = ("camera=(self), microphone=(self), display-capture=(self), "
                                                  "geolocation=(), usb=(), payment=(self \"https://checkout.razorpay.com\"), interest-cohort=()")
        if settings.is_production:  # HTTPS only from now on: browsers ignore this over plain http
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path.startswith("/api/"):
            ms = (time.perf_counter() - start) * 1000
            response.headers["Server-Timing"] = f"app;dur={ms:.0f}"
            if ms > 1500:
                log.info("%s %s %d %.0fms", request.method, request.url.path, response.status_code, ms)
        return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        report(exc)
        return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side. Please try again."})

    @app.get("/api/health", tags=["meta"])
    def health():
        # Public, so only what a signed-out page needs: no versions, providers or model names.
        return {"status": "ok", "llm": {"available": llm.available}, "email": mailer.configured(),
                "google_client_id": settings.GOOGLE_CLIENT_ID or None}  # Sign in with Google (public by design)

    @app.get("/api/health/ready", tags=["meta"])
    def health_ready():
        """For the uptime monitor: also proves the database answers. Kept apart from /api/health, which the Docker
        healthcheck and the web app use, so a database blip doesn't mark the container unhealthy."""
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            log.error("readiness check: database not answering: %s", type(exc).__name__)
            return JSONResponse(status_code=503, content={"status": "degraded", "database": "down"})
        return {"status": "ok", "database": "ok"}

    @app.get("/api/health/details", tags=["meta"])
    def health_details(_user=Depends(get_current_user)):
        ocr = ocr_engine.status()
        return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION,
                "database": "supabase" if engine.dialect.name == "postgresql" else "local",
                "storage": storage.backend(),
                "llm": {"available": llm.available, "model": " → ".join(llm.models) if llm.available else None},
                "ocr": {"engines": ocr["engines"], "default": ocr["default"], "detector": ocr["detector"]},
                "email": mailer.configured(), "build": BUILD,
                "google_client_id": settings.GOOGLE_CLIENT_ID or None}

    @app.post("/api/csp-report", include_in_schema=False, status_code=204)
    async def csp_report(request: Request):
        """Browsers post here what the report-only script policy would have blocked. Logged, never stored."""
        global _csp_logged
        body = (await request.body())[:2000]
        if _csp_logged < 500:  # a page stuck in a loop must not fill the logs
            _csp_logged += 1
            log.warning("csp would block: %s", body.decode("utf-8", "replace"))
        return Response(status_code=204)

    app.include_router(api_router)
    _mount_frontend(app, settings.FRONTEND_DIST)
    return app


_csp_logged = 0
_SCRIPT_POLICY: str | None = None


def _script_policy() -> str:
    """script-src for our own files, the inline theme script in index.html (by its hash, read once from the build),
    Google sign-in, YouTube's player API and Razorpay checkout. Workers come from blob: (lib/focus.ts)."""
    global _SCRIPT_POLICY
    if _SCRIPT_POLICY is None:
        import base64
        import hashlib
        hashes = []
        try:
            html = (settings.FRONTEND_DIST / "index.html").read_text(encoding="utf-8")
            for body in re.findall(r"<script>(.*?)</script>", html, re.S):
                digest = base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode()
                hashes.append(f"'sha256-{digest}'")
        except OSError:
            pass
        _SCRIPT_POLICY = ("script-src 'self' " + " ".join(hashes) + " 'unsafe-eval' https://accounts.google.com "
                          "https://www.youtube.com https://checkout.razorpay.com https://*.razorpay.com; "
                          "worker-src 'self' blob:; report-uri /api/csp-report")
    return _SCRIPT_POLICY


class ImmutableStatic(StaticFiles):
    """Vite puts a content hash in every asset name, so browsers may cache them for good."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


mimetypes.add_type("application/manifest+json", ".webmanifest")  # unknown to Windows' registry


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built React app (single-page routing) from the same origin as the API."""
    index = dist / "index.html"
    if not index.exists():
        @app.get("/", include_in_schema=False)
        def no_frontend():
            return JSONResponse({"app": settings.APP_NAME, "api_docs": "/api/docs",
                                 "hint": "Frontend not built yet. Run run.bat (or: cd frontend && npm run build)."})
        return

    if (dist / "assets").exists():
        app.mount("/assets", ImmutableStatic(directory=dist / "assets"), name="assets")
    if (dist / "q").exists():  # question figures: named by a hash of the picture, so they never change either
        app.mount("/q", ImmutableStatic(directory=dist / "q"), name="figures")

    root = dist.resolve()

    @app.get("/sitemap.xml", include_in_schema=False)
    def sitemap(request: Request):
        base = str(request.base_url).rstrip("/")
        urls = "".join(f"<url><loc>{base}{p}</loc></url>" for p in PUBLIC_PAGES)
        return Response('<?xml version="1.0" encoding="UTF-8"?>'
                        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
                        media_type="application/xml")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and root in candidate.parents:
            # the service worker must be re-checked on every visit, or a fixed one never reaches browsers
            return FileResponse(candidate, headers={"Cache-Control": "no-cache"} if path == "sw.js" else None)
        # The app still renders its own "blank board" page, but search engines and tools see a real 404
        # for anything that isn't one of the app's routes.
        status = 200 if _is_app_route("/" + path) else 404
        return FileResponse(index, status_code=status, headers={"Cache-Control": "no-cache"})


# Pages anyone can open, listed in the sitemap.
PUBLIC_PAGES = ["/", "/login", "/signup", "/mentor/signup", "/privacy", "/terms"]
# Every route the React app knows (frontend/src/App.tsx). Keep the two in step.
_APP_ROUTES = [r"/", r"/pricing", r"/privacy", r"/terms", r"/p/[^/]+", r"/login", r"/signup", r"/mentor/signup", r"/switch/mentor",
               r"/forgot-password", r"/reset-password", r"/app(/.*)?", r"/mentor(/.*)?", r"/admin(/login)?",
               r"/exam/[^/]+", r"/onboarding(/.*)?"]
_APP_ROUTE_RE = re.compile("^(?:" + "|".join(_APP_ROUTES) + ")/?$")


def _is_app_route(path: str) -> bool:
    return bool(_APP_ROUTE_RE.match(path))

app = create_app()
