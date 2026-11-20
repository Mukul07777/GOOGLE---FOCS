"""Outgoing email over SMTP (any provider: Zoho, Resend, Amazon SES, Brevo, a Gmail app password…).

Unconfigured (no SMTP_HOST), Focs simply hides features that need email; nothing breaks.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
import unicodedata
from email.message import EmailMessage

from app.core.config import settings

log = logging.getLogger("focs.mail")


def configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_FROM)


def send(to: str, subject: str, text: str, html: str | None = None) -> bool:
    if not configured():
        log.warning("email not sent (SMTP not configured): %s", subject)
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.SMTP_FROM, to, subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    try:
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, 465, context=ssl.create_default_context(), timeout=20) as s:
                _login_and_send(s, msg)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as s:
                s.starttls(context=ssl.create_default_context())
                _login_and_send(s, msg)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        log.error("email to %s failed: %s", to, exc)
        return False


def _login_and_send(server: smtplib.SMTP, msg: EmailMessage) -> None:
    if settings.SMTP_USER:
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
    server.send_message(msg)


def greeting_name(name: str | None) -> str:
    """The first name for "Hi …": letters only, so a name can't carry HTML or a link into an email Focs sends (anyone
    can sign up with someone else's address and a name of their choosing)."""
    first = (name or "").split()[0] if (name or "").split() else ""
    first = "".join(ch for ch in first if unicodedata.category(ch)[0] in "LM" or ch in "'-")[:30]  # M: Hindi's matras
    return first or "there"


def send_password_reset(to: str, name: str, link: str) -> bool:
    first = greeting_name(name)
    text = (f"Hi {first},\n\nSomeone (hopefully you) asked to reset your Focs password. Open this link within 30 minutes "
            f"to choose a new one:\n\n{link}\n\nIf you didn't ask, ignore this email — your password stays the same.\n\n— Focs")
    html = (f"<p>Hi {first},</p><p>Someone (hopefully you) asked to reset your Focs password. "
            f"The link works for 30 minutes:</p><p><a href=\"{link}\" style=\"display:inline-block;padding:10px 18px;"
            f"background:#7c5cff;color:#fff;border-radius:10px;text-decoration:none\">Choose a new password</a></p>"
            f"<p style=\"color:#666\">If you didn't ask, ignore this email — your password stays the same.</p><p>— Focs</p>")
    return send(to, "Reset your Focs password", text, html)
