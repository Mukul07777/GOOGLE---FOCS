"""Sign in with Google: the ID token Google's button hands the browser, checked here before anyone is signed in.

A token counts only when Google signed it (its published keys), it was issued for Focs (our client ID), by Google, is
still in date, and its email is one Google has verified. Off unless GOOGLE_CLIENT_ID is set.
"""
from __future__ import annotations

import logging
from typing import Any

import jwt
from jwt import PyJWKClient

from app.core.config import settings

log = logging.getLogger("focs.google")

GOOGLE_KEYS = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("accounts.google.com", "https://accounts.google.com")
_keys: PyJWKClient | None = None


def enabled() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID)


def _client() -> PyJWKClient:
    global _keys
    if _keys is None:  # Google rotates its keys every few days; they are fetched once and kept for an hour
        _keys = PyJWKClient(GOOGLE_KEYS, cache_keys=True, lifespan=3600, timeout=10)
    return _keys


class GoogleTokenError(ValueError):
    pass


def verify(credential: str) -> dict[str, Any]:
    """The token's claims (email, name, sub...) when it is genuine. Raises GoogleTokenError otherwise."""
    if not enabled():
        raise GoogleTokenError("Google sign-in isn't set up on this server.")
    try:
        key = _client().get_signing_key_from_jwt(credential)
        claims = jwt.decode(credential, key.key, algorithms=["RS256"], audience=settings.GOOGLE_CLIENT_ID,
                            issuer=ISSUERS, leeway=30, options={"require": ["exp", "iat", "aud", "iss", "sub"]})
    except jwt.PyJWKClientError as exc:  # Google's key list unreachable, or a key it doesn't list
        log.warning("Google keys unavailable: %s", exc)
        raise GoogleTokenError("Couldn't check that with Google just now. Try again in a minute.") from exc
    except jwt.PyJWTError as exc:
        raise GoogleTokenError("That Google sign-in didn't check out. Please try again.") from exc
    if not claims.get("email") or claims.get("email_verified") is not True:
        raise GoogleTokenError("Your Google account's email isn't verified, so it can't be used to sign in.")
    return claims
