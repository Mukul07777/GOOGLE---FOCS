"""Study rooms 3.0: playback-speed sync, the doubt board, shared board notes, and the leaderboard."""
from tests.conftest import board_png


def _register(client, email: str, name: str) -> tuple[dict, str]:
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": name, "password": "correct-horse-1",
                                                 "exam_target": "jee"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, token


def _until(ws, kind, limit=30, **match):
    for _ in range(limit):
        msg = ws.receive_json()
        if msg["type"] == kind and all(msg.get(k) == v for k, v in match.items()):
            return msg
    raise AssertionError(f"no {kind} message")


def _room(client, monkeypatch, host):
    from app.services import youtube

    monkeypatch.setattr(youtube, "title", lambda vid: "Rotational Motion | Class 11")
    monkeypatch.setattr(youtube, "has_captions", lambda vid: False)
    return client.post("/api/rooms", headers=host, json={"name": "Night owls", "topic": "Torque and angular momentum"}).json()["code"]


def test_room_speed_sync_and_doubt_board(client, monkeypatch):
    host, host_token = _register(client, "rooms3.host@example.com", "Asha Verma")
    member, member_token = _register(client, "rooms3.member@example.com", "Ravi Kumar")
    code = _room(client, monkeypatch, host)

    with client.websocket_connect(f"/api/rooms/ws/{code}?token={host_token}") as a, \
         client.websocket_connect(f"/api/rooms/ws/{code}?token={member_token}") as b:
        _until(a, "welcome")
        _until(b, "welcome")

        # the host's playback speed reaches everyone; unsupported speeds are ignored
        a.send_json({"type": "video", "action": "load", "url": "https://youtu.be/dQw4w9WgXcQ"})
        _until(b, "video")
        a.send_json({"type": "video", "action": "play", "position": 10, "rate": 1.5})
        v = _until(b, "video", reason="play")["video"]
        assert v["playing"] and v["rate"] == 1.5
        a.send_json({"type": "video", "action": "rate", "rate": 3.0})
        assert _until(b, "video", reason="rate")["video"]["rate"] == 1.5

        # a doubt carries its video timestamp, collects "me too" votes and replies
        b.send_json({"type": "chat", "text": "Why is torque a vector?", "kind": "doubt"})
        doubt = _until(a, "chat")
        assert doubt["kind"] == "doubt" and doubt["votes"] == [] and doubt["video_at"] is not None and doubt["video_at"] >= 10
        a.send_json({"type": "vote", "id": doubt["id"]})
        assert len(_until(b, "doubt")["doubt"]["votes"]) == 1
        a.send_json({"type": "vote", "id": doubt["id"]})  # toggles off
        assert _until(b, "doubt")["doubt"]["votes"] == []
        a.send_json({"type": "reply", "id": doubt["id"], "text": "Because it has a direction: the axis of rotation."})
        reply = _until(b, "doubt")["doubt"]["replies"][0]

        # only the asker (or host) can accept; the helper earns points
        a.send_json({"type": "resolve", "id": "nope"})
        b.send_json({"type": "accept", "id": doubt["id"], "reply_id": reply["id"]})
        board = _until(a, "leaderboard")["leaderboard"]
        assert board[0]["name"] == "Asha Verma" and board[0]["points"] == 5 and board[0]["helped"] == 1
        done = _until(a, "doubt")["doubt"]
        assert done["resolved"] and done["replies"][0]["accepted"]

    # "Ask Focs" can answer a specific doubt
    r = client.post(f"/api/rooms/{code}/ask", headers=member, json={"question": "Why is torque a vector?", "doubt_id": doubt["id"]})
    assert r.status_code == 200, r.text


