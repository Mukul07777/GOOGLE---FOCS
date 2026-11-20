"""Last-day revision: what to revise with one day left, from the student's own progress and test results."""
from datetime import date, timedelta

from app.services import lastday, planner, syllabus, topic_notes
from app.services.llm import LLMUnavailable

TODAY = date(2027, 4, 3)
EXAM = date(2027, 4, 4)


def _done(syl, chapter_ids, on=TODAY - timedelta(days=60), part=1.0):
    out = {}
    for cid in chapter_ids:
        topics = syl.by_id[cid].topics
        for t in topics[: max(1, round(len(topics) * part))]:
            out[t.id] = on
    return out


def test_only_studied_chapters_are_scheduled_and_nothing_new_is_started():
    syl = syllabus.get("jee")
    studied = ["physics.kinematics", "physics.laws-of-motion", "physics.electrostatics", "chemistry.chemical-bonding-and-molecular-structure",
               "mathematics.matrices-and-determinants"]
    studied = [c for c in studied if c in syl.by_id]
    progress = planner.Progress(done_topics=_done(syl, studied))
    plan = lastday.build(syl, progress, TODAY, hours=6, exam_date=EXAM, cover="studied")
    listed = {c["id"] for c in plan["chapters"]} | {c["id"] for c in plan["if_time"]}
    assert listed == set(studied) and plan["days_left"] == 1 and plan["scope"] == "all"
    assert plan["leave_count"] == len(syl.chapters) - len(studied)
    assert not {c["id"] for c in plan["leave"]} & set(studied)
    weights = [syl.by_id[c["id"]].weight for c in plan["leave"]]
    assert weights == sorted(weights, reverse=True)  # the biggest temptations first
    assert all(lastday.MIN_BLOCK <= c["minutes"] <= lastday.MAX_BLOCK and c["minutes"] % 5 == 0 for c in plan["chapters"])
    assert plan["minutes"]["chapters"] + plan["minutes"]["own"] <= 6 * 60 and plan["minutes"]["own"] >= 20
    assert 0 < plan["paper_share"] < 30 and len(plan["checklist"]) >= 5


def test_shaky_and_stale_chapters_come_first_and_revised_ones_drop():
    syl = syllabus.get("jee")
    a, b, c = "physics.kinematics", "physics.laws-of-motion", "physics.work-energy-and-power"
    same_weight = {syl.by_id[x].weight for x in (a, b, c)}
    progress = planner.Progress(done_topics=_done(syl, [a, b, c], on=TODAY - timedelta(days=3)))
    acc = {("Physics", syl.by_id[b].name): lastday.Accuracy(correct=2, attempted=10),   # 20%: shaky
           ("Physics", syl.by_id[a].name): lastday.Accuracy(correct=9, attempted=10),   # 90%: solid
           ("Physics", syl.by_id[c].name): lastday.Accuracy(correct=1, attempted=2)}    # two questions say nothing
    plan = lastday.build(syl, progress, TODAY, hours=2, subject="Physics", accuracy=acc)
    order = [x["id"] for x in plan["chapters"] + plan["if_time"]]
    if len(same_weight) == 1:
        assert order.index(b) < order.index(c) < order.index(a)
    shaky = next(x for x in plan["chapters"] if x["id"] == b)
    assert shaky["accuracy"] == 20 and "20% in your tests" in shaky["reasons"]
    assert next(x for x in plan["chapters"] + plan["if_time"] if x["id"] == c).get("accuracy") is None

    before = lastday.build(syl, progress, TODAY, hours=6, subject="Physics", accuracy=acc)
    progress.revisions[b] = [TODAY]  # ticked off this morning: counted as done, and the day's list doesn't reshuffle
    again = lastday.build(syl, progress, TODAY, hours=6, subject="Physics", accuracy=acc)
    row = next(x for x in again["chapters"] if x["id"] == b)
    assert row["revised_today"] and again["revised"] == 1 and before["revised"] == 0
    assert [(x["id"], x["minutes"]) for x in again["chapters"]] == [(x["id"], x["minutes"]) for x in before["chapters"]]


