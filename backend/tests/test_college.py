"""College (B.Tech) students: the course library and semester plans, and every Prep Hub feature run as one of them."""
from datetime import date, timedelta

import pytest

from app.services import mock_patterns, planner, syllabus, topic_notes

TODAY = date(2026, 10, 12)


# ---------------------------------------------------------------- the course library and the semester plans
def test_course_library_is_well_formed():
    library = syllabus.courses()
    assert len(library) >= 100
    for name, course in library.items():
        assert len(name) <= 40, name  # a subject name is stored in 40 characters in several places
        assert name not in mock_patterns.SYLLABUS, name  # never a JEE/NEET subject's name: they share the question bank
        chapters = course["chapters"]
        assert 4 <= len(chapters) <= 8 and 15 <= sum(c["hours"] for c in chapters) <= 50, name
        assert len({syllabus.slug(c["name"]) for c in chapters}) == len(chapters), name
        for c in chapters:
            assert c["hours"] > 0 and c["weight"] > 0 and len(c["topics"]) >= 3, (name, c["name"])
            ids = [f"{syllabus.slug(name)}.{syllabus.slug(c['name'])}.{syllabus.slug(t)}" for t in c["topics"]]
            assert len(set(ids)) == len(ids) and max(map(len, ids)) <= 200, (name, c["name"])  # topic_progress.topic_id
            assert len(f"{syllabus.slug(name)}.{syllabus.slug(c['name'])}") <= 120, (name, c["name"])  # …chapter_id


@pytest.mark.parametrize("exam", syllabus.COLLEGE_BRANCHES)
def test_every_semester_plan_uses_known_courses_once(exam):
    library = syllabus.courses()
    for college in syllabus.COLLEGES:
        semesters, source = syllabus.semester_plan(exam, college)
        seen: dict[str, int] = {}
        assert [n for n, _ in semesters] == list(range(1, 9)) and source
        for n, subjects in semesters:
            assert subjects or n == 8, (exam, college, n)  # (a final semester may be the project alone)
            for s in subjects:
                assert s in library and s not in seen, (exam, college, n, s)
                seen[s] = n
        syl = syllabus.get(exam, college)
        assert syl.is_college and syl.library == "college" and len(syl.subjects) == len(library)
        assert syl.subjects[: len(semesters[0][1])] == semesters[0][1]  # this branch's courses first, in plan order
        assert len({c.id for c in syl.chapters}) == len(syl.chapters)
        assert {c.cls for c in syl.subject_chapters(semesters[2][1][0])} == {3}
        assert syl.college == (college if syllabus.has_own_plan(exam, college) else "other")


def test_a_college_plan_differs_from_the_typical_one_and_branches_share_courses():
    typical, dtu, iitd = (syllabus.get("college_cse", c) for c in ("other", "dtu", "iitd"))
    assert "Operating Systems" in dtu.semester_subjects(3) and "Operating Systems" in typical.semester_subjects(4)
    assert "Operating Systems" in iitd.semester_subjects(6) and "Programming Languages" in iitd.semester_subjects(4)
    assert syllabus.get("college_it", "iiitd").college == "other"  # IIIT-Delhi has no IT branch: the typical plan
    cse, it = syllabus.get("college_cse"), syllabus.get("college_it")
    assert cse.by_id["data-structures.trees"] == it.by_id["data-structures.trees"]  # one course, one set of notes
    assert syllabus.family("college_me") == "college" and syllabus.family("neet") == "neet"
    assert syllabus.label("college_ece") == "B.Tech ECE" and syllabus.label("jee") == "JEE" and syllabus.label(None) == "EXAM"


