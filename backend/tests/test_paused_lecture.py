"""A paused lecture is not an abandoned one: heartbeats keep it open, an idle-closed one reopens, and a pause is not
lecture time."""
from datetime import timedelta

import pytest

from app.api._common import IDLE_END, session_minutes
from app.core.database import SessionLocal
from app.models._util import utcnow
from app.models.session import StudySession
from app.services import link_lecture, live, youtube


@pytest.fixture(autouse=True)
def _video(monkeypatch):
    monkeypatch.setattr(link_lecture, "available", lambda: True)
    monkeypatch.setattr(link_lecture, "_watch", lambda vid, s, e, p: {
        "lecture": True, "topic": "Identities", "subject": "Mathematics", "board": "x", "notes_md": "## Identities\n- a"})
    monkeypatch.setattr(youtube, "title", lambda vid: "Trig")


def _student(client, email):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Pause Test",
                                                "password": "correct-horse-1", "exam_target": "jee"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _start(client, h):
    r = client.post("/api/sessions", headers=h, json={"source": "link", "video_url": "https://youtu.be/7K1sB05pE0A"})
    sid = r.json()["id"]
    assert client.post(f"/api/capture/{sid}/clip", headers=h, json={"start_s": 0, "end_s": 100}).status_code == 200
    return sid


def _age(sid, minutes, **extra):
    """Pretend `minutes` have passed: start, notes and (when given) heartbeat all move back."""
    d = timedelta(minutes=minutes)
    with SessionLocal() as db:
        s = db.get(StudySession, sid)
        s.started_at -= d
        for n in s.notes:
            n.captured_at -= d
        if s.alive_at:
            s.alive_at -= d
        if s.ended_at:
            s.ended_at -= d
        for k, v in extra.items():
            setattr(s, k, v)
        db.commit()
    live.forget(sid)


def _row(sid):
    with SessionLocal() as db:
        s = db.get(StudySession, sid)
        len(s.notes)
        return s


def _active(client, h):
    return client.get("/api/sessions/active", headers=h).json()


def test_heartbeat_keeps_a_paused_lecture_open(client):
    h = _student(client, "pause.one@example.com")
    sid = _start(client, h)
    _age(sid, 120)
    r = client.post(f"/api/sessions/{sid}/alive", headers=h, json={"paused": True, "paused_for_s": 7000})
    assert r.status_code == 200 and r.json()["active"] and not r.json()["reopened"]
    assert _active(client, h)["id"] == sid
    assert client.post(f"/api/capture/{sid}/clip", headers=h, json={"start_s": 100, "end_s": 200}).status_code == 200


def test_without_heartbeats_it_is_still_closed(client):
    h = _student(client, "pause.two@example.com")
    sid = _start(client, h)
    _age(sid, 120)
    assert _active(client, h) is None
    assert _row(sid).ended_by == "idle"
    _age(sid, 0)
    # a heartbeat older than IDLE_END does not keep it either
    sid2 = _start(client, h)
    client.post(f"/api/sessions/{sid2}/alive", headers=h, json={})
    _age(sid2, 120)
    assert _active(client, h) is None


def test_heartbeat_adds_no_lecture_time_and_the_pause_is_not_duration(client):
    h = _student(client, "pause.three@example.com")
    sid = _start(client, h)
    with SessionLocal() as db:
        from app.models.user import User
        before = db.scalar(__import__("sqlalchemy").select(User.lecture_day_seconds).where(User.email == "pause.three@example.com"))
    _age(sid, 120)
    client.post(f"/api/sessions/{sid}/alive", headers=h, json={"paused": True, "paused_for_s": 6900})
    with SessionLocal() as db:
        after = db.scalar(__import__("sqlalchemy").select(User.lecture_day_seconds).where(User.email == "pause.three@example.com"))
    assert (after or 0) == (before or 0)
    assert live.idle_seconds(sid) is None  # the heartbeat did not touch the lecture clock
    assert session_minutes(_row(sid)) < 25  # 120 min since start, 115 of them paused
    client.post(f"/api/sessions/{sid}/end", headers=h)
    assert session_minutes(_row(sid)) < 25


