"""Two-step sign-in: with email set up, the right password alone doesn't sign anyone in; the 6-digit code from the
account's email does. A wrong code five times, an old code, a resent code's predecessor or a forged step all fail.
Google sign-in and servers without email skip the step."""
import re

import pytest

from app.core.config import settings
from app.services import login_code, mailer

PASSWORD = "correct-horse-1"


@pytest.fixture
def inbox(monkeypatch):
    sent = []
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_FROM", "Focs <no-reply@example.com>")
    monkeypatch.setattr(mailer, "send", lambda to, subject, text, html=None: sent.append((to, text)) or True)
    monkeypatch.setattr(login_code, "BACKGROUND", False)
    return sent


def _account(client, email):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Two Step", "password": PASSWORD,
                                                "exam_target": "jee", "accepted_terms": True})
    assert r.status_code == 201


def _code(inbox):
    return re.search(r"\b(\d{6})\b", inbox[-1][1]).group(1)


def test_the_password_alone_doesnt_sign_in_the_emailed_code_does(client, inbox):
    _account(client, "two.step@example.com")
    r = client.post("/api/auth/login", json={"email": "two.step@example.com", "password": PASSWORD}).json()
    assert r["code_required"] and "access_token" not in r and r["sent_to"] == "tw******@example.com"
    assert inbox[-1][0] == "two.step@example.com"
    # the step token is no login token
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {r['challenge']}"}).status_code == 401
    wrong = "000000" if _code(inbox) != "000000" else "111111"
    assert client.post("/api/auth/login/verify", json={"challenge": r["challenge"], "code": wrong}).status_code == 400
    ok = client.post("/api/auth/login/verify", json={"challenge": r["challenge"], "code": _code(inbox)})
    assert ok.status_code == 200 and ok.json()["user"]["email"] == "two.step@example.com"
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {ok.json()['access_token']}"}).status_code == 200
    # a code works once
    assert client.post("/api/auth/login/verify", json={"challenge": r["challenge"], "code": _code(inbox)}).status_code == 400


def test_five_wrong_codes_end_the_sign_in(client, inbox):
    _account(client, "guesser@example.com")
    r = client.post("/api/auth/login", json={"email": "guesser@example.com", "password": PASSWORD}).json()
    right = _code(inbox)
    wrong = [f"{n:06d}" for n in range(10) if f"{n:06d}" != right][:login_code.CODE_TRIES]
    for code in wrong:
        assert client.post("/api/auth/login/verify", json={"challenge": r["challenge"], "code": code}).status_code == 400
    late = client.post("/api/auth/login/verify", json={"challenge": r["challenge"], "code": right})
    assert late.status_code == 400 and "Sign in again" in late.json()["detail"]


def test_a_resent_code_replaces_the_old_one_after_a_wait(client, inbox, monkeypatch):
    _account(client, "resend@example.com")
    inbox.clear()  # signing up sent its own code
    r = client.post("/api/auth/login", json={"email": "resend@example.com", "password": PASSWORD}).json()
    first = _code(inbox)
    assert client.post("/api/auth/login/resend", json={"challenge": r["challenge"]}).status_code == 429  # too soon
    monkeypatch.setattr(login_code, "RESEND_AFTER_S", 0)
    again = client.post("/api/auth/login/resend", json={"challenge": r["challenge"]})
    assert again.status_code == 200 and len(inbox) == 2
    second = _code(inbox)
    if first != second:
        assert client.post("/api/auth/login/verify", json={"challenge": r["challenge"], "code": first}).status_code == 400
    assert client.post("/api/auth/login/verify", json={"challenge": again.json()["challenge"], "code": second}).status_code == 200


def test_a_forged_or_outdated_step_is_refused(client, inbox):
    _account(client, "forged.step@example.com")
    r = client.post("/api/auth/login", json={"email": "forged.step@example.com", "password": PASSWORD}).json()
    assert client.post("/api/auth/login/verify", json={"challenge": "x" * 40, "code": _code(inbox)}).status_code == 401
    # a password reset in between ends the half-finished sign-in
    from app.core.database import SessionLocal
    from app.models.user import User
    with SessionLocal() as db:
        u = db.query(User).filter(User.email == "forged.step@example.com").one()
        u.token_version = (u.token_version or 0) + 1
        db.commit()
    assert client.post("/api/auth/login/verify", json={"challenge": r["challenge"], "code": _code(inbox)}).status_code == 401


def test_without_email_or_with_it_turned_off_the_password_signs_in(client, monkeypatch):
    _account(client, "no.smtp@example.com")
    assert "access_token" in client.post("/api/auth/login", json={"email": "no.smtp@example.com", "password": PASSWORD}).json()
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_FROM", "Focs <no-reply@example.com>")
    monkeypatch.setattr(settings, "LOGIN_EMAIL_CODE", False)
    assert "access_token" in client.post("/api/auth/login", json={"email": "no.smtp@example.com", "password": PASSWORD}).json()


def test_an_email_that_fails_to_send_says_so(client, monkeypatch):
    _account(client, "mail.down@example.com")
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_FROM", "Focs <no-reply@example.com>")
    monkeypatch.setattr(mailer, "send", lambda *a, **k: False)
    monkeypatch.setattr(login_code, "BACKGROUND", False)  # (live, the mail goes out after the reply; the student can resend)
    r = client.post("/api/auth/login", json={"email": "mail.down@example.com", "password": PASSWORD})
    assert r.status_code == 502 and "access_token" not in r.text


def test_signing_up_with_a_password_also_needs_the_emailed_code(client, inbox):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": "newcomer@example.com", "full_name": "New Comer", "password": PASSWORD,
                                                "exam_target": "jee", "accepted_terms": True})
    body = r.json()
    assert r.status_code == 201 and body["code_required"] and "access_token" not in body
    assert inbox[-1][0] == "newcomer@example.com"
    wrong = "000000" if _code(inbox) != "000000" else "111111"
    assert client.post("/api/auth/login/verify", json={"challenge": body["challenge"], "code": wrong}).status_code == 400
    ok = client.post("/api/auth/login/verify", json={"challenge": body["challenge"], "code": _code(inbox)})
    assert ok.status_code == 200 and ok.json()["user"]["exam_target"] == "jee"


def test_signing_up_without_email_set_up_signs_in_straight_away(client):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": "nomail@example.com", "full_name": "No Mail", "password": PASSWORD,
                                                "exam_target": "jee", "accepted_terms": True})
    assert r.status_code == 201 and r.json()["access_token"]
