"""Small in-process sliding-window rate limiter (per client key and bucket).

Good for a single server. Behind multiple workers, swap the store for Redis.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()
KEEP_S = 3600.0  # the longest window in use; a key with no hit for this long is forgotten
_swept = time.monotonic()


def _sweep(now: float) -> None:
    """Forget visitors not seen for an hour (call with the lock held). Every address and account that ever made a
    request has a key here, so without this the dictionary only grows."""
    global _swept
    if now - _swept < 300:
        return
    _swept = now
    for key in [k for k, q in _hits.items() if not q or now - q[-1] > KEEP_S]:
        del _hits[key]


def _check(key: str, limit: int, window: float) -> None:
    now = time.monotonic()
    with _lock:
        _sweep(now)
        q = _hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            retry = int(window - (now - q[0])) + 1
            raise HTTPException(status_code=429, detail=f"Too many requests — try again in {retry}s.",
                                headers={"Retry-After": str(retry)})
        q.append(now)


def client_ip(request: Request) -> str:
    """The visitor's address. Behind TRUSTED_PROXY_HOPS proxies, the X-Forwarded-For entry that the outermost of
    them added (counted from the right: anything further left was written by the visitor and can't be trusted)."""
    from app.core.config import settings

    hops = settings.TRUSTED_PROXY_HOPS
    forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if hops > 0 and forwarded:
        return forwarded[-hops] if len(forwarded) >= hops else forwarded[0]
    return request.client.host if request.client else "unknown"


def client_key(request: Request) -> str:
    """Who is asking: the signed-in student when the token verifies (so classmates on one Wi-Fi don't share a limit),
    otherwise the address. An Authorization header that doesn't verify counts as no header: a made-up one must not
    buy a fresh limit."""
    from app.core.security import decode_token

    auth = request.headers.get("authorization", "")
    payload = decode_token(auth[7:]) if auth[:7].lower() == "bearer " else None
    sub = str(payload.get("sub", "")) if payload else ""
    if sub.isdigit():
        return f"user:{sub}"
    return f"ip:{client_ip(request)}"


def limit(bucket: str, per_minute: int):
    """FastAPI dependency: at most ``per_minute`` requests a minute per client (see client_key)."""

    def dependency(request: Request) -> None:
        _check(f"{bucket}:{client_key(request)}", per_minute, 60.0)

    return dependency


def guard(key: str, limit: int, window_seconds: float) -> None:
    """Raise 429 if `key` already has `limit` recorded hits in the window. Unlike `limit`, it adds none itself:
    pair it with `record` to count only some outcomes (e.g. failed sign-ins)."""
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window_seconds:
            q.popleft()
        if len(q) >= limit:
            retry = int(window_seconds - (now - q[0])) + 1
            raise HTTPException(status_code=429, detail=f"Too many attempts — try again in {_minutes(retry)}.",
                                headers={"Retry-After": str(retry)})


def record(key: str) -> None:
    with _lock:
        _hits[key].append(time.monotonic())


def _minutes(seconds: int) -> str:
    return f"{seconds}s" if seconds < 90 else f"{round(seconds / 60)} minutes"


def reset() -> None:
    with _lock:
        _hits.clear()
