"""Master sessions: a mentor posts them at their own price (or free), students register (paying, free, or with the one
a week Pro includes), and what mentors earn."""
from datetime import timedelta

from app.api import group_sessions as group_api
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models._util import utcnow
from app.models.mentor import GroupSession, MentorCall, Mentorship
from app.models.payment import Payment
from app.models.user import User
from app.services.mentors import mentor_share


def _user(client, email, exam="jee", name="Test Person", role="student"):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": name, "password": "correct-horse-1", "exam_target": exam, "role": role})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _admin(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_USERNAME", "admin@focs")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_HASH", hash_password("panel-password-1"))
    return {"Authorization": "Bearer " + client.post("/api/admin/login", json={"username": "admin@focs", "password": "panel-password-1"}).json()["token"]}


def _mentor(client, monkeypatch, email, name):
    h, admin = _user(client, email, name=name, role="mentor"), _admin(client, monkeypatch)
    pid = client.post("/api/mentors/apply", headers=h, data={"exam": "jee", "credential": "JEE Advanced 2021, AIR 950", "institution": "IIT Kanpur",
                                                             "qualification": "B.Tech ME, IIT Kanpur", "phone": "9876543210", "call_price_inr": "49"},
                      files={"proof": ("p.png", b"png", "image/png")}).json()["id"]
    client.post(f"/api/admin/mentors/{pid}/review", headers=admin, json={"approve": True})
    return h, admin, pid


def _pay(client, h, checkout):
    assert checkout["provider"] == "dev"
    return client.post(f"/api/billing/payments/{checkout['payment_id']}/confirm", headers=h, json={})


def _row(client, h, sid):
    return next(s for s in client.get("/api/mentors/sessions", headers=h).json()["sessions"] if s["id"] == sid)


def test_master_sessions_free_paid_and_pro(client, monkeypatch):
    mentor, admin, pid = _mentor(client, monkeypatch, "group.mentor@example.com", "Ishaan Gupta")
    pro, free = _user(client, "group.pro@example.com", name="Sana Khan"), _user(client, "group.free@example.com", name="Dev Patel")
    client.post("/api/billing/dev-upgrade", headers=pro, json={"plan": "pro"})
    assert client.post("/api/mentors/me/sessions", headers=pro, json={"starts_at": (utcnow() + timedelta(days=1)).isoformat()}).status_code == 403
    assert client.get("/api/mentors/sessions", headers=mentor).status_code == 403  # mentors host, they don't register

    # next week's Wednesday morning: "two days from now" on a Friday evening put the session 5 h later in a new week
    today = utcnow().replace(hour=6, minute=0, second=0, microsecond=0)
    start = today + timedelta(days=7 - today.weekday() + 2)
    made = client.post("/api/mentors/me/sessions", headers=mentor, json={
        "starts_at": start.isoformat() + "Z", "topic": "Rotational motion masterclass", "description": "Torque, angular momentum, rolling.",
        "minutes": 90, "seats": 3, "price_inr": 199, "repeat_weeks": 2}).json()
    assert len(made) == 2 and made[0]["price_inr"] == 199 and made[0]["seats"] == 3 and made[0]["minutes"] == 90
    assert made[0]["description"] == "Torque, angular momentum, rolling."
    assert client.post("/api/mentors/me/sessions", headers=mentor, json={"starts_at": (utcnow() + timedelta(minutes=10)).isoformat()}).status_code == 422
    assert client.post("/api/mentors/me/sessions", headers=mentor, json={"starts_at": start.isoformat() + "Z", "price_inr": 99999}).status_code == 422
    paid, next_week = made[0]["id"], made[1]["id"]
    gratis = client.post("/api/mentors/me/sessions", headers=mentor, json={"starts_at": (start + timedelta(hours=3)).isoformat() + "Z",
                                                                          "topic": "Open doubts", "price_inr": 0}).json()[0]["id"]

    # at launch Pro includes no paid seats (Focs would pay the mentor out of the Pro price)
    monkeypatch.setattr(settings, "PRO_GROUP_SESSIONS_PER_WEEK", 0)
    assert not _row(client, pro, paid)["pro_free"]
    assert client.get("/api/mentors/sessions", headers=pro).json()["per_week"] == 0
    monkeypatch.setattr(settings, "PRO_GROUP_SESSIONS_PER_WEEK", 1)
    row = _row(client, pro, paid)
    assert row["mentor"] == "Ishaan Gupta" and row["price_inr"] == 199 and row["pro_free"] and not row["seated"] and row["join_url"] is None
    assert not _row(client, free, paid)["pro_free"]

    # a free session: anyone registers at once
    r = client.post(f"/api/mentors/sessions/{gratis}/seat", headers=free, json={"doubt": "Rolling without slipping? 9876543210"}).json()
    assert r["seated"] and r["paid_via"] == "free" and r["checkout"] is None and "9876543210" not in r["my_doubt"]
    assert client.post(f"/api/mentors/sessions/{gratis}/seat", headers=free, json={}).status_code == 409

    # a paid session: held while the student pays, then booked
    r = client.post(f"/api/mentors/sessions/{paid}/seat", headers=free, json={"doubt": "Why is torque r x F?"}).json()
    assert not r["seated"] and r["seat_status"] == "held" and r["checkout"]["amount_inr"] == 199
    assert _row(client, free, paid)["seat_status"] == "held"
    assert _pay(client, free, r["checkout"]).json()["status"] == "paid"
    assert _row(client, free, paid)["seated"]

    # Pro: one included a week (Focs pays the mentor's share); the next one that week is paid
    r = client.post(f"/api/mentors/sessions/{paid}/seat", headers=pro, json={"doubt": "Angular momentum?"}).json()
    assert r["seated"] and r["paid_via"] == "pro" and r["checkout"] is None
    same_week = client.post("/api/mentors/me/sessions", headers=mentor, json={"starts_at": (start + timedelta(hours=5)).isoformat() + "Z",
                                                                             "price_inr": 99, "seats": 1}).json()[0]["id"]
    r = client.post(f"/api/mentors/sessions/{same_week}/seat", headers=pro, json={}).json()
    assert r["paid_via"] == "paid" and r["checkout"]["amount_inr"] == 99
    assert client.post(f"/api/mentors/sessions/{same_week}/seat", headers=free, json={}).status_code == 409  # one seat, held by Sana
    assert client.post(f"/api/mentors/sessions/{next_week}/seat", headers=pro, json={}).json()["paid_via"] == "pro"  # a new week

    queue = next(s for s in client.get("/api/mentors/me/sessions", headers=mentor).json()["sessions"] if s["id"] == paid)
    assert queue["registered"] == 2 and queue["earning_inr"] == 2 * mentor_share(199)
    assert {q["student"] for q in queue["queue"]} == {"Dev P.", "Sana K."}
    first_seat = queue["queue"][0]["id"]
    assert client.put(f"/api/mentors/sessions/{paid}/queue/{first_seat}", headers=mentor, json={"answered": True}).json()["answered"]
    assert client.post(f"/api/mentors/sessions/{paid}/held", headers=mentor, json={}).status_code == 409  # not started yet

    # during the session the room opens for those registered; afterwards the mentor marks it held
    monkeypatch.setattr(group_api, "utcnow", lambda: start + timedelta(minutes=5))
    live = _row(client, pro, paid)
    assert live["can_join"] and live["join_url"].startswith(settings.CALL_ROOM_BASE)
    assert client.post(f"/api/mentors/sessions/{paid}/held", headers=mentor, json={"notes": "Covered torque and angular momentum."}).json()["status"] == "done"
    monkeypatch.undo()

    money = client.get("/api/mentors/me/earnings", headers=mentor).json()
    owed = 2 * mentor_share(199)
    assert money["total"]["sessions"] == 1 and money["total"]["owed_inr"] == owed
    admin = _admin(client, monkeypatch)
    out = client.post(f"/api/admin/mentors/{pid}/payouts", headers=admin, json={"amount_inr": 100, "note": "UPI 17 Oct"}).json()
    assert out["paid_out_inr"] == 100 and out["owed_inr"] == owed - 100
    assert client.get("/api/mentors/me/earnings", headers=mentor).json()["payouts"][0]["note"] == "UPI 17 Oct"


