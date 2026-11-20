"""The demo seed: labelled accounts with a finished lecture, a live class with a confusion map, and Ask a senior."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _login(client, key):
    import seed_demo

    r = client.post("/api/auth/login", json={"email": seed_demo.email(key), "password": "demo-pass-123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_seed_demo_makes_the_whole_demo_and_resets_cleanly(client):
    import seed_demo

    out = seed_demo.seed(client, "demo-pass-123")
    student = _login(client, "student")
    me = client.get("/api/auth/me", headers=student).json()
    assert me["full_name"].startswith("Demo") and me["language"] == "hinglish" and me["plan"] == "pro"
    assert client.get("/api/auth/me", headers=_login(client, "hindi")).json()["language"] == "hi"

    sessions = client.get("/api/sessions", headers=student).json()
    lecture = next(s for s in (sessions if isinstance(sessions, list) else sessions.get("items", [])) if not s.get("is_active"))
    detail = client.get(f"/api/sessions/{lecture['id']}", headers=student).json()
    assert len(detail["notes"]) >= 2

    teacher = _login(client, "teacher")
    report = client.get(f"/api/rooms/{out['room']}/report", headers=teacher).json()
    assert report["totals"]["lost"] == 6 and report["totals"]["doubts"] == 2 and report["totals"]["quizzes"] == 1
    assert report["boards"][0]["number"] == 2  # the board that lost the room comes first

    asked = client.get("/api/campus/ask?subject=Physics", headers=student).json()["questions"]
    demo = next(q for q in asked if q["body"].startswith("[Demo]"))
    senior_answer = next(a for a in demo["answers"] if not a.get("ai"))
    assert senior_answer["accepted"] and senior_answer["senior"] == "B.Tech, Sem 5 · verified"

    with pytest.raises(SystemExit):  # never doubles up
        seed_demo.seed(client, "demo-pass-123")
    again = seed_demo.seed(client, "demo-pass-123", reset=True)
    assert again["room"] != out["room"]
    fresh = client.get("/api/sessions", headers=_login(client, "student")).json()
    assert len(fresh if isinstance(fresh, list) else fresh.get("items", [])) == 1  # the old lecture went with the old account
