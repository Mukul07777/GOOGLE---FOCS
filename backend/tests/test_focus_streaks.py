"""Focus time from heartbeats, GitHub-style year heatmap, streaks with weekly freezes, silent token refresh."""
from datetime import date, timedelta

from app.services import streaks


def _days(*ds: str) -> set[date]:
    return {date.fromisoformat(d) for d in ds}


def test_streak_freeze_bridges_one_missed_day():
    # Mon 6 Oct .. Fri 10 Oct studied, Sat 11 missed, Sunday morning 12 Oct not studied yet
    active = _days("2025-10-06", "2025-10-07", "2025-10-08", "2025-10-09", "2025-10-10")
    s = streaks.current_streak(active, date(2025, 10, 12))
    assert s["streak"] == 5 and s["at_risk"] and not s["active_today"] and s["frozen_days"] == 1

    s = streaks.current_streak(active | _days("2025-10-12"), date(2025, 10, 12))
    assert s["streak"] == 6 and not s["at_risk"]

    # two missed days in a row always break it
    assert streaks.current_streak(active, date(2025, 10, 13))["streak"] == 0


def test_only_one_freeze_per_week():
    # missed Tue and Thu of the same week: the second gap breaks the streak
    active = _days("2025-10-06", "2025-10-08", "2025-10-10")
    s = streaks.current_streak(active, date(2025, 10, 10))
    assert s["streak"] == 2 and s["freezes_left"] == 0
    assert streaks.best_streak(active) == 2
    # gaps in different weeks each get their own freeze
    assert streaks.best_streak(_days("2025-10-09", "2025-10-11", "2025-10-12", "2025-10-14")) == 4


def test_heartbeats_become_focus_time(client):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": "focus@example.com", "full_name": "Ishaan Rao",
                                                 "password": "correct-horse-1", "exam_target": "jee"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    from app.core.database import SessionLocal
    from app.models.study_day import StudyDay

    for activity in ("mock", "mock", "flashcards"):
        assert client.post("/api/analytics/heartbeat", headers=h, json={"activity": activity, "tz_offset": 330}).status_code == 204
        with SessionLocal() as db:  # pretend a minute passed (the server ignores beats < 50 s apart)
            for row in db.query(StudyDay).all():
                row.last_beat_at = row.last_beat_at - timedelta(minutes=1)
            db.commit()
    # a second open tab beating at the same moment adds nothing
    client.post("/api/analytics/heartbeat", headers=h, json={"activity": "mock", "tz_offset": 330})
    assert client.post("/api/analytics/heartbeat", headers=h, json={"activity": "mock", "tz_offset": 330}).status_code == 204
    assert client.post("/api/analytics/heartbeat", headers=h, json={"activity": "gaming", "tz_offset": 330}).status_code == 422

    o = client.get("/api/analytics/overview?tz_offset=330", headers=h).json()
    assert o["today_minutes"] == 4 and o["today_by_activity"] == {"mock": 3, "flashcards": 1}
    assert o["active_today"] and o["streak"] == 1 and not o["streak_at_risk"] and o["study_days_year"] == 1
    assert len(o["heatmap"]) == 7 * 53 and o["heatmap"][-1]["minutes"] == 4 and o["heatmap"][-1]["active"]

    # signed-in students get a fresh token instead of being logged out after 7 days
    fresh = client.post("/api/auth/refresh", headers=h)
    assert fresh.status_code == 200 and fresh.json()["access_token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {fresh.json()['access_token']}"}).status_code == 200
    assert client.get("/api/auth/export", headers=h).json()["focus_time"][0]["minutes"] == 4
