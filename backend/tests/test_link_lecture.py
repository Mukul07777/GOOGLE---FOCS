"""Lecture by link: a YouTube lecture played inside Focs (phones can't share a tab). Each watched stretch becomes a
note; a rewatched stretch costs nothing; with the video model unreachable, the captions are written up instead."""
import pytest

from app.services import ai, link_lecture, youtube
from app.services.llm import LLMUnavailable


@pytest.fixture
def watched(monkeypatch):
    calls = []

    def watch(vid, start, end, prompt):
        calls.append((vid, start, end))
        return {"lecture": True, "topic": "Trigonometric identities", "subject": "Mathematics",
                "board": "sin^2 x + cos^2 x = 1", "notes_md": "## Identities\n- $\\sin^2 x + \\cos^2 x = 1$"}

    monkeypatch.setattr(link_lecture, "available", lambda: True)
    monkeypatch.setattr(link_lecture, "_watch", watch)
    monkeypatch.setattr(youtube, "title", lambda vid: "Trigonometry One Shot")
    return calls


def _student(client, email):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Link Test", "password": "correct-horse-1",
                                                "exam_target": "jee"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _start(client, h, url="https://youtu.be/7K1sB05pE0A?si=x"):
    return client.post("/api/sessions", headers=h, json={"source": "link", "video_url": url})


def test_a_link_lecture_writes_a_note_per_watched_stretch(client, watched):
    h = _student(client, "link.one@example.com")
    s = _start(client, h)
    assert s.status_code == 201, s.text
    assert s.json()["title"] == "Trigonometry One Shot" and s.json()["video_url"].endswith("v=7K1sB05pE0A")
    sid = s.json()["id"]
    r = client.post(f"/api/capture/{sid}/clip", headers=h, json={"start_s": 0, "end_s": 150})
    assert r.status_code == 200 and r.json()["status"] == "created", r.text
    assert r.json()["note"]["topic"] == "Trigonometric identities" and "\\sin" in r.json()["note"]["ai_notes"]
    assert watched == [("7K1sB05pE0A", 0, 150)]
    # rewound and watched again: nothing new is written, nothing is spent
    again = client.post(f"/api/capture/{sid}/clip", headers=h, json={"start_s": 10, "end_s": 140})
    assert again.json()["status"] == "rewatch" and len(watched) == 1
    detail = client.get(f"/api/sessions/{sid}", headers=h).json()
    assert len(detail["notes"]) == 1 and detail["subject"] == "Mathematics"


def test_bad_links_and_wrong_sessions_are_refused(client, watched):
    h = _student(client, "link.two@example.com")
    assert _start(client, h, "https://example.com/video").status_code == 422
    screen = client.post("/api/sessions", headers=h, json={}).json()["id"]
    assert client.post(f"/api/capture/{screen}/clip", headers=h, json={"start_s": 0, "end_s": 100}).status_code == 409


def test_captions_stand_in_when_the_video_model_is_down(client, monkeypatch):
    def down(*a, **k):
        raise LLMUnavailable("busy")

    monkeypatch.setattr(link_lecture, "available", lambda: True)
    monkeypatch.setattr(link_lecture, "_watch", down)
    monkeypatch.setattr(youtube, "title", lambda vid: None)
    monkeypatch.setattr(youtube, "caption_window", lambda vid, pos, span=300: "the teacher explains Newton's second law " * 10)
    monkeypatch.setattr(ai, "speech_notes", lambda *a, **k: {"topic": "Newton's laws", "notes_md": "- $F = ma$", "source": "ai"})
    h = _student(client, "link.three@example.com")
    sid = _start(client, h).json()["id"]
    r = client.post(f"/api/capture/{sid}/clip", headers=h, json={"start_s": 0, "end_s": 120}).json()
    assert r["status"] == "created" and r["note"]["engine"] == "captions"
