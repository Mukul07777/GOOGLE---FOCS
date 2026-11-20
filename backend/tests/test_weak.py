"""Weak spots: the result of a test taken anywhere → weak topics placed in the syllabus → a plan that works them
off, weighs them next time and checks whether the concept is now clear."""
import io
from datetime import date, timedelta

import pytest

from app.services import ai, planner, syllabus, vision, weak
from app.services.llm import LLMUnavailable


def _student(client, email, exam="jee", goal=True):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Test Taker", "password": "correct-horse-1",
                                                "exam_target": exam})
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    if goal:
        g = {"track": "jee_main" if exam == "jee" else "neet", "class_level": "12", "exam_date": (date.today() + timedelta(days=200)).isoformat(),
             "target": "air_10k", "weekday_hours": 6, "weekend_hours": 6, "coaching": "offline", "standing": {}}
        assert client.put("/api/prep/goal", headers=h, json=g).status_code == 200
    return h


def _png():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (800, 1100), "white").save(buf, format="PNG")
    return buf.getvalue()


REPORT = {
    "test_name": "Allen Minor Test 4", "score": 63, "max_score": 80,
    "subjects": [{"name": "Physics", "score": 18, "max": 30}, {"name": "Chemistry", "score": 45, "max": 50}],
    "questions": [
        {"no": "3", "subject": "Physics", "area": "Projectile Motion", "status": "wrong", "about": "range of a projectile on an incline"},
        {"no": "7", "subject": "Physics", "area": "Projectile motion", "status": "skipped", "about": None},
        {"no": "9", "subject": "Physics", "area": "Newton's Laws of Motion", "status": "wrong", "about": "block on a wedge with friction, static and kinetic"},
        {"no": "12", "subject": "Physics", "area": "NLM", "status": "wrong", "about": "pulley with two masses, find tension"},
        {"no": "15", "subject": "Chemistry", "area": None, "status": "wrong", "about": "hybridisation of the central atom in SF4"},
        {"no": "20", "subject": "Chemistry", "area": "Thermo", "status": "correct", "about": "enthalpy"},
        {"no": "22", "subject": None, "area": "blurred", "status": "wrong", "about": None},
    ],
    "weak_areas": ["Rotational Motion"],
}


# ---------------------------------------------------------------- placing what the result says in the syllabus
@pytest.mark.parametrize("subject,text,chapter,topic", [
    ("Physics", "Projectile Motion", "physics.kinematics", "physics.kinematics.projectile-motion"),
    ("Physics", "Newton's Laws of Motion", "physics.laws-of-motion", None),
    (None, "Rotational Motion", "physics.rotational-motion", None),
    ("Chemistry", "Chemical Bonding & Molecular Structure", "chemistry.chemical-bonding-and-molecular-structure", None),
])
def test_printed_areas_are_placed(subject, text, chapter, topic):
    found = weak.place(syllabus.get("jee"), subject, text)
    assert found and found[0].id == chapter and (found[1].id if found[1] else None) == topic


@pytest.mark.parametrize("text", ["Motion", "NLM", "Section A", "blurred", ""])
def test_vague_areas_are_left_for_the_model_or_the_student(text):
    assert weak.place(syllabus.get("jee"), "Physics", text) is None


def test_a_read_result_becomes_a_draft(monkeypatch):
    asked = []

    def place_by_model(messages, **kwargs):  # the two the names couldn't place: "NLM" and the SF4 question
        asked.append(messages[-1]["content"])
        return {"items": [{"i": 0, "chapter_id": "physics.laws-of-motion"},
                          {"i": 1, "chapter_id": "chemistry.chemical-bonding-and-molecular-structure"}, {"i": 2, "chapter_id": "made.up"}]}

    monkeypatch.setattr(weak.llm, "json", place_by_model)
    d = weak.draft(syllabus.get("jee"), REPORT, "jee")
    assert (d["title"], d["score"], d["max_score"]) == ("Allen Minor Test 4", 63.0, 80.0) and len(d["subjects"]) == 2
    assert d["questions_read"] == 7 and d["wrong_read"] == 6
    rows = {(w["chapter_id"], w["topic_id"]): w for w in d["weak"]}
    proj = rows[("physics.kinematics", "physics.kinematics.projectile-motion")]
    assert proj["misses"] == 2 and proj["note"] == "Q3, Q7" and proj["topic"] == "Projectile motion"
    nlm_friction = rows[("physics.laws-of-motion", "physics.laws-of-motion.static-and-kinetic-friction")]  # the topic, from the question's words
    assert nlm_friction["misses"] == 1 and nlm_friction["note"] == "Q9"
    assert sum(w["misses"] for w in d["weak"] if w["chapter_id"] == "physics.laws-of-motion") == 2  # Q12 placed by the model
    pulley = rows[("physics.laws-of-motion", "physics.laws-of-motion.tension-normal-force-and-pulleys")]  # one telling word is enough
    assert pulley["note"] == "Q12"
    assert ("chemistry.chemical-bonding-and-molecular-structure" in {w["chapter_id"] for w in d["weak"]})
    assert rows[("physics.rotational-motion", None)]["misses"] == 1                # named weak by the report itself
    assert "thermo" not in str(d["weak"]).lower()                                    # a correct answer is never a weak spot
    assert d["unplaced"] == ["Q22 blurred"] and "[Physics] NLM pulley" in asked[0] and d["weak"][0]["misses"] == 2

    # no model to ask: the unplaced ones are handed to the student instead of being guessed
    monkeypatch.setattr(weak.llm, "json", lambda *a, **k: (_ for _ in ()).throw(LLMUnavailable("down")))
    d = weak.draft(syllabus.get("jee"), REPORT, "jee")
    assert len(d["unplaced"]) == 3 and ("physics.kinematics", "physics.kinematics.projectile-motion") in {(w["chapter_id"], w["topic_id"]) for w in d["weak"]}


