"""Rate limits that can't be dodged, sign-in at a crowded venue, signing out on a password change, dev-only shortcuts."""
import secrets

from app.core.config import settings


def _user(client, email):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Sec Student", "password": "correct-horse-1", "exam_target": "jee"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def test_a_made_up_token_does_not_buy_a_fresh_limit(client):
    for _ in range(5):  # forgot-password allows 5 a minute per client
        h = {"Authorization": f"Bearer {secrets.token_hex(24)}"}
        assert client.post("/api/auth/forgot-password", headers=h, json={"email": "nobody@example.com"}).status_code == 204
    h = {"Authorization": f"Bearer {secrets.token_hex(24)}"}
    assert client.post("/api/auth/forgot-password", headers=h, json={"email": "nobody@example.com"}).status_code == 429


def test_signed_in_students_on_one_wifi_have_their_own_limits(client):
    a, b = _user(client, "wifi.a@example.com"), _user(client, "wifi.b@example.com")
    for _ in range(6):  # export allows 6 a minute
        assert client.get("/api/auth/export", headers={"Authorization": f"Bearer {a}"}).status_code == 200
    assert client.get("/api/auth/export", headers={"Authorization": f"Bearer {a}"}).status_code == 429
    assert client.get("/api/auth/export", headers={"Authorization": f"Bearer {b}"}).status_code == 200


def test_password_guessing_is_stopped_per_email_not_per_hall(client):
    _user(client, "guessed@example.com")
    _user(client, "neighbour@example.com")
    for _ in range(8):
        assert client.post("/api/auth/login", json={"email": "guessed@example.com", "password": "wrong-password"}).status_code == 401
    locked = client.post("/api/auth/login", json={"email": "guessed@example.com", "password": "correct-horse-1"})
    assert locked.status_code == 429  # even the right password waits now
    # the rest of the room (same address) signs in fine
    assert client.post("/api/auth/login", json={"email": "neighbour@example.com", "password": "correct-horse-1"}).status_code == 200


def test_changing_the_password_signs_out_other_devices(client):
    old = _user(client, "phone.laptop@example.com")
    other_device = client.post("/api/auth/login", json={"email": "phone.laptop@example.com", "password": "correct-horse-1"}).json()["access_token"]
    r = client.post("/api/auth/change-password", headers={"Authorization": f"Bearer {old}"},
                    json={"current_password": "correct-horse-1", "new_password": "a-new-password-2"})
    assert r.status_code == 200 and r.json()["access_token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {other_device}"}).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).status_code == 200


def test_dev_shortcuts_only_from_the_server_machine(client, monkeypatch):
    token = _user(client, "remote.dev@example.com")
    monkeypatch.setattr(settings, "DEV_FEATURES_LOCAL_ONLY", True)  # the test client isn't 127.0.0.1: it plays a remote visitor
    h = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/billing/dev-upgrade", headers=h, json={"plan": "pro"}).status_code == 403
    plans = client.get("/api/billing/plans").json()
    assert plans["dev_upgrade"] is False and plans["payments"] is None
    assert client.post("/api/billing/pro", headers=h).status_code == 503


def test_forwarded_addresses_count_from_the_right(monkeypatch):
    from starlette.requests import Request

    from app.core import ratelimit
    from app.services import payments

    def req(xff=None, host="10.0.0.5"):
        headers = [(b"x-forwarded-for", xff.encode())] if xff else []
        return Request({"type": "http", "headers": headers, "client": (host, 1234)})

    assert ratelimit.client_ip(req("1.2.3.4")) == "10.0.0.5"  # no proxy configured: the header is ignored
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    assert ratelimit.client_ip(req("6.6.6.6, 203.0.113.9")) == "203.0.113.9"  # the visitor's made-up entry is on the left
    assert ratelimit.client_ip(req("203.0.113.9")) == "203.0.113.9"
    assert not payments.is_local(req("127.0.0.1", host="127.0.0.1"))  # through a proxy is never "this machine"
    assert payments.is_local(req(host="127.0.0.1"))
