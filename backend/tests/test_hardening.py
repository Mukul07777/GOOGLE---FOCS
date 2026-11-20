"""Launch hardening: oversized bodies, image and PDF bombs, the daily AI budget, room sockets, sign-up floods."""
import io

import pytest
from starlette.websockets import WebSocketDisconnect

from app.core import ratelimit
from app.core.config import settings


def _user(client, email):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Hard Student", "password": "correct-horse-1", "exam_target": "jee"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def test_oversized_bodies_are_turned_away(client, auth):
    big = "x" * (2 * 1024 * 1024 + 10)
    assert client.patch("/api/auth/me", headers={**auth, "Content-Type": "application/json"},
                        content=f'{{"full_name": "{big}"}}').status_code == 413
    # an upload bigger than any real one is refused before the app reads it
    r = client.post("/api/capture/1/frame", headers={**auth, "Content-Type": "multipart/form-data; boundary=x"},
                    content=b"x" * (65 * 1024 * 1024))
    assert r.status_code == 413

    def chunks():  # no Content-Length at all: counted as it arrives
        yield b'{"full_name": "'
        for _ in range(3):
            yield b"y" * (1024 * 1024)
        yield b'"}'

    r = client.patch("/api/auth/me", headers={**auth, "Content-Type": "application/json"}, content=chunks())
    assert r.status_code == 413


def test_a_small_file_that_unpacks_huge_is_refused():
    from PIL import Image

    from app.services import images, vision

    buf = io.BytesIO()
    Image.new("1", (8000, 6000)).save(buf, format="PNG")  # 48 megapixels in a few kilobytes
    assert len(buf.getvalue()) < 200_000
    with pytest.raises(ValueError):
        images.open_image(buf.getvalue(), 1600)
    with pytest.raises(ValueError):
        vision.to_jpeg(buf.getvalue())
    ok = io.BytesIO()
    Image.new("RGB", (4000, 3000), "white").save(ok, format="JPEG")  # a phone photo opens, shrunk while decoding
    assert max(images.open_image(ok.getvalue(), 1600).size) < 4000


def test_a_pdf_page_claiming_a_huge_size_is_drawn_small():
    import pymupdf

    from app.services import vision

    doc = pymupdf.open()
    doc.new_page(width=14400, height=14400)  # 200 × 200 inches
    data = doc.tobytes()
    assert vision.pdf_page_count(data) == 1
    from PIL import Image

    page = Image.open(io.BytesIO(vision.pdf_pages(data, 1)[0]))
    assert max(page.size) <= 2400
    with pytest.raises(ValueError):
        vision.pdf_page_count(b"%PDF-1.4 not really")


def test_the_daily_budget_pauses_free_accounts_only(client, monkeypatch):
    from app.models.user import User
    from app.services import ledger
    from app.services.llm import LLMUnavailable, ensure_budget

    free = _user(client, "budget.free@example.com")
    pro = _user(client, "budget.pro@example.com")
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        free_id = db.query(User).filter(User.email == "budget.free@example.com").one().id
        pro_user = db.query(User).filter(User.email == "budget.pro@example.com").one()
        pro_user.plan, pro_id = "pro", pro_user.id
        db.commit()
    assert free and pro
    monkeypatch.setattr(settings, "FREE_AI_DAY_FLOOR_INR", 1.0)
    monkeypatch.setattr(settings, "FREE_AI_REVENUE_SHARE", 0.0)
    monkeypatch.setattr(ledger, "_free_budget", [0.0, -1e9])  # work it out afresh
    ledger.spent_today_inr()  # start today's total
    monkeypatch.setitem(ledger._today, "usd", 10.0)  # well past Rs 1
    for uid, allowed in ((free_id, False), (pro_id, True), (None, True)):
        token = ledger.current_user.set(uid)
        try:
            if allowed:
                ensure_budget()
            else:
                with pytest.raises(LLMUnavailable):
                    ensure_budget()
        finally:
            ledger.current_user.reset(token)
    monkeypatch.setattr(settings, "FREE_AI_DAY_FLOOR_INR", 0.0)  # both 0: no budget
    monkeypatch.setattr(ledger, "_free_budget", [0.0, -1e9])
    token = ledger.current_user.set(free_id)
    try:
        ensure_budget()
    finally:
        ledger.current_user.reset(token)


def test_room_socket_signs_in_with_the_first_message(client, auth):
    code = client.post("/api/rooms", headers=auth, json={"name": "Token-free URL"}).json()["code"]
    token = auth["Authorization"].split()[1]
    with client.websocket_connect(f"/api/rooms/ws/{code}") as ws:
        ws.send_json({"type": "auth", "token": token})
        assert ws.receive_json()["type"] == "welcome"
    with pytest.raises(WebSocketDisconnect) as bad:
        with client.websocket_connect(f"/api/rooms/ws/{code}") as ws:
            ws.send_json({"type": "auth", "token": "bogus"})
            ws.receive_json()
    assert bad.value.code == 4401


def test_a_flooding_member_is_muted(client, auth, monkeypatch):
    import time

    from app.api import rooms

    monkeypatch.setattr(rooms, "FLOOD_MESSAGES", 5)
    monkeypatch.setattr(rooms, "FLOOD_WINDOW_S", 0.5)
    code = client.post("/api/rooms", headers=auth, json={"name": "Flood"}).json()["code"]
    token = auth["Authorization"].split()[1]
    with client.websocket_connect(f"/api/rooms/ws/{code}") as ws:
        ws.send_json({"type": "auth", "token": token})
        assert ws.receive_json()["type"] == "welcome"
        for _ in range(5):  # the cap (sign-in comes before counting starts)
            ws.send_json({"type": "ping"})
        ws.send_json({"type": "chat", "text": "dropped"})  # over the cap: never reaches the room
        time.sleep(0.7)  # the window has passed
        ws.send_json({"type": "chat", "text": "kept"})
        while (msg := ws.receive_json())["type"] != "chat":
            pass
        assert msg["text"] == "kept"  # messages are handled in order: "dropped" would have come first


def test_signups_from_one_address_are_capped_per_hour(client, monkeypatch):
    from app.api import auth as auth_api

    monkeypatch.setattr(auth_api, "SIGNUPS_PER_ADDRESS_HOUR", 3)
    for i in range(3):
        _user(client, f"cap{i}@example.com")
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": "cap3@example.com", "full_name": "Hard Student",
                                                "password": "correct-horse-1", "exam_target": "jee"})
    assert r.status_code == 429


def test_razorpay_signature_needs_a_secret(monkeypatch):
    from app.services import payments

    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "")
    import hashlib
    import hmac

    forged = hmac.new(b"", b"order_1|pay_1", hashlib.sha256).hexdigest()
    assert not payments.signature_ok("order_1", "pay_1", forged)


def test_stale_rate_limit_keys_are_forgotten(monkeypatch):
    ratelimit.reset()
    ratelimit.record("old-visitor")
    ratelimit._hits["old-visitor"][0] -= ratelimit.KEEP_S + 1
    monkeypatch.setattr(ratelimit, "_swept", ratelimit.time.monotonic() - 1000)  # due for a sweep
    ratelimit._check("new-visitor", 5, 60)
    assert "old-visitor" not in ratelimit._hits and "new-visitor" in ratelimit._hits


def test_production_hides_the_api_map(monkeypatch):
    from app.main import create_app

    monkeypatch.setattr(settings, "ENV", "production")
    prod = create_app()
    assert prod.openapi_url is None and prod.docs_url is None
