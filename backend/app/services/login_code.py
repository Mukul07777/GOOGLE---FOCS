"""Two-step sign-in: after the right password, a 6-digit code goes to the account's email and must be typed too, so a
leaked password alone doesn't open the account. Google sign-in skips it (Google has checked the person already).
The code is kept only as a hash, works for CODE_MINUTES and allows CODE_TRIES wrong guesses."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from datetime import datetime, timedelta

from app.core.config import settings
from app.models._util import utcnow
from app.models.user import User
from app.services import mailer

CODE_MINUTES, CODE_TRIES, RESEND_AFTER_S = 10, 5, 30
BACKGROUND = True  # tests send in line, to read the code straight away


def needed() -> bool:
    """On where email is set up (and not turned off): without it nobody could receive the code."""
    return settings.LOGIN_EMAIL_CODE and mailer.configured()


def _hash(code: str, user_id: int) -> str:
    return hmac.new(f"{settings.SECRET_KEY}:login-code".encode(), f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def start(user: User) -> str:
    """A fresh code for this sign-in (any earlier one stops working); returns the code to send."""
    code = f"{secrets.randbelow(10**6):06d}"
    now = utcnow()
    user.login_pending = {"code_hash": _hash(code, user.id), "expires": (now + timedelta(minutes=CODE_MINUTES)).isoformat(),
                          "tries": 0, "sent": now.isoformat()}
    return code


def wait_before_resend(user: User) -> int:
    """Seconds until another code may be sent (0: now)."""
    sent = (user.login_pending or {}).get("sent")
    if not sent:
        return 0
    return max(0, int(RESEND_AFTER_S - (utcnow() - datetime.fromisoformat(sent)).total_seconds()))


def confirm(user: User, code: str) -> str | None:
    """None when the code is right (and it is used up), else why not."""
    p = user.login_pending or {}
    if not p:
        return "Sign in again to get a new code."
    if utcnow() > datetime.fromisoformat(p["expires"]):
        user.login_pending = None
        return "That code has expired. Sign in again to get a new one."
    if p.get("tries", 0) >= CODE_TRIES:
        user.login_pending = None
        return "Too many wrong codes. Sign in again to get a new one."
    if not hmac.compare_digest(p["code_hash"], _hash(code.strip(), user.id)):
        user.login_pending = {**p, "tries": p.get("tries", 0) + 1}
        return "That code isn't right. Check the latest email from Focs."
    user.login_pending = None
    return None


def hint(email: str) -> str:
    """Where the code went, without spelling out the address: ri****@gmail.com."""
    name, _, domain = email.partition("@")
    return f"{name[:2]}{'*' * max(2, len(name) - 2)}@{domain}"


def send(user: User, code: str) -> bool:
    first = mailer.greeting_name(user.full_name)
    text = (f"Hi {first},\n\nYour Focs sign-in code is {code}\n\nIt works for {CODE_MINUTES} minutes. If you didn't just try to "
            f"sign in, someone may know your password: change it in Settings.\n\n— Focs")
    html = (f"<p>Hi {first},</p><p>Your Focs sign-in code is</p><p style=\"font-size:28px;font-weight:700;letter-spacing:6px\">"
            f"{code}</p><p>It works for {CODE_MINUTES} minutes. If you didn't just try to sign in, someone may know your password: "
            f"change it in Settings.</p><p>— Focs</p>")
    return mailer.send(user.email, f"Your Focs sign-in code: {code}", text, html)


def send_in_background(user: User, code: str) -> bool:
    """Send the code without making the student wait for the mail server (sign-up took 8-9 s while it answered).
    False only when no mail server is set up at all; a failed send is logged and the student can ask for a resend."""
    if not mailer.configured():
        return False
    email, name = user.email, user.full_name  # read now: the request's session is closed by the time the thread runs
    stub = User(email=email, full_name=name)
    if not BACKGROUND:
        return send(stub, code)
    threading.Thread(target=send, args=(stub, code), daemon=True, name="login-code-mail").start()
    return True