def test_ai_chemical_and_biotech_branches():
    ai, che, bt = (syllabus.get(b) for b in ("college_ai", "college_che", "college_bt"))
    assert "Foundations of Data Science" in ai.semester_subjects(3) and "Computer Vision" in ai.semester_subjects(7)
    assert "Machine Learning" in ai.semester_subjects(5) and "Generative AI" in ai.semester_subjects(8)
    assert che.semester_subjects(3)[:2] == ("Engineering Mathematics III", "Chemical Process Calculations")
    assert "Mass Transfer I" in che.semester_subjects(5) and "Mass Transfer II" in che.semester_subjects(6)
    assert bt.semester_subjects(3)[:3] == ("Biochemistry", "Cell Biology", "Microbiology")
    assert "Genetic Engineering" in bt.semester_subjects(5) and "Downstream Processing" in bt.semester_subjects(6)
    # Chemical and Biotech share courses: one course, one set of notes and questions
    shared = [b.by_id["bioprocess-engineering.bioreactors"] for b in (che, bt)]
    assert shared[0].topics == shared[1].topics and (shared[0].cls, shared[1].cls) == (7, 5)  # a semester of its own in each
    assert "Chemical Process Calculations" in che.semester_subjects(3) and "Chemical Process Calculations" in bt.semester_subjects(3)
    assert syllabus.label("college_ai") == "B.Tech AI & DS" and syllabus.label("college_bt") == "B.Tech BT"
    assert syllabus.get("college_che", "dtu").college == "other"  # no checked DTU plan for it: the typical one


def test_aktu_and_ggsipu_plans():
    aktu, ipu = syllabus.get("college_cse", "aktu"), syllabus.get("college_cse", "ggsipu")
    assert aktu.college == "aktu" and "AKTU" in aktu.source and ipu.college == "ggsipu" and "GGSIPU" in ipu.source
    assert aktu.semester_subjects(4) == ("Operating Systems", "Theory of Computation", "Object-Oriented Programming")
    assert aktu.semester_subjects(2)[1] == "Numerical Methods" and "Data Structures" in aktu.semester_subjects(3)
    assert ipu.semester_subjects(5)[:2] == ("Engineering Economics", "Compiler Design") and ipu.semester_subjects(8) == ()
    # the project semester keeps the last taught semester's courses until the student picks their own
    assert syllabus.student_subjects(ipu, 8, None) == ipu.semester_subjects(7) == ("Cloud Computing", "Machine Learning")
    che, me = syllabus.get("college_che", "aktu"), syllabus.get("college_me", "aktu")
    assert che.semester_subjects(3)[1:] == ("Chemical Process Calculations", "Fluid Mechanics", "Process Heat Transfer")
    assert "Data Structures" in che.semester_subjects(2) and me.semester_subjects(7) == ("Metrology and Measurements",)
    assert syllabus.get("college_bt", "ggsipu").college == "other"  # no Biotech at GGSIPU's colleges: the typical plan
    assert syllabus.get("college_ai", "ggsipu").semester_subjects(7) == ("Deep Learning", "Reinforcement Learning", "Computer Vision")


def test_a_students_syllabus_is_their_semester_or_their_own_pick():
    class Student:
        exam_target, college, semester, subjects = "college_cse", "dtu", 4, None

    s = Student()
    assert syllabus.of(s).subjects == syllabus.get("college_cse", "dtu").semester_subjects(4)
    s.subjects = ["Operating Systems", "No Such Course", "Engineering Hydrology"]
    assert syllabus.of(s).subjects == ("Operating Systems", "Engineering Hydrology")  # any course of the library
    assert len(syllabus.of(s, whole=True).subjects) == len(syllabus.courses())
    s.semester, s.subjects = None, None
    assert syllabus.of(s).subjects == syllabus.get("college_cse", "dtu").semester_subjects(1)
    s.exam_target = "upsc"
    assert syllabus.of(s) is None


# ---------------------------------------------------------------- the plan engine on one semester
def _semester(n=3, college="other"):
    full = syllabus.get("college_cse", college)
    return full.only(full.semester_subjects(n))


def test_college_exam_dates_and_revision_window():
    rounds = planner.college_exam_dates(TODAY)
    assert [name for _, name in rounds] == ["End-semester exams", "Mid-semester exams", "End-semester exams"]
    assert rounds[0][0] == date(2026, 11, 25) and planner.default_college_exam_date(TODAY) == date(2026, 11, 25)
    assert planner.default_college_exam_date(date(2026, 11, 20)) == date(2027, 5, 5)  # five days away: the next ones
    assert planner.revision_window(TODAY, date(2026, 11, 25), college=True) == 7
    assert planner.revision_window(date(2026, 1, 10), date(2026, 5, 5), college=True) == 14
    assert planner.revision_window(TODAY, TODAY + timedelta(days=300)) == 45  # entrance exams keep their long window