def test_room_shared_board_notes(client, monkeypatch):
    host, host_token = _register(client, "notes.host@example.com", "Meera Iyer")
    member, member_token = _register(client, "notes.member@example.com", "Kabir Singh")
    code = _room(client, monkeypatch, host)

    with client.websocket_connect(f"/api/rooms/ws/{code}?token={host_token}") as a, \
         client.websocket_connect(f"/api/rooms/ws/{code}?token={member_token}") as b:
        _until(a, "welcome")
        _until(b, "welcome")
        started = client.post(f"/api/rooms/{code}/notes/start", headers=member)
        assert started.status_code == 200, started.text
        assert _until(a, "note_taker")["note_taker"]["name"] == "Kabir Singh"
        # one note taker at a time; the host may take over
        assert client.post(f"/api/rooms/{code}/notes/start", headers=host).status_code == 409

        img = board_png(["Torque tau = r x F", "Angular momentum L = I w", "dL/dt = tau"])
        r = client.post(f"/api/capture/{started.json()['session_id']}/frame", headers=member,
                        files={"frame": ("f.png", img, "image/png")})
        assert r.status_code == 200 and r.json()["status"] == "created", r.text
        live = _until(a, "note")
        assert live["status"] == "created" and live["by"] == "Kabir Singh" and live["note"]["ai_notes"]

        taken = client.post(f"/api/rooms/{code}/notes/start", headers=host, json={"take_over": True})
        assert taken.status_code == 200
        for _ in range(10):  # skip the earlier "Kabir is taking notes" message still queued for b
            if _until(b, "note_taker")["note_taker"]["name"] == "Meera Iyer":
                break
        else:
            raise AssertionError("take-over was not broadcast")

    notes = client.get(f"/api/rooms/{code}/notes", headers=host).json()
    assert len(notes) == 1 and notes[0]["topic"]
    saved = client.post(f"/api/rooms/{code}/notes/save", headers=host)
    assert saved.status_code == 201 and saved.json()["notes"] == 1
    mine = client.get(f"/api/sessions/{saved.json()['session_id']}", headers=host).json()
    assert mine["title"].endswith("(room notes)") and len(mine["notes"]) == 1
    # the room session never becomes the note taker's "live lecture"
    assert client.get("/api/sessions/active", headers=member).json() is None
    assert client.post(f"/api/rooms/{code}/notes/stop", headers=host).status_code == 204
    # once the host closes the room, everyone is still offered the notes
    assert client.post(f"/api/rooms/{code}/close", headers=host).status_code == 204
    after = client.post(f"/api/rooms/{code}/notes/save", headers=member)
    assert after.status_code == 201 and after.json()["notes"] == 1


def test_leaderboard_week_and_opt_out(client):
    h, _ = _register(client, "lb.one@example.com", "Priya Nair")
    for ok in (True, True, False):
        client.post("/api/quiz/attempt", headers=h, json={"question": "q", "q_type": "mcq", "correct": ok, "subject": "Physics"})
    board = client.get("/api/leaderboard?period=week", headers=h).json()
    me = board["me"]
    assert me["name"] == "Priya N." and me["correct"] == 2 and me["answered"] == 3 and me["xp"] == 22 and me["rank"] >= 1
    assert any(r["user_id"] == me["user_id"] for r in board["top"])

    assert client.patch("/api/auth/me", headers=h, json={"show_on_leaderboard": False}).json()["show_on_leaderboard"] is False
    hidden = client.get("/api/leaderboard?period=all&scope=everyone", headers=h).json()
    assert hidden["hidden"] is True and hidden["me"] is None
    assert all(r["name"] != "Priya N." for r in hidden["top"])


def test_doubt_about_one_board_in_hinglish(client):
    h, _ = _register(client, "hinglish@example.com", "Rohan Das")
    s = client.post("/api/sessions", headers=h, json={"title": "Waves"}).json()
    img = board_png(["Wave speed v = f lambda", "Frequency f = 1/T"])
    note = client.post(f"/api/capture/{s['id']}/frame", headers=h, files={"frame": ("f.png", img, "image/png")}).json()["note"]
    r = client.post("/api/companion/ask", headers=h, json={"question": "Isko simple mein samjhao", "session_id": s["id"],
                                                           "note_id": note["id"], "mode": "hinglish", "history": []})
    assert r.status_code == 200 and r.json()["answer"]
    for mode in ("steps", "simple", "socratic", "explain"):
        assert client.post("/api/companion/ask", headers=h, json={"question": "v = f lambda?", "mode": mode, "history": []}).status_code == 200
    # someone else's board can't be used as context
    other, _ = _register(client, "hinglish2@example.com", "Neha Rao")
    r = client.post("/api/companion/ask", headers=other, json={"question": "x", "note_id": note["id"], "mode": "explain", "history": []})
    assert r.status_code == 404


def test_room_timer_pause_right_after_start_reads_as_paused(client):
    _, token = _register(client, "timer.host@example.com", "Tara Joshi")
    host = {"Authorization": f"Bearer {token}"}
    code = client.post("/api/rooms", headers=host, json={"name": "Focus"}).json()["code"]
    with client.websocket_connect(f"/api/rooms/ws/{code}?token={token}") as ws:
        _until(ws, "welcome")
        ws.send_json({"type": "timer", "action": "start", "minutes": 25, "mode": "focus"})
        assert _until(ws, "timer")["timer"]["running"]
        ws.send_json({"type": "timer", "action": "pause"})
        t = _until(ws, "timer")["timer"]
        assert not t["running"] and t["paused"]  # shows as paused, not as a fresh timer
        ws.send_json({"type": "timer", "action": "reset"})
        assert _until(ws, "timer")["timer"]["paused"] is False
