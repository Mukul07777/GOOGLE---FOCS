"""Classes (a teacher sees a class's progress) and the parent link (a parent sees one child's)."""
from datetime import timedelta

from app.core.database import SessionLocal
from app.models._util import utcnow
from app.models.mock import MockTest
from app.models.study_day import StudyDay
from app.models.weak import WeakTopic
from app.services import syllabus


def _user(client, email, name, exam="jee"):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": name, "password": "correct-horse-1", "exam_target": exam})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]["id"]


def _studied(uid):
    """Two days of study, a weak chapter and a submitted test."""
    syl = syllabus.get("jee")
    chapter = next(iter(syl.by_id.values()))
    today = utcnow().date()
    with SessionLocal() as db:
        db.add_all([StudyDay(user_id=uid, day=today, minutes=50, last_beat_at=utcnow()), StudyDay(user_id=uid, day=today - timedelta(days=1), minutes=40, last_beat_at=utcnow()),
                        StudyDay(user_id=uid, day=today - timedelta(days=20), minutes=300, last_beat_at=utcnow()),
                    WeakTopic(user_id=uid, chapter_id=chapter.id, misses=3, status="open"),
                    WeakTopic(user_id=uid, chapter_id=list(syl.by_id)[1], misses=1, status="cleared"),
                    MockTest(user_id=uid, title="JEE Main mock", status="submitted", score=120, max_score=300, submitted_at=utcnow())])
        db.commit()
    return chapter


def test_a_teacher_sees_the_class_and_only_their_own(client):
    teacher, _ = _user(client, "class.teacher@example.com", "Meera Rao")
    asha, asha_id = _user(client, "class.asha@example.com", "Asha Verma")
    ravi, ravi_id = _user(client, "class.ravi@example.com", "Ravi Kumar", exam="college_cse")
    other, _ = _user(client, "class.other@example.com", "Someone Else")
    chapter = _studied(asha_id)
    topics = [t.id for t in chapter.topics][:2]
    for t in topics:
        assert client.put(f"/api/prep/topics/{t}", headers=asha, json={"done": True}).status_code < 300, t

    assert client.post("/api/classes", headers=teacher, json={"name": "x"}).status_code == 422
    room = client.post("/api/classes", headers=teacher, json={"name": "  Batch  A 2027 "}).json()
    assert room["name"] == "Batch A 2027" and len(room["code"]) == 6 and room["students"] == 0
    assert client.post("/api/classes/join", headers=asha, json={"code": "ZZZZZZ"}).status_code == 404
    assert client.post("/api/classes/join", headers=teacher, json={"code": room["code"]}).status_code == 409
    for h in (asha, asha, ravi):  # joining twice changes nothing
        joined = client.post("/api/classes/join", headers=h, json={"code": f" {room['code'].lower()} "})
        assert joined.status_code == 200 and joined.json()["teacher"] == "Meera Rao"
    assert client.get("/api/classes", headers=teacher).json()["teaching"][0]["students"] == 2
    assert [c["name"] for c in client.get("/api/classes", headers=asha).json()["joined"]] == ["Batch A 2027"]

    assert client.get(f"/api/classes/{room['id']}", headers=asha).status_code == 404   # a student can't open the dashboard
    assert client.get(f"/api/classes/{room['id']}", headers=other).status_code == 404
    view = client.get(f"/api/classes/{room['id']}", headers=teacher).json()
    a, r = view["students"]
    assert (a["name"], r["name"]) == ("Asha Verma", "Ravi Kumar") and r["exam"] == "B.Tech CSE"
    assert a["week_minutes"] == 90 and a["days"][-2:] == [40, 50] and a["streak"] == 2 and a["today_minutes"] == 50
    assert a["syllabus"]["done"] == len(topics) and a["syllabus"]["total"] > 100 and a["weak_count"] == 1
    assert a["weak"] == [{"id": chapter.id, "chapter": chapter.name, "subject": chapter.subject}]
    assert a["last_test"]["percent"] == 40 and a["tests_week"] == 1
    assert r["week_minutes"] == 0 and r["last_test"] is None and r["weak"] == [] and r["syllabus"]["total"] > 0
    assert view["weakest"] == [{"id": chapter.id, "chapter": chapter.name, "subject": chapter.subject, "students": 1}]
    assert view["totals"]["students"] == 2 and view["totals"]["active_week"] == 1 and view["totals"]["avg_week_minutes"] == 45

    assert client.post(f"/api/classes/{room['id']}/leave", headers=ravi).status_code == 204
    assert client.delete(f"/api/classes/{room['id']}/students/{asha_id}", headers=other).status_code == 404
    assert client.delete(f"/api/classes/{room['id']}/students/{asha_id}", headers=teacher).status_code == 204
    assert client.get(f"/api/classes/{room['id']}", headers=teacher).json()["students"] == []
    assert client.delete(f"/api/classes/{room['id']}", headers=teacher).status_code == 204
    assert client.get("/api/classes", headers=teacher).json() == {"teaching": [], "joined": []}


def test_the_parent_link_shows_a_week_and_can_be_taken_back(client):
    kid, kid_id = _user(client, "parent.kid@example.com", "Asha Verma")
    _studied(kid_id)
    assert client.get("/api/parent/link", headers=kid).json()["token"] is None
    assert client.post("/api/parent/link").status_code == 401
    token = client.post("/api/parent/link", headers=kid).json()["token"]
    assert client.get("/api/parent/link", headers=kid).json()["token"] == token

    seen = client.get(f"/api/parent/view/{token}")  # no sign-in
    assert seen.status_code == 200
    seen = seen.json()
    assert seen["name"] == "Asha" and seen["week_minutes"] == 90 and seen["last_test"]["title"] == "JEE Main mock" and seen["weak_count"] == 1
    assert "email" not in seen and "user_id" not in seen

    again = client.post("/api/parent/link", headers=kid).json()["token"]  # a new link: the old one stops
    assert again != token and client.get(f"/api/parent/view/{token}").status_code == 404
    assert client.get(f"/api/parent/view/{again}").status_code == 200
    assert client.delete("/api/parent/link", headers=kid).status_code == 204
    assert client.get(f"/api/parent/view/{again}").status_code == 404 and client.get("/api/parent/view/short").status_code == 404
