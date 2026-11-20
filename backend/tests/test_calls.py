"""Mentor calls and payments: weekly hours, booking (Pro-included or paid), joining, notes, ratings, refunds, Pro months."""
import hashlib
import hmac
import json
from datetime import timedelta

from app.api import calls as calls_api
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models._util import utcnow
from app.models.mentor import MentorCall
from app.models.payment import Payment
from app.models.user import User
from app.services import payments, pricing


def _user(client, email, exam="jee", name="Test Person", role="student"):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": name, "password": "correct-horse-1", "exam_target": exam, "role": role})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _admin(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_USERNAME", "admin@focs")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_HASH", hash_password("panel-password-1"))
    return {"Authorization": "Bearer " + client.post("/api/admin/login", json={"username": "admin@focs", "password": "panel-password-1"}).json()["token"]}


def _mentorship(client, monkeypatch, tag, price=49):
    mentor = _user(client, f"callmentor{tag}@example.com", name="Kavya Iyer", role="mentor")
    student = _user(client, f"callstudent{tag}@example.com", name="Rohan Das")
    admin = _admin(client, monkeypatch)
    pid = client.post("/api/mentors/apply", headers=mentor, data={"exam": "jee", "credential": "JEE Advanced 2022, AIR 800", "institution": "IIT Bombay",
                                                                  "qualification": "B.Tech EE, IIT Bombay", "phone": "9876543210", "call_price_inr": str(price)},
                      files={"proof": ("p.png", b"png", "image/png")}).json()["id"]
    client.post(f"/api/admin/mentors/{pid}/review", headers=admin, json={"approve": True})
    every_evening = [{"day": d, "time": "19:00"} for d in range(7)] + [{"day": d, "time": "19:30"} for d in range(7)]
    assert len(client.put("/api/mentors/me/slots", headers=mentor, json={"slots": every_evening}).json()["slots"]) == 14
    assert client.put("/api/mentors/me/slots", headers=mentor, json={"slots": [{"day": 1, "time": "19:15"}]}).status_code == 422
    mid = client.post(f"/api/mentors/{pid}/request", headers=student, json={"goal": "I need a weekly plan for JEE and help with mocks."}).json()["id"]
    client.post(f"/api/mentors/mentorships/{mid}/accept", headers=mentor)
    return mentor, student, admin, mid


def _pay(client, h, checkout):
    assert checkout["provider"] == "dev"
    return client.post(f"/api/billing/payments/{checkout['payment_id']}/confirm", headers=h, json={})


