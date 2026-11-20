"""End-to-end API flow in offline mode (no LLM): the whole product must work without a key."""
from tests.conftest import board_png


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["llm"]["available"] is False


def test_auth_flow(client, auth):
    assert client.get("/api/auth/me").status_code == 401
    me = client.get("/api/auth/me", headers=auth).json()
    assert me["email"] == "asha@example.com" and me["plan"] == "free"
    dup = client.post("/api/auth/register", json={"accepted_terms": True, "email": "ASHA@example.com", "full_name": "x", "password": "12345678"})
    assert dup.status_code == 409
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": "wrong-pass"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "Asha@Example.com", "password": "correct-horse-1"}).status_code == 200
    r = client.patch("/api/auth/me", headers=auth, json={"exam_target": "neet", "daily_goal_min": 90})
    assert r.json()["exam_target"] == "neet" and r.json()["daily_goal_min"] == 90
    client.patch("/api/auth/me", headers=auth, json={"exam_target": "jee"})


def test_live_session_flow(client, auth):
    s = client.post("/api/sessions", headers=auth, json={"title": "Laws of Motion", "source": "screen"}).json()
    sid = s["id"]
    assert s["is_active"] is True

    board = board_png(["Newton's Laws of Motion", "F = ma", "Momentum p = mv", "Impulse J = F x t"])
    r = client.post(f"/api/capture/{sid}/frame", headers=auth, files={"frame": ("f.png", board, "image/png")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "created", body
    assert "Motion" in body["ocr"]["text"]
    note = body["note"]
    assert note["has_image"] and note["ai_notes"]

    # identical frame → skipped by perceptual hash before OCR runs
    again = client.post(f"/api/capture/{sid}/frame", headers=auth, files={"frame": ("f.png", board, "image/png")})
    assert again.json()["status"] == "unchanged"

    # teacher keeps writing on the same board → the existing note grows instead of duplicating
    grown = board_png(["Newton's Laws of Motion", "F = ma", "Momentum p = mv", "Impulse J = F x t",
                       "Newton's third law: action = reaction"])
    r = client.post(f"/api/capture/{sid}/frame", headers=auth, files={"frame": ("f.png", grown, "image/png")})
    assert r.json()["status"] == "growing", r.json()["status"]  # held while the teacher is still writing
    r = client.post(f"/api/capture/{sid}/settle", headers=auth)  # the board stopped changing
    assert r.json()["status"] == "updated" and "third law" in r.json()["note"]["ocr_raw"].lower(), r.json()

    img = client.get(f"/api/notes/{note['id']}/image", headers=auth)
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"

    notes = client.get("/api/notes", headers=auth, params={"q": "Momentum"}).json()
    assert notes["total"] >= 1

    detail = client.get(f"/api/sessions/{sid}", headers=auth).json()
    assert len(detail["notes"]) == 1

    md = client.get(f"/api/sessions/{sid}/export", headers=auth)
    assert md.status_code == 200 and "Laws of Motion" in md.text

    ask = client.post("/api/companion/ask", headers=auth, json={"question": "What is momentum?", "session_id": sid})
    assert ask.status_code == 200 and ask.json()["source"] == "offline"

    end = client.post(f"/api/sessions/{sid}/end", headers=auth).json()
    assert end["session"]["is_active"] is False and end["summary_md"]
    closed = client.post(f"/api/capture/{sid}/frame", headers=auth, files={"frame": ("f.png", board, "image/png")})
    assert closed.status_code == 409


def test_photo_upload_creates_session(client, auth):
    photo = board_png(["Chemical Equilibrium", "Kc = [C][D] / [A][B]", "Le Chatelier principle"], dark=False)
    r = client.post("/api/capture/photo", headers=auth, files={"photo": ("p.png", photo, "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "created" and r.json()["session_id"]


def test_rejects_non_images(client, auth):
    r = client.post("/api/capture/photo", headers=auth, files={"photo": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 415


def test_practice_and_flashcards(client, auth):
    text = ("Momentum is the product of mass and velocity.\nImpulse equals change in momentum.\n"
            "Newton's second law states that force equals rate of change of momentum.\n"
            "F = ma\np = mv\nFriction opposes relative motion between surfaces.")
    quiz = client.post("/api/quiz/generate", headers=auth, json={"text": text, "n_mcq": 3, "n_tf": 2}).json()
    assert quiz["source"] == "offline" and quiz["mcq"]
    for q in quiz["mcq"]:
        assert len(q["options"]) == 4 and 0 <= q["answer_index"] < 4

    wrong = client.post("/api/quiz/attempt", headers=auth, json={"question": quiz["mcq"][0]["q"], "q_type": "mcq",
                                                                  "correct": False, "topic": "Momentum", "subject": "Physics"})
    assert wrong.json()["needs_redo"] is True
    redo = client.get("/api/quiz/redo", headers=auth).json()
    assert redo and client.post(f"/api/quiz/redo/{redo[0]['id']}/done", headers=auth).status_code == 204

    ev = client.post("/api/quiz/evaluate", headers=auth, json={"question": "Define momentum", "student_answer":
                     "momentum is mass times velocity", "key_points": ["mass times velocity", "vector quantity"]}).json()
    assert 0 <= ev["score"] <= 10

    card = client.post("/api/flashcards", headers=auth, json={"front": "p = ?", "back": "mv"}).json()
    assert card["intervals"]["good"] == "1d"
    reviewed = client.post(f"/api/flashcards/{card['id']}/review", headers=auth, json={"grade": "good"}).json()
    assert reviewed["repetitions"] == 1 and reviewed["interval_days"] == 1
    again = client.post(f"/api/flashcards/{card['id']}/review", headers=auth, json={"grade": "again"}).json()
    assert again["repetitions"] == 0 and again["lapses"] == 1
    stats = client.get("/api/flashcards/stats", headers=auth).json()
    assert stats["total"] >= 1


def test_analytics(client, auth):
    a = client.get("/api/analytics/overview", headers=auth, params={"tz_offset": 330}).json()
    assert a["streak"] >= 1
    assert len(a["heatmap"]) == 7 * 53 and len(a["week"]) == 7
    assert a["totals"]["notes"] >= 2


def test_rooms_websocket(client, auth):
    room = client.post("/api/rooms", headers=auth, json={"name": "Physics grind"}).json()
    code = room["code"]
    assert client.post("/api/rooms/join", headers=auth, json={"code": code.lower()}).status_code == 200
    token = auth["Authorization"].split()[1]
    with client.websocket_connect(f"/api/rooms/ws/{code}?token={token}") as ws:
        assert ws.receive_json()["type"] == "welcome"
        kinds = {ws.receive_json()["type"] for _ in range(2)}
        assert kinds == {"presence", "system"}
        ws.send_json({"type": "chat", "text": "Starting chapter 5"})
        assert ws.receive_json()["text"] == "Starting chapter 5"
        ws.send_json({"type": "timer", "action": "start", "minutes": 25})
        timer = ws.receive_json()["timer"]
        assert timer["running"] and 1490 <= timer["remaining"] <= 1500


def test_room_socket_rejects_bad_token(client, auth):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    code = client.post("/api/rooms", headers=auth, json={"name": "x"}).json()["code"]
    with pytest.raises(WebSocketDisconnect) as bad_token:
        with client.websocket_connect(f"/api/rooms/ws/{code}?token=bogus") as ws:
            ws.receive_json()
    assert bad_token.value.code == 4401  # a real close code, so the browser stops reconnecting
    token = auth["Authorization"].split()[1]
    with pytest.raises(WebSocketDisconnect) as missing:
        with client.websocket_connect(f"/api/rooms/ws/NOROOM?token={token}") as ws:
            ws.receive_json()
    assert missing.value.code == 4404


def test_ocr_lab(client, auth):
    info = client.get("/api/ocr/model", headers=auth).json()
    assert info["engines"]
    img = board_png(["Work Energy Theorem", "W = F . s"], dark=False)
    r = client.post("/api/ocr/run", headers=auth, files={"image": ("b.png", img, "image/png")}, data={"engine": "auto"})
    assert r.status_code == 200
    assert "Energy" in r.json()["text"]


def test_billing(client, auth):
    assert len(client.get("/api/billing/plans").json()["plans"]) == 3
    assert client.post("/api/billing/dev-upgrade", headers=auth, json={"plan": "pro"}).json()["plan"] == "pro"


def _until(ws, kind, limit=20):
    for _ in range(limit):
        msg = ws.receive_json()
        if msg["type"] == kind:
            return msg
    raise AssertionError(f"no {kind} message")


def test_room_watch_party_quiz_and_ask(client, auth, monkeypatch):
    from app.services import youtube

    monkeypatch.setattr(youtube, "title", lambda vid: "Newton's Laws of Motion | Class 11 Physics")
    monkeypatch.setattr(youtube, "has_captions", lambda vid: False)
    room = client.post("/api/rooms", headers=auth, json={
        "name": "Physics watch party", "topic": "Newton's laws: inertia, momentum, force, acceleration and friction"}).json()
    code, token = room["code"], auth["Authorization"].split()[1]
    assert client.post("/api/rooms", headers=auth, json={"name": "x", "video_url": "https://example.com/v.mp4"}).status_code == 422

    with client.websocket_connect(f"/api/rooms/ws/{code}?token={token}") as ws:
        welcome = _until(ws, "welcome")
        assert welcome["you"]["host"] is True and welcome["video"]["id"] is None

        ws.send_json({"type": "video", "action": "load", "url": "https://youtu.be/dQw4w9WgXcQ"})
        v = _until(ws, "video")["video"]
        assert v["id"] == "dQw4w9WgXcQ" and v["title"].startswith("Newton") and v["playing"] is False
        ws.send_json({"type": "video", "action": "play", "position": 42})
        v = _until(ws, "video")["video"]
        assert v["playing"] is True and v["position"] == 42

        ws.send_json({"type": "chat", "text": "Why is inertia not a force?", "kind": "doubt"})
        assert _until(ws, "chat")["kind"] == "doubt"

        r = client.post(f"/api/rooms/{code}/quiz", headers=auth, json={"seconds": 15})
        assert r.status_code == 200, r.text
        paused = _until(ws, "video")
        assert paused["reason"] == "quiz" and paused["video"]["playing"] is False
        quiz = _until(ws, "quiz")["quiz"]
        assert len(quiz["options"]) == 4 and "answer_index" not in quiz
        ws.send_json({"type": "answer", "quiz_id": quiz["id"], "choice": 0})
        result = _until(ws, "quiz_result")["result"]  # only member answered -> revealed immediately
        assert result["answered"] == 1 and sum(result["counts"]) == 1 and result["leaderboard"][0]["answered"] == 1

        r = client.post(f"/api/rooms/{code}/ask", headers=auth, json={"question": "What is inertia?"})
        assert r.status_code == 200
        ai_msg = _until(ws, "ai")
        assert ai_msg["question"] == "What is inertia?" and ai_msg["answer"]

    redo = client.get("/api/quiz/redo", headers=auth).json()
    assert any(item["q_type"] == "room" for item in redo) or result["correct_names"]


def test_room_video_control_is_host_only(client, auth):
    code = client.post("/api/rooms", headers=auth, json={"name": "host only"}).json()["code"]
    other = client.post("/api/auth/register", json={"accepted_terms": True, "email": "ravi@example.com", "full_name": "Ravi", "password": "another-pass-1"}).json()
    with client.websocket_connect(f"/api/rooms/ws/{code}?token={other['access_token']}") as ws:
        assert _until(ws, "welcome")["you"]["host"] is False
        ws.send_json({"type": "video", "action": "load", "url": "https://youtu.be/dQw4w9WgXcQ"})
        ws.send_json({"type": "ping"})
        seen = []
        while not seen or seen[-1] != "pong":
            seen.append(ws.receive_json()["type"])
        assert "video" not in seen  # the non-host's load was ignored
    r = client.post(f"/api/rooms/{code}/quiz", headers={"Authorization": f"Bearer {other['access_token']}"}, json={})
    assert r.status_code == 403


def test_session_pop_quiz(client, auth):
    sid = client.post("/api/sessions", headers=auth, json={"title": "Kinematics"}).json()["id"]
    assert client.post(f"/api/sessions/{sid}/pop-quiz", headers=auth).status_code == 409  # nothing captured yet
    board = board_png(["Kinematics equations", "velocity v = u + at", "displacement s = ut + half at squared",
                       "acceleration is the rate of change of velocity"])
    r = client.post(f"/api/capture/{sid}/frame", headers=auth, files={"frame": ("f.png", board, "image/png")})
    assert r.json()["status"] == "created"
    q = client.post(f"/api/sessions/{sid}/pop-quiz", headers=auth).json()
    assert len(q["options"]) == 4 and 0 <= q["answer_index"] < 4 and q["topic"]
    assert client.post("/api/quiz/attempt", headers=auth, json={"question": q["question"], "q_type": "pop", "correct": True}).status_code == 201