# ---------------------------------------------------------------- reading an upload
def test_reading_an_uploaded_result(client, monkeypatch):
    h = _student(client, "weak.read@example.com")
    files = [("files", ("result.png", _png(), "image/png"))]
    assert client.get("/api/weak", headers=h).json()["reader"] == "none"
    assert client.post("/api/weak/read", headers=h, files=files).status_code == 503  # no AI on the test server

    seen = {}

    def see(images, prompt, feature, max_tokens=3000):
        seen.update(images=len(images), jpeg=images[0][:3] == b"\xff\xd8\xff", prompt=prompt, feature=feature)
        return REPORT

    monkeypatch.setattr(vision, "available", lambda: True)
    monkeypatch.setattr(vision, "read_json", see)
    monkeypatch.setattr(weak.llm, "json", lambda *a, **k: {"items": []})
    r = client.post("/api/weak/read", headers=h, files=files * 2)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["read_by"] == "vision" and d["score"] == 63 and d["weak"][0]["topic"] == "Projectile motion"
    assert seen == {**seen, "images": 2, "jpeg": True, "feature": "test_analysis"} and "JEE" in seen["prompt"]
    assert client.get("/api/usage", headers=h).json()["window"]["used"] == 5
    assert client.get("/api/weak", headers=h).json()["tests"] == []  # reading saves nothing

    assert client.post("/api/weak/read", headers=h, files=[("files", ("a.txt", b"hello", "text/plain"))]).status_code == 415
    assert client.post("/api/weak/read", headers=h, files=[("files", ("a.png", b"not an image", "image/png"))]).status_code == 400
    assert client.post("/api/weak/read", headers=h, files=files * 7).status_code == 422
    monkeypatch.setattr(vision, "read_json", lambda *a, **k: (_ for _ in ()).throw(LLMUnavailable("busy")))
    monkeypatch.setattr(weak, "_ocr_text", lambda images: "")  # and nothing legible for the OCR route either
    assert client.post("/api/weak/read", headers=h, files=files).status_code == 503
    assert client.get("/api/usage", headers=h).json()["window"]["used"] == 5  # a failed read costs nothing
    assert client.post("/api/weak/read", headers=_student(client, "weak.upsc@example.com", exam="other", goal=False), files=files).status_code == 404


def test_without_a_vision_model_the_result_is_read_from_ocr_text(monkeypatch):
    monkeypatch.setattr(vision, "available", lambda: False)
    monkeypatch.setattr(weak, "_ocr_text", lambda images: "Minor Test 4   Score 63/80\nQ3 Projectile Motion  Wrong")
    monkeypatch.setattr(weak.llm, "json", lambda messages, **k: {"score": 63, "max_score": 80, "seen": messages[-1]["content"]})
    data, how = weak.read_result([(_png(), "image/png")], "jee")
    assert how == "ocr" and data["score"] == 63 and "Projectile Motion" in data["seen"]
    with pytest.raises(ValueError):
        weak.read_result([(b"%PDF-broken", "application/pdf")], "jee")


# ---------------------------------------------------------------- the fix-it plan
PROJECTILE = {"chapter_id": "physics.kinematics", "topic_id": "physics.kinematics.projectile-motion", "misses": 2, "note": "Q3, Q7"}
ROTATION = {"chapter_id": "physics.rotational-motion", "topic_id": None, "misses": 3}