def test_a_semester_plan_takes_chapters_in_teaching_order_and_names_its_tests():
    syl = _semester()
    goal = planner.Goal("college_cse", "college", "3", date(2026, 12, 1), "sgpa_8", 3, 5)
    plan = planner.build(goal, syl, planner.Progress(), date(2026, 8, 10))
    assert plan["kind"] == "college" and plan["status"] in ("comfortable", "on_track") and not plan["unfinished"]
    assert plan["revision_weeks"] == 2 and plan["target"]["label"] == "8+ SGPA"
    first = {}
    for week in plan["weeks"]:
        for item in week["learn"]:
            first.setdefault(item["subject"], item["chapter"])
    assert first == {s: syl.subject_chapters(s)[0].name for s in syl.subjects}  # each course from its first chapter
    milestones = [m for month in plan["months"] for m in month["milestones"]]
    assert "Data Structures complete" in milestones and "Revision and subject tests begin" in milestones
    assert not any("Class" in m or "mock" in m.lower() for m in milestones)
    text = " ".join(n["text"] + n["title"] for n in plan["mentor"])
    assert "subject tests" in text and "outside classes" not in text  # 3.6 h a day is what 8+ SGPA takes
    assert not any(w in text for w in ("PYQ", "cut-off", "mock", "JEE", "rank"))
    learn = [t for t in plan["today"]["tasks"] if t["kind"] == "learn"]
    assert len(learn) == 2 and {t["subject"] for t in learn} <= set(syl.subjects)

    # the last days before the exam: a subject test, not a three-hour mock
    sunday = date(2026, 11, 29)
    late = planner.build(goal, syl, planner.Progress(), sunday)["today"]["tasks"]
    assert [(t["title"], t["minutes"]) for t in late if t["kind"] == "mock"] == [("Subject test + analysis", 90)]
    # every subject gets its turn over the rotation
    seen = set()
    for i in range(len(syl.subjects)):
        day = planner.build(goal, syl, planner.Progress(), date(2026, 8, 10) + timedelta(days=i))["today"]["tasks"]
        seen |= {t["subject"] for t in day if t["kind"] == "learn"}
    assert seen == set(syl.subjects)


def test_too_little_time_puts_foundations_and_marks_first():
    syl = _semester()
    goal = planner.Goal("college_cse", "college", "3", date(2026, 11, 25), "clear", 0.5, 1)
    plan = planner.build(goal, syl, planner.Progress(), TODAY)
    assert plan["priority_mode"] and plan["status"] == "behind" and plan["unfinished"]
    assert "% of the marks" in plan["mentor"][0]["text"]


# ---------------------------------------------------------------- the API as a college student
def _student(client, email, exam="college_cse", **extra):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "College Student", "password": "correct-horse-1",
                                                "exam_target": exam, **extra})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _goal(semester="3", **changes):
    exam_date = (date.today() + timedelta(days=60)).isoformat()
    return {"track": "college", "class_level": semester, "exam_date": exam_date, "target": "sgpa_8", "dream": None,
            "weekday_hours": 3, "weekend_hours": 5, "coaching": "self", "standing": {}, **changes}


