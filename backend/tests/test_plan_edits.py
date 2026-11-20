"""An editable plan: the student's own hours day by day, chapters taken next or left out, and today's list
with tasks of their own added and planned ones taken off."""
from datetime import date, timedelta

from app.services import planner, syllabus

TODAY = date(2026, 10, 5)  # a Monday


def _goal(**kw):
    base = dict(exam="jee", track="jee_main", class_level="11", exam_date=planner.default_exam_date("jee_main", "11", TODAY),
                target="air_10k", weekday_hours=5.0, weekend_hours=8.0)
    return planner.Goal(**{**base, **kw})


# ---------------------------------------------------------------- the engine
def test_hours_set_day_by_day_shape_every_day_and_week():
    syl = syllabus.get("jee")
    hours = (2.0, 6.0, 0.0, 6.0, 4.0, 9.0, 3.0)  # Wednesday off, a long Saturday
    goal = _goal(day_hours=hours)
    assert goal.weekly_hours == 30 and goal.hours_on(TODAY) == 2 and goal.hours_on(TODAY + timedelta(days=5)) == 9
    plan = planner.build(goal, syl, planner.Progress(), TODAY)
    assert plan["hours"]["by_day"] == list(hours) and plan["hours"]["custom_days"] and plan["hours"]["weekly"] == 30
    assert plan["weeks"][0]["hours"] == 30 and plan["today"]["minutes"] == 120
    wednesday = planner.build(goal, syl, planner.Progress(), TODAY + timedelta(days=2))["today"]
    assert wednesday["tasks"] == [] and "Rest day" in wednesday["note"]
    assert planner.build(_goal(), syl, planner.Progress(), TODAY)["hours"]["by_day"] == [5, 5, 5, 5, 5, 8, 8]


def test_a_pinned_chapter_is_studied_next_today_and_this_week():
    syl = syllabus.get("jee")
    before = planner.build(_goal(), syl, planner.Progress(), TODAY)
    first_physics = next(i["chapter_id"] for i in before["weeks"][0]["learn"] if i["subject"] == "Physics")
    pin = "physics.gravitation"
    assert pin != first_physics and pin not in {t.get("chapter_id") for t in before["today"]["tasks"]}

    plan = planner.build(_goal(pinned=(pin,)), syl, planner.Progress(), TODAY)
    assert next(i["chapter_id"] for i in plan["weeks"][0]["learn"] if i["subject"] == "Physics") == pin
    assert pin in {t["chapter_id"] for t in plan["today"]["tasks"] if t["kind"] == "learn"}
    assert plan["pinned"] == [pin]
    # the rest of the subject keeps the mentor's order, right behind it
    physics = [i["chapter_id"] for w in plan["weeks"] for i in w["learn"] if i["subject"] == "Physics"]
    assert list(dict.fromkeys(physics))[1] == first_physics
    # once it's finished the pin has done its job
    progress = planner.Progress(done_topics={t.id: TODAY - timedelta(days=1) for t in syl.by_id[pin].topics})
    assert planner.build(_goal(pinned=(pin,)), syl, progress, TODAY)["pinned"] == []


def test_a_skipped_chapter_leaves_the_plan_and_its_time_goes_to_the_rest():
    syl = syllabus.get("jee")
    full = planner.build(_goal(), syl, planner.Progress(), TODAY)
    skip = ("physics.units-measurements-and-errors", "mathematics.mathematical-reasoning-and-statistics"
            if "mathematics.mathematical-reasoning-and-statistics" in syl.by_id else syl.subject_chapters("Mathematics")[-1].id)
    plan = planner.build(_goal(skipped=frozenset(skip)), syl, planner.Progress(), TODAY)
    planned = {i["chapter_id"] for w in plan["weeks"] for i in w["learn"]}
    assert not planned & set(skip) and {c["id"] for c in plan["skipped"]} == set(skip)
    assert plan["syllabus_done_on"] <= full["syllabus_done_on"]            # less to study: done no later
    assert 0 < plan["skipped_weight"] < 15 and plan["covered_weight"] == 100 - plan["skipped_weight"]
    assert any("left out of your plan" in m["title"] for m in plan["mentor"])
    assert not any("Whole syllabus done" in m for month in plan["months"] for m in month["milestones"])
    assert not {t.get("chapter_id") for t in plan["today"]["tasks"]} & set(skip)
    # a chapter already finished isn't "left out", whatever the list says
    done = planner.Progress(done_topics={t.id: TODAY - timedelta(days=30) for t in syl.by_id[skip[0]].topics})
    assert [c["id"] for c in planner.build(_goal(skipped=frozenset(skip)), syl, done, TODAY)["skipped"]] == [skip[1]]


