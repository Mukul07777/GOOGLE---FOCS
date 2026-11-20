"""The return lane: a room's confusion reaches its host, pinned to the board, and never names a student."""
import time

from tests.test_rooms_v3 import _register, _room, _until


def _boards(code: str) -> list[int]:
    """Two boards written for the room, as a note taker's capture would leave them."""
    from app.core.database import SessionLocal
    from app.models.note import Note
    from app.models.room import Room
    from app.models.session import StudySession

    with SessionLocal() as db:
        room = db.query(Room).filter(Room.code == code).one()
        session = StudySession(user_id=room.host_id, source="room", room_code=code, is_active=False, title="Projectiles")
        db.add(session)
        db.flush()
        a = Note(session_id=session.id, topic="Horizontal launch", ai_notes="## Horizontal launch\n- x = u t, y = g t^2 / 2")
        db.add(a)
        db.flush()
        b = Note(session_id=session.id, topic="Range of a projectile", ai_notes="## Range of a projectile\n- R = u^2 sin 2θ / g")
        db.add(b)
        db.commit()
        return [a.id, b.id]


def _report(client, code, headers, until=lambda r: True):
    for _ in range(40):
        r = client.get(f"/api/rooms/{code}/report", headers=headers)
        if r.status_code != 200 or until(r.json()):
            return r
        time.sleep(0.05)
    return r


def test_lost_taps_reach_only_the_host_pinned_to_the_board(client, monkeypatch):
    from app.services import ai

    host, host_token = _register(client, "confusion.host@example.com", "Meera Teacher")
    student, student_token = _register(client, "confusion.student@example.com", "Kabir Student")
    code = _room(client, monkeypatch, host)
    first, second = _boards(code)
    monkeypatch.setattr(ai, "room_question", lambda *a, **k: {
        "question": "What is the range on level ground?", "options": ["u²/g", "u² sin 2θ / g", "u sinθ / g", "2u/g"],
        "answer_index": 1, "explanation": "R = u² sin 2θ / g.", "source": "ai"})
    monkeypatch.setattr(ai, "companion", lambda *a, **k: {"answer": "Split the motion into x and y...", "source": "ai"})

    with client.websocket_connect(f"/api/rooms/ws/{code}?token={host_token}") as h, \
         client.websocket_connect(f"/api/rooms/ws/{code}?token={student_token}") as s:
        assert _until(h, "welcome")["confusion"] == {"last_minute": 0, "total": 0, "board": None}
        assert _until(s, "welcome")["confusion"] is None  # the meter is the host's alone

        # an anonymous "I'm lost": the student is told which board it was pinned to, the host sees the count
        s.send_json({"type": "lost"})
        ack = _until(s, "lost_ack")
        assert ack["ok"] and ack["board"]["note_id"] == second and ack["board"]["number"] == 2
        meter = _until(h, "confusion")["meter"]
        assert meter["last_minute"] == 1 and meter["board"]["topic"] == "Range of a projectile" and meter["board"]["count"] == 1
        assert "Kabir" not in str(meter)

        # one tap per half minute
        s.send_json({"type": "lost"})
        again = _until(s, "lost_ack")
        assert not again["ok"] and again["wait"] > 0

        # the host can't tap their own meter
        h.send_json({"type": "lost"})
        h.send_json({"type": "ping"})
        _until(h, "pong")

        # a doubt is pinned to the board too, and its votes follow it
        s.send_json({"type": "chat", "text": "Why sin 2θ and not sin θ?", "kind": "doubt"})
        doubt = _until(h, "chat")
        h.send_json({"type": "vote", "id": doubt["id"]})
        _until(s, "doubt")

        # a check on one board, straight from the map: a confidently wrong answer is marked as such
        r = client.post(f"/api/rooms/{code}/quiz", headers=host, json={"seconds": 30, "note_id": second})
        assert r.status_code == 200, r.text
        quiz = _until(s, "quiz")["quiz"]
        s.send_json({"type": "answer", "quiz_id": quiz["id"], "choice": 0, "confidence": "sure"})
        h.send_json({"type": "answer", "quiz_id": quiz["id"], "choice": 1, "confidence": "unsure"})
        _until(s, "quiz_result")

        # the recap goes to the whole room
        r = client.post(f"/api/rooms/{code}/recap", headers=host, json={"note_id": second})
        assert r.status_code == 200, r.text
        assert _until(s, "ai")["question"].startswith("Recap of board 2")
        assert client.post(f"/api/rooms/{code}/recap", headers=student, json={"note_id": second}).status_code == 403

    report = _report(client, code, host, until=lambda d: d["totals"]["quizzes"] == 1).json()
    assert report["totals"] == {"lost": 1, "wrong": 1, "doubts": 1, "quizzes": 1, "boards": 2}
    top = report["boards"][0]
    assert top["note_id"] == second and top["number"] == 2
    assert (top["lost"], top["wrong"], top["doubts"], top["sure_wrong"], top["score"]) == (1, 1, 1, 1, 3)
    assert all(b["note_id"] != first for b in report["boards"])  # a board nobody struggled with isn't listed
    q = report["quizzes"][0]
    assert q["counts"] == [1, 1, 0, 0] and q["correct"] == 1 and q["board"] == 2
    assert report["doubts"] == [{"text": "Why sin 2θ and not sin θ?", "votes": 1, "resolved": False, "board": 2}]
    assert sum(m["lost"] + m["wrong"] + m["doubts"] for m in report["timeline"]) == 3
    assert "Kabir" not in str(report) and "confusion.student" not in str(report)

    # only the host sees it, open or closed
    assert client.get(f"/api/rooms/{code}/report", headers=student).status_code == 404
    client.post(f"/api/rooms/{code}/close", headers=host)
    assert client.get(f"/api/rooms/{code}/report", headers=host).json()["is_active"] is False
