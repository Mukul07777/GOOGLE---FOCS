"""A lecture's name: the one the student typed (or renamed it to) is kept when the lecture ends; an untitled lecture
is still named for the student from its boards."""
import pytest

from app.services import ai
from tests.conftest import board_png


@pytest.fixture
def fake_ai(monkeypatch):
    def notes(text, exam, prev_topic=None, offline_only=False, patient=True, board=None):
        return {"is_lecture": True, "topic": "Quadratic equations", "subject": "Mathematics", "notes_md": "## Notes", "source": "ai"}

    monkeypatch.setattr(ai, "generate_notes", notes)
    monkeypatch.setattr(ai, "summarize_session", lambda *a, **k: {"summary_md": "## Sheet", "title": "Quadratic Equations Revision",
                                                                 "subject": "Mathematics", "flashcards": [], "source": "ai"})


def _student(client, email):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Title Test", "password": "correct-horse-1",
                                                "exam_target": "jee"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _lecture(client, h, title=None):
    sid = client.post("/api/sessions", headers=h, json={"title": title} if title else {}).json()["id"]
    client.post(f"/api/capture/{sid}/frame", headers=h, data={"force": "true"},
                files={"frame": ("f.png", board_png(["Quadratic equations", "ax^2 + bx + c = 0", "D = b^2 - 4ac"]), "image/png")})
    return sid


def _end(client, h, sid):
    return client.post(f"/api/sessions/{sid}/end", headers=h).json()["session"]["title"]


def test_a_typed_title_is_kept_when_the_lecture_ends(client, fake_ai):
    """It used to be replaced when it happened to match the first board's topic."""
    h = _student(client, "typed.title@example.com")
    assert _end(client, h, _lecture(client, h, "Quadratic equations")) == "Quadratic equations"


def test_a_renamed_lecture_keeps_its_name(client, fake_ai):
    h = _student(client, "renamed.title@example.com")
    sid = _lecture(client, h)
    assert client.patch(f"/api/sessions/{sid}", headers=h, json={"title": "  Maths class 3  "}).json()["title"] == "Maths class 3"
    assert _end(client, h, sid) == "Maths class 3"
    assert client.patch(f"/api/sessions/{sid}", headers=h, json={"title": "Quadratics, done"}).json()["title"] == "Quadratics, done"
    assert client.patch(f"/api/sessions/{sid}", headers=h, json={"title": "   "}).status_code == 422


def test_an_untitled_lecture_is_still_named_for_the_student(client, fake_ai):
    h = _student(client, "untitled.title@example.com")
    assert _end(client, h, _lecture(client, h)) == "Quadratic Equations Revision"