def test_todays_list_takes_the_students_own_tasks_and_drops_what_they_hide():
    syl = syllabus.get("jee")
    plain = planner.build(_goal(), syl, planner.Progress(), TODAY)["today"]
    practice = next(t for t in plain["tasks"] if t["kind"] == "practice")
    progress = planner.Progress(checks={f"hide:{practice['key']}"},
                                custom=[{"id": 7, "title": "School physics homework", "minutes": 40, "done": True}])
    today = planner.build(_goal(), syl, progress, TODAY)["today"]
    keys = [t["key"] for t in today["tasks"]]
    assert practice["key"] not in keys and keys[-1] == "custom:7" and today["tasks"][-1]["kind"] == "custom"
    assert today["hidden"] == [{"key": practice["key"], "title": f"Practise: {practice['title']}"}]
    assert today["done"] == 1 and len(today["tasks"]) == len(plain["tasks"])
    # a rest day still shows what the student put on it
    rest = planner.build(_goal(day_hours=(0, 5, 5, 5, 5, 8, 8)), syl, progress, TODAY)["today"]
    assert [t["key"] for t in rest["tasks"]] == ["custom:7"] and rest["note"] is None


def test_edits_that_no_longer_fit_the_syllabus_are_dropped():
    syl = syllabus.get("neet")
    day_hours, pinned, skipped = planner.clean_edits(syl, {
        "day_hours": [1, 2, 3], "pinned": ["mathematics.sets", "biology.cell-the-unit-of-life", "biology.cell-the-unit-of-life"],
        "skipped": ["physics.gravitation", "nope"]})
    assert day_hours is None and skipped == frozenset({"physics.gravitation"})
    assert pinned == tuple(c for c in ("biology.cell-the-unit-of-life",) if c in syl.by_id)
    assert planner.clean_edits(syl, None) == (None, (), frozenset())


def test_a_passed_exam_still_gives_the_pages_every_field():
    plan = planner.build(_goal(exam_date=TODAY - timedelta(days=3)), syllabus.get("jee"), planner.Progress(), TODAY)
    assert plan["status"] == "past" and plan["target"]["label"] and plan["hours"]["by_day"] and plan["skipped"] == []


def test_the_last_two_days_are_revision_only():
    syl = syllabus.get("jee")
    for days in (1, 2):
        plan = planner.build(_goal(exam_date=TODAY + timedelta(days=days)), syl, planner.Progress(), TODAY)
        assert "learn" not in {t["kind"] for t in plan["today"]["tasks"]}, days
    week_out = planner.build(_goal(exam_date=TODAY + timedelta(days=7)), syl, planner.Progress(), TODAY)
    assert "learn" in {t["kind"] for t in week_out["today"]["tasks"]}  # with a week left there is still time to learn
    assert planner.revision_window(TODAY, TODAY + timedelta(days=400)) == 60 and planner.revision_window(TODAY, TODAY + timedelta(days=1)) == 1


# ---------------------------------------------------------------- the API
GOAL = {"track": "jee_main", "class_level": "12", "exam_date": "2027-04-04", "target": "air_10k", "dream": "NIT Trichy",
        "weekday_hours": 6, "weekend_hours": 9, "coaching": "self", "standing": {}}