def test_free_student_pays_per_call_and_the_call_runs(client, monkeypatch):
    mentor, student, admin, mid = _mentorship(client, monkeypatch, 1)
    info = client.get(f"/api/mentors/mentorships/{mid}/calls", headers=student).json()
    assert info["price_inr"] == settings.MENTOR_CALL_PRICE_INR and info["payments"] == "dev" and not info["pro"]
    assert info["slots"] and info["mentor_share_inr"] == 49 - round(49 * settings.MENTOR_COMMISSION_PCT / 100)
    assert client.get("/api/mentors", headers=student).json()["mentors"][0]["has_hours"]
    slot = info["slots"][0]["starts_at"]

    booked = client.post(f"/api/mentors/mentorships/{mid}/calls", headers=student, json={"starts_at": slot, "agenda": "Maths speed. Call 9876543210"}).json()
    call, checkout = booked["call"], booked["checkout"]
    assert call["status"] == "held" and call["price_inr"] == 49 and checkout["amount_paise"] == 4900 and "9876543210" not in call["agenda"]
    assert client.post(f"/api/mentors/mentorships/{mid}/calls", headers=student, json={"starts_at": slot}).status_code == 409  # held
    assert client.post(f"/api/mentors/mentorships/{mid}/calls", headers=mentor, json={"starts_at": slot}).status_code == 403
    assert _pay(client, student, checkout).json()["status"] == "paid"
    assert _pay(client, student, checkout).json()["status"] == "paid"  # twice is fine
    mine = client.get("/api/mentors/calls", headers=student).json()
    assert [c["status"] for c in mine["upcoming"]] == ["booked"] and mine["upcoming"][0]["join_url"] is None  # not open yet
    assert slot not in [s["starts_at"] for s in client.get(f"/api/mentors/mentorships/{mid}/calls", headers=student).json()["slots"]]

    # five minutes into the call: the room opens; the mentor sees the agenda with the student's progress
    with SessionLocal() as db:
        start = db.get(MentorCall, call["id"]).starts_at
    monkeypatch.setattr(calls_api, "utcnow", lambda: start + timedelta(minutes=5))
    live = client.get("/api/mentors/calls", headers=mentor).json()["upcoming"][0]
    assert live["can_join"] and live["join_url"].startswith(settings.CALL_ROOM_BASE) and live["snapshot"]["exam"] == "JEE"
    assert client.post(f"/api/mentors/calls/{call['id']}/rate", headers=student, json={"rating": 5}).status_code == 409  # not over
    note = {"notes": "Good call. Main issue is speed in calculus.", "actions": ["Two timed calculus sets a day", "One full mock on Sunday", " "]}
    assert client.post(f"/api/mentors/calls/{call['id']}/notes", headers=student, json=note).status_code == 403
    done = client.post(f"/api/mentors/calls/{call['id']}/notes", headers=mentor, json=note).json()
    assert done["status"] == "done" and [a["text"] for a in done["actions"]] == note["actions"][:2]

    monkeypatch.setattr(calls_api, "utcnow", lambda: start + timedelta(hours=2))
    todo = client.get("/api/mentors/calls", headers=student).json()
    assert [a["text"] for a in todo["actions"]] == note["actions"][:2] and todo["to_rate"][0]["id"] == call["id"]
    assert client.put(f"/api/mentors/calls/{call['id']}/actions/0", headers=student, json={"done": True}).json()["actions"][0]["done"]
    assert client.post(f"/api/mentors/calls/{call['id']}/rate", headers=student, json={"rating": 4, "review": "Clear plan."}).json()["rating"] == 4
    card = client.get("/api/mentors", headers=student).json()["mentors"][0]
    assert card["calls_done"] == 1 and card["rating"] == 4.0

    money = client.get("/api/admin/mentors/calls", headers=admin).json()
    kavya = next(r for r in money["by_mentor"] if r["mentor"] == "Kavya Iyer")
    assert money["calls_revenue_inr"] >= 49 and kavya["calls"] == 1 and kavya["owed_inr"] == info["mentor_share_inr"]


def test_calls_are_paid_even_on_pro_and_refunds(client, monkeypatch):
    mentor, student, admin, mid = _mentorship(client, monkeypatch, 2)
    client.post("/api/billing/dev-upgrade", headers=student, json={"plan": "pro"})
    slots = client.get(f"/api/mentors/mentorships/{mid}/calls", headers=student).json()["slots"]
    paid = client.post(f"/api/mentors/mentorships/{mid}/calls", headers=student, json={"starts_at": slots[0]["starts_at"]}).json()
    assert paid["checkout"]["amount_inr"] == 49 and paid["call"]["paid_via"] == "paid"  # Pro's mentoring is the group session
    _pay(client, student, paid["checkout"])

    # the mentor cancels: a refund is owed and shows for the admin
    assert client.post(f"/api/mentors/calls/{paid['call']['id']}/cancel", headers=mentor).json()["status"] == "cancelled"
    owed = client.get("/api/admin/mentors/calls", headers=admin).json()["refunds_due"]
    assert any(o["id"] == paid["checkout"]["payment_id"] for o in owed)
    assert client.post(f"/api/admin/mentors/payments/{paid['checkout']['payment_id']}/refunded", headers=admin).status_code == 204
    assert slots[0]["starts_at"] in [s["starts_at"] for s in client.get(f"/api/mentors/mentorships/{mid}/calls", headers=student).json()["slots"]]


