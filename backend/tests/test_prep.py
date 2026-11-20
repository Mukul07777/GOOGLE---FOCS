"""Prep Hub: the syllabus data, the mentor plan engine and the goal → plan → daily tasks flow."""
from datetime import date, timedelta

import pytest

from app.services import planner, syllabus
from app.services.mock_patterns import SYLLABUS

TODAY = date(2026, 10, 4)


# ---------------------------------------------------------------- syllabus
@pytest.mark.parametrize("exam", syllabus.ENTRANCE)
def test_syllabus_is_well_formed(exam):
    syl = syllabus.get(exam)
    ids = [c.id for c in syl.chapters]
    topics = [t.id for c in syl.chapters for t in c.topics]
    assert len(ids) == len(set(ids)) and len(topics) == len(set(topics))
    govt = exam in syllabus.GOVT  # SSC: no classes, and shorter chapters (a topic can be a single question type)
    for c in syl.chapters:
        assert c.cls in ((0,) if govt else (11, 12)) and c.hours > 0 and c.weight > 0 and len(c.topics) >= (1 if govt else 3), c.name
        assert all(t.id.startswith(c.id + ".") for t in c.topics)
    assert (200 if govt else 1000) < syl.total_hours < 2000  # learning + practice for the whole syllabus, before revision


def test_jee_chapters_match_the_question_bank_and_neet_shares_physics_and_chemistry():
    jee, neet = syllabus.get("jee"), syllabus.get("neet")
    for subject in jee.subjects:
        assert {c.name for c in jee.subject_chapters(subject)} == set(SYLLABUS[subject])  # chapter tests work from the hub
    assert set(SYLLABUS["Biology"]) == {c.name for c in neet.subject_chapters("Biology")}  # and Biology for NEET
    for subject in ("Physics", "Chemistry"):
        assert [c.name for c in neet.subject_chapters(subject)] == [c.name for c in jee.subject_chapters(subject)]
        assert sum(c.hours for c in neet.subject_chapters(subject)) < sum(c.hours for c in jee.subject_chapters(subject))
    assert neet.subjects == ("Physics", "Chemistry", "Biology") and len(neet.subject_chapters("Biology")) >= 30
    assert neet.by_id["chemistry.biomolecules"] and neet.by_id["biology.biomolecules"]  # same name, two subjects


# ---------------------------------------------------------------- exam dates
@pytest.mark.parametrize("track,cls,today,expected", [
    ("jee_main", "11", TODAY, date(2028, 1, 22)),     # two seasons away: session 1
    ("jee_main", "12", TODAY, date(2027, 4, 4)),      # January is under 5 months away: aim at session 2
    ("jee_main", "12", date(2026, 6, 10), date(2027, 1, 22)),
    ("jee_main", "12", date(2027, 2, 1), date(2027, 4, 4)),
    ("neet", "12", TODAY, date(2027, 5, 2)),          # first Sunday of May
    ("neet", "dropper", date(2027, 5, 20), date(2028, 5, 7)),
])
def test_default_exam_dates(track, cls, today, expected):
    assert planner.default_exam_date(track, cls, today) == expected


# ---------------------------------------------------------------- the plan
def _goal(cls="11", wd=4.0, we=7.0, exam="jee", track="jee_main", target="air_10k", today=TODAY):
    return planner.Goal(exam, track, cls, planner.default_exam_date(track, cls, today), target, wd, we)


def test_class_11_plan_follows_school_order_and_leaves_revision_time():
    syl = syllabus.get("jee")
    plan = planner.build(_goal(wd=5, we=8), syl, planner.Progress(), TODAY)
    assert plan["status"] in ("comfortable", "on_track") and not plan["unfinished"]
    assert plan["syllabus_done_on"] < plan["revision_from"] <= plan["exam_date"]
    first = [i["chapter"] for i in plan["weeks"][0]["learn"]]
    assert "Units, Measurements & Errors" in first and all(syl.by_id[i["chapter_id"]].cls == 11 for i in plan["weeks"][0]["learn"])
    milestones = [m for month in plan["months"] for m in month["milestones"]]
    assert "Class 11 Physics complete" in milestones and "Whole syllabus done" in milestones
    assert plan["months"][-1]["phase"] == "revision" and plan["months"][-1]["mocks"] >= 4
    assert plan["mentor"][0]["title"] == "This plan works"