def test_hours_decide_how_many_chapters_and_subjects_alternate():
    syl = syllabus.get("neet")
    progress = planner.Progress(done_topics=_done(syl, [c.id for c in syl.chapters]))
    short = lastday.build(syl, progress, TODAY, hours=2)
    long = lastday.build(syl, progress, TODAY, hours=10)
    assert 2 <= len(short["chapters"]) <= 4 < len(long["chapters"]) <= 24
    assert short["leave"] == [] and short["leave_count"] == 0 and len(short["chapters"]) + len(short["if_time"]) == len(syl.chapters)
    assert not any(c["quick"] for c in short["chapters"] + short["if_time"])  # everything studied: nothing is new
    assert long["paper_share"] > short["paper_share"]
    subjects = [c["subject"] for c in long["chapters"]]
    for i in range(len(subjects) - 2):  # three in a row only once nothing else is left to put between them
        if subjects[i] == subjects[i + 1] == subjects[i + 2]:
            assert set(subjects[i:]) == {subjects[i]}, subjects
    assert long["minutes"]["chapters"] <= 10 * 60 - long["minutes"]["own"] + lastday.MAX_BLOCK  # rounding slack only


def test_a_class_test_on_chosen_chapters_lists_them_even_if_barely_studied():
    syl = syllabus.get("jee")
    picked = ["physics.gravitation", "physics.thermodynamics"]
    progress = planner.Progress(done_topics=_done(syl, ["physics.gravitation"], part=0.3))
    plan = lastday.build(syl, progress, TODAY, hours=4, chapter_ids=picked + ["physics.nope"])
    assert plan["scope"] == "chapters" and {c["id"] for c in plan["chapters"]} == set(picked) and plan["leave"] == []
    partial = next(c for c in plan["chapters"] if c["id"] == "physics.gravitation")
    assert any("studied" in r for r in partial["reasons"]) and partial["topics"]
    assert not any(c["quick"] for c in plan["chapters"])  # a chosen chapter is tomorrow's test, studied or not
    nothing = lastday.build(syl, planner.Progress(), TODAY, hours=6, cover="studied")
    assert nothing["chapters"] == [] and nothing["leave_count"] == len(syl.chapters)

    # a test on a whole subject's chapters is the whole day: every one of them, and the day still adds up
    physics = [c.id for c in syl.subject_chapters("Physics")]
    whole = lastday.build(syl, progress, TODAY, hours=6, chapter_ids=physics)
    available = 6 * 60 - whole["minutes"]["own"]
    assert {c["id"] for c in whole["chapters"]} == set(physics) and whole["if_time"] == []
    assert all(c["minutes"] >= lastday.MIN_BLOCK for c in whole["chapters"]) and whole["minutes"]["chapters"] <= available + 10
    heavy = max(whole["chapters"], key=lambda c: syl.by_id[c["id"]].weight)
    assert heavy["minutes"] > min(c["minutes"] for c in whole["chapters"])  # what is left over goes to the heaviest


