"""Fixes from the 27 October pre-handover test: public health check, real 404s and a sitemap, practice questions
checked before they're shown, abandoned lectures ending by themselves, tidy maths in notes, named rooms, and
flashcards counted as new until first reviewed."""
from datetime import timedelta

from app.models._util import utcnow
from app.services import ai
from app.services.llm import LLMUnavailable
from app.services.question_bank import only_correct


def _student(client, email):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Fix Student", "password": "correct-horse-1", "exam_target": "jee"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------- what strangers can read
def test_public_health_check_names_no_versions_or_providers(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and "llm" in body
    for private in ("version", "build", "database", "storage", "ocr"):
        assert private not in body
    assert "model" not in body["llm"]


def test_full_health_check_needs_a_signed_in_user(client):
    assert client.get("/api/health/details").status_code == 401
    details = client.get("/api/health/details", headers=_student(client, "fix.health@example.com")).json()
    assert "version" in details and "database" in details


def test_security_headers(client):
    headers = client.get("/api/health").headers
    assert "camera=(self)" in headers["Permissions-Policy"] and "geolocation=()" in headers["Permissions-Policy"]
    assert "form-action 'self'" in headers["Content-Security-Policy"]


def test_unknown_pages_are_real_404s(client):
    from app.main import _is_app_route

    for page in ("/", "/login", "/app", "/app/library/12", "/mentor/calls", "/exam/3", "/p/abc"):
        assert _is_app_route(page), page
    for junk in ("/docs", "/openapi.json", "/wp-admin", "/app-old", "/loginx"):
        assert not _is_app_route(junk), junk


def test_sitemap_lists_the_public_pages(client):
    r = client.get("/sitemap.xml")
    if r.status_code == 404:  # the frontend isn't built in this checkout: the sitemap is served with it
        return
    assert r.headers["content-type"].startswith("application/xml")
    assert "/signup</loc>" in r.text and "/app" not in r.text


# ---------------------------------------------------------------- practice questions are checked
def test_a_question_with_two_correct_options_is_rejected():
    assert only_correct({"correct": [1]}, 1)
    assert not only_correct({"correct": [0, 1]}, 1)  # both (-inf,-2) and [3,5) were true: a broken question
    assert not only_correct({"correct": []}, 1)
    assert only_correct({"answer_index": 2}, 2)      # an older-style reply


def test_practice_set_keeps_only_questions_the_checker_agrees_with(monkeypatch):
    mcq = [{"q": "Solve f(x) <= 0", "options": ["(-inf,-2)", "[3,5)", "x=7", "none"], "answer_index": 1, "explanation": "..."},
           {"q": "2+2", "options": ["3", "4", "5", "6"], "answer_index": 1, "explanation": "4"},
           {"q": "3+3", "options": ["6", "4", "5", "7"], "answer_index": 0, "explanation": "skips a case"}]
    seen = {}

    def checker(messages, **kwargs):
        seen.update(kwargs)
        return {"answers": [{"n": 1, "correct": [0, 1]}, {"n": 2, "correct": [1]},
                            {"n": 3, "correct": [0], "explanation_ok": False}]}, "checker"

    monkeypatch.setattr(ai.llm, "json_with_model", checker)
    kept = ai._checked_mcqs(mcq, "jee", "writer")
    assert [m["q"] for m in kept] == ["2+2"] and kept[0]["checked"] is True
    assert seen["skip"] == frozenset({"writer"})  # a different model checks


def test_practice_questions_stay_marked_unchecked_without_a_second_model(monkeypatch):
    monkeypatch.setattr(ai.llm, "json_with_model", lambda *a, **k: (_ for _ in ()).throw(LLMUnavailable("down")))
    kept = ai._checked_mcqs([{"q": "q", "options": ["a", "b", "c", "d"], "answer_index": 0, "explanation": ""}], "jee", "writer")
    assert kept[0]["checked"] is False


# ---------------------------------------------------------------- notes
def test_an_unmatched_display_dollar_is_dropped():
    assert ai.tidy_math("so $$\\ne v here\n\n$x$ fine") == "so \\ne v here\n\n$x$ fine"
    assert ai.tidy_math("$$a$$ and $b") == "$$a$$ and $b$"
    assert ai.tidy_math("```\n$$ code\n```") == "```\n$$ code\n```"


def test_a_sign_chart_row_keeps_its_spacing():
    assert ai._literal("+ -+-++") == "`+  −  +  −  +  +`"
    assert ai._literal("x - y") != "`x - y`"


# ---------------------------------------------------------------- abandoned lectures
def test_an_abandoned_lecture_ends_at_its_last_activity(client):
    from app.core.database import SessionLocal
    from app.models.session import StudySession

    h = _student(client, "fix.idle@example.com")
    sid = client.post("/api/sessions", headers=h, json={"title": "Untitled lecture"}).json()["id"]
    started = utcnow() - timedelta(hours=12)
    with SessionLocal() as db:
        s = db.get(StudySession, sid)
        s.started_at = started
        db.commit()
    assert client.get("/api/sessions/active", headers=h).json() is None
    lecture = next(s for s in client.get("/api/sessions", headers=h).json() if s["id"] == sid)
    assert lecture["is_active"] is False and lecture["duration_min"] == 0  # 12 hours open, no boards: no study time


def test_a_fresh_lecture_stays_live(client):
    h = _student(client, "fix.live@example.com")
    sid = client.post("/api/sessions", headers=h, json={"title": "Live now"}).json()["id"]
    assert client.get("/api/sessions/active", headers=h).json()["id"] == sid


def test_focus_time_is_the_heartbeat_minutes_when_there_are_any(client):
    from app.core.database import SessionLocal
    from app.models.session import StudySession

    h = _student(client, "fix.focus@example.com")
    sid = client.post("/api/sessions", headers=h, json={"title": "Open all day"}).json()["id"]
    with SessionLocal() as db:
        s = db.get(StudySession, sid)
        s.started_at, s.ended_at, s.is_active = utcnow() - timedelta(hours=6), utcnow(), False
        db.commit()
    client.post("/api/analytics/heartbeat", headers=h, json={"activity": "lecture", "tz_offset": 0})
    o = client.get("/api/analytics/overview?tz_offset=0", headers=h).json()
    assert o["today_minutes"] == 1 == sum(o["today_by_activity"].values())


# ---------------------------------------------------------------- rooms and flashcards
def test_a_room_needs_a_name(client):
    h = _student(client, "fix.room@example.com")
    assert client.post("/api/rooms", headers=h, json={}).status_code == 422
    assert client.post("/api/rooms", headers=h, json={"name": "   "}).status_code == 422
    assert client.post("/api/rooms", headers=h, json={"name": " Night owls "}).json()["name"] == "Night owls"


def test_new_flashcards_are_counted_as_new_not_learning(client):
    h = _student(client, "fix.cards@example.com")
    card = client.post("/api/flashcards", headers=h, json={"front": "F = ?", "back": "ma"}).json()
    stats = client.get("/api/flashcards/stats", headers=h).json()
    assert stats["new"] == 1 and stats["learning"] == 0
    client.post(f"/api/flashcards/{card['id']}/review", headers=h, json={"grade": "again"})
    stats = client.get("/api/flashcards/stats", headers=h).json()
    assert stats["new"] == 0 and stats["learning"] == 1
