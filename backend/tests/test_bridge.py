"""The test bridge: the warm-up while a paper is written, and the gap map after it."""
import json

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.mock import BankQuestion, MockTest
from app.services import bridge, mock, question_bank, topic_notes
from app.services.mock_patterns import SYLLABUS

CHAPTERS = list(SYLLABUS["Physics"])[:2]

CAPSULE = """## Must-know formulas
| Formula or fact | Use when |
|---|---|
| $v = u + at$ | constant acceleration |

## Key points
- Displacement is a vector; distance is not.
- The slope of a $v$-$t$ graph is the acceleration.

## Common mistakes
- **Mistake:** adding speeds as scalars. **Instead:** add velocities as vectors.

## Quick self-check
1. What does the area under a $v$-$t$ graph give?
   Answer: The displacement.
2. Can speed be negative?
   Answer: No.
"""


def _register(client, email):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Bridge Student", "password": "correct-horse-1",
                                                 "exam_target": "jee"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def stocked(tmp_path_factory):
    items = [{"subject": "Physics", "chapter": CHAPTERS[i % 2], "qtype": "mcq", "options": ["one", "two", "three", "four"],
              "question": f"Bridge question {i} about {CHAPTERS[i % 2]}: pick the right option.", "answer": i % 4, "solution": "So."}
             for i in range(24)]
    path = tmp_path_factory.mktemp("bridge") / "bank.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    with SessionLocal() as db:
        question_bank.load_seed(db, path)


def test_markdown_reading():
    assert bridge._bullets(bridge._section(CAPSULE, "Key points"), 4) == [
        "Displacement is a vector; distance is not.", "The slope of a $v$-$t$ graph is the acceleration."]
    assert bridge._self_check(CAPSULE) == [{"q": "What does the area under a $v$-$t$ graph give?", "a": "The displacement."},
                                           {"q": "Can speed be negative?", "a": "No."}]
    assert bridge._section(CAPSULE, "Not there") == ""


def test_warmup_feeling_and_gap_map(client, stocked):
    h = _register(client, "bridge1@example.com")
    t = client.post("/api/mock", headers=h, json={"pattern": "chapter", "subject": "Physics", "chapters": CHAPTERS, "count": 10}).json()
    assert t["status"] == "ready", t

    warm = client.get(f"/api/mock/{t['id']}/warmup", headers=h).json()
    assert [c["chapter"] for c in warm["cards"]] == CHAPTERS
    first = warm["cards"][0]
    assert first["chapter_id"] and first["topics"] and first["felt"] is None
    with SessionLocal() as db:  # a capsule in the library shows up as key points and self-check questions
        topic_notes._store(db, "jee", "capsule", first["chapter_id"], CAPSULE, None, True)
    first = client.get(f"/api/mock/{t['id']}/warmup", headers=h).json()["cards"][0]
    assert first["points"][0].startswith("Displacement") and first["check"][1]["a"] == "No."

    feel = lambda chapter, felt: client.put(f"/api/mock/{t['id']}/feeling", headers=h,  # noqa: E731
                                            json={"subject": "Physics", "chapter": chapter, "felt": felt})
    assert feel(CHAPTERS[0], "sure").json()["felt"] == {f"Physics::{CHAPTERS[0]}": "sure"}
    assert feel(CHAPTERS[1], "shaky").status_code == 200
    assert feel("Organic Chemistry", "sure").status_code == 422
    assert client.get(f"/api/mock/{t['id']}/warmup", headers=h).json()["cards"][0]["felt"] == "sure"

    # the chapter they felt sure about goes all wrong, the shaky one all right
    qs = client.post(f"/api/mock/{t['id']}/start", headers=h).json()["questions"]
    with SessionLocal() as db:
        paper = db.get(MockTest, t["id"])
        rows = {q.id: (q.chapter, mock.shown_answer(paper, q))  # the key as this paper shows it
                for q in db.scalars(select(BankQuestion).where(BankQuestion.id.in_([q["id"] for q in qs])))}
    responses = {str(q["id"]): {"a": rows[q["id"]][1] if rows[q["id"]][0] == CHAPTERS[1]
                                else str((int(rows[q["id"]][1]) + 1) % 4), "t": 30} for q in qs}
    res = client.post(f"/api/mock/{t['id']}/submit", headers=h, json={"responses": responses}).json()
    gap = res["gap_map"]
    top = gap["chapters"][0]
    assert top["chapter"] == CHAPTERS[0] and top["flag"] == "blind_spot" and top["level"] == "gap" and top["share"] == 0
    assert gap["chapters"][1]["flag"] == "hidden_strength" and gap["chapters"][1]["level"] == "strong"
    assert "felt sure" in gap["summary"] and "better than you thought" in gap["summary"]
    kinds = [s["kind"] for s in gap["steps"]]
    assert kinds == ["revise", "retest", "redo"]
    retest = gap["steps"][1]
    assert retest["subject"] == "Physics" and retest["chapters"] == [CHAPTERS[0]]
    assert client.post("/api/mock", headers=h, json={"pattern": "chapter", "subject": retest["subject"],
                                                      "chapters": retest["chapters"], "count": retest["count"]}).status_code == 201
    assert feel(CHAPTERS[0], "shaky").status_code == 409  # marked: the feeling before it stays as it was