# ---------------------------------------------------------------- the API
def _student(client, email, exam="jee"):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Last Day", "password": "correct-horse-1",
                                                "exam_target": exam})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_last_day_page_data_and_capsules(client, monkeypatch):
    h = _student(client, "lastday@example.com")
    empty = client.get("/api/prep/last-day?cover=studied", headers=h).json()
    assert empty["chapters"] == [] and empty["exam_date"] is None and empty["own"] == {"redo": 0, "cards_due": 0, "formulas": 0, "weak": 0}
    assert empty["cover"] == "studied" and empty["final_test"] is None and empty["test_sizes"] == list(lastday.TEST_SIZES)
    fresh = client.get("/api/prep/last-day", headers=h).json()  # nothing studied, and still the day is full of what counts
    assert fresh["cover"] == "important" and fresh["chapters"] and all(c["quick"] for c in fresh["chapters"])
    assert fresh["leave"] == [] and len(fresh["chapters"]) + len(fresh["if_time"]) == len(syllabus.get("jee").chapters)
    for topic in ("frame-of-reference-distance-and-displacement", "speed-velocity-and-acceleration", "equations-of-motion-in-a-straight-line",
                  "motion-graphs-x-t-v-t-a-t", "vectors-addition-components-products", "motion-in-a-plane", "projectile-motion"):
        assert client.put(f"/api/prep/topics/physics.kinematics.{topic}", headers=h, json={"done": True}).status_code == 200
    client.post("/api/quiz/attempt", headers=h, json={"question": "v = u + at?", "q_type": "mcq", "correct": False, "topic": "Kinematics"})

    plan = client.get("/api/prep/last-day?hours=4&cover=studied", headers=h).json()
    row = plan["chapters"][0]
    assert [c["id"] for c in plan["chapters"]] == ["physics.kinematics"] and not row["has_capsule"] and row["studied"] == 78
    assert plan["own"]["redo"] == 1 and plan["subjects"] == ["Physics", "Chemistry", "Mathematics"] and plan["hours"] == 4
    assert client.get("/api/prep/last-day?subject=Chemistry&cover=studied", headers=h).json()["chapters"] == []
    chemistry = client.get("/api/prep/last-day?subject=Chemistry", headers=h).json()["chapters"]
    assert chemistry and {c["subject"] for c in chemistry} == {"Chemistry"}
    assert client.get("/api/prep/last-day?chapters=chemistry.equilibrium,physics.kinematics", headers=h).json()["scope"] == "chapters"
    assert client.get("/api/prep/last-day?hours=40", headers=h).status_code == 422
    assert client.get("/api/prep/last-day?cover=everything", headers=h).status_code == 422
    assert client.get("/api/prep/last-day", headers=_student(client, "lastday.ca@example.com", exam="other")).status_code == 404

    # studied, it leads the day over chapters not studied yet, with every topic and not only the ones ticked
    whole = client.get("/api/prep/last-day?hours=4", headers=h).json()
    kinematics = next(c for c in whole["chapters"] if c["id"] == "physics.kinematics")
    assert not kinematics["quick"] and len(kinematics["topics"]) == kinematics["topic_count"] == 9
    assert kinematics["minutes"] == max(c["minutes"] for c in whole["chapters"])

    # ticking it as revised moves the day along
    client.put("/api/prep/chapters/physics.kinematics/revision", headers=h, json={"done": True})
    assert client.get("/api/prep/last-day", headers=h).json()["revised"] == 1

    # the chapter's capsule comes from the library: written and checked once, then shared
    capsule = ("## Must-know formulas\n| Formula or fact | Use when |\n| --- | --- |\n| $v = u + at$ | constant acceleration |\n\n"
               "## Key points\n- Displacement is a vector.\n\n## Common mistakes\n- **Mistake:** speed for velocity **Instead:** mind the sign\n\n"
               "## Quick self-check\n1. Unit of acceleration?\n   Answer: m/s^2\n") + "Filler so the capsule is long enough. " * 30
    written = []
    monkeypatch.setattr(topic_notes.llm, "chat_with_model", lambda m, **k: (written.append(m[-1]["content"]) or capsule, "writer"))
    monkeypatch.setattr(topic_notes.llm, "json_with_model", lambda m, **k: ({"ok": True}, "reviewer"))
    first = client.post("/api/prep/chapters/physics.kinematics/capsule", headers=h).json()
    assert first["written_now"] and first["checked"] and "Must-know formulas" in first["notes_md"] and "Kinematics" in written[0]
    other = _student(client, "lastday.b@example.com")
    again = client.post("/api/prep/chapters/physics.kinematics/capsule", headers=other).json()
    assert not again["written_now"] and len(written) == 1
    rows = client.get("/api/prep/last-day", headers=h).json()["chapters"]
    assert next(c for c in rows if c["id"] == "physics.kinematics")["has_capsule"] is True
    assert client.post("/api/prep/chapters/physics.nope/capsule", headers=h).status_code == 404

    def down(*a, **k):
        raise LLMUnavailable("no model")

    monkeypatch.setattr(topic_notes.llm, "chat_with_model", down)
    r = client.post("/api/prep/chapters/physics.semiconductor-electronics/capsule", headers=h)
    assert r.status_code == 503 and "capsule" in r.json()["detail"]