def test_weak_spots_drive_the_plan_until_a_recheck_clears_them(client, monkeypatch):
    h = _student(client, "weak.plan@example.com")
    body = {"title": "  Allen Minor  Test 4 ", "score": 63, "max_score": 80, "source": "upload",
            "subjects": [{"name": "Physics", "score": 18, "max": 30}], "weak": [PROJECTILE, ROTATION, {"chapter_id": "made.up"}]}
    r = client.post("/api/weak/tests", headers=h, json=body)
    assert r.status_code == 201, r.text
    o = r.json()
    assert [(w["chapter"]["id"], w["misses"]) for w in o["open"]] == [("physics.rotational-motion", 3), ("physics.kinematics", 2)]
    assert o["open"][1]["topic"]["name"] == "Projectile motion" and o["open"][1]["test"]["title"] == "Allen Minor Test 4"
    assert o["tests"][0] == {**o["tests"][0], "score": 63, "max_score": 80, "weak": 2, "source": "upload"}

    # the day's list starts with the costliest weak spot, the mentor says so, and last-day revision weighs it
    plan = client.get("/api/prep/plan", headers=h).json()
    fix = plan["today"]["tasks"][0]
    assert fix["kind"] == "fix" and fix["title"] == "Rotational Motion" and fix["more"] == 1 and not fix["done"]
    assert any("2 weak spots from your tests" == m["title"] for m in plan["mentor"])
    for t in syllabus.get("jee").by_id["physics.rotational-motion"].topics:
        client.put(f"/api/prep/topics/{t.id}", headers=h, json={"done": True})
    last = client.post("/api/prep/last-day", headers=h, json={}).json()
    assert last["own"]["weak"] == 2 and last["chapters"][0]["weak"] and "a weak spot from your last test" in last["chapters"][0]["reasons"]
    ticked = client.put(f"/api/prep/today/{fix['key']}", headers=h, json={"done": True}).json()
    assert ticked["tasks"][0]["done"]  # working on it today is ticked off; the weak spot itself stays open
    assert len(client.get("/api/weak", headers=h).json()["open"]) == 2

    # practice on the weak topic is aimed at it
    asked = []
    monkeypatch.setattr(ai, "generate_quiz", lambda material, *a, **k: asked.append(material) or {
        "topic": "x", "subject": "Physics", "source": "ai", "true_false": [], "subjective": [],
        "mcq": [{"q": "q", "options": ["a", "b", "c", "d"], "answer_index": 0, "explanation": ""}]})
    client.post("/api/quiz/generate", headers=h, json={"topic_id": PROJECTILE["topic_id"]})
    client.post("/api/quiz/generate", headers=h, json={"topic_id": "physics.kinematics.motion-in-a-plane"})
    assert "weak spot for this student: they lost 2 questions" in asked[0] and "weak spot" not in asked[1]

    # the re-check: under 70% (or too few questions) it stays open, 70% or better clears it
    check = lambda c, t, topic=PROJECTILE["topic_id"]: client.post("/api/weak/check", headers=h, json={"topic_id": topic, "correct": c, "total": t}).json()  # noqa: E731
    assert check(2, 5) == {"weak": True, "cleared": False, "percent": 40, "needed": 70, "enough_questions": True}
    assert check(3, 3)["cleared"] is False and check(3, 3)["enough_questions"] is False
    assert check(4, 5)["cleared"] is True
    o = client.get("/api/weak", headers=h).json()
    assert [w["chapter"]["id"] for w in o["open"]] == ["physics.rotational-motion"]
    assert o["cleared"][0]["last_check"] == {**o["cleared"][0]["last_check"], "correct": 4, "total": 5, "kind": "practice"} and o["cleared"][0]["checks"] == 4
    assert check(5, 5, "physics.kinematics.motion-in-a-plane") == {**check(5, 5, "physics.kinematics.motion-in-a-plane"), "weak": False, "cleared": False}
    assert client.post("/api/weak/check", headers=h, json={"topic_id": "x.y.z", "correct": 9, "total": 5}).status_code == 422

    # a chapter-wide weak spot is cleared by a chapter test on Focs taken after it (70%+), not by one topic's practice
    from app.core.database import SessionLocal
    from app.models._util import utcnow
    from app.models.mock import MockTest
    from app.models.user import User
    from sqlalchemy import select

    def chapter_test(correct, attempted):
        with SessionLocal() as db:
            uid = db.scalar(select(User.id).where(User.email == "weak.plan@example.com"))
            db.add(MockTest(user_id=uid, title="Rotation", pattern="chapter", status="submitted", duration_min=30, submitted_at=utcnow(),
                            config={"subject": "Physics", "chapters": ["Rotational Motion"], "count": 10},
                            result={"chapters": [{"subject": "Physics", "chapter": "Rotational Motion", "correct": correct, "attempted": attempted}]}))
            db.commit()

    chapter_test(4, 10)
    assert len(client.get("/api/weak", headers=h).json()["open"]) == 1
    chapter_test(10, 10)  # pooled with the first: 14 of 20
    o = client.get("/api/weak", headers=h).json()
    assert o["open"] == [] and {w["chapter"]["id"] for w in o["cleared"]} == {"physics.rotational-motion", "physics.kinematics"}
    plan = client.get("/api/prep/plan", headers=h).json()
    assert plan["today"]["tasks"][0]["kind"] == "fix" and plan["today"]["tasks"][0]["done"]  # cleared today: shown as done, gone tomorrow
    assert not any("weak spot" in m["title"] for m in plan["mentor"])


