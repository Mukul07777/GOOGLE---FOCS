"""GATE papers and school (Class 1 to 12, NCERT books): their syllabi, and the Prep Hub features run as one of each."""
import re
from datetime import date, timedelta

import pytest

from app.services import mock_patterns, planner, question_bank, syllabus


@pytest.mark.parametrize("exam", syllabus.PAPERS)
def test_a_gate_paper_is_library_courses_worth_100_marks(exam):
    syl = syllabus.get(exam)
    library = syllabus.courses()
    assert syl.kind == "gate" and syl.library == "college" and syl.subjects[0] == "General Aptitude"
    assert all(s in library for s in syl.subjects) and len(set(syl.subjects)) == len(syl.subjects)
    assert round(sum(c.weight for c in syl.chapters)) == 100
    aptitude = sum(c.weight for c in syl.subject_chapters("General Aptitude"))
    assert round(aptitude) == 15
    paper = mock_patterns.PATTERNS[f"{exam}_full"]
    assert paper.total_questions == 65 and paper.max_score == 100 and paper.duration_min == 180
    assert set(paper.counts) <= set(syl.subjects) and paper.counts["General Aptitude"] == {"1": 5, "2": 5}
    assert sum(len(paper.sections_for(s)) > 0 for s in syl.subjects) >= len(syl.subjects) - 3  # nearly every subject is asked


CUT_OFF = {"of", "the", "and", "to", "for", "a", "an", "with", "their", "its", "in", "on", "or", "into"}


@pytest.mark.parametrize("exam,cls", syllabus.SCHOOL.items())
def test_a_class_is_its_ncert_books_chapter_by_chapter(exam, cls):
    syl = syllabus.get(exam)
    assert syl.kind == "school" and syl.library == "cbse" and syllabus.label(exam) == f"CBSE Class {cls}" and syllabus.group(exam) == "cbse"
    assert {c.cls for c in syl.chapters} == {cls} and all(c.id.startswith(f"c{cls}.") for c in syl.chapters)
    assert len({c.id for c in syl.chapters}) == len(syl.chapters) and len({t.id for c in syl.chapters for t in c.topics}) == sum(len(c.topics) for c in syl.chapters)
    assert all(len(syl.subject_chapters(s)) >= 3 for s in syl.subjects) and "Mathematics" in syl.subjects
    assert set(syllabus.school_subjects(exam)) <= set(syl.subjects) and len(syllabus.school_subjects(exam)) >= 3
    assert all(syllabus.school_class(c.subject, c.name) == cls for c in syl.chapters)  # a chapter name says which class it is
    assert all(c.topics and 0.75 <= c.weight <= 3 and c.hours > 0 for c in syl.chapters)
    topics = [t.name for c in syl.chapters for t in c.topics]
    assert not [t for t in topics if re.search(r"\b[A-Za-z] [A-Za-z] [A-Za-z]\b", t)]  # no letter-spaced title art ("E x e r c i s e s")
    assert not [t for t in topics if t.split()[-1] in CUT_OFF]  # no heading cut off where the book wrapped it
    assert not [t for t in topics if re.search(r"(\w)\1(\w)\2(\w)\3(\w)\4|[ﬀ-ﬆ]", t)]  # no shadowed ("TTyyppeess") or broken letters