def test_test_results_feed_the_revision_order(client):
    from app.core.database import SessionLocal
    from app.models.mock import MockTest
    from app.models.user import User
    from sqlalchemy import select

    h = _student(client, "lastday.tests@example.com", exam="neet")
    with SessionLocal() as db:
        uid = db.scalar(select(User.id).where(User.email == "lastday.tests@example.com"))
        for correct, attempted in ((1, 4), (2, 6)):  # two tests, pooled: 3 of 10
            db.add(MockTest(user_id=uid, title="Chapter test", pattern="chapter", status="submitted", duration_min=30,
                            result={"chapters": [{"subject": "Botany", "chapter": "Cell: The Unit of Life", "correct": correct, "attempted": attempted}]}))
        db.add(MockTest(user_id=uid, title="Unfinished", pattern="chapter", status="in_progress", duration_min=30,
                        result={"chapters": [{"subject": "Botany", "chapter": "Cell: The Unit of Life", "correct": 50, "attempted": 50}]}))
        db.commit()
    syl = syllabus.get("neet")
    cell = next(c for c in syl.chapters if c.name == "Cell: The Unit of Life")
    for t in cell.topics:
        client.put(f"/api/prep/topics/{t.id}", headers=h, json={"done": True})
    row = client.get("/api/prep/last-day?cover=studied", headers=h).json()["chapters"][0]
    assert row["id"] == cell.id and row["accuracy"] == 30 and "30% in your tests" in row["reasons"]
    rows = client.get("/api/prep/last-day", headers=h).json()["chapters"]  # shaky: still on a day of everything important
    assert next(c for c in rows if c["id"] == cell.id)["accuracy"] == 30


# ---------------------------------------------------------------- the student shapes the list
def test_named_topics_added_and_removed_chapters_and_weak_spots():
    syl = syllabus.get("jee")
    studied = ["physics.kinematics", "physics.laws-of-motion", "physics.work-energy-and-power", "physics.gravitation"]
    progress = planner.Progress(done_topics=_done(syl, studied))
    kin = syl.by_id["physics.kinematics"]
    two = [kin.topics[6].id, kin.topics[7].id]  # only projectile motion and relative velocity are coming

    whole = lastday.build(syl, progress, TODAY, hours=4, chapter_ids=["physics.kinematics", "physics.gravitation"])
    named = lastday.build(syl, progress, TODAY, hours=4, chapter_ids=["physics.kinematics", "physics.gravitation"], topic_ids=two + ["nope"])
    row = next(c for c in named["chapters"] if c["id"] == kin.id)
    assert [t["id"] for t in row["topics"]] == two and row["topics_chosen"] and all(t["done"] for t in row["topics"])
    assert row["minutes"] <= next(c for c in whole["chapters"] if c["id"] == kin.id)["minutes"]  # two topics need less than nine
    assert whole["minutes"]["chapters"] > 2 * lastday.MAX_BLOCK  # two chapters and four hours: they share the time there is
    assert all(c["minutes"] <= lastday.LONG_BLOCK for c in whole["chapters"]) and whole["minutes"]["chapters"] <= 4 * 60
    other = next(c for c in named["chapters"] if c["id"] == "physics.gravitation")
    assert not other["topics_chosen"] and len(other["topics"]) == len(syl.by_id["physics.gravitation"].topics)

    # taken off today's list, and a chapter that wasn't on it added (even one not studied yet: the student's call)
    shaped = lastday.build(syl, progress, TODAY, hours=2, subject="Physics", exclude=["physics.kinematics", "nope"],
                           include=["physics.thermodynamics", "chemistry.equilibrium"])
    ids = [c["id"] for c in shaped["chapters"]]
    assert "physics.kinematics" not in ids + [c["id"] for c in shaped["if_time"]] and [c["id"] for c in shaped["removed"]] == ["physics.kinematics"]
    assert {"physics.thermodynamics", "chemistry.equilibrium"} <= set(ids)
    assert all(c["added"] for c in shaped["chapters"] if c["id"] in ("physics.thermodynamics", "chemistry.equilibrium"))
    assert "physics.thermodynamics" not in [c["id"] for c in shaped["leave"]]

    # a chapter the last test showed to be weak moves up, and says why
    plain = [c["id"] for c in lastday.build(syl, progress, TODAY, hours=6, subject="Physics", cover="studied")["chapters"]]
    weak = lastday.build(syl, progress, TODAY, hours=6, subject="Physics", weak={plain[-1]: 3}, cover="studied")
    first = max(weak["chapters"], key=lambda c: c["minutes"])
    assert first["id"] == plain[-1] and first["weak"] and "a weak spot from your last test" in first["reasons"]