def test_set_up_college_semester_and_subjects(client):
    h = _student(client, "college.setup@example.com", college="dtu", semester=3)
    me = client.get("/api/auth/me", headers=h).json()
    assert (me["exam_target"], me["college"], me["semester"], me["class_level"]) == ("college_cse", "dtu", 3, "Semester 3")

    info = client.get("/api/prep/college", headers=h).json()
    assert info["branch"]["short"] == "CSE" and info["college"] == "dtu" and info["own_plan"] and "DTU" in info["source"]
    assert info["subjects"] == info["semesters"][2]["subjects"] and "Operating Systems" in info["subjects"] and not info["picked"]
    assert {c["id"]: c["has_plan"] for c in info["colleges"]} == {"other": False, "iitd": True, "iiitd": True, "dtu": True, "nsut": True,
                                                                       "ggsipu": True, "aktu": True}
    assert len(info["catalogue"]) == len(syllabus.courses()) and all(c["hours"] and c["topics"] for c in info["catalogue"])
    # looking at another college before saving changes nothing
    assert "Discrete Mathematics" in client.get("/api/prep/college?college=iitd&semester=3", headers=h).json()["subjects"]
    assert client.get("/api/auth/me", headers=h).json()["college"] == "dtu"

    tree = client.get("/api/prep/syllabus", headers=h).json()
    assert tree["kind"] == "college" and tree["college"]["semester"] == 3 and tree["name"].startswith("B.Tech Computer Science")
    assert [s["name"] for s in tree["subjects"]] == info["subjects"] and all(s["mine"] and s["semester"] == 3 for s in tree["subjects"])
    assert tree["stats"]["subjects"] == 5 and 20 <= tree["stats"]["chapters"] <= 40
    ahead = client.get("/api/prep/syllabus?semester=5", headers=h).json()  # looking ahead at the plan
    assert "Compiler Design" in [s["name"] for s in ahead["subjects"]] and not any(s["mine"] for s in ahead["subjects"])

    # their own list: drop one, add a course from another branch
    mine = [s for s in info["subjects"] if s != "Software Engineering"] + ["Signals and Systems"]
    saved = client.put("/api/prep/college", headers=h, json={"college": "dtu", "semester": 3, "subjects": mine}).json()
    assert saved["picked"] and saved["subjects"] == mine
    assert [s["name"] for s in client.get("/api/prep/syllabus", headers=h).json()["subjects"]] == mine
    for bad in ({"college": "dtu", "semester": 9}, {"college": "mit", "semester": 3},
                {"college": "dtu", "semester": 3, "subjects": ["Astrology"]}, {"college": "dtu", "semester": 3, "subjects": mine * 3}):
        assert client.put("/api/prep/college", headers=h, json=bad).status_code == 422, bad
    # picking exactly the plan, or moving to the next semester, goes back to following the plan
    plan = client.put("/api/prep/college", headers=h, json={"college": "dtu", "semester": 3, "subjects": info["subjects"]}).json()
    assert not plan["picked"]
    nxt = client.put("/api/prep/college", headers=h, json={"college": "dtu", "semester": 4}).json()
    assert nxt["semester"] == 4 and "Database Management Systems" in nxt["subjects"]
    assert client.get("/api/auth/me", headers=h).json()["class_level"] == "Semester 4"

    # the profile form can change them too; another branch starts from that branch's plan
    client.put("/api/prep/college", headers=h, json={"college": "dtu", "semester": 4, "subjects": ["Operating Systems"]})
    moved = client.patch("/api/auth/me", headers=h, json={"exam_target": "college_me"}).json()
    assert moved["subjects"] is None and client.get("/api/prep/college", headers=h).json()["branch"]["short"] == "ME"
    assert "Fluid Mechanics" in [s["name"] for s in client.get("/api/prep/syllabus", headers=h).json()["subjects"]]
    jee = _student(client, "college.notcollege@example.com", exam="jee")
    assert client.get("/api/prep/college", headers=jee).status_code == 404