def test_not_enough_time_switches_to_most_marks_first():
    syl = syllabus.get("jee")
    plan = planner.build(_goal(cls="dropper", wd=6, we=8), syl, planner.Progress(), TODAY)
    assert plan["priority_mode"] and plan["unfinished"] and plan["status"] == "behind"
    assert plan["mentor"][0]["title"].startswith("Priority mode")
    for subject in syl.subjects:  # within each subject, what gets done is worth more per hour than what waits
        chapters = [c for c in syl.subject_chapters(subject) if not c.foundation]
        done = [c.weight / c.hours for c in chapters if c.name not in plan["unfinished"]]
        skipped = [c.weight / c.hours for c in chapters if c.name in plan["unfinished"]]
        if done and skipped:
            assert min(done) >= max(skipped) - 1e-9, subject
    text = plan["mentor"][0]["text"]
    assert "h a day" in text and "% of the paper" in text


def test_falling_behind_the_baseline_is_spotted():
    syl = syllabus.get("neet")
    goal = _goal(cls="12", wd=6, we=8, exam="neet", track="neet", target="govt_mbbs")
    first = planner.build(goal, syl, planner.Progress(), TODAY)
    fresh = planner.build(goal, syl, planner.Progress(), TODAY, baseline=first["baseline"])
    assert fresh["expected_now"] == fresh["completion"]  # a brand-new plan is never "behind"
    assert not any("behind your plan" in m["title"] for m in fresh["mentor"])
    later = TODAY + timedelta(days=60)
    plan = planner.build(goal, syl, planner.Progress(), later, baseline=first["baseline"])  # two months, nothing done
    assert plan["expected_now"] > 10
    assert any("behind your plan" in m["title"] for m in plan["mentor"])


def test_daily_plan_learns_practises_and_revises():
    syl = syllabus.get("jee")
    progress = planner.Progress()
    ch = syl.by_id["physics.units-measurements-and-errors"]
    for t in ch.topics:
        progress.done_topics[t.id] = TODAY - timedelta(days=8)  # finished 8 days ago: first revision is due
    plan = planner.build(_goal(), syl, progress, TODAY)
    kinds = [t["kind"] for t in plan["today"]["tasks"]]
    assert kinds.count("learn") == 2 and "practice" in kinds and "revise" in kinds
    revise = next(t for t in plan["today"]["tasks"] if t["kind"] == "revise")
    assert revise["chapter_id"] == ch.id
    progress.revisions[ch.id] = [TODAY]
    again = planner.build(_goal(), syl, progress, TODAY)
    assert next(t for t in again["today"]["tasks"] if t["kind"] == "revise")["done"]


def test_rest_day_and_past_exam():
    syl = syllabus.get("jee")
    sunday = date(2026, 10, 4)
    plan = planner.build(_goal(wd=4, we=0), syl, planner.Progress(), sunday)
    assert plan["today"]["tasks"] == [] and "Rest day" in plan["today"]["note"]
    past = planner.Goal("jee", "jee_main", "12", TODAY - timedelta(days=1), "air_10k", 4, 4)
    assert planner.build(past, syl, planner.Progress(), TODAY)["status"] == "past"


# ---------------------------------------------------------------- API flow
def _student(client, email, exam="jee"):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Prep Student", "password": "correct-horse-1",
                                                "exam_target": exam})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


GOAL = {"track": "jee_main", "class_level": "12", "exam_date": "2027-04-04", "target": "air_10k", "dream": "  NIT Trichy CSE ",
        "weekday_hours": 6, "weekend_hours": 9, "coaching": "offline", "standing": {"Physics": {"11": "done", "12": "none"},
                                                                                    "Chemistry": {"11": "partial"}}}


