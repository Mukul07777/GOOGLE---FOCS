"""Placement preparation: the "coding" target follows a syllabus of library courses, planned to a placement date."""
from datetime import date, timedelta

from app.services import mock_patterns, planner, syllabus


def test_the_placement_syllabus_is_library_courses_weighted_to_100():
    syl = syllabus.get("placement")
    library = syllabus.courses()
    assert syl.kind == "gate" and syl.library == "college" and len(syl.subjects) == 11 and all(s in library for s in syl.subjects)
    assert round(sum(c.weight for c in syl.chapters)) == 100
    assert syl.subjects[0] == "Coding Interview Patterns" and {"Interview Skills", "System Design Basics", "General Aptitude"} <= set(syl.subjects)
    assert all(len(c.topics) >= 4 and c.hours > 0 for c in syl.chapters)
    assert syllabus.exam_of("coding") == "placement" and syllabus.group("placement") == "placement" and syllabus.family("placement") == "college"
    assert syllabus.label("coding") == "coding interview"
    assert all(mock_patterns.is_course(s) and mock_patterns.chapters_of(s) for s in syl.subjects)  # each can be tested
    assert [n for _, n in planner.placement_dates(date(2026, 10, 13))][0] == "IIT placements begin"
    assert all(d > date(2026, 6, 20) + timedelta(days=14) for d, _ in planner.placement_dates(date(2026, 6, 20)))


def _goal(track, target, **more):
    return {"track": track, "class_level": "dropper", "exam_date": (date.today() + timedelta(days=150)).isoformat(), "target": target,
            "dream": "A product company", "weekday_hours": 3, "weekend_hours": 6, "coaching": "self", "standing": {}, **more}


def test_placement_student_end_to_end(client):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": "placement@example.com", "full_name": "Kabir Shah", "password": "correct-horse-1",
                                                "exam_target": "coding"})
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    tree = client.get("/api/prep/syllabus", headers=h).json()
    assert tree["kind"] == "gate" and tree["name"].startswith("Placements") and len(tree["subjects"]) == 11
    assert tree["subjects"][0]["name"] == "Coding Interview Patterns" and tree["subjects"][0]["about"]
    opts = client.get("/api/prep/options", headers=h).json()
    assert [t["id"] for t in opts["targets"]["placement"]] == ["top_product", "product", "service_plus", "placed"]
    assert len(opts["rounds"]["placement"]) == 3

    for bad in (_goal("gate", "air_1k"), _goal("placement", "air_1k"), _goal("college", "sgpa_8", class_level="3")):
        assert client.put("/api/prep/goal", headers=h, json=bad).status_code == 422, bad
    standing = {"Data Structures": {"all": "done"}, "Operating Systems": {"all": "partial"}}
    plan = client.put("/api/prep/goal", headers=h, json=_goal("placement", "product", standing=standing))
    assert plan.status_code == 200, plan.text
    plan = plan.json()
    assert plan["kind"] == "gate" and plan["goal"]["exam"] == "placement" and plan["goal"]["group"] == "placement"
    assert plan["by_subject"]["Data Structures"] == 100 and plan["target"]["label"].startswith("A product company") and plan["weeks"]
    text = " ".join(n["title"] + n["text"] for n in plan["mentor"])
    assert "full mocks" not in text and "GATE" not in text and "JEE" not in text
    me = client.get("/api/auth/me", headers=h).json()
    assert me["exam_target"] == "coding" and me["class_level"] != "Dropper"

    names = {s["name"] for s in tree["subjects"]}
    assert all(t.get("subject") in (None, *names) for t in plan["today"]["tasks"])
    assert not any(t["kind"] == "mock" and "full" in t["title"].lower() for t in plan["today"]["tasks"])
    meta = client.get("/api/mock/meta", headers=h).json()   # tested a subject at a time, no full mock
    assert meta["exam"] == "college" and meta["patterns"] == [] and "Coding Interview Patterns" in meta["syllabus"]
    assert "Dynamic Programming Patterns" in meta["syllabus"]["Advanced Coding Patterns"]
    assert client.get("/api/campus", headers=h).status_code == 200  # the shelf of papers and notes is theirs too
    assert client.get("/api/weak", headers=h).status_code == 200 and client.get("/api/prep/last-day", headers=h).status_code == 200