def test_last_day_can_be_shaped_through_the_api(client):
    h = _student(client, "lastday.shape@example.com")
    body = {"hours": 4, "chapters": ["physics.kinematics", "physics.gravitation"],
            "topics": ["physics.kinematics.projectile-motion"], "exclude": ["physics.gravitation"]}
    plan = client.post("/api/prep/last-day", headers=h, json=body).json()
    assert [c["id"] for c in plan["chapters"]] == ["physics.kinematics"] and plan["scope"] == "chapters"
    assert [t["name"] for t in plan["chapters"][0]["topics"]] == ["Projectile motion"] and plan["chapters"][0]["topics"][0]["done"] is False
    assert [c["id"] for c in plan["removed"]] == ["physics.gravitation"]
    assert client.post("/api/prep/last-day", headers=h, json={"hours": 99}).status_code == 422
    assert client.post("/api/prep/last-day", headers=h, json={}).json()["scope"] == "all"


def test_lectures_count_as_studied_and_each_board_is_placed_once(client, monkeypatch):
    """A student who learns from lectures and never ticks the Prep Hub still gets a revision order. Each captured
    board is placed in the syllabus once: by name when its topic names one, else by the model, and the place kept.
    While no model can be asked, a board waits rather than being filed under no chapter."""
    from app.core.database import SessionLocal
    from app.models.note import Note
    from app.services import weak

    h = _student(client, "lastday.lectures@example.com")
    sid = client.post("/api/sessions", headers=h, json={"title": "Mixed"}).json()["id"]
    with SessionLocal() as db:
        db.add_all([Note(session_id=sid, topic="Projectile motion", subject="Physics", ai_notes="- range"),  # names a topic
                    Note(session_id=sid, topic="Rational Inequality", subject="Mathematics", ai_notes="- sign chart"),
                    Note(session_id=sid, topic="havecommm", subject="General", ai_notes="- ?")])
        db.commit()
    asked: list[list[str]] = []
    monkeypatch.setattr(weak, "ask_chapters", lambda syl, items, exam, **k: asked.append([it["text"] for it in items]))  # no model now
    plan = client.get("/api/prep/last-day?cover=studied", headers=h).json()
    assert [c["id"] for c in plan["chapters"]] == ["physics.kinematics"]
    kinematics = plan["chapters"][0]
    assert [t["name"] for t in kinematics["topics"]] == ["Projectile motion"]
    assert "from your lectures: revise what they covered" in kinematics["reasons"]

    def place(syl, items, exam, **k):
        asked.append([it["text"] for it in items])
        return {i: syl.by_id["mathematics.quadratic-equations"] for i, it in enumerate(items) if "Inequality" in it["text"]}

    monkeypatch.setattr(weak, "ask_chapters", place)
    plan = client.get("/api/prep/last-day?cover=studied", headers=h).json()
    assert {c["id"] for c in plan["chapters"]} == {"physics.kinematics", "mathematics.quadratic-equations"}
    assert not {c["id"] for c in plan["leave"]} & {"physics.kinematics", "mathematics.quadratic-equations"}
    whole = client.get("/api/prep/last-day?hours=10", headers=h).json()  # everything important: the lectures, every topic of them
    lectured = {c["id"]: c for c in whole["chapters"] if c["id"] in ("physics.kinematics", "mathematics.quadratic-equations")}
    assert len(lectured) == 2 and not any(c["quick"] for c in lectured.values())
    assert "from your lectures" in lectured["physics.kinematics"]["reasons"]
    assert len(lectured["physics.kinematics"]["topics"]) == lectured["physics.kinematics"]["topic_count"]
    assert asked == [["Rational Inequality", "havecommm"]] * 2  # asked again only while unanswered, then kept