def test_goal_plan_and_daily_ticks_for_a_semester(client):
    h = _student(client, "college.plan@example.com", exam="college_ece")
    opts = client.get("/api/prep/options", headers=h).json()
    assert [t["id"] for t in opts["targets"]["college"]] == ["sgpa_9", "sgpa_8", "sgpa_7", "clear"]
    assert set(opts["subjects"]) == {"jee", "neet", "ssc_cgl"} and opts["college"]["dates"] and opts["college"]["default_date"]
    assert client.get("/api/prep/plan", headers=h).json() is None

    for bad in (_goal(track="jee_main"), _goal(semester="12"), _goal(target="air_10k"), _goal(semester="9")):
        assert client.put("/api/prep/goal", headers=h, json=bad).status_code == 422, bad
    standing = {"Signals and Systems": {"all": "done"}, "Digital Logic Design": {"all": "partial"}, "Physics": {"11": "done"}}
    plan = client.put("/api/prep/goal", headers=h, json=_goal(standing=standing)).json()
    assert plan["kind"] == "college" and plan["goal"]["kind"] == "college" and plan["goal"]["exam"] == "college_ece"
    assert plan["goal"]["standing"].keys() == {"Signals and Systems", "Digital Logic Design"} and plan["target"]["id"] == "sgpa_8"
    assert plan["by_subject"]["Signals and Systems"] == 100 and 0 < plan["by_subject"]["Digital Logic Design"] < 100
    assert set(plan["by_subject"]) == set(syllabus.get("college_ece").semester_subjects(3)) and plan["weeks"] and plan["mentor"]
    me = client.get("/api/auth/me", headers=h).json()
    assert (me["exam_target"], me["semester"], me["class_level"]) == ("college_ece", 3, "Semester 3")  # still an ECE student
    assert me["daily_goal_min"] == round((5 * 3 + 2 * 5) / 7 * 60)

    today = plan["today"]
    learn = next((t for t in today["tasks"] if t["kind"] == "learn"), None)
    if learn:  # (a rest day has none)
        done = client.put(f"/api/prep/today/{learn['key']}", headers=h, json={"done": True}).json()
        assert next(t for t in done["tasks"] if t["key"] == learn["key"])["done"]
        tree = client.get("/api/prep/syllabus", headers=h).json()
        ticked = {t["id"] for s in tree["subjects"] for u in s["units"] for c in u["chapters"] for t in c["topics"] if t["done"]}
        assert {t["id"] for t in learn["topics"]} <= ticked

    edited = client.patch("/api/prep/plan", headers=h, json={"target": "sgpa_9", "weekday_hours": 4}).json()
    assert edited["target"]["id"] == "sgpa_9" and edited["hours"]["weekday"] == 4
    assert client.patch("/api/prep/plan", headers=h, json={"target": "air_1k"}).status_code == 422
    chapter = "control-systems.stability-and-root-locus"  # semester 4 in the plan: not this semester's
    assert client.put(f"/api/prep/plan/chapters/{chapter}", headers=h, json={"action": "next"}).status_code == 404
    mine = "network-analysis-and-synthesis.two-port-networks"
    assert client.put(f"/api/prep/plan/chapters/{mine}", headers=h, json={"action": "next"}).json()["pinned"] == [mine]
    assert client.put(f"/api/prep/plan/chapters/{mine}", headers=h, json={"action": "skip"}).json()["skipped"][0]["id"] == mine

    # a JEE student can't be given a semester, and a college student isn't turned into a JEE one by accident
    jee = _student(client, "college.jee@example.com", exam="jee")
    assert client.put("/api/prep/goal", headers=jee, json=_goal()).status_code == 422