def test_cancelling_and_leaving_refund_paid_seats(client, monkeypatch):
    mentor, admin, _ = _mentor(client, monkeypatch, "refund.mentor@example.com", "Meera Rao")
    student = _user(client, "refund.student@example.com", name="Kabir Jain")
    start = (utcnow() + timedelta(days=3)).replace(minute=0, second=0, microsecond=0)
    one, two = (client.post("/api/mentors/me/sessions", headers=mentor, json={"starts_at": (start + timedelta(hours=h)).isoformat() + "Z", "price_inr": 149}).json()[0]["id"]
                for h in (0, 2))
    a = client.post(f"/api/mentors/sessions/{one}/seat", headers=student, json={}).json()["checkout"]
    b = client.post(f"/api/mentors/sessions/{two}/seat", headers=student, json={}).json()["checkout"]
    _pay(client, student, a), _pay(client, student, b)

    assert client.delete(f"/api/mentors/sessions/{one}/seat", headers=student).status_code == 204  # days ahead: refunded
    assert client.post(f"/api/mentors/sessions/{two}/cancel", headers=mentor).json()["status"] == "cancelled"
    with SessionLocal() as db:
        assert db.get(Payment, a["payment_id"]).status == "refund_due" and db.get(Payment, b["payment_id"]).status == "refund_due"
    assert client.get("/api/notifications", headers=student).json()["items"][0]["kind"] == "session_cancelled"
    owed = {o["id"] for o in client.get("/api/admin/mentors/calls", headers=admin).json()["refunds_due"]}
    assert {a["payment_id"], b["payment_id"]} <= owed


def test_paid_call_earnings_split(client, monkeypatch):
    mentor, admin, pid = _mentor(client, monkeypatch, "split.mentor@example.com", "Neha Joshi")
    _user(client, "split.student@example.com")
    with SessionLocal() as db:  # a paid call that happened, an older one Pro included (pays nothing), a session nobody came to
        sid = db.query(User).filter_by(email="split.student@example.com").one().id
        m = Mentorship(mentor_id=pid, student_id=sid, status="active", goal="x", reports=[])
        db.add(m)
        db.flush()
        for via, price in (("paid", 49), ("pro", 0)):
            db.add(MentorCall(mentorship_id=m.id, mentor_id=pid, student_id=sid, starts_at=utcnow() - timedelta(hours=2), status="done",
                              paid_via=via, price_inr=price, room="r"))
        db.add(GroupSession(mentor_id=pid, starts_at=utcnow() - timedelta(hours=1), room="g", status="done", pay_inr=150))
        db.commit()
    month = client.get("/api/mentors/me/earnings", headers=mentor).json()["month"]
    cut = round(49 * settings.MENTOR_COMMISSION_PCT / 100)
    assert month["calls"] == 1 and month["calls_inr"] == 49 - cut and month["focs_inr"] == cut and month["sessions"] == 0
    summary = client.get("/api/admin/mentors/calls", headers=admin).json()
    row = next(r for r in summary["by_mentor"] if r["mentor"] == "Neha Joshi")
    assert row["owed_inr"] == 49 - cut and summary["commission_pct"] == settings.MENTOR_COMMISSION_PCT