# ---------------------------------------------------------------- everything important, most-asked topics first
def test_everything_important_is_planned_and_new_chapters_get_their_most_asked_topics():
    syl = syllabus.get("jee")
    light = sorted(syl.chapters, key=lambda c: c.weight)[:2]  # what the student has studied: two light chapters
    heavy = max(syl.chapters, key=lambda c: c.weight)
    progress = planner.Progress(done_topics=_done(syl, [c.id for c in light]))
    hot = [heavy.topics[2].id, heavy.topics[0].id]  # what papers ask most, most asked first
    asked = {heavy.id: hot, light[0].id: [light[0].topics[-1].id]}
    plan = lastday.build(syl, progress, TODAY, hours=10, asked=asked)
    studied = lastday.build(syl, progress, TODAY, hours=10, asked=asked, cover="studied")

    rows = {c["id"]: c for c in plan["chapters"]}
    new = rows[heavy.id]  # not studied: on the list for its marks, with its most-asked topics only
    assert new["quick"] and [t["id"] for t in new["topics"]] == hot and all(t["asked"] for t in new["topics"])
    assert new["topic_count"] == len(heavy.topics) and "not studied yet: its most-asked topics only" in new["reasons"]
    mine = rows[light[0].id]  # studied: all of it, the most-asked topic first
    assert not mine["quick"] and len(mine["topics"]) == len(light[0].topics) and mine["topics"][0]["asked"]
    assert mine["topics"][0]["id"] == light[0].topics[-1].id and not any(t["asked"] for t in mine["topics"][1:])
    assert all(lastday.MIN_BLOCK <= c["minutes"] for c in plan["chapters"])

    # marks first: no chapter left for later outweighs a new one on the list
    planned = [syl.by_id[c["id"]].weight for c in plan["chapters"] if c["quick"]]
    later = [syl.by_id[c["id"]].weight for c in plan["if_time"] if c["quick"]]
    assert planned and later and min(planned) >= max(later)
    assert plan["leave"] == [] and len(plan["chapters"]) + len(plan["if_time"]) == len(syl.chapters)
    assert {c["id"] for c in studied["chapters"]} == {c.id for c in light} and studied["leave_count"] == len(syl.chapters) - 2
    assert plan["paper_share"] > studied["paper_share"] and plan["cover"] == "important" and studied["cover"] == "studied"

    unranked = lastday.build(syl, progress, TODAY, hours=10)  # before the most-asked topics are known: the capsule
    row = next(c for c in unranked["chapters"] if c["id"] == heavy.id)
    assert row["quick"] and len(row["topics"]) == len(heavy.topics) and "not studied yet: its capsule only" in row["reasons"]


def test_the_final_test_covers_the_days_list_subject_by_subject():
    def row(subject, name, minutes, listed, of):
        return {"subject": subject, "name": name, "minutes": minutes, "topic_count": of, "topics": [{"name": n} for n in listed]}

    plan = {"chapters": [row("Physics", "Kinematics", 40, ["Projectile motion"], 9),
                         row("Chemistry", "Equilibrium", 20, [f"e{i}" for i in range(6)], 6),
                         row("Physics", "Gravitation", 20, [f"g{i}" for i in range(5)], 5),
                         row("Mathematics", "Circles", 15, ["c0", "c1"], 4)]}
    parts = lastday.test_parts(plan, 15)
    assert [p["subject"] for p in parts] == ["Physics", "Chemistry", "Mathematics"]  # in the order of the list
    assert sum(p["count"] for p in parts) == 15 and parts[0]["count"] > parts[1]["count"] >= parts[2]["count"] >= 1
    assert parts[0]["chapters"] == ["Kinematics", "Gravitation"] and parts[0]["topics"] == {"Kinematics": ["Projectile motion"]}
    assert parts[1]["topics"] == {} and parts[2]["topics"] == {"Circles": ["c0", "c1"]}
    few = lastday.test_parts(plan, 2)  # more subjects than questions: the ones with the most time on the list
    assert [(p["subject"], p["count"]) for p in few] == [("Physics", 1), ("Chemistry", 1)]


def test_a_last_day_test_is_marked_like_the_exam():
    from app.services import mock_patterns

    parts = [{"subject": "Physics", "chapters": ["Kinematics"], "topics": {"Kinematics": ["Projectile motion"]}, "count": 6},
             {"subject": "Chemistry", "chapters": ["Equilibrium"], "topics": {}, "count": 4}]
    jee = mock_patterns.revision_pattern(parts, 10, "jee")
    assert jee.total_questions == 10 and [s.count for s in jee.sections_for("Physics")] == [4, 2] and jee.max_score == 40
    assert jee.topics == {"Physics": {"Kinematics": ("Projectile motion",)}} and jee.public()["subject_counts"] == {"Physics": 6, "Chemistry": 4}
    assert jee.duration_min == 20 and jee.subjects == ("Physics", "Chemistry")
    college = mock_patterns.revision_pattern(parts, 10, "college")
    assert college.max_score == 10 and college.sections[0].wrong == 0 and college.duration_min == 15
    assert mock_patterns.test_pattern({"kind": "revision", "parts": parts, "count": 10}).name == "Last-day test"
    assert mock_patterns.test_pattern({"subject": "Physics", "chapters": ["Kinematics"], "count": 10}).name == "Chapter test · Physics"
    assert mock_patterns.PATTERNS["jee_main_30"].public()["subject_counts"] is None