def test_what_each_class_studies():
    assert syllabus.get("cbse_1").subjects == ("English", "Mathematics", "Hindi")
    assert syllabus.get("cbse_5").subjects == ("English", "Mathematics", "Hindi", "The World Around Us")
    assert set(syllabus.get("cbse_8").subjects) == {"English", "Mathematics", "Science", "Social Science", "Hindi", "Sanskrit", "French", "German", "Spanish"}
    assert "French" not in syllabus.school_subjects("cbse_8")  # the third language is Sanskrit until they pick another
    assert {"Information Technology", "Computer Applications"} <= set(syllabus.get("cbse_9").subjects)
    assert "Information Technology" in syllabus.school_subjects("cbse_10")
    ten = syllabus.get("cbse_10")
    assert [c.name for c in ten.subject_chapters("Mathematics")][:2] == ["Real Numbers", "Polynomials"] and len(ten.subject_chapters("Mathematics")) == 14
    assert "Hindi Course A" in ten.subjects and "Hindi Course B" in ten.subjects and "Hindi Course B" not in syllabus.school_subjects("cbse_10")
    twelve = syllabus.get("cbse_12")
    assert {"Accountancy", "Business Studies", "Economics", "History", "Political Science", "Psychology", "Computer Science"} <= set(twelve.subjects)
    assert "Current Electricity" in [c.name for c in twelve.subject_chapters("Physics")]
    weights = {c.name: c.weight for c in twelve.subject_chapters("Mathematics")}
    assert weights["Integrals"] > weights["Matrices"]  # CBSE's marks: Calculus carries the most
    assert syllabus.school_class("Mathematics", "Probability (Class 10)") == 10 and syllabus.school_class("Mathematics", "Probability (Class 12)") == 12


def test_dates_and_legacy_targets():
    assert planner.gate_exam_date(date(2026, 10, 13)) == date(2027, 2, 6)   # the first Saturday of February
    assert planner.gate_exam_date(date(2027, 2, 1)) == date(2028, 2, 5)     # this year's is days away: next year's
    assert planner.board_exam_dates(date(2026, 10, 13), 12)[0][1] == "Pre-boards"
    assert ("Board exams" in [n for _, n in planner.board_exam_dates(date(2026, 10, 13), 12)])
    assert ("Board exams" in [n for _, n in planner.board_exam_dates(date(2026, 10, 13), 10)])
    assert [n for _, n in planner.board_exam_dates(date(2026, 10, 13), 5)] == ["Unit tests round 2", "Final exams", "Half-yearly exams"]
    assert syllabus.exam_of("gate") == "gate_cs" and syllabus.exam_of("cbse") == "cbse_12" and syllabus.label("gate_me") == "GATE ME"


def _student(client, email, exam):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "A Student", "password": "correct-horse-1", "exam_target": exam})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _goal(track, level, target, **more):
    return {"track": track, "class_level": level, "exam_date": (date.today() + timedelta(days=120)).isoformat(), "target": target,
            "dream": None, "weekday_hours": 4, "weekend_hours": 7, "coaching": "self", "standing": {}, **more}


def test_gate_student_end_to_end(client):
    h = _student(client, "gate.ec@example.com", "gate_ec")
    tree = client.get("/api/prep/syllabus", headers=h).json()
    assert tree["kind"] == "gate" and tree["name"].startswith("GATE Electronics") and tree["college"] is None
    assert [s["name"] for s in tree["subjects"]][:2] == ["General Aptitude", "Linear Algebra"] and len(tree["subjects"]) == 15
    opts = client.get("/api/prep/options", headers=h).json()
    assert [t["id"] for t in opts["targets"]["gate"]] == ["air_100", "air_1k", "psu", "qualify"] and opts["rounds"]["gate"][0]["label"].startswith("GATE 20")

    for bad in (_goal("gate", "dropper", "air_10k"), _goal("college", "3", "sgpa_8"), _goal("cbse", "12", "pct_90")):
        assert client.put("/api/prep/goal", headers=h, json=bad).status_code == 422, bad
    standing = {"Signals and Systems": {"all": "done"}, "Control Systems": {"all": "partial"}}
    plan = client.put("/api/prep/goal", headers=h, json=_goal("gate", "dropper", "air_1k", standing=standing)).json()
    assert plan["kind"] == "gate" and plan["goal"]["exam"] == "gate_ec" and plan["goal"]["group"] == "gate"
    assert plan["by_subject"]["Signals and Systems"] == 100 and plan["target"]["label"] == "AIR under 1,000" and plan["weeks"]
    text = " ".join(n["title"] + n["text"] for n in plan["mentor"])
    assert "full mocks" in text or "Priority mode" in text
    assert client.get("/api/auth/me", headers=h).json()["exam_target"] == "gate_ec"

    meta = client.get("/api/mock/meta", headers=h).json()
    assert meta["exam"] == "gate" and meta["default"] == "gate_ec_full" and meta["patterns"][0]["total_questions"] == 65
    assert meta["patterns"][0]["max_score"] == 100 and "Analog Circuits" in meta["syllabus"]
    paper = client.post("/api/mock", headers=h, json={"pattern": "gate_ec_full"}).json()
    assert paper["kind"] == "full" and paper["status"] == "failed" and "AI is offline" in paper["error"]  # an empty bank, no AI in tests
    test = client.post("/api/mock", headers=h, json={"pattern": "chapter", "subject": "Control Systems", "count": 30}).json()
    assert test["pattern_name"] == "Subject test · Control Systems" and test["config"]["exam"] == "college"

    topic = "control-systems.stability-and-root-locus.routh-hurwitz-criterion"
    assert client.get(f"/api/prep/topics/{topic}", headers=h).json()["chapter"]["subject"] == "Control Systems"
    assert client.post(f"/api/prep/topics/{topic}/notes", headers=h).status_code == 503  # no AI here: said, not crashed
    last = client.post("/api/prep/last-day", headers=h, json={"hours": 6}).json()
    assert last["kind"] == "gate" and "Admit card" in last["checklist"][0]["text"]
    assert client.get("/api/weak", headers=h).status_code == 200
    # another paper keeps the goal
    client.patch("/api/auth/me", headers=h, json={"exam_target": "gate_cs"})
    assert client.get("/api/prep/plan", headers=h).json()["goal"]["exam"] == "gate_cs"