def test_topics_notes_tests_and_revision(client):
    h = _student(client, "college.study@example.com", college="other", semester=4)
    tree = client.get("/api/prep/syllabus", headers=h).json()
    os_course = next(s for s in tree["subjects"] if s["name"] == "Operating Systems")
    chapter = os_course["units"][0]["chapters"][3]
    assert os_course["units"][0]["name"] == "Course syllabus" and chapter["name"] == "Deadlocks" and chapter["class"] == 4
    topic = chapter["topics"][3]["id"]
    assert topic == "operating-systems.deadlocks.banker-s-algorithm"

    detail = client.get(f"/api/prep/topics/{topic}", headers=h).json()
    assert detail["kind"] == "college" and detail["chapter"]["subject"] == "Operating Systems" and not detail["notes_ready"]
    assert client.put(f"/api/prep/topics/{topic}", headers=h, json={"done": True}).json()["done"] == 1
    # a topic of a course outside this semester opens too (revising last semester, reading ahead)
    assert client.get("/api/prep/topics/data-structures.trees.avl-trees-and-rotations", headers=h).status_code == 200
    assert client.get("/api/prep/topics/physics.kinematics.projectile-motion", headers=h).status_code == 404

    # no AI in the test run: notes and practice say so instead of failing
    for path in (f"/api/prep/topics/{topic}/notes", f"/api/prep/chapters/{chapter['id']}/capsule"):
        assert client.post(path, headers=h).status_code == 503
    quiz = client.post("/api/quiz/generate", headers=h, json={"topic_id": topic, "difficulty": "medium", "n_mcq": 2, "n_tf": 1, "n_subjective": 0})
    assert quiz.status_code == 503 and "AI" in quiz.json()["detail"]

    meta = client.get("/api/mock/meta", headers=h).json()
    assert meta["exam"] == "college" and meta["patterns"] == [] and meta["default"] is None
    assert list(meta["syllabus"]) == [s["name"] for s in tree["subjects"]] and "Deadlocks" in meta["syllabus"]["Operating Systems"]
    test = client.post("/api/mock", headers=h, json={"pattern": "chapter", "subject": "Operating Systems", "chapters": ["Deadlocks"], "count": 15})
    assert test.status_code == 201 and test.json()["kind"] == "chapter" and "Chapter test · Operating Systems" in test.json()["title"]
    assert test.json()["status"] == "failed" and "AI is offline" in test.json()["error"]  # an empty bank and no AI: said plainly
    whole = client.post("/api/mock", headers=h, json={"pattern": "chapter", "subject": "Operating Systems", "count": 30}).json()
    assert whole["pattern_name"] == "Subject test · Operating Systems" and len(whole["config"]["chapters"]) == 6
    assert whole["config"]["exam"] == "college" and whole["duration_min"] == 45
    for bad in ({"subject": "Operating Systems", "chapters": ["Kinematics"]}, {"subject": "Astrology", "chapters": ["x"]}):
        assert client.post("/api/mock", headers=h, json={"pattern": "chapter", "count": 15, **bad}).status_code == 422

    client.put(f"/api/prep/chapters/{chapter['id']}/revision", headers=h, json={"done": True})
    last = client.post("/api/prep/last-day", headers=h, json={"hours": 4, "subject": "Operating Systems"}).json()
    assert last["kind"] == "college" and last["scope"] == "subject" and last["subjects"] == [s["name"] for s in tree["subjects"]]
    assert "Hall ticket" in last["checklist"][0]["text"] and not any("admit card" in c["text"].lower() for c in last["checklist"])
    picked = client.post("/api/prep/last-day", headers=h, json={"hours": 2, "chapters": [chapter["id"]]}).json()
    assert [c["id"] for c in picked["chapters"]] == [chapter["id"]] and picked["chapters"][0]["revised_today"]


def test_weak_spots_from_a_college_test(client):
    h = _student(client, "college.weak@example.com", exam="college_ee", college="iitd", semester=3)
    assert client.get("/api/weak", headers=h).json()["open"] == []
    body = {"title": "Minor 1: Circuit Theory", "score": 14, "max_score": 30, "source": "manual", "subjects": [],
            "weak": [{"chapter_id": "network-analysis-and-synthesis.transient-analysis", "topic_id": None, "misses": 3},
                     {"chapter_id": "physics.kinematics", "topic_id": None, "misses": 2}]}
    saved = client.post("/api/weak/tests", headers=h, json=body).json()
    assert [w["chapter"]["name"] for w in saved["open"]] == ["Transient Analysis"] and saved["tests"][0]["weak"] == 1
    assert client.put("/api/prep/goal", headers=h, json=_goal()).status_code == 200
    today = client.get("/api/prep/plan", headers=h).json()["today"]
    if today["minutes"]:
        assert today["tasks"][0]["kind"] == "fix" and today["tasks"][0]["chapter"] == "Transient Analysis"
    # next semester the subject is behind them, but the weak spot stays on the list until it is cleared
    client.put("/api/prep/college", headers=h, json={"college": "iitd", "semester": 4})
    assert [w["chapter"]["name"] for w in client.get("/api/weak", headers=h).json()["open"]] == ["Transient Analysis"]