def test_questions_on_part_of_a_chapter_keep_to_its_topics(monkeypatch):
    from types import SimpleNamespace as Q

    from app.services import question_bank as qb

    rows = [Q(id=1, chapter="Kinematics", topic="Projectile motion", question="x", solution=""),
            Q(id=2, chapter="Kinematics", topic="Relative velocity and river-boat problems", question="projectile motion", solution=""),
            Q(id=3, chapter="Kinematics", topic=None, question="The range of a projectile motion launched at 30 degrees", solution=""),
            Q(id=4, chapter="Kinematics", topic=None, question="A car brakes uniformly to rest on a straight road", solution=""),
            Q(id=5, chapter="Gravitation", topic=None, question="Escape speed from the moon", solution="")]
    assert {q.id for q in qb.on_topics(rows, {"Kinematics": ("Projectile motion",)})} == {1, 3, 5}

    seen = {}

    def write(messages, **k):
        seen["system"] = messages[0]["content"]
        return {"questions": [
            {"chapter": "Kinematics", "topic": "projectile motion", "difficulty": "easy", "question": "A ball is projected at 45 degrees "
             "with speed 20 m/s. Find its horizontal range.", "options": ["40 m", "20 m", "10 m", "80 m"], "answer_index": 0,
             "solution": "R = u^2/g = 40 m."},
            {"chapter": "Kinematics", "difficulty": "easy", "question": "A car accelerates uniformly from rest to 20 m/s in 5 s. "
             "Find its acceleration.", "options": ["4", "2", "5", "10"], "answer_index": 0, "solution": "a = 20/5 = 4."}]}, "writer"

    monkeypatch.setattr(qb.llm, "json_with_model", write)
    monkeypatch.setattr(qb, "verify_batch", lambda items, model, deadline=None: [True] * len(items))
    out = qb.generate_batch("Physics", "mcq", ["Kinematics"], n=2, topics={"Kinematics": ("Projectile motion",)})
    assert "Kinematics (only: Projectile motion)" in seen["system"] and '"topic"' in seen["system"]
    assert [q["topic"] for q in out] == ["Projectile motion", None]  # unlabelled: a question on the chapter, not the topic
    plain = qb.generate_batch("Physics", "mcq", ["Kinematics"], n=2)
    assert "only:" not in seen["system"] and [q["topic"] for q in plain] == [None, None]


def test_most_asked_topics_are_judged_once_and_shared(client, monkeypatch):
    import time

    from app.core.database import SessionLocal
    from app.services import likely

    syl = syllabus.get("jee")
    kin, grav = syl.by_id["physics.kinematics"], syl.by_id["physics.gravitation"]
    calls: list[str] = []
    skipped: list[frozenset] = []

    class Model:
        available = True

        def json_with_model(self, messages, **k):
            calls.append(messages[-1]["content"])
            skipped.append(k.get("skip") or frozenset())
            return {"chapters": [{"n": 1, "topics": [7, 8, 99, 7]}, {"n": 2, "topics": [1]}, {"n": 0, "topics": [1]}]}, "ranker"

    monkeypatch.setattr(likely, "llm", Model())
    monkeypatch.setattr(likely, "_rest_until", 0.0)
    with SessionLocal() as db:
        got = likely.rank(db, syl, [kin, grav])
        assert got == {kin.id: [kin.topics[6].id, kin.topics[7].id], grav.id: [grav.topics[0].id]}
        assert "7) Projectile motion" in calls[0] and likely.rank(db, syl, [kin, grav]) == got and len(calls) == 1
        assert "openai/gpt-oss-20b" in skipped[0]  # the light model ranks a list by its order: never asked this

    class Down:
        available = True

        def json_with_model(self, *a, **k):
            raise LLMUnavailable("busy")

    monkeypatch.setattr(likely, "llm", Down())
    with SessionLocal() as db:
        assert likely.rank(db, syl, [syl.by_id["chemistry.equilibrium"]]) == {}  # not now, and not again for a while
        assert likely._rest_until > time.monotonic()

    h = _student(client, "lastday.asked@example.com")
    row = client.post("/api/prep/last-day", headers=h, json={"chapters": [kin.id]}).json()["chapters"][0]
    assert [t["id"] for t in row["topics"][:2]] == got[kin.id] and row["topics"][1]["asked"] and not row["topics"][2]["asked"]