def test_class_12_student_end_to_end(client):
    h = _student(client, "boards.12@example.com", "cbse_12")
    tree = client.get("/api/prep/syllabus", headers=h).json()
    assert tree["kind"] == "school" and len(tree["choices"]) == 16 and tree["choices"][:4] == ["Physics", "Chemistry", "Mathematics", "Biology"]
    assert [s["name"] for s in tree["subjects"]] == ["Physics", "Chemistry", "Mathematics", "Biology", "English Core"]  # until they pick
    assert client.put("/api/prep/subjects", headers=h, json={"subjects": ["Astrology"]}).status_code == 422
    assert client.put("/api/prep/subjects", headers=h, json={"subjects": ["Mathematics", "Physics", "Chemistry"]}).json()["subjects"] == ["Physics", "Chemistry", "Mathematics"]
    tree = client.get("/api/prep/syllabus", headers=h).json()
    assert [s["name"] for s in tree["subjects"]] == ["Physics", "Chemistry", "Mathematics"]
    assert all(c["class"] == 12 for s in tree["subjects"] for u in s["units"] for c in u["chapters"])

    assert client.put("/api/prep/goal", headers=h, json=_goal("cbse", "11", "pct_90")).status_code == 422  # they are in Class 12
    plan = client.put("/api/prep/goal", headers=h, json=_goal("cbse", "12", "pct_90", standing={"Physics": {"12": "partial"}})).json()
    assert plan["kind"] == "school" and plan["goal"]["exam"] == "cbse_12" and set(plan["by_subject"]) == {"Physics", "Chemistry", "Mathematics"}
    assert 0 < plan["by_subject"]["Physics"] < 100 and plan["target"]["id"] == "pct_90"
    me = client.get("/api/auth/me", headers=h).json()
    assert me["exam_target"] == "cbse_12" and me["class_level"] == "Class 12"

    meta = client.get("/api/mock/meta", headers=h).json()
    assert meta["exam"] == "cbse" and meta["patterns"] == [] and list(meta["syllabus"]) == ["Physics", "Chemistry", "Mathematics"]
    test = client.post("/api/mock", headers=h, json={"pattern": "chapter", "subject": "Physics", "chapters": ["Current Electricity"], "count": 15}).json()
    assert test["config"]["exam"] == "cbse" and test["duration_min"] == 22 and test["status"] == "failed"  # board questions are written, not borrowed from JEE
    topic = syllabus.get("cbse_12").by_id["c12.physics.current-electricity"].topics[0].id
    assert client.post(f"/api/prep/topics/{topic}/notes", headers=h).status_code == 503
    assert client.get("/api/prep/topics/c11.physics.units-and-measurements.si-units-fundamental-and-derived", headers=h).status_code == 404  # Class 11's
    assert client.get("/api/prep/topics/physics.kinematics.projectile-motion", headers=h).status_code == 404  # JEE's
    assert client.post("/api/prep/last-day", headers=h, json={"hours": 4, "subject": "Physics"}).json()["kind"] == "school"
    jee = _student(client, "boards.jee@example.com", "jee")
    assert client.put("/api/prep/subjects", headers=jee, json={"subjects": ["Physics"]}).status_code == 404


