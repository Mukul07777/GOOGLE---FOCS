"""AI allowance (usage windows) and full mock tests."""
import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models._util import utcnow
from app.models.mock import BankQuestion, MockTest
from app.models.user import User
from app.services import mock, question_bank, usage
from app.services.mock_patterns import SUBJECTS, SYLLABUS
from tests.conftest import board_png


def _register(client, email: str) -> dict:
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Test Student", "password": "correct-horse-1",
                                                 "exam_target": "jee"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _user(db, email: str) -> User:
    return db.scalar(select(User).where(User.email == email))


# ---------------------------------------------------------------- usage
def test_usage_status_window_and_reset(client):
    h = _register(client, "usage1@example.com")
    r = client.get("/api/usage", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["plan"] == "free" and data["window"]["used"] == 0 and data["window"]["limit"] == settings.USAGE_FREE_WINDOW
    assert data["mocks"]["limit"] == settings.MOCKS_FREE_PER_WEEK
    assert {c["action"] for c in data["costs"]} >= {"doubt", "practice_set"}
    assert "board_note" not in {c["action"] for c in data["costs"]}  # lecture notes are counted in lecture hours
    assert data["lecture"]["limit"] == round(60 * settings.LECTURE_HOURS_FREE) and data["lecture"]["used"] == 0

    with SessionLocal() as db:
        u = _user(db, "usage1@example.com")
        usage.charge(db, u, "doubt")
        usage.charge(db, u, "practice_set")
        usage.charge(db, u, "board_note", source="offline")  # offline answers are free
    data = client.get("/api/usage", headers=h).json()
    assert data["window"]["used"] == 7 and data["week"]["used"] == 7 and data["window"]["resets_at"]

    with SessionLocal() as db:  # the window ends 5 hours after it opened
        u = _user(db, "usage1@example.com")
        u.usage_window_start = utcnow() - timedelta(hours=settings.USAGE_WINDOW_HOURS, minutes=1)
        db.commit()
    data = client.get("/api/usage", headers=h).json()
    assert data["window"]["used"] == 0 and data["week"]["used"] == 7


def test_usage_limit_blocks_doubts_but_not_the_live_lecture(client, monkeypatch):
    h = _register(client, "usage2@example.com")
    with SessionLocal() as db:
        u = _user(db, "usage2@example.com")
        u.usage_window_start, u.usage_window_used = utcnow(), settings.USAGE_FREE_WINDOW
        db.commit()

    ask = {"question": "What is torque?", "mode": "explain", "history": []}
    r = client.post("/api/companion/ask", headers=h, json=ask)
    assert r.status_code == 402
    # no payments on this server: the message doesn't send the student to a Pro they can't buy
    assert "resets in" in r.json()["detail"] and "Pro" not in r.json()["detail"]
    assert r.headers.get("x-usage-resets-at")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_x")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "secret")
    assert "Pro" in client.post("/api/companion/ask", headers=h, json=ask).json()["detail"]

    # the lecture has its own allowance, in hours: its boards still get full notes
    s = client.post("/api/sessions", headers=h, json={"title": "Limits"}).json()
    img = board_png(["Newton's second law", "F = m a", "Momentum p = m v"])
    r = client.post(f"/api/capture/{s['id']}/frame", headers=h, files={"frame": ("f.png", img, "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "created" and r.json()["basic_mode"] is False

    # and past the day's lecture hours it keeps going: boards still become (basic) notes
    with SessionLocal() as db:
        u = _user(db, "usage2@example.com")
        u.lecture_day_start, u.lecture_day_seconds = utcnow(), usage.lecture_limit_s("free")
        db.commit()
    s = client.post("/api/sessions", headers=h, json={"title": "Limits"}).json()
    img = board_png(["Ohm's law", "V = I R", "Power P = V I"])
    r = client.post(f"/api/capture/{s['id']}/frame", headers=h, files={"frame": ("f.png", img, "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "created" and r.json()["basic_mode"] is True

    # ending still writes a (basic) revision sheet
    r = client.post(f"/api/sessions/{s['id']}/end", headers=h)
    assert r.status_code == 200 and r.json()["summary_md"]

    # Pro has 10x the room
    with SessionLocal() as db:
        u = _user(db, "usage2@example.com")
        u.plan = "pro"
        db.commit()
    r = client.post("/api/companion/ask", headers=h, json={"question": "What is torque?", "mode": "explain", "history": []})
    assert r.status_code == 200


# ---------------------------------------------------------------- mock tests
@pytest.fixture(scope="module")
def bank(tmp_path_factory):
    """A small synthetic bank: enough for two 30+30+30 papers."""
    items = []
    for subject in SUBJECTS:
        chapters = list(SYLLABUS[subject])
        for i in range(45):
            items.append({"subject": subject, "chapter": chapters[i % len(chapters)], "qtype": "mcq",
                          "question": f"{subject} MCQ number {i}: which option is the right one here?",
                          "options": ["first", "second", "third", "fourth"], "answer": i % 4, "solution": "Because."})
        for i in range(22):
            items.append({"subject": subject, "chapter": chapters[i % len(chapters)], "qtype": "numerical",
                          "question": f"{subject} numerical number {i}: what integer is the answer?",
                          "answer": i + 1, "solution": f"It is {i + 1}."})
    path = tmp_path_factory.mktemp("bank") / "bank.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    with SessionLocal() as db:
        added = question_bank.load_seed(db, path)
        assert question_bank.load_seed(db, path) == 0  # idempotent
    return added


def test_mock_full_flow_grading_and_quota(client, bank):
    h = _register(client, "mock1@example.com")
    meta = client.get("/api/mock/meta", headers=h).json()
    assert {p["id"] for p in meta["patterns"]} == {"jee_main_30", "jee_main_25", "jee_advanced"}
    p30 = next(p for p in meta["patterns"] if p["id"] == "jee_main_30")
    assert p30["total_questions"] == 90 and p30["max_score"] == 300 and p30["duration_min"] == 180

    t = client.post("/api/mock", headers=h, json={"pattern": "jee_main_30"}).json()
    assert t["status"] == "ready"
    assert client.post("/api/mock", headers=h, json={"pattern": "jee_main_30"}).json()["id"] == t["id"]  # reused
    assert client.get(f"/api/mock/{t['id']}", headers=h).json()["questions"] == []  # nothing visible before the start

    started = client.post(f"/api/mock/{t['id']}/start", headers=h).json()
    qs = started["questions"]
    assert started["status"] == "in_progress" and len(qs) == 90 and 0 < started["remaining_sec"] <= 180 * 60
    assert all("answer" not in q and "solution" not in q for q in qs)
    assert [q["subject"] for q in qs[:30]] == ["Physics"] * 30 and qs[20]["section"] == "B" and qs[30]["subject"] == "Chemistry"
    assert all(q["qtype"] == "numerical" for q in qs[20:30])

    with SessionLocal() as db:
        paper = db.get(MockTest, t["id"])  # the key as this paper shows it (its options are shuffled)
        key = {q.id: mock.shown_answer(paper, q) for q in db.scalars(select(BankQuestion).where(BankQuestion.id.in_([q["id"] for q in qs])))}
    responses = {}
    for q in qs[:3]:  # 3 correct MCQs
        responses[str(q["id"])] = {"a": key[q["id"]], "v": True, "t": 60}
    wrong = str((int(key[qs[3]["id"]]) + 1) % 4)
    responses[str(qs[3]["id"])] = {"a": wrong, "m": True, "v": True, "t": 300}  # answered & marked: still evaluated
    for q in qs[20:26]:  # 6 numerical answers: only the first 5 count
        responses[str(q["id"])] = {"a": key[q["id"]], "v": True, "t": 90}
    r = client.put(f"/api/mock/{t['id']}/responses", headers=h, json={"responses": responses, "current_index": 25, "tab_switches": 2})
    assert r.status_code == 200 and r.json()["status"] == "in_progress"

    # can't open a second paper while one is running
    assert client.post("/api/mock", headers=h, json={"pattern": "jee_main_25"}).status_code == 409

    res = client.post(f"/api/mock/{t['id']}/submit", headers=h).json()
    total = res["result"]["total"]
    assert res["status"] == "submitted"
    assert total["score"] == 3 * 4 - 1 + 5 * 4 == 31
    assert (total["correct"], total["incorrect"], total["unattempted"]) == (8, 1, 81)
    assert total["negative"] == 1 and total["max"] == 300
    physics = next(s for s in res["result"]["subjects"] if s["subject"] == "Physics")
    assert physics["score"] == 31 and {s["key"] for s in physics["sections"]} == {"A", "B"}
    assert all("answer" in q and "solution" in q for q in res["questions"])  # review shows the key now
    assert res["result"]["insights"]
    assert res["tab_switches"] == 2

    # the wrong answer joins the redo queue
    redo = client.get("/api/quiz/redo", headers=h).json()
    assert any(r["q_type"] == "mock" for r in redo)

    # history
    hist = client.get("/api/mock", headers=h).json()
    assert hist[0]["id"] == t["id"] and hist[0]["score"] == 31

    # free plan: one full mock a week
    t2 = client.post("/api/mock", headers=h, json={"pattern": "jee_main_25"})
    assert t2.status_code == 402 and "this week" in t2.json()["detail"]

    # reporting a wrong key twice retires the question
    qid = qs[0]["id"]
    assert client.post(f"/api/mock/questions/{qid}/report", headers=h, json={"reason": "key looks wrong"}).status_code == 204
    assert client.post(f"/api/mock/questions/{qid}/report", headers=h, json={}).status_code == 204
    with SessionLocal() as db:
        assert db.get(BankQuestion, qid).reports == 2
        assert qid not in {q.id for q in question_bank._pool(db, "Physics", "mcq", set())}


def test_mock_overdue_paper_submits_itself_and_new_papers_avoid_repeats(client, bank):
    h = _register(client, "mock2@example.com")
    with SessionLocal() as db:
        u = _user(db, "mock2@example.com")
        u.plan = "pro"
        db.commit()
    t = client.post("/api/mock", headers=h, json={"pattern": "jee_main_25"}).json()
    first = client.post(f"/api/mock/{t['id']}/start", headers=h).json()
    assert len(first["questions"]) == 75

    with SessionLocal() as db:  # the student closed the browser three hours ago
        db.get(MockTest, t["id"]).started_at = utcnow() - timedelta(hours=3, minutes=5)
        db.commit()
    r = client.get(f"/api/mock/{t['id']}", headers=h).json()
    assert r["status"] == "submitted" and r["result"]["total"]["unattempted"] == 75
    assert client.put(f"/api/mock/{t['id']}/responses", headers=h, json={"responses": {}}).json()["status"] == "submitted"

    t2 = client.post("/api/mock", headers=h, json={"pattern": "jee_main_25"}).json()
    second = client.post(f"/api/mock/{t2['id']}/start", headers=h).json()
    overlap = {q["id"] for q in first["questions"]} & {q["id"] for q in second["questions"]}
    assert not overlap  # the bank had enough unseen questions


def test_chapter_test(client, bank):
    h = _register(client, "chapter1@example.com")
    meta = client.get("/api/mock/meta", headers=h).json()
    assert "Electrostatics" in meta["syllabus"]["Physics"] and meta["chapter_sizes"] == [10, 15, 20, 25]

    bad = client.post("/api/mock", headers=h, json={"pattern": "chapter", "subject": "Physics", "chapters": ["Not a chapter"], "count": 10})
    assert bad.status_code == 422
    assert client.post("/api/mock", headers=h, json={"pattern": "chapter", "subject": "Physics",
                                                     "chapters": ["Kinematics"], "count": 12}).status_code == 422

    chapters = ["Kinematics", "Laws of Motion", "Rotational Motion"]
    t = client.post("/api/mock", headers=h, json={"pattern": "chapter", "subject": "Physics", "chapters": chapters, "count": 10}).json()
    assert t["status"] == "ready" and t["kind"] == "chapter" and t["title"].startswith("Chapter test · Physics")
    started = client.post(f"/api/mock/{t['id']}/start", headers=h).json()
    qs = started["questions"]
    assert len(qs) == 10 and started["duration_min"] == 20 and started["pattern_info"]["subjects"] == ["Physics"]
    assert sum(q["qtype"] == "mcq" for q in qs) == 7 and sum(q["qtype"] == "numerical" for q in qs) == 3
    with SessionLocal() as db:
        got = {q.chapter for q in db.scalars(select(BankQuestion).where(BankQuestion.id.in_([q["id"] for q in qs])))}
    assert got <= set(chapters)
    res = client.post(f"/api/mock/{t['id']}/submit", headers=h).json()
    assert res["status"] == "submitted" and res["result"]["total"]["max"] == 40

    # chapter tests don't use the weekly full-mock quota
    assert client.get("/api/usage", headers=h).json()["mocks"]["used"] == 0
    full = client.post("/api/mock", headers=h, json={"pattern": "jee_main_25"}).json()
    assert client.post(f"/api/mock/{full['id']}/start", headers=h).status_code == 200


def test_full_mocks_bought_without_pro(client, bank):
    """A Starter student who used the week's free mock buys one (or a pack): it is used only after the free one, never
    runs out with time, and a refund-owed or unpaid checkout gives nothing."""
    h = _register(client, "mockbuy@example.com")
    first = client.post("/api/mock", headers=h, json={"pattern": "jee_main_30"}).json()
    client.post(f"/api/mock/{first['id']}/start", headers=h)
    client.post(f"/api/mock/{first['id']}/submit", headers=h)
    q = client.get("/api/mock/meta", headers=h).json()["quota"]
    assert q["left"] == 0 and q["credits"] == 0 and {o["id"] for o in q["offers"]} == {"one", "pack"}
    assert client.post("/api/mock", headers=h, json={"pattern": "jee_main_25"}).status_code == 402

    unpaid = client.post("/api/billing/mocks?pack=pack", headers=h).json()  # opened, never paid
    assert unpaid["amount_inr"] == settings.MOCK_PACK_INR
    assert client.get("/api/mock/meta", headers=h).json()["quota"]["credits"] == 0

    one = client.post("/api/billing/mocks?pack=one", headers=h).json()
    assert one["amount_inr"] == settings.MOCK_PRICE_INR
    assert client.post(f"/api/billing/payments/{one['payment_id']}/confirm", headers=h, json={}).status_code == 200
    q = client.get("/api/mock/meta", headers=h).json()["quota"]
    assert q["credits"] == 1 and q["left"] == 1 and q["free_left"] == 0

    t = client.post("/api/mock", headers=h, json={"pattern": "jee_main_25"})
    assert t.status_code == 201
    assert client.post(f"/api/mock/{t.json()['id']}/start", headers=h).json()["status"] == "in_progress"
    with SessionLocal() as db:
        assert db.get(MockTest, t.json()["id"]).config == {"paid": True}
    client.post(f"/api/mock/{t.json()['id']}/submit", headers=h)
    q = client.get("/api/mock/meta", headers=h).json()["quota"]
    assert q["credits"] == 0 and q["left"] == 0
    assert client.post("/api/mock", headers=h, json={"pattern": "jee_main_25"}).status_code == 402

    # a week later the free one comes back first, and a bought pack is kept for after it
    pack = client.post("/api/billing/mocks?pack=pack", headers=h).json()
    client.post(f"/api/billing/payments/{pack['payment_id']}/confirm", headers=h, json={})
    with SessionLocal() as db:
        for m in db.scalars(select(MockTest).where(MockTest.user_id == _user(db, "mockbuy@example.com").id)):
            m.started_at = m.started_at - timedelta(days=8)
        db.commit()
    q = client.get("/api/mock/meta", headers=h).json()["quota"]
    assert q["free_left"] == 1 and q["credits"] == settings.MOCK_PACK_SIZE
    t = client.post("/api/mock", headers=h, json={"pattern": "jee_main_25"}).json()
    client.post(f"/api/mock/{t['id']}/start", headers=h)
    with SessionLocal() as db:
        assert not (db.get(MockTest, t["id"]).config or {}).get("paid")  # the free one went first
    assert client.get("/api/mock/meta", headers=h).json()["quota"]["credits"] == settings.MOCK_PACK_SIZE

    assert client.post("/api/billing/mocks?pack=ten", headers=h).status_code == 422