def test_changing_what_you_prepare_for_keeps_each_plan(client):
    h = _student(client, "college.switch@example.com", exam="jee")
    jee_goal = {"track": "jee_main", "class_level": "12", "exam_date": (date.today() + timedelta(days=200)).isoformat(),
                "target": "air_10k", "weekday_hours": 6, "weekend_hours": 9, "coaching": "self", "standing": {}}
    assert client.put("/api/prep/goal", headers=h, json=jee_goal).json()["goal"]["exam"] == "jee"
    client.patch("/api/auth/me", headers=h, json={"exam_target": "college_cse", "semester": 2, "college": "nsut"})
    assert client.get("/api/prep/plan", headers=h).json() is None  # the JEE plan is not a B.Tech student's plan
    tree = client.get("/api/prep/syllabus", headers=h).json()
    assert tree["kind"] == "college" and "Data Structures" in [s["name"] for s in tree["subjects"]]
    plan = client.put("/api/prep/goal", headers=h, json=_goal(semester="2")).json()
    assert plan["goal"]["exam"] == "college_cse" and plan["pinned"] == []
    client.patch("/api/auth/me", headers=h, json={"exam_target": "upsc"})
    assert client.get("/api/prep/syllabus", headers=h).status_code == 404  # (the goal is for B.Tech; UPSC has no Prep Hub)


def test_notes_library_is_shared_by_every_branch(client):
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        topic_notes._store(db, "college", "detailed", "data-structures.trees.heaps-and-heap-operations", "## In one line\nA heap…", "test", True)
    for n, exam in enumerate(("college_cse", "college_it", "college_ee")):
        h = _student(client, f"college.library{n}@example.com", exam=exam)
        note = client.post("/api/prep/topics/data-structures.trees.heaps-and-heap-operations/notes", headers=h).json()
        assert note["notes_md"].startswith("## In one line") and not note["written_now"] and note["subject"] == "Data Structures"


def test_college_wording_reaches_the_prompts():
    syl = syllabus.get("college_me")
    chapter = syl.by_id["heat-and-mass-transfer.radiation"]
    assert syllabus.place(chapter) == "the B.Tech course Heat and Mass Transfer"
    assert syllabus.place(syllabus.get("jee").by_id["physics.kinematics"]) == "Physics, Class 11"
    voice = topic_notes._voice("college")
    prompt = topic_notes.DETAILED_SYSTEM.format(exam=topic_notes._label("college"), topic="Shape factors", chapter=chapter.name,
                                                where=syllabus.place(chapter), siblings="none", **voice)
    assert "## How exams ask it" in prompt and "B.Tech course Heat and Mass Transfer" in prompt
    assert not any(w in prompt for w in ("NCERT", "Class 1", "calculator", "COLLEGE", "JEE"))
    school = topic_notes.DETAILED_SYSTEM.format(exam=topic_notes._label("neet"), topic="t", chapter="c", where="Biology, Class 11",
                                                siblings="none", **topic_notes._voice("neet"))
    assert "## How NEET asks it" in school and "NCERT" in school
    pattern = mock_patterns.chapter_pattern("Heat and Mass Transfer", ["Radiation"], 10)
    assert pattern.exam == "college" and pattern.max_score == 10 and pattern.sections[0].wrong == 0
    assert mock_patterns.chapter_targets("Heat and Mass Transfer", 10, ["Radiation", "Forced Convection"]) == {"Radiation": 5, "Forced Convection": 5}
    code = "## In one line\nx\n## Core ideas\n- a\n## How it works\n```c\nint main() { return 0; }\n```\n" + "word " * 120
    assert "```c\nint main() { return 0; }\n```" in topic_notes._tidy(code, 100)  # code blocks survive
    assert topic_notes._tidy("```markdown\n" + code + "\n```", 100).startswith("## In one line")