def test_class_11_commerce_student(client):
    h = _student(client, "commerce.11@example.com", "cbse_11")
    commerce = ["Accountancy", "Business Studies", "Economics", "English Core", "Mathematics"]
    assert client.put("/api/prep/subjects", headers=h, json={"subjects": commerce}).json()["subjects"] == [
        "Mathematics", "English Core", "Accountancy", "Business Studies", "Economics"]  # in the class's own order
    tree = client.get("/api/prep/syllabus", headers=h).json()
    assert [s["name"] for s in tree["subjects"]] == ["Mathematics", "English Core", "Accountancy", "Business Studies", "Economics"]
    assert all(c["class"] == 11 for s in tree["subjects"] for u in s["units"] for c in u["chapters"])
    plan = client.put("/api/prep/goal", headers=h, json=_goal("cbse", "11", "pct_90", standing={"Accountancy": {"11": "done"}})).json()
    assert plan["kind"] == "school" and set(plan["by_subject"]) == set(commerce) and plan["by_subject"]["Accountancy"] == 100

    assert client.get("/api/mock/meta", headers=h).status_code == 403  # tests open in the board years (Class 10 and 12)
    assert client.post("/api/mock", headers=h, json={"pattern": "chapter", "subject": "Accountancy", "chapters": ["Introduction to Accounting"], "count": 15}).status_code == 403
    topic = syllabus.get("cbse_11").by_id["c11.accountancy.introduction-to-accounting"].topics[0].id
    assert client.get(f"/api/prep/topics/{topic}", headers=h).json()["chapter"]["subject"] == "Accountancy"
    level = question_bank._school_level("Accountancy", ["Introduction to Accounting"])
    assert level["level"] == "Class 11 school" and level["age"] == "" and "Introduction to Accounting: " in level["covers"]


def test_a_school_or_gate_board_is_filed_under_the_students_own_subjects():
    from app.services import ai

    assert ai._subjects("cbse_10").split(" | ")[:4] == ["English", "Mathematics", "Science", "Social Science"]
    assert "Accountancy" in ai._subjects("cbse_11") and "Operating Systems" in ai._subjects("gate_cs")
    assert ai._subjects("other") == ai.SUBJECTS and ai._subjects("cbse_10").endswith("General")


def test_class_10_student(client):
    h = _student(client, "boards.10@example.com", "cbse_10")
    tree = client.get("/api/prep/syllabus", headers=h).json()
    assert [s["name"] for s in tree["subjects"]] == ["English", "Mathematics", "Science", "Social Science", "Hindi Course A", "Information Technology"]
    assert client.put("/api/prep/goal", headers=h, json=_goal("cbse", "12", "pct_90")).status_code == 422  # they are in Class 10
    plan = client.put("/api/prep/goal", headers=h, json=_goal("cbse", "10", "pct_95", standing={"Science": {"10": "done"}})).json()
    assert plan["kind"] == "school" and plan["goal"]["exam"] == "cbse_10" and plan["target"]["id"] == "pct_95"
    assert plan["by_subject"]["Science"] == 100 and plan["by_subject"]["Mathematics"] == 0  # what they said they had covered
    assert client.get("/api/auth/me", headers=h).json()["class_level"] == "Class 10"
    test = client.post("/api/mock", headers=h, json={"pattern": "chapter", "subject": "Science", "chapters": ["Life Processes"], "count": 15}).json()
    assert test["config"]["exam"] == "cbse" and test["status"] == "failed"
    assert question_bank._school_level("Science", ["Life Processes"])["level"] == "Class 10 board"
    assert question_bank._school_level("Mathematics", ["Probability (Class 10)"])["level"] == "Class 10 board"


