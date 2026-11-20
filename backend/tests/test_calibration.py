"""W5: confidence vs reality. Answers locked in as sure or guessing; blind spots (sure and wrong) lead."""
import json

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.mock import BankQuestion, MockTest
from app.models.weak import WeakTopic
from app.services import mock, question_bank
from app.services.mock_patterns import SYLLABUS

CHAPTERS = list(SYLLABUS["Physics"])[2:4]


def _student(client, email):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Cal Student", "password": "correct-horse-1", "exam_target": "jee"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_lecture_quizzes_sure_vs_right(client):
    h = _student(client, "cal1@example.com")
    sid = client.post("/api/sessions", headers=h, json={"title": "Projectiles"}).json()["id"]
    answer = lambda topic, correct, conf: client.post("/api/quiz/attempt", headers=h, json={  # noqa: E731
        "question": f"Q on {topic}", "q_type": "checkpoint", "correct": correct, "topic": topic, "subject": "Physics",
        "session_id": sid, "confidence": conf}).status_code
    assert answer("Range", False, "sure") == 201          # a blind spot
    assert answer("Range", True, "sure") == 201
    assert answer("Time of flight", True, "unsure") == 201  # a hidden strength
    assert answer("Time of flight", False, "unsure") == 201
    assert answer("Old style", True, None) == 201          # no confidence asked: left out of the 2x2
    assert client.post("/api/quiz/attempt", headers=h, json={"question": "x", "q_type": "pop", "correct": True, "confidence": "maybe"}).status_code == 422

    rep = client.get(f"/api/analytics/calibration?session_id={sid}", headers=h).json()
    assert rep["grid"] == {"sure_right": 1, "sure_wrong": 1, "guess_right": 1, "guess_wrong": 1} and rep["answers"] == 4
    assert rep["sure_accuracy"] == 50 and rep["guess_accuracy"] == 50
    assert rep["blind_spots"][0]["topic"] == "Range" and rep["hidden_strengths"][0]["topic"] == "Time of flight"
    assert rep["topics"][0]["topic"] == "Range"  # the topic with a blind spot comes first
    assert rep["headline"].startswith("You were sure about Range and got it wrong: start there.")

    end = client.post(f"/api/sessions/{sid}/end", headers=h).json()
    assert end["calibration"]["headline"].startswith("You were sure about Range")


@pytest.fixture(scope="module")
def stocked(tmp_path_factory):
    items = [{"subject": "Physics", "chapter": CHAPTERS[i % 2], "qtype": "mcq", "options": ["a", "b", "c", "d"],
              "question": f"Calibration question {i} about {CHAPTERS[i % 2]}: which option?", "answer": i % 4, "solution": "So."}
             for i in range(24)]
    path = tmp_path_factory.mktemp("cal") / "bank.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    with SessionLocal() as db:
        question_bank.load_seed(db, path)


def test_sure_and_wrong_in_a_test_becomes_a_double_weak_spot(client, stocked):
    h = _student(client, "cal2@example.com")
    t = client.post("/api/mock", headers=h, json={"pattern": "chapter", "subject": "Physics", "chapters": CHAPTERS, "count": 10}).json()
    qs = client.post(f"/api/mock/{t['id']}/start", headers=h).json()["questions"]
    with SessionLocal() as db:
        paper = db.get(MockTest, t["id"])
        key = {q.id: (q.chapter, mock.shown_answer(paper, q))  # the key as this paper shows it
               for q in db.scalars(select(BankQuestion).where(BankQuestion.id.in_([q["id"] for q in qs])))}
    responses = {}
    for q in qs:  # the first chapter: sure and wrong; the second: guessed and right
        chapter, right = key[q["id"]]
        if chapter == CHAPTERS[0]:
            responses[str(q["id"])] = {"a": str((int(right) + 1) % 4), "t": 20, "c": "sure"}
        else:
            responses[str(q["id"])] = {"a": right, "t": 20, "c": "unsure"}
    res = client.post(f"/api/mock/{t['id']}/submit", headers=h, json={"responses": responses}).json()
    assert {r["confidence"] for r in res["result"]["questions"]} == {"sure", "unsure"}
    wrong_sure = sum(1 for r in res["result"]["questions"] if r["outcome"] == "incorrect")

    with SessionLocal() as db:
        from app.models.user import User

        uid = db.scalar(select(User.id).where(User.email == "cal2@example.com"))
        spots = db.scalars(select(WeakTopic).where(WeakTopic.user_id == uid)).all()
    assert len(spots) == 1 and spots[0].misses == 2 * wrong_sure and "blind spot" in spots[0].note
    weak = client.get("/api/weak", headers=h).json()
    assert weak["open"] and weak["open"][0]["chapter"]["name"] == CHAPTERS[0]

    rep = client.get("/api/analytics/calibration", headers=h).json()
    assert rep["grid"]["sure_wrong"] == wrong_sure and rep["grid"]["guess_right"] == len(qs) - wrong_sure
