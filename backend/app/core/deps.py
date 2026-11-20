from collections.abc import Iterator
from datetime import timedelta

from fastapi import Depends, HTTPException, status
from fastapi.requests import HTTPConnection
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import admin_token_valid, decode_token
from app.models._util import utcnow
from app.models.user import User

LAST_SEEN_EVERY = timedelta(minutes=10)

bearer = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def user_from_token(token: str | None, db: Session) -> User | None:
    payload = decode_token(token) if token else None
    if not payload or not str(payload.get("sub", "")).isdigit():
        return None
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active or payload.get("tv", 0) != (user.token_version or 0):  # signed out by a password change
        return None
    return user


def get_current_user(
    conn: HTTPConnection,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials if credentials else None
    checked = getattr(conn.state, "checked_user", None)  # read moments ago by the router's role check (only_role)
    if checked and token and checked[0] == token and checked[1] is not None:
        user = db.merge(checked[1], load=False)  # this request's session, without asking the database again
    else:
        user = user_from_token(token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    now = utcnow()
    if user.plan == "pro" and user.pro_until and user.pro_until < now:  # a paid Pro month has run out
        user.plan = "free"
        db.commit()
    if not user.last_seen_at or now - user.last_seen_at > LAST_SEEN_EVERY:  # active-user stats, not every request
        user.last_seen_at = now
        db.commit()
    return user


def require_admin(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    """The admin panel's own sign-in (ADMIN_USERNAME / ADMIN_PASSWORD_HASH); student logins never pass."""
    token = credentials.credentials if credentials else ""
    if not token or not admin_token_valid(token, settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD_HASH):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please sign in to the admin panel.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return settings.ADMIN_USERNAME


# Roles. Every account is a student or a mentor (User.role, fixed at sign-up: no endpoint changes it). The admin is not
# an account: the admin panel has its own sign-in (require_admin). Which role may use which part of the API is set in
# one place, app/api/__init__.py, and tests/test_access.py checks every route against it.
STUDENT, MENTOR = "student", "mentor"
ROLE_DENIED = {
    STUDENT: "This is for mentor accounts. Sign in with your mentor account.",
    MENTOR: "Mentor accounts can't do this: it's for students.",
}


def role_of(user: User) -> str:
    return MENTOR if user.role == MENTOR else STUDENT  # accounts from before roles have none: students


def require_role(role: str):
    """A dependency that lets only ``role``'s accounts through (401 when signed out, 403 for the other role)."""
    def check(user: User = Depends(get_current_user)) -> User:
        if role_of(user) != role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ROLE_DENIED[role_of(user)])
        return user
    check.__name__ = f"require_{role}"
    return check


# A mentor account (approved or not: each endpoint checks the approval it needs).
require_mentor = require_role(MENTOR)
# A student account: studying, the AI, finding mentors, booking calls and seats. Mentor accounts guide; they don't study here.
require_student = require_role(STUDENT)


def only_role(role: str):
    """For a whole router: refuses a signed-in account of the other role. Without a token it lets the request on, so
    each endpoint's own check answers 401 and the few public endpoints stay public. Websockets check in their handler
    (their token comes in the first message, not a header)."""
    def check(conn: HTTPConnection, db: Session = Depends(get_db)) -> None:
        if conn.scope["type"] != "http":
            return
        scheme, _, token = conn.headers.get("authorization", "").partition(" ")
        user = user_from_token(token.strip(), db) if scheme.lower() == "bearer" and token.strip() else None
        conn.state.checked_user = (token.strip(), user)  # get_current_user takes it from here: one database read, not two
        if user is not None and role_of(user) != role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ROLE_DENIED[role_of(user)])
    check.__name__ = f"only_{role}s"
    return check


def require_pro(user: User = Depends(get_current_user)) -> User:
    if user.plan not in ("pro", "team"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This feature is part of Focs Pro.")
    return user