def _student(client, email):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Plan Editor", "password": "correct-horse-1",
                                                "exam_target": "jee"})
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.put("/api/prep/goal", headers=h, json=GOAL).status_code == 200
    return h


def test_editing_hours_date_and_goal_in_place(client):
    h = _student(client, "edit.hours@example.com")
    week = [4, 4, 0, 4, 4, 10, 6.3]
    plan = client.patch("/api/prep/plan", headers=h, json={"day_hours": week}).json()
    assert plan["hours"]["by_day"] == [4, 4, 0, 4, 4, 10, 6.5] and plan["hours"]["weekly"] == 32.5  # half-hour steps
    assert plan["goal"]["weekday_hours"] == 3.2 and plan["goal"]["weekend_hours"] == 8.25             # the averages
    assert client.get("/api/auth/me", headers=h).json()["daily_goal_min"] == round(32.5 / 7 * 60)
    assert plan["expected_now"] == plan["completion"]  # a changed plan is never "behind" on day one
    assert client.get("/api/prep/plan", headers=h).json()["hours"]["custom_days"] is True

    plan = client.patch("/api/prep/plan", headers=h, json={"weekday_hours": 7, "weekend_hours": 10}).json()
    assert plan["hours"]["by_day"] == [7, 7, 7, 7, 7, 10, 10] and not plan["hours"]["custom_days"]

    plan = client.patch("/api/prep/plan", headers=h, json={"exam_date": "2027-01-22", "target": "air_1k", "dream": "  IIT Bombay CSE "}).json()
    assert plan["exam_date"] == "2027-01-22" and plan["target"]["id"] == "air_1k" and plan["goal"]["dream"] == "IIT Bombay CSE"
    assert client.patch("/api/prep/plan", headers=h, json={"dream": ""}).json()["goal"]["dream"] is None
    assert client.patch("/api/prep/plan", headers=h, json={}).json()["hours"]["weekday"] == 7  # nothing sent, nothing changed

    for bad in ({"day_hours": [1, 2, 3]}, {"day_hours": [0] * 7}, {"day_hours": [20, 1, 1, 1, 1, 1, 1]}, {"exam_date": "2020-01-01"},
                {"target": "govt_mbbs"}, {"weekday_hours": 0, "weekend_hours": 0}, {"weekday_hours": 30}):
        assert client.patch("/api/prep/plan", headers=h, json=bad).status_code == 422, bad
    fresh = client.post("/api/auth/register", json={"accepted_terms": True, "email": "edit.nogoal@example.com", "full_name": "No Goal",
                                                    "password": "correct-horse-1", "exam_target": "jee"}).json()["access_token"]
    assert client.patch("/api/prep/plan", headers={"Authorization": f"Bearer {fresh}"}, json={"weekday_hours": 5}).status_code == 404
    # setting the goal again in onboarding goes back to the two numbers typed there
    client.patch("/api/prep/plan", headers=h, json={"day_hours": week})
    assert client.put("/api/prep/goal", headers=h, json=GOAL).json()["hours"]["by_day"] == [6, 6, 6, 6, 6, 9, 9]