def test_the_final_test_asks_only_what_was_revised(client):
    from app.core.database import SessionLocal
    from app.models.mock import BankQuestion, MockTest
    from app.services import question_bank

    def q(chapter, text, qtype="mcq", topic=None):
        return BankQuestion(exam="jee_main", subject="Physics", chapter=chapter, qtype=qtype, difficulty="medium", question=text,
                            options=["1", "2", "3", "4"] if qtype == "mcq" else None, answer="0" if qtype == "mcq" else "5",
                            solution="Worked through.", verified=True, source="ai", topic=topic, fingerprint=question_bank.fingerprint(text))

    with SessionLocal() as db:
        db.add_all([q("Kinematics", f"FINALTEST {i}: a ball is thrown at 30 degrees above the ground from a cliff", topic="Projectile motion")
                    for i in range(5)]
                   + [q("Kinematics", f"FINALTEST off {i}: a car brakes uniformly on a straight road until it stops") for i in range(5)]
                   + [q("Gravitation", f"FINALTEST {i}: a satellite circles the earth at a height of 600 km") for i in range(5)]
                   + [q("Kinematics", f"FINALTEST {i}: find the range in projectile motion for a launch at 45 degrees", "numerical")
                      for i in range(3)]
                   + [q("Gravitation", f"FINALTEST {i}: the escape speed from a planet twice as dense", "numerical") for i in range(3)])
        db.commit()

    h = _student(client, "lastday.final@example.com")
    body = {"hours": 4, "chapters": ["physics.kinematics", "physics.gravitation"], "topics": ["physics.kinematics.projectile-motion"]}
    assert client.post("/api/prep/last-day/test", headers=h, json={**body, "count": 12}).status_code == 422
    r = client.post("/api/prep/last-day/test", headers=h, json={**body, "count": 10})
    assert r.status_code == 201, r.text
    test_id = r.json()["id"]
    assert client.post("/api/prep/last-day/test", headers=h, json={**body, "count": 10}).json()["id"] == test_id  # not twice

    with SessionLocal() as db:
        test = db.get(MockTest, test_id)
        assert test.status == "ready" and test.config["kind"] == "revision" and test.config["count"] == 10
        [part] = test.config["parts"]
        assert part["subject"] == "Physics" and set(part["chapters"]) == {"Kinematics", "Gravitation"} and part["count"] == 10
        assert part["topics"] == {"Kinematics": ["Projectile motion"]}
        paper = [db.get(BankQuestion, i) for i in test.question_ids]
    assert len(paper) == 10 and {x.chapter for x in paper} <= {"Kinematics", "Gravitation"}
    assert all(x.topic == "Projectile motion" or "projectile" in x.question.lower() for x in paper if x.chapter == "Kinematics")
    assert not any("FINALTEST off" in x.question for x in paper)

    detail = client.get(f"/api/mock/{test_id}", headers=h).json()
    info = detail["pattern_info"]
    assert detail["kind"] == "chapter" and info["name"] == "Last-day test" and info["subjects"] == ["Physics"]
    assert info["subject_counts"] == {"Physics": 10} and info["total_questions"] == 10 and info["duration_min"] == 20
    cards = {c["chapter"]: c for c in client.get(f"/api/mock/{test_id}/warmup", headers=h).json()["cards"]}
    assert cards["Kinematics"]["topics"] == ["Projectile motion"] and len(cards["Gravitation"]["topics"]) > 1

    final = client.post("/api/prep/last-day", headers=h, json=body).json()["final_test"]
    assert final["id"] == test_id and final["status"] == "ready" and final["count"] == 10
    assert client.post(f"/api/mock/{test_id}/start", headers=h).status_code == 200
    busy = client.post("/api/prep/last-day/test", headers=h, json={**body, "count": 15})
    assert busy.status_code == 409 and "Finish" in busy.json()["detail"]

    nothing = client.post("/api/prep/last-day/test", headers=_student(client, "lastday.final.b@example.com"),
                          json={"cover": "studied", "count": 10})
    assert nothing.status_code == 422 and "nothing on today's list" in nothing.json()["detail"]