def test_each_mentor_sets_their_price_and_free_calls_book_at_once(client, monkeypatch):
    mentor, student, _, mid = _mentorship(client, monkeypatch, 4, price=199)
    info = client.get(f"/api/mentors/mentorships/{mid}/calls", headers=student).json()
    assert info["price_inr"] == 199 and info["mentor_share_inr"] == 199 - round(199 * settings.MENTOR_COMMISSION_PCT / 100)
    paid = client.post(f"/api/mentors/mentorships/{mid}/calls", headers=student, json={"starts_at": info["slots"][0]["starts_at"]}).json()
    assert paid["checkout"]["amount_inr"] == 199 and paid["call"]["status"] == "held"

    assert client.patch("/api/mentors/me", headers=mentor, json={"call_price_inr": 0}).json()["call_price_inr"] == 0
    free = client.post(f"/api/mentors/mentorships/{mid}/calls", headers=student, json={"starts_at": info["slots"][1]["starts_at"]}).json()
    assert free["checkout"] is None and free["call"]["status"] == "booked" and free["call"]["paid_via"] == "free"
    assert client.put("/api/mentors/me/slots", headers=student, json={"slots": []}).status_code == 403  # students don't set hours


def test_unpaid_hold_lapses(client, monkeypatch):
    _, student, _, mid = _mentorship(client, monkeypatch, 3)
    slot = client.get(f"/api/mentors/mentorships/{mid}/calls", headers=student).json()["slots"][0]["starts_at"]
    held = client.post(f"/api/mentors/mentorships/{mid}/calls", headers=student, json={"starts_at": slot}).json()
    with SessionLocal() as db:
        db.get(MentorCall, held["call"]["id"]).held_until = utcnow() - timedelta(minutes=1)
        db.commit()
    info = client.get(f"/api/mentors/mentorships/{mid}/calls", headers=student).json()
    assert slot in [s["starts_at"] for s in info["slots"]] and all(c["id"] != held["call"]["id"] for c in info["calls"])
    with SessionLocal() as db:
        assert db.get(Payment, held["checkout"]["payment_id"]).status == "failed"