def test_class_5_student(client):
    h = _student(client, "young.5@example.com", "cbse_5")
    tree = client.get("/api/prep/syllabus", headers=h).json()
    assert tree["kind"] == "school" and [s["name"] for s in tree["subjects"]] == ["English", "Mathematics", "Hindi", "The World Around Us"]
    assert tree["choices"] == ["English", "Mathematics", "Hindi", "The World Around Us"]
    plan = client.put("/api/prep/goal", headers=h, json=_goal("cbse", "5", "pass", standing={"Mathematics": {"5": "partial"}})).json()
    assert plan["kind"] == "school" and set(plan["by_subject"]) == {"English", "Mathematics", "Hindi", "The World Around Us"}
    assert 0 < plan["by_subject"]["Mathematics"] < 100
    assert client.get("/api/auth/me", headers=h).json()["class_level"] == "Class 5"
    first = syllabus.get("cbse_5").subject_chapters("Mathematics")[0].name
    assert client.post("/api/mock", headers=h, json={"pattern": "chapter", "subject": "Mathematics", "chapters": [first], "count": 15}).status_code == 403
    young = question_bank._school_level("Mathematics", [first])
    assert young["level"] == "Class 5 school" and "young children" in young["age"]
    assert all(t in young["covers"] for t in syllabus.school_topics("Mathematics", first))  # what the book's chapter is about
    assert question_bank._school_level("Physics", ["Kinematics"])["covers"] == ""  # not a school chapter: nothing to add


def test_mock_board_exam_in_the_board_years_only(client):
    h = _student(client, "boards.mock.12@example.com", "cbse_12")
    meta = client.get("/api/mock/meta", headers=h).json()
    assert meta["board_mock"] is True
    test = client.post("/api/mock", headers=h, json={"pattern": "chapter", "subject": "Physics", "board": True}).json()
    every = [c.name for c in syllabus.get("cbse_12").subject_chapters("Physics")]
    assert test["config"]["board"] is True and test["config"]["chapters"] == every and test["config"]["count"] == mock_patterns.BOARD_MOCK_QUESTIONS
    assert test["title"].startswith("Mock board exam · Physics") and test["duration_min"] == mock_patterns.BOARD_MOCK_MINUTES
    nine = _student(client, "class.9@example.com", "cbse_9")
    assert client.post("/api/mock", headers=nine, json={"pattern": "chapter", "subject": "Science", "board": True}).status_code == 403
    plan = client.put("/api/prep/goal", headers=nine, json=_goal("cbse", "9", "pct_90")).json()
    assert all(w["mocks"] == 0 and not w["chapter_tests"] for w in plan["weeks"])  # no tests on a Class 9 plan


def test_ssc_cgl_student(client):
    h = _student(client, "ssc.aspirant@example.com", "ssc_cgl")
    options = client.get("/api/prep/options").json()
    assert options["rounds"]["ssc_cgl"] and options["targets"]["ssc_cgl"]
    plan = client.put("/api/prep/goal", headers=h, json=_goal("ssc_cgl", "dropper", "any_post", exam_date=options["rounds"]["ssc_cgl"][0]["date"])).json()
    assert plan["goal"]["exam"] == "ssc_cgl" and plan["kind"] == "gate"
    assert set(plan["by_subject"]) == set(syllabus.get("ssc_cgl").subjects)
    meta = client.get("/api/mock/meta", headers=h).json()
    assert meta["exam"] == "ssc_cgl" and {p["id"] for p in meta["patterns"]} == {"ssc_cgl_t1", "ssc_cgl_t2"}
    mentors = client.get("/api/mentors", headers=h).json()
    assert mentors["my_exam"] == "ssc_cgl" and "ssc_cgl" in mentors["exams"]