def test_taking_a_chapter_next_and_leaving_one_out(client):
    h = _student(client, "edit.order@example.com")
    url = "/api/prep/plan/chapters/"
    plan = client.put(url + "physics.gravitation", headers=h, json={"action": "next"}).json()
    assert plan["pinned"] == ["physics.gravitation"]
    assert "physics.gravitation" in {t["chapter_id"] for t in plan["today"]["tasks"] if t["kind"] == "learn"} or plan["today"]["minutes"] == 0
    plan = client.put(url + "physics.ray-and-wave-optics", headers=h, json={"action": "next"}).json()
    assert plan["pinned"][0].startswith("physics.") and len(plan["pinned"]) == 2  # the newest request goes first
    assert client.put(url + plan["pinned"][0], headers=h, json={"action": "unpin"}).json()["pinned"] == ["physics.gravitation"]

    plan = client.put(url + "physics.gravitation", headers=h, json={"action": "skip"}).json()
    assert [c["id"] for c in plan["skipped"]] == ["physics.gravitation"] and plan["pinned"] == []  # left out wins over "next"
    assert plan["expected_now"] == plan["completion"]
    assert not any(i["chapter_id"] == "physics.gravitation" for w in plan["weeks"] for i in w["learn"])
    plan = client.put(url + "physics.gravitation", headers=h, json={"action": "restore"}).json()
    assert plan["skipped"] == [] and any(i["chapter_id"] == "physics.gravitation" for w in plan["weeks"] for i in w["learn"])

    assert client.put(url + "physics.nope", headers=h, json={"action": "skip"}).status_code == 404
    assert client.put(url + "physics.gravitation", headers=h, json={"action": "delete"}).status_code == 422
    exported = client.get("/api/auth/export", headers=h).json()
    assert exported["plan_edits"]["pinned"] == [] and exported["plan_edits"]["skipped"] == []


def test_own_tasks_and_not_today(client):
    h = _student(client, "edit.today@example.com")
    client.patch("/api/prep/plan", headers=h, json={"day_hours": [6] * 7})  # whatever weekday the suite runs on
    today = client.get("/api/prep/plan", headers=h).json()["today"]
    planned = [t["key"] for t in today["tasks"]]
    assert planned and today["hidden"] == []

    today = client.post("/api/prep/today/tasks", headers=h, json={"title": "  School   chemistry practical file ", "minutes": 45}).json()
    own = today["tasks"][-1]
    assert own["title"] == "School chemistry practical file" and own["kind"] == "custom" and not own["done"]
    done = client.put(f"/api/prep/today/{own['key']}", headers=h, json={"done": True}).json()
    assert done["tasks"][-1]["done"] and done["done"] == 1

    gone = client.put(f"/api/prep/today-hidden/{planned[0]}", headers=h, json={"done": True}).json()
    assert planned[0] not in [t["key"] for t in gone["tasks"]] and gone["hidden"][0]["key"] == planned[0]
    back = client.put(f"/api/prep/today-hidden/{planned[0]}", headers=h, json={"done": False}).json()
    assert [t["key"] for t in back["tasks"]] == planned + [own["key"]] and back["hidden"] == []

    removed = client.delete(f"/api/prep/today/tasks/{own['key'].split(':')[1]}", headers=h).json()
    assert [t["key"] for t in removed["tasks"]] == planned
    assert client.put(f"/api/prep/today/{own['key']}", headers=h, json={"done": True}).status_code == 404
    assert client.post("/api/prep/today/tasks", headers=h, json={"title": "   ", "minutes": 30}).status_code == 422
    assert client.post("/api/prep/today/tasks", headers=h, json={"title": "x", "minutes": 2}).status_code == 422
    assert client.put("/api/prep/today-hidden/custom:1", headers=h, json={"done": True}).status_code == 422  # delete those instead
    for i in range(12):
        assert client.post("/api/prep/today/tasks", headers=h, json={"title": f"Task {i}"}).status_code == 201
    assert client.post("/api/prep/today/tasks", headers=h, json={"title": "One too many"}).status_code == 422

    other = _student(client, "edit.other@example.com")
    mine = client.get("/api/prep/plan", headers=h).json()["today"]["tasks"][-1]["key"].split(":")[1]
    assert client.delete(f"/api/prep/today/tasks/{mine}", headers=other).status_code == 404
    assert client.put(f"/api/prep/today/custom:{mine}", headers=other, json={"done": True}).status_code == 404
    assert len(client.get("/api/auth/export", headers=h).json()["own_tasks"]) == 12
    assert client.delete("/api/prep/goal", headers=h).status_code == 204  # starting over clears them too