def test_buying_pro_and_razorpay_checks(client, monkeypatch):
    h = _user(client, "buyer@example.com")
    checkout = client.post("/api/billing/pro", headers=h).json()
    assert checkout["amount_inr"] == pricing.price("exam", "month")[0]
    user = _pay(client, h, checkout).json()["user"]
    assert user["plan"] == "pro" and user["pro_until"]
    with SessionLocal() as db:  # the month runs out: back to Starter
        u = db.query(User).filter_by(email="buyer@example.com").one()
        u.pro_until = utcnow() - timedelta(minutes=1)
        db.commit()
    assert client.get("/api/auth/me", headers=h).json()["plan"] == "free"

    # the semester pass: one payment, its own price and length, added to any Pro time left
    passes = {p["id"]: p for p in client.get("/api/billing/plans").json()["passes"]}
    semester = pricing.price("exam", "semester")[0]
    assert passes["semester"]["price_inr"] == semester and passes["semester"]["days"] == settings.PRO_SEMESTER_DAYS
    assert passes["semester"]["label"] == "6 months" and 0 < passes["semester"]["save_pct"] < passes["year"]["save_pct"]
    checkout = client.post("/api/billing/pro?plan=semester", headers=h).json()
    assert checkout["amount_inr"] == semester
    _pay(client, h, checkout)
    with SessionLocal() as db:
        u = db.query(User).filter_by(email="buyer@example.com").one()
        assert u.plan == "pro" and timedelta(days=settings.PRO_SEMESTER_DAYS - 1) < u.pro_until - utcnow() <= timedelta(days=settings.PRO_SEMESTER_DAYS)
        u.pro_until = utcnow() - timedelta(minutes=1)
        db.commit()
    monkeypatch.setitem(settings.PRO_PRICES_INR, "exam", {**settings.PRO_PRICES_INR["exam"], "semester": 0})  # not on sale
    assert client.post("/api/billing/pro?plan=semester", headers=h).status_code == 404
    assert [p["id"] for p in client.get("/api/billing/plans").json()["passes"]] == ["month", "year"]
    assert client.get("/api/auth/me", headers=h).json()["plan"] == "free"

    # a Razorpay payment counts only with a valid signature, or a signed webhook
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "rzp-secret")
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "hook-secret")
    with SessionLocal() as db:
        uid = db.query(User).filter_by(email="buyer@example.com").one().id
        p = Payment(user_id=uid, purpose="pro_month", amount_inr=149, provider="razorpay", order_id="order_ABC")
        db.add(p)
        db.commit()
        pid = p.id
    bad = client.post(f"/api/billing/payments/{pid}/confirm", headers=h, json={"razorpay_order_id": "order_ABC", "razorpay_payment_id": "pay_1", "razorpay_signature": "nope"})
    assert bad.status_code == 400
    sig = hmac.new(b"rzp-secret", b"order_ABC|pay_1", hashlib.sha256).hexdigest()
    assert payments.signature_ok("order_ABC", "pay_1", sig)
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_1", "order_id": "order_ABC"}}}}).encode()
    assert client.post("/api/billing/webhook", content=body, headers={"X-Razorpay-Signature": "forged"}).status_code == 400
    signed = hmac.new(b"hook-secret", body, hashlib.sha256).hexdigest()
    assert client.post("/api/billing/webhook", content=body, headers={"X-Razorpay-Signature": signed}).status_code == 200
    assert client.get("/api/auth/me", headers=h).json()["plan"] == "pro"
    assert client.get("/api/billing/me", headers=h).json()["pro"] is True


def test_a_mentor_closing_their_account_refunds_and_tells_students(client, monkeypatch):
    mentor, student, admin, mid = _mentorship(client, monkeypatch, "leaving", price=99)
    slot = client.get(f"/api/mentors/mentorships/{mid}/calls", headers=student).json()["slots"][0]["starts_at"]
    call = client.post(f"/api/mentors/mentorships/{mid}/calls", headers=student, json={"starts_at": slot, "agenda": "Mock review"}).json()
    assert _pay(client, student, call["checkout"]).json()["status"] == "paid"
    start = (utcnow() + timedelta(days=3)).replace(minute=0, second=0, microsecond=0)
    sid = client.post("/api/mentors/me/sessions", headers=mentor, json={"starts_at": start.isoformat() + "Z", "topic": "Electrostatics", "price_inr": 149}).json()[0]["id"]
    seat = client.post(f"/api/mentors/sessions/{sid}/seat", headers=student, json={}).json()
    assert _pay(client, student, seat["checkout"]).json()["status"] == "paid"

    assert client.post("/api/auth/delete-account", headers=mentor, json={"password": "correct-horse-1", "confirm": "DELETE"}).status_code == 204
    with SessionLocal() as db:
        assert db.get(Payment, call["checkout"]["payment_id"]).status == "refund_due"
        assert db.get(Payment, seat["checkout"]["payment_id"]).status == "refund_due"
        assert db.get(MentorCall, call["call"]["id"]) is None
    told = [n for n in client.get("/api/notifications", headers=student).json()["items"] if n["kind"] == "session_cancelled"]
    assert len(told) == 2 and any("upcoming call" in n["text"] for n in told) and any("Electrostatics" in n["text"] for n in told)
    owed = {r["id"] for r in client.get("/api/admin/mentors/calls", headers=admin).json()["refunds_due"]}
    assert {call["checkout"]["payment_id"], seat["checkout"]["payment_id"]} <= owed
    assert client.get("/api/mentors/mentorships", headers=student).json()["as_student"] == []