def test_goal_to_plan_to_daily_ticks(client):
    h = _student(client, "prep.flow@example.com")
    assert client.get("/api/prep/goal", headers=h).json() is None
    opts = client.get("/api/prep/options", headers=h).json()
    assert {t["id"] for t in opts["tracks"]} == {"jee_main", "jee_advanced", "neet"} and opts["targets"]["neet"]

    plan = client.put("/api/prep/goal", headers=h, json=GOAL).json()
    assert plan["goal"]["dream"] == "NIT Trichy CSE" and plan["completion"] > 10 and plan["months"] and plan["mentor"]
    me = client.get("/api/auth/me", headers=h).json()
    assert me["class_level"] == "Class 12" and me["daily_goal_min"] == round((5 * 6 + 2 * 9) / 7 * 60)

    syl = client.get("/api/prep/syllabus", headers=h).json()
    physics = next(s for s in syl["subjects"] if s["name"] == "Physics")
    kinematics = next(c for u in physics["units"] for c in u["chapters"] if c["name"] == "Kinematics")
    assert kinematics["done"] == kinematics["total"]  # "Class 11 Physics: done" was applied
    assert syl["stats"]["chapters"] == 58 and syl["stats"]["done_topics"] > 50

    today = client.get("/api/prep/plan", headers=h).json()["today"]
    assert not any(t["done"] for t in today["tasks"])  # what was covered before Focs doesn't count as done today
    assert not any(t["chapter_id"].startswith("physics.") and t["chapter_id"] in {"physics.kinematics", "physics.units-measurements-and-errors"}
                   for t in today["tasks"] if t["kind"] == "learn")
    learn = next(t for t in today["tasks"] if t["kind"] == "learn")
    assert client.put(f"/api/prep/today/{learn['key']}", headers=h, json={"done": True}).status_code == 200
    detail = client.get(f"/api/prep/topics/{learn['topics'][0]['id']}", headers=h).json()
    assert detail["done"] and detail["chapter"]["id"] == learn["chapter_id"]

    practice = next(t for t in today["tasks"] if t["kind"] == "practice")
    after = client.put(f"/api/prep/today/{practice['key']}", headers=h, json={"done": True}).json()
    assert next(t for t in after["tasks"] if t["key"] == practice["key"])["done"]

    # untick a topic in the hub, revise a chapter
    tid = learn["topics"][0]["id"]
    assert client.put(f"/api/prep/topics/{tid}", headers=h, json={"done": False}).json()["done"] >= 0
    rev = client.put("/api/prep/chapters/physics.kinematics/revision", headers=h, json={"done": True}).json()
    assert rev["revisions"] == 1
    assert client.put("/api/prep/chapters/physics.kinematics/revision", headers=h, json={"done": True}).json()["revisions"] == 1

    exported = client.get("/api/auth/export", headers=h).json()
    assert exported["goal"]["target"] == "air_10k" and exported["topics_done"] and exported["revisions"]

    assert client.delete("/api/prep/goal", headers=h).status_code == 204
    assert client.get("/api/prep/goal", headers=h).json() is None
    assert client.get("/api/prep/syllabus", headers=h).json()["stats"]["done_topics"] == 0


def test_goal_validation_and_other_exams(client):
    h = _student(client, "prep.checks@example.com", exam="other")
    assert client.get("/api/prep/syllabus", headers=h).status_code == 404  # no Prep Hub for this exam yet
    assert client.get("/api/prep/syllabus?exam=neet", headers=h).status_code == 200  # but it can be browsed
    assert client.put("/api/prep/goal", headers=h, json={**GOAL, "target": "govt_mbbs"}).status_code == 422  # a NEET goal
    assert client.put("/api/prep/goal", headers=h, json={**GOAL, "exam_date": "2020-01-01"}).status_code == 422
    assert client.put("/api/prep/goal", headers=h, json={**GOAL, "weekday_hours": 30}).status_code == 422
    assert client.get("/api/prep/plan", headers=h).json() is None  # no goal yet: nothing to plan, not an error
    neet = client.put("/api/prep/goal", headers=h, json={**GOAL, "track": "neet", "target": "govt_mbbs",
                                                          "exam_date": "2027-05-02", "standing": {}}).json()
    assert neet["goal"]["exam"] == "neet" and client.get("/api/auth/me", headers=h).json()["exam_target"] == "neet"


def test_ticking_a_task_keeps_todays_list_stable():
    syl = syllabus.get("jee")
    goal, progress = _goal(), planner.Progress()
    before = planner.build(goal, syl, progress, TODAY)["today"]["tasks"]
    learn = next(t for t in before if t["kind"] == "learn")
    for topic in learn["topics"]:
        progress.done_topics[topic["id"]] = TODAY  # ticked just now
    after = planner.build(goal, syl, progress, TODAY)["today"]["tasks"]
    assert [t["key"] for t in after] == [t["key"] for t in before]  # same list, nothing swapped in
    assert next(t for t in after if t["key"] == learn["key"])["done"]
    tomorrow = planner.build(goal, syl, progress, TODAY + timedelta(days=1))["today"]["tasks"]
    assert learn["key"] not in [t["key"] for t in tomorrow]  # the next day moves on


@pytest.mark.parametrize("cls,wd", [("11", 5), ("12", 6), ("dropper", 6)])
def test_today_and_this_week_pick_the_same_chapters(cls, wd):
    syl = syllabus.get("jee")
    plan = planner.build(_goal(cls=cls, wd=wd, we=wd + 2), syl, planner.Progress(), TODAY)
    week = {i["chapter_id"] for w in plan["weeks"][:2] for i in w["learn"]}
    today = {t["chapter_id"] for t in plan["today"]["tasks"] if t["kind"] == "learn"}
    assert today and today <= week, (today, week)