def test_ordinary_words_are_not_taken_for_a_model_thinking_aloud():
    from app.services.question_bank import looks_clean

    fine = ["The four conditions are mutual exclusion, hold and wait, no preemption and circular wait. Hence option (a).",
            "Is the state safe? No, the system has no safe sequence: P0 can never finish.",
            "Wait-for graphs are used for detection. A cycle in the wait-for graph means deadlock.",
            "Each process must wait until the semaphore is released; the average wait is 5 ms.",
            "No, because the graph is acyclic. Actually the same holds for any tree."]
    shaky = ["x = 5. Wait, that doesn't match the options.", "So T = 12 N, wait, the mass is 3 kg, so T = 18 N.", "Hmm, let's check the sign again.",
             "The answer is 4. No, wait, it is 8.", "Actually, the correct formula is different.", "I think the answer is B.",
             "Hold on, the limit was taken wrongly.", "Wait a second: the units are wrong."]
    for text in fine:
        assert looks_clean("A question of ordinary length?", text), text
    for text in shaky:
        assert not looks_clean("A question of ordinary length?", text), text


def test_a_question_that_leans_on_another_question_is_dropped():
    from app.services.question_bank import _clean

    item = {"chapter": "Profitability Analysis", "difficulty": "medium", "options": ["2 years", "3 years", "4 years", "5 years"],
            "answer_index": 1, "solution": "Payback is reached in the third year."}
    leaning = "For the cash flows in question 2, what is the simple payback period?"
    alone = "A plant costing ₹1,00,000 returns ₹40,000 a year. What is its simple payback period, to the nearest year?"
    assert _clean({**item, "question": leaning}, "Plant Design and Economics", "mcq", ["Profitability Analysis"]) is None
    assert _clean({**item, "question": alone}, "Plant Design and Economics", "mcq", ["Profitability Analysis"])
    charges = "Two charges q1 = 2 μC and q2 = 3 μC are 1 m apart. What is the force between them?"
    assert _clean({**item, "question": charges}, "Plant Design and Economics", "mcq", ["Profitability Analysis"])  # not "question 1"


def test_what_is_stored_fits_the_columns_the_cloud_database_already_has(client):
    """Postgres enforces VARCHAR lengths (SQLite, which the tests run on, does not): nothing a college student saves
    may be longer than its column, or it would fail only in production."""
    from sqlalchemy import select

    from app.core.database import Base, SessionLocal
    from app.models.prep import StudyGoal
    from app.models.user import User

    h = _student(client, "college.columns@example.com", exam="college_ece", college="iiitd", semester=3)
    assert client.put("/api/prep/goal", headers=h, json=_goal()).status_code == 200
    topic = "signals-and-systems.sampling-and-z-transform.properties-and-inverse-z-transform"
    client.put(f"/api/prep/topics/{topic}", headers=h, json={"done": True})
    client.post("/api/weak/tests", headers=h, json={"title": "Quiz 1", "score": 4, "max_score": 10, "source": "manual", "subjects": [],
                                                    "weak": [{"chapter_id": topic.rsplit(".", 1)[0], "topic_id": topic, "misses": 2}]})
    with SessionLocal() as db:
        uid = db.scalar(select(User.id).where(User.email == "college.columns@example.com"))
        goal = db.scalar(select(StudyGoal).where(StudyGoal.user_id == uid))
        assert goal.exam == "college" and goal.track == "college" and goal.class_level == "3"
        checked = 0
        for table in Base.metadata.sorted_tables:
            limited = [c for c in table.columns if getattr(c.type, "length", None)]
            if not limited:
                continue
            for row in db.execute(select(*limited)).all():
                for col, value in zip(limited, row, strict=True):
                    assert value is None or len(str(value)) <= col.type.length, (table.name, col.name, value)
                    checked += 1
        assert checked > 20

    # another branch keeps the goal (the exam date, the grade, the hours) and plans the new branch's subjects
    client.patch("/api/auth/me", headers=h, json={"exam_target": "college_me"})
    plan = client.get("/api/prep/plan", headers=h).json()
    assert plan["goal"]["exam"] == "college_me" and plan["target"]["id"] == "sgpa_8" and plan["expected_now"] is None
    assert set(plan["by_subject"]) == set(syllabus.get("college_me").semester_subjects(3))
