"""Edge cases from the pre-event hard test, and the word-by-word doubt answer."""
import json

from app.models.doubt import Doubt
from app.services import ai
from app.services.llm import LLMUnavailable, llm


def _events(text: str) -> list[tuple[str, object]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_id_past_the_database_range_is_404_not_500(client, auth):
    for path in ("/api/notes/99999999999999999999", "/api/classes/99999999999999999999", "/api/sessions/99999999999999999999"):
        r = client.get(path, headers=auth)
        assert r.status_code == 404, (path, r.status_code)


def test_rejected_values_are_never_echoed_back(client):
    r = client.post("/api/auth/register", json={"email": "leak@example.com", "password": "s3cr", "full_name": "",
                                                 "accepted_terms": True})
    assert r.status_code == 422
    assert "s3cr" not in r.text and all("input" not in e for e in r.json()["detail"])
    assert any(e["type"] == "string_too_short" for e in r.json()["detail"])  # the page still learns what was wrong


def test_stream_sends_pieces_then_the_saved_answer(client, auth, monkeypatch):
    monkeypatch.setattr(type(llm), "stream", lambda self, messages, **k: iter(["Momentum is ", "$p = mv$", "."]))
    r = client.post("/api/companion/ask/stream", headers=auth, json={"question": "What is momentum?"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = _events(r.text)
    assert [v for k, v in events if k == "delta"] == ["Momentum is ", "$p = mv$", "."]
    kind, done = events[-1]
    assert kind == "done" and done["source"] == "ai" and done["answer"] == "Momentum is $p = mv$." and done["id"]
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        assert db.get(Doubt, done["id"]).answer == done["answer"]


def test_stream_falls_back_when_no_model_can_stream(client, auth, monkeypatch):
    def broken(self, messages, **k):
        raise LLMUnavailable("down")
        yield  # pragma: no cover - makes this a generator

    monkeypatch.setattr(type(llm), "stream", broken)
    monkeypatch.setattr(ai, "companion", lambda *a, **k: {"answer": "from your notes", "source": "offline"})
    r = client.post("/api/companion/ask/stream", headers=auth, json={"question": "What is momentum?"})
    assert _events(r.text) == [("done", {"id": None, "answer": "from your notes", "source": "offline"})]


def test_stream_checks_ownership_before_opening(client, auth):
    r = client.post("/api/companion/ask/stream", headers=auth, json={"question": "q", "session_id": 987654})
    assert r.status_code == 404
