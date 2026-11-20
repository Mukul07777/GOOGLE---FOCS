"""Error reports to Sentry: every unhandled server error, and every log.error / log.exception (background write-ups
included), with the code line and the build that made it. Off unless SENTRY_DSN is set: tests and a
PC with no DSN send nothing. Errors are tagged with ENV, so development errors stay apart from production in Sentry.

No personal data: no emails, no IP addresses, no cookies or login tokens, no request bodies (a student's notes,
uploads and answers), no account. Only the error, the route and the code that failed."""
from __future__ import annotations

import logging

from app.core.config import settings

log = logging.getLogger("focs")


def _scrub(event: dict, _hint: dict) -> dict:
    request = event.get("request") or {}
    request.pop("data", None)
    request.pop("cookies", None)
    for header in ("authorization", "cookie", "x-forwarded-for", "x-real-ip"):
        for key in list((request.get("headers") or {})):
            if key.lower() == header:
                request["headers"].pop(key)
    event.pop("user", None)
    return event


def init_monitoring(build: str) -> bool:
    if not settings.SENTRY_DSN:
        return False
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENV,
            release=f"focs@{settings.APP_VERSION}+{build}",
            send_default_pii=False,
            max_request_body_size="never",
            traces_sample_rate=0.0,  # errors only: performance tracing has its own quota
            before_send=_scrub,
        )
    except Exception:  # noqa: BLE001 (a broken DSN must never stop the app starting)
        log.exception("Sentry could not start; carrying on without error reports")
        return False
    log.info("Error reports go to Sentry (%s)", settings.ENV)
    return True


def report(exc: BaseException) -> None:
    """Send one caught exception (the app's own 500 handler swallows it before Sentry would see it)."""
    if settings.SENTRY_DSN:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
