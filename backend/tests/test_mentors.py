"""Mentors: a mentor account of their own, an application with qualifications and proof, admin review, then guiding
students over weeks with check-ins. Students and mentors can't do each other's part."""
from datetime import timedelta

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.mentor import Mentorship
from app.services import storage
from app.services.mentors import exam_of, mask_contacts


def _user(client, email, exam="jee", name="Test Person", role="student"):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": name, "password": "correct-horse-1", "exam_target": exam, "role": role})
    assert r.status_code == 201, r.text
    assert r.json()["user"]["role"] == role
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _admin(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_USERNAME", "admin@focs")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_HASH", hash_password("panel-password-1"))
    token = client.post("/api/admin/login", json={"username": "admin@focs", "password": "panel-password-1"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _apply(client, h, exam="jee", **extra):
    proof = extra.pop("proof", True)
    form = {"exam": exam, "credential": "JEE Advanced 2023, AIR 1,204", "institution": "IIT Delhi, B.Tech CSE",
            "qualification": "B.Tech CSE, IIT Delhi (2026)", "experience": "Taught maths to juniors for two years", "phone": "+91 98765 43210",
            "call_price_inr": "99", "headline": "Cleared JEE from a small town, happy to help", "topics": "plan,mocks,nonsense", "languages": "en,hi",
            "capacity": "2", **extra}
    files = {"proof": ("rank.png", b"\x89PNG fake", "image/png")} if proof else None
    return client.post("/api/mentors/apply", headers=h, data=form, files=files)


def test_helpers():
    assert [exam_of(t) for t in ("jee", "gate_cs", "college_cse", "cbse_12", "coding", "upsc", "other")] == \
        ["jee", "gate", "college", "cbse", "placement", "upsc", None]
    assert "98765" not in mask_contacts("Call me on +91 98765 43210 or mail a.b@gmail.com, wa.me/919876543210")
    assert mask_contacts("I got AIR 1204 in 2023 and 87 marks") == "I got AIR 1204 in 2023 and 87 marks"


def test_mentorship_from_application_to_weekly_checkins(client, monkeypatch):
    mentor = _user(client, "mentor.iitd@example.com", name="Aarav Khanna", role="mentor")
    student = _user(client, "aspirant@example.com", name="Priya Singh")
    other = _user(client, "aspirant2@example.com")
    admin = _admin(client, monkeypatch)

    # two kinds of account: a student can't apply to mentor, a mentor can't browse or ask for mentors
    assert _apply(client, student).status_code == 403
    assert client.get("/api/mentors/me", headers=student).status_code == 403
    assert client.get("/api/mentors", headers=mentor).status_code == 403
    assert client.get("/api/mentors/me", headers=mentor).json()["profile"] is None  # signed up, not applied yet
    assert _apply(client, mentor, phone="123").status_code == 422  # Focs needs a way to reach them
    assert _apply(client, mentor, proof=False).status_code == 422  # and proof

    applied = _apply(client, mentor)
    assert applied.status_code == 201 and applied.json()["status"] == "pending"
    assert applied.json()["topics"] == ["plan", "mocks"] and applied.json()["languages"] == ["en", "hi"]
    assert applied.json()["qualification"] == "B.Tech CSE, IIT Delhi (2026)" and applied.json()["call_price_inr"] == 99
    # while it waits it can be sent again with changes, keeping the proof already sent
    again = _apply(client, mentor, proof=False, headline="Went from 90 to 210 in mocks")
    assert again.status_code == 201 and again.json()["headline"] == "Went from 90 to 210 in mocks" and again.json()["has_proof"]
    listed = lambda h: {m["name"]: m for m in client.get("/api/mentors", headers=h).json()["mentors"]}  # noqa: E731  (other tests add mentors too)
    assert "Aarav Khanna" not in listed(student)  # not listed before review

    pending = client.get("/api/admin/mentors", headers=admin).json()
    row = next(p for p in pending if p["name"] == "Aarav Khanna")
    assert row["email"] == "mentor.iitd@example.com" and row["has_proof"] and row["phone"] == "+91 98765 43210"
    assert row["experience"].startswith("Taught maths")
    assert client.get(f"/api/admin/mentors/{row['id']}/proof", headers=admin).content == b"\x89PNG fake"
    assert client.get("/api/admin/mentors", headers=student).status_code == 401  # students can't review
    assert client.post(f"/api/admin/mentors/{row['id']}/review", headers=admin, json={"approve": True}).json()["status"] == "approved"
    assert client.get(f"/api/admin/mentors/{row['id']}/proof", headers=admin).status_code == 404  # proof deleted after review
    assert client.get("/api/notifications", headers=mentor).json()["items"][0]["kind"] == "mentor_review"
    assert _apply(client, mentor).status_code == 409  # approved: the profile is edited instead

    found = client.get("/api/mentors", headers=student).json()
    assert found["exam"] == "jee" and "Aarav Khanna" in listed(student)
    m = listed(student)["Aarav Khanna"]
    assert m["verified"] and m["open_spots"] == 2 and m["with_me"] is None and m["call_price_inr"] == 99 and "phone" not in m
    assert client.get("/api/mentors/me", headers=mentor).json()["profile"]["status"] == "approved"

    goal = "I'm at 60 percentile in mocks and keep running out of time in maths. Call 9876543210."
    req = client.post(f"/api/mentors/{m['id']}/request", headers=student, json={"goal": goal})
    assert req.status_code == 201 and req.json()["status"] == "requested" and "9876543210" not in req.json()["goal"]
    assert client.post(f"/api/mentors/{m['id']}/request", headers=student, json={"goal": goal}).status_code == 409
    assert client.post(f"/api/mentors/{m['id']}/request", headers=mentor, json={"goal": goal}).status_code == 403
    mid = req.json()["id"]
    bell = client.get("/api/notifications", headers=mentor).json()["items"][0]
    assert bell["kind"] == "mentor_request" and bell["link"] == f"/mentor/seekers/{mid}"
    assert client.post(f"/api/mentors/mentorships/{mid}/messages", headers=student, json={"body": "hi"}).status_code == 409  # not accepted yet

    inbox = client.get("/api/mentors/mentorships", headers=mentor).json()
    assert inbox["requests"] == 1 and inbox["as_mentor"][0]["with"] == "Priya S."
    assert client.post(f"/api/mentors/mentorships/{mid}/accept", headers=student).status_code == 409  # the mentor decides
    assert client.post(f"/api/mentors/mentorships/{mid}/accept", headers=mentor).json()["status"] == "active"
    assert client.get("/api/notifications", headers=student).json()["items"][0]["kind"] == "mentor_accepted"
    assert client.get(f"/api/mentors/mentorships/{mid}", headers=other).status_code == 404

    mine = client.get("/api/mentors/mentorships", headers=student).json()
    assert mine["checkins_due"] == 1 and mine["as_student"][0]["with"] == "Aarav Khanna"
    sent = client.post(f"/api/mentors/mentorships/{mid}/messages", headers=student, json={"body": "This week was rough.", "checkin": True})
    assert sent.status_code == 201 and sent.json()["kind"] == "checkin" and "week_minutes" in sent.json()["snapshot"]
    assert client.get("/api/mentors/mentorships", headers=student).json()["checkins_due"] == 0
    assert client.post(f"/api/mentors/mentorships/{mid}/messages", headers=mentor, json={"body": "", "checkin": True}).status_code == 422
    client.post(f"/api/mentors/mentorships/{mid}/messages", headers=mentor, json={"body": "Do 2 timed maths sets a day. My insta: instagram.com/aarav"})

    assert client.get("/api/mentors/mentorships", headers=student).json()["unread"] == 1
    convo = client.get(f"/api/mentors/mentorships/{mid}", headers=student).json()
    assert [x["kind"] for x in convo["messages"]] == ["checkin", "text"] and "instagram.com" not in convo["messages"][1]["body"]
    assert convo["progress"] is None  # the student doesn't see a progress panel of themselves
    assert client.get("/api/mentors/mentorships", headers=student).json()["unread"] == 0
    assert client.get(f"/api/mentors/mentorships/{mid}", headers=mentor).json()["progress"]["exam"] == "JEE"
    client.patch(f"/api/mentors/mentorships/{mid}", headers=student, json={"share_progress": False})
    assert client.get(f"/api/mentors/mentorships/{mid}", headers=mentor).json()["progress"] is None

    with SessionLocal() as db:  # a week later the next check-in is due
        row = db.get(Mentorship, mid)
        row.last_checkin_at -= timedelta(days=8)
        db.commit()
    assert client.get("/api/mentors/mentorships", headers=student).json()["checkins_due"] == 1

    # capacity 2, one taken; reports pause the mentor and reach the admin
    assert client.post(f"/api/mentors/{m['id']}/request", headers=other, json={"goal": goal}).status_code == 201
    assert client.post(f"/api/mentors/mentorships/{mid}/report", headers=student, json={"reason": "Asked for my number"}).status_code == 204
    assert listed(student)["Aarav Khanna"]["accepting"] is False
    reported = client.get("/api/admin/mentors/reports", headers=admin).json()
    assert reported[0]["id"] == mid and reported[0]["reports"][0]["reason"] == "Asked for my number" and reported[0]["messages"]

    assert client.post(f"/api/mentors/mentorships/{mid}/end", headers=student).json()["status"] == "ended"
    assert client.post(f"/api/mentors/mentorships/{mid}/messages", headers=student, json={"body": "hello?"}).status_code == 409


def test_rejected_mentor_can_apply_again(client, monkeypatch):
    h = _user(client, "upsc.mentor@example.com", role="mentor")
    admin = _admin(client, monkeypatch)
    pid = _apply(client, h, exam="upsc", credential="UPSC CSE 2024, interview").json()["id"]
    client.post(f"/api/admin/mentors/{pid}/review", headers=admin, json={"approve": False, "note": "The proof was unreadable."})
    me = client.get("/api/mentors/me", headers=h).json()["profile"]
    assert me["status"] == "rejected" and me["review_note"] == "The proof was unreadable." and not me["has_proof"]
    assert "unreadable" in client.get("/api/notifications", headers=h).json()["items"][0]["text"]
    assert _apply(client, h, exam="upsc", proof=False).status_code == 422  # the old proof was deleted: send new proof
    again = _apply(client, h, exam="upsc", credential="UPSC CSE 2024, AIR 412")
    assert again.status_code == 201 and again.json()["status"] == "pending"
    edited = client.patch("/api/mentors/me", headers=h, json={"capacity": 8, "accepting": False, "call_price_inr": 0}).json()
    assert edited["capacity"] == 8 and edited["call_price_inr"] == 0
    assert client.patch("/api/mentors/me", headers=h, json={"call_price_inr": 99999}).status_code == 422
    assert storage is not None
