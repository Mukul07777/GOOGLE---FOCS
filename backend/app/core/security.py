import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    # bcrypt only looks at the first 72 bytes; truncate explicitly so bcrypt>=5 never raises.
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int, expires_minutes: int | None = None, version: int = 0) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "tv": version,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return None


# ---------------------------------------------------------------- password reset links
# Signed with a key derived for this purpose only, so a reset token can never pass as a login token.
# It carries a fingerprint of the current password hash: once the password changes, the link is dead.
def _reset_key() -> str:
    return settings.SECRET_KEY + ":password-reset"


def _fingerprint(hashed_pw: str) -> str:
    return hashlib.sha256(hashed_pw.encode()).hexdigest()[:20]


def create_reset_token(user_id: int, hashed_pw: str, minutes: int = 30) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "purpose": "password-reset", "pw": _fingerprint(hashed_pw),
               "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, _reset_key(), algorithm=settings.ALGORITHM)


def read_reset_token(token: str) -> tuple[int, str] | None:
    """(user id, password fingerprint) for a valid, unexpired reset token."""
    try:
        data = jwt.decode(token, _reset_key(), algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return None
    if data.get("purpose") != "password-reset":
        return None
    try:
        return int(data["sub"]), str(data["pw"])
    except (KeyError, ValueError):
        return None


def reset_token_matches(fingerprint: str, hashed_pw: str) -> bool:
    return hmac.compare_digest(fingerprint, _fingerprint(hashed_pw))


# ---------------------------------------------------------------- the second step of a password sign-in
# After the right password, the browser holds this until the emailed code is typed. Its own key: it never passes as a
# login token. It carries the token version, so a password change in between ends it.
def _login_code_key() -> str:
    return settings.SECRET_KEY + ":login-code"


def create_login_challenge(user_id: int, version: int, minutes: int = 10) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "purpose": "login-code", "tv": version, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, _login_code_key(), algorithm=settings.ALGORITHM)


def read_login_challenge(token: str) -> tuple[int, int] | None:
    """(user id, token version) for a valid, unexpired sign-in challenge."""
    try:
        data = jwt.decode(token, _login_code_key(), algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return None
    if data.get("purpose") != "login-code":
        return None
    try:
        return int(data["sub"]), int(data.get("tv", 0))
    except (KeyError, ValueError):
        return None


# ---------------------------------------------------------------- admin panel sessions
# Signed with their own key: a student token never opens the admin panel, and an admin token is no student login.
# They carry a fingerprint of the admin password hash, so setting a new admin password signs every admin out.
def _admin_key() -> str:
    return settings.SECRET_KEY + ":admin-panel"


def create_admin_token(username: str, hashed_pw: str, hours: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": username, "purpose": "admin", "pw": _fingerprint(hashed_pw),
               "iat": now, "exp": now + timedelta(hours=hours)}
    return jwt.encode(payload, _admin_key(), algorithm=settings.ALGORITHM)


def admin_token_valid(token: str, username: str, hashed_pw: str) -> bool:
    if not hashed_pw:
        return False
    try:
        data = jwt.decode(token, _admin_key(), algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return False
    return (data.get("purpose") == "admin" and data.get("sub") == username
            and hmac.compare_digest(str(data.get("pw", "")), _fingerprint(hashed_pw)))