def test_full_mock_warmup_picks_a_few_heavy_chapters(client):
    h = _register(client, "bridge2@example.com")
    with SessionLocal() as db:
        from app.models.mock import MockTest
        from app.models.user import User

        user = db.scalar(select(User).where(User.email == "bridge2@example.com"))
        test = MockTest(user_id=user.id, pattern="jee_main_30", title="Mock", status="preparing")
        db.add(test)
        db.commit()
        cards = bridge.warmup(db, user, test)["cards"]
    assert 3 <= len(cards) <= bridge.MAX_CARDS and {c["subject"] for c in cards} == {"Physics", "Chemistry", "Mathematics"}


def test_explanations_in_the_students_language(client, stocked, monkeypatch):
    from app.services import ai
    from app.services.llm import llm

    h = _register(client, "bridge3@example.com")
    assert client.patch("/api/auth/me", headers=h, json={"language": "hinglish"}).json()["language"] == "hinglish"
    assert client.patch("/api/auth/me", headers=h, json={"language": "tamil"}).status_code == 422

    seen = {}

    def fake_chat(messages, **kw):
        seen["system"] = messages[0]["content"]
        return "Yahan $\frac{1}{2}mv^2$ lagao, answer **4** hai."

    monkeypatch.setattr(llm, "chat", fake_chat)
    assert client.post("/api/companion/ask", headers=h, json={"question": "What is work?", "mode": "explain", "history": []}).status_code == 200
    assert "Hinglish" in seen["system"]

    t = client.post("/api/mock", headers=h, json={"pattern": "chapter", "subject": "Physics", "chapters": CHAPTERS, "count": 10}).json()
    qid = client.post(f"/api/mock/{t['id']}/start", headers=h).json()["questions"][0]["id"]
    r = client.post(f"/api/mock/questions/{qid}/explain", headers=h, json={"language": "hinglish"})
    assert r.status_code == 200 and "\frac{1}{2}" in r.json()["solution"]
    seen.clear()
    again = client.post(f"/api/mock/questions/{qid}/explain", headers=h, json={"language": "hinglish"}).json()
    assert again["solution"] == r.json()["solution"] and not seen  # kept: no second AI call
    assert client.post(f"/api/mock/questions/{qid}/explain", headers=h, json={"language": "fr"}).status_code == 422
    other = _register(client, "bridge4@example.com")  # only a question from your own paper
    assert client.post(f"/api/mock/questions/{qid}/explain", headers=other, json={"language": "hi"}).status_code == 404
    assert ai.language_rule("en") == "" and "Devanagari" in ai.language_rule("hi")
