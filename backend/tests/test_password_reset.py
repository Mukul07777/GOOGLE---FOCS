"""Password reset by email: single-use, expiring links that can't be used to log in."""
from app.core.config import settings
from app.services import mailer


def test_password_reset_flow(client, monkeypatch):
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_FROM", "Focs <no-reply@example.com>")
    monkeypatch.setattr(mailer, "send_password_reset", lambda to, name, link: sent.append((to, link)) or True)
    monkeypatch.setattr(mailer, "send", lambda *a, **k: True)  # the sign-in code (email is set up, so signing in takes two steps)
    assert client.get("/api/health").json()["email"] is True

    client.post("/api/auth/register", json={"accepted_terms": True, "email": "reset.me@example.com", "full_name": "Dev Patel",
                                            "password": "old-password-1", "exam_target": "jee"})
    # unknown addresses look exactly the same from outside
    assert client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"}).status_code == 204
    assert sent == []
    assert client.post("/api/auth/forgot-password", json={"email": "Reset.Me@example.com"}).status_code == 204
    assert len(sent) == 1 and sent[0][0] == "reset.me@example.com" and "/reset-password?token=" in sent[0][1]
    token = sent[0][1].split("token=")[1]

    # a reset token is not a login token
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert client.post("/api/auth/reset-password", json={"token": token[:-4] + "abcd", "new_password": "x" * 10}).status_code == 400

    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "new-password-2"}).status_code == 204
    new = client.post("/api/auth/login", json={"email": "reset.me@example.com", "password": "new-password-2"})
    assert new.status_code == 200 and new.json()["code_required"]  # the new password is right: on to the emailed code
    assert client.post("/api/auth/login", json={"email": "reset.me@example.com", "password": "old-password-1"}).status_code == 401
    # single use: the password changed, so the same link is dead
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "third-password-3"}).status_code == 400


def test_forgot_password_without_email_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    assert client.get("/api/health").json()["email"] is False
    assert client.post("/api/auth/forgot-password", json={"email": "someone@example.com"}).status_code == 204