def test_the_next_test_adds_weight_instead_of_a_duplicate_and_the_student_has_the_last_word(client):
    h = _student(client, "weak.again@example.com")
    client.post("/api/weak/tests", headers=h, json={"title": "Test 1", "weak": [PROJECTILE]})
    o = client.post("/api/weak/tests", headers=h, json={"title": "Test 2", "score": 40, "max_score": 100, "weak": [{**PROJECTILE, "misses": 3}]}).json()
    assert len(o["open"]) == 1 and o["open"][0]["misses"] == 5 and o["open"][0]["test"]["title"] == "Test 2" and len(o["tests"]) == 2

    wid = o["open"][0]["id"]
    o = client.patch(f"/api/weak/{wid}", headers=h, json={"status": "cleared"}).json()  # "I've got this now"
    assert o["open"] == [] and o["cleared"][0]["last_check"]["kind"] == "self"
    assert client.patch(f"/api/weak/{wid}", headers=h, json={"status": "open"}).json()["open"][0]["id"] == wid
    other = _student(client, "weak.other@example.com")
    assert client.patch(f"/api/weak/{wid}", headers=other, json={"status": "cleared"}).status_code == 404

    # a test added by mistake goes, with the open weak spots that came from it
    test2 = next(t["id"] for t in o["tests"] if t["title"] == "Test 2")
    assert client.delete(f"/api/weak/tests/{test2}", headers=other).status_code == 404
    o = client.delete(f"/api/weak/tests/{test2}", headers=h).json()
    assert [t["title"] for t in o["tests"]] == ["Test 1"] and o["open"] == []

    for bad in ({"title": " "}, {"title": "T"}, {"title": "T", "score": 90, "max_score": 80}, {"title": "T", "score": 5, "taken_on": "2019-01-01"},
                {"title": "T", "weak": [{"chapter_id": "physics.kinematics", "misses": 0}]}):
        assert client.post("/api/weak/tests", headers=h, json=bad).status_code == 422, bad
    assert client.post("/api/weak/tests", headers=h, json={"title": "Marks only", "score": 55, "max_score": 80}).status_code == 201
    exported = client.get("/api/auth/export", headers=h).json()
    assert {t["title"] for t in exported["outside_tests"]} == {"Test 1", "Marks only"} and "weak_spots" in exported


def test_the_plan_takes_one_weak_spot_a_day_most_marks_lost_first():
    syl = syllabus.get("jee")
    goal = planner.Goal("jee", "jee_main", "12", date(2027, 4, 4), "air_10k", 6, 6)
    spots = [{"id": 2, "chapter_id": "physics.rotational-motion", "chapter": "Rotational Motion", "subject": "Physics", "misses": 3, "topic": None, "cleared": False},
             {"id": 1, "chapter_id": "physics.kinematics", "chapter": "Kinematics", "subject": "Physics", "misses": 2, "cleared": False,
              "topic": {"id": "physics.kinematics.projectile-motion", "name": "Projectile motion"}}]
    today = planner.build(goal, syl, planner.Progress(weak=spots), date(2026, 10, 5))["today"]
    fixes = [t for t in today["tasks"] if t["kind"] == "fix"]
    assert len(fixes) == 1 and today["tasks"][0] is fixes[0] and fixes[0]["key"] == "fix:2" and fixes[0]["minutes"] == planner.FIX_MINUTES
    hidden = planner.build(goal, syl, planner.Progress(weak=spots, checks={"hide:fix:2"}), date(2026, 10, 5))["today"]
    assert not [t for t in hidden["tasks"] if t["kind"] == "fix"] and hidden["hidden"][0]["title"] == "Fix: Rotational Motion"
    rest = planner.Goal("jee", "jee_main", "12", date(2027, 4, 4), "air_10k", 6, 6, day_hours=(0, 6, 6, 6, 6, 6, 6))
    assert planner.build(rest, syl, planner.Progress(weak=spots), date(2026, 10, 5))["today"]["tasks"] == []  # a rest day stays a rest day