def test_an_idle_closed_lecture_reopens_by_heartbeat_and_by_capture(client):
    h = _student(client, "pause.four@example.com")
    sid = _start(client, h)
    _age(sid, 120)
    assert _active(client, h) is None
    r = client.post(f"/api/sessions/{sid}/alive", headers=h, json={})
    assert r.json() == {"active": True, "reopened": True, "paused_for_s": 7200.0}  # how long it sat closed
    row = _row(sid)
    assert row.is_active and row.ended_at is None and row.ended_by is None and len(row.notes) == 1
    # closed again, this time resumed by a clip
    _age(sid, 120)
    assert _active(client, h) is None
    c = client.post(f"/api/capture/{sid}/clip", headers=h, json={"start_s": 100, "end_s": 200})
    assert c.status_code == 200 and _row(sid).is_active
    assert len(_row(sid).notes) == 2


def test_ended_and_replaced_lectures_do_not_reopen(client):
    h = _student(client, "pause.five@example.com")
    sid = _start(client, h)
    client.post(f"/api/sessions/{sid}/end", headers=h)
    assert client.post(f"/api/sessions/{sid}/alive", headers=h, json={}).json() == {"active": False, "reopened": False, "paused_for_s": 0.0}
    c = client.post(f"/api/capture/{sid}/clip", headers=h, json={"start_s": 100, "end_s": 200})
    assert c.status_code == 409 and "Start a new one" in c.json()["detail"]
    old = _start(client, h)
    new = _start(client, h)  # starting a lecture closes the old one as replaced
    assert _row(old).ended_by == "replaced"
    assert client.post(f"/api/sessions/{old}/alive", headers=h, json={}).json()["active"] is False
    assert _row(new).is_active


def test_a_newer_lecture_blocks_reopening(client):
    h = _student(client, "pause.six@example.com")
    sid = _start(client, h)
    _age(sid, 120)
    assert _active(client, h) is None
    client.post("/api/sessions", headers=h, json={})  # a newer one, now closed as idle or left running
    assert client.post(f"/api/sessions/{sid}/alive", headers=h, json={}).json()["active"] is False


def test_the_twelve_hour_limit(client):
    h = _student(client, "pause.seven@example.com")
    sid = _start(client, h)
    _age(sid, 13 * 60)
    assert _active(client, h) is None
    assert client.post(f"/api/sessions/{sid}/alive", headers=h, json={}).json()["active"] is False
    sid2 = _start(client, h)
    _age(sid2, 11 * 60)
    assert _active(client, h) is None
    assert client.post(f"/api/sessions/{sid2}/alive", headers=h, json={}).json()["reopened"] is True


def test_another_students_session_is_a_404(client):
    a = _student(client, "pause.eight@example.com")
    b = _student(client, "pause.nine@example.com")
    sid = _start(client, a)
    assert client.post(f"/api/sessions/{sid}/alive", headers=b, json={}).status_code == 404

def test_a_pause_broken_by_the_lecture_is_not_counted_twice(client):
    """Speech or a new board ends the pause on the server; the browser, still seeing a still screen, goes on saying
    "paused since T0". The time before the last heartbeat must not be subtracted again."""
    h = _student(client, "pause.twice@example.com")
    sid = _start(client, h)
    client.post(f"/api/sessions/{sid}/alive", headers=h, json={"paused": True, "paused_for_s": 120})
    with SessionLocal() as db:  # the pause began 2 min ago; the heartbeat before this one was 1 min ago
        s = db.get(StudySession, sid)
        s.pause_since, s.alive_at = utcnow() - timedelta(seconds=120), utcnow() - timedelta(seconds=60)
        db.commit()
    assert client.post(f"/api/capture/{sid}/clip", headers=h, json={"start_s": 100, "end_s": 200}).status_code == 200
    first = _row(sid).paused_s
    assert 115 <= first <= 130 and _row(sid).pause_since is None
    client.post(f"/api/sessions/{sid}/alive", headers=h, json={"paused": True, "paused_for_s": 180})
    since = _row(sid).pause_since
    assert since is not None and (utcnow() - since).total_seconds() < 5  # not back to T0: that stretch was counted
