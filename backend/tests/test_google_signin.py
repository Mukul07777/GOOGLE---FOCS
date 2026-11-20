"""Continue with Google: only a genuine, in-date token issued for Focs with a verified email signs anyone in; an email
that already has an account signs in to it; a new one gets an account only from the sign-up page."""
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import settings
from app.services import google_auth

CLIENT = "focs-test.apps.googleusercontent.com"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _Key:
    key = KEY.public_key()


class _Keys:  # stands in for Google's published keys
    def get_signing_key_from_jwt(self, token):
        return _Key()


@pytest.fixture(autouse=True)
def google(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT)
    monkeypatch.setattr(google_auth, "_client", lambda: _Keys())


def token(email, verified=True, aud=CLIENT, iss="https://accounts.google.com", age=0, key=KEY, name="Riya Sharma"):
    now = int(time.time()) - age
    return jwt.encode({"iss": iss, "aud": aud, "sub": "1234567890", "email": email, "email_verified": verified,
                       "name": name, "iat": now, "exp": now + 3600}, key, algorithm="RS256")


def test_a_new_student_signs_up_with_google_and_lands_in_goal_setup(client):
    r = client.post("/api/auth/google", json={"credential": token("riya.g@example.com"), "accepted_terms": True,
                                              "exam_target": "neet"})
    assert r.status_code == 200 and r.json()["created"] is True
    user = r.json()["user"]
    assert user["email"] == "riya.g@example.com" and user["full_name"] == "Riya Sharma" and user["exam_target"] == "neet"
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200
    # signing in again with Google is the same account, not a new one
    again = client.post("/api/auth/google", json={"credential": token("Riya.G@example.com")}).json()
    assert again["user"]["id"] == user["id"] and again["created"] is False


def test_an_email_with_a_password_account_signs_in_to_it(client):
    client.post("/api/auth/register", json={"accepted_terms": True, "email": "pw.user@example.com", "full_name": "Pw User", "password": "correct-horse-1",
                                            "exam_target": "jee", "accepted_terms": True})
    r = client.post("/api/auth/google", json={"credential": token("pw.user@example.com")})
    assert r.status_code == 200 and r.json()["user"]["full_name"] == "Pw User"
    assert client.post("/api/auth/login", json={"email": "pw.user@example.com", "password": "correct-horse-1"}).status_code == 200


def test_the_sign_in_page_sends_a_new_email_to_sign_up(client):
    r = client.post("/api/auth/google", json={"credential": token("nobody.yet@example.com")})
    assert r.status_code == 404 and "Create one" in r.json()["detail"]


def test_a_new_account_needs_its_exam_chosen(client):
    """With JEE assumed, a student who went straight to Continue with Google became a JEE student without choosing."""
    r = client.post("/api/auth/google", json={"credential": token("no.exam@example.com"), "accepted_terms": True})
    assert r.status_code == 422 and "preparing for" in r.json()["detail"]
    r = client.post("/api/auth/google", json={"credential": token("no.exam@example.com"), "accepted_terms": True,
                                              "exam_target": "cbse_11"})
    assert r.status_code == 200 and r.json()["user"]["exam_target"] == "cbse_11"


@pytest.mark.parametrize("bad", [
    {"verified": False},                       # Google hasn't verified the email
    {"aud": "someone-else.apps.googleusercontent.com"},  # a token another site was given
    {"iss": "https://evil.example.com"},
    {"age": 7300},                             # expired two hours ago
    {"key": OTHER_KEY},                        # not signed by Google
])
def test_a_token_that_doesnt_check_out_signs_nobody_in(client, bad):
    r = client.post("/api/auth/google", json={"credential": token("forged@example.com", **bad), "accepted_terms": True})
    assert r.status_code == 401


def test_without_a_client_id_google_sign_in_is_off(client, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    assert client.post("/api/auth/google", json={"credential": token("off@example.com")}).status_code == 401
    assert client.get("/api/health").json()["google_client_id"] is None
