"""A student gets their own exam's content.

Before launch (2026-10-19): a JEE paper short of questions was topped up with any exam's questions on the same chapter
(Class 11-12 boards included), and a student preparing for UPSC, CA or anything else was offered JEE Main mocks and
kept an old JEE plan. JEE Main and NEET do share Physics and Chemistry questions, on purpose (the user's call)."""
from datetime import date, timedelta

from app.api.auth import CLOSED_SIGNUP_EXAMS
from app.core.database import SessionLocal
from app.models.mock import BankQuestion
from app.services import ai, question_bank, syllabus, topic_notes
from app.services.text_utils import guess_subject


def _student(client, email, exam):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Scope Student", "password": "correct-horse-1",
                                                "exam_target": "jee" if exam in CLOSED_SIGNUP_EXAMS else exam})
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    if exam in CLOSED_SIGNUP_EXAMS:  # closed to new sign-ups: a student who joined before switches to it
        assert client.patch("/api/auth/me", headers=h, json={"exam_target": exam}).status_code == 200
    return h


def _add(exam: str, chapter: str, n: int, tag: str) -> set[int]:
    with SessionLocal() as db:
        rows = []
        for i in range(n):
            text = f"{tag} {chapter} scope question {i}: pick the right option"
            q = BankQuestion(exam=exam, subject="Physics", chapter=chapter, qtype="mcq", question=text,
                             options=["one", "two", "three", "four"], answer="1", solution="Because.", verified=True,
                             source="ai", fingerprint=question_bank.fingerprint(text))
            db.add(q)
            rows.append(q)
        db.commit()
        return {q.id for q in rows}


def test_physics_and_chemistry_are_shared_by_jee_and_neet_and_nothing_else_mixes(client):  # (client: the tables exist)
    """JEE Main and NEET share Physics and Chemistry questions (the student's own exam's first); NEET never gets JEE
    Advanced ones (a level above), and board or college questions never fill an entrance paper."""
    chapter = "Gravitation"  # the shipped seed has JEE Main questions on it too
    neet = _add("neet", chapter, 6, "scope-neet")
    board = _add("cbse", chapter, 6, "scope-cbse")
    advanced = _add("jee_advanced", chapter, 3, "scope-adv")
    with SessionLocal() as db:
        main = {q.id for q in db.query(BankQuestion).filter(BankQuestion.chapter == chapter, BankQuestion.qtype == "mcq",
                                                            BankQuestion.exam == "jee_main")}
        picked, missing = question_bank.pick(db, "Physics", "mcq", len(main), set(), chapters=[chapter], exam="jee")
        assert {q.id for q in picked} == main and not missing  # their own exam's first
        picked, missing = question_bank.pick(db, "Physics", "mcq", 100, set(), chapters=[chapter], exam="jee")
        assert {q.id for q in picked} == main | neet | advanced and missing  # then NEET's and Advanced; never the boards'
        picked, missing = question_bank.pick(db, "Physics", "mcq", 6, set(), chapters=[chapter], exam="neet")
        assert {q.id for q in picked} == neet and not missing
        picked, _ = question_bank.pick(db, "Physics", "mcq", 100, set(), chapters=[chapter], exam="neet")
        assert {q.id for q in picked} == neet | main  # JEE Main's too, never JEE Advanced or the boards'
        picked, _ = question_bank.pick(db, "Physics", "mcq", 100, set(), chapters=[chapter], exam="cbse")
        assert {q.id for q in picked} == board

        g = syllabus.get("jee").by_id["physics.gravitation"]
        shown = topic_notes.exam_questions(db, "jee", g, limit=100)
        exams = [db.get(BankQuestion, q["id"]).exam for q in shown]
        assert set(exams) <= {"jee_main", "jee_advanced", "neet"} and exams[0] == "jee_main"
        n = syllabus.get("neet").by_id["physics.gravitation"]
        exams = [db.get(BankQuestion, q["id"]).exam for q in topic_notes.exam_questions(db, "neet", n, limit=100)]
        assert set(exams) == {"neet", "jee_main"} and exams[0] == "neet"


def test_biology_and_mathematics_stay_with_their_exam(client):
    bio = _add("neet", "Evolution", 3, "scope-bio")
    with SessionLocal() as db:
        db.query(BankQuestion).filter(BankQuestion.id.in_(bio)).update({"subject": "Biology"}, synchronize_session=False)
        db.commit()
        picked, _ = question_bank.pick(db, "Biology", "mcq", 10, set(), chapters=["Evolution"], exam="jee")
        assert not picked
        assert question_bank.exam_family("neet", "Mathematics") == ("neet",)
        assert question_bank.exam_family("jee", "Mathematics") == ("jee_main", "jee_advanced")


def test_students_get_only_their_own_exams_papers(client):
    jee = _student(client, "scope.jee@example.com", "jee")
    assert client.post("/api/mock", headers=jee, json={"pattern": "neet_180"}).status_code == 422
    biology = {"pattern": "chapter", "subject": "Biology", "chapters": ["Evolution"], "count": 10}
    assert client.post("/api/mock", headers=jee, json=biology).status_code == 422
    neet = _student(client, "scope.neet@example.com", "neet")
    assert client.post("/api/mock", headers=neet, json={"pattern": "jee_main_30"}).status_code == 422

    for exam in ("upsc", "ca", "other"):  # no syllabus here: no papers, and never JEE's
        h = _student(client, f"scope.{exam}@example.com", exam)
        r = client.get("/api/mock/meta", headers=h)
        assert r.status_code == 404 and "Settings" in r.json()["detail"]
        assert client.post("/api/mock", headers=h, json={"pattern": "jee_main_30"}).status_code == 404


def test_switching_to_an_exam_without_a_syllabus_hides_the_old_plan(client):
    h = _student(client, "scope.switch@example.com", "jee")
    goal = {"track": "jee_main", "class_level": "12", "exam_date": (date.today() + timedelta(days=200)).isoformat(),
            "target": "air_10k", "weekday_hours": 6, "weekend_hours": 9, "coaching": "self", "standing": {}}
    assert client.put("/api/prep/goal", headers=h, json=goal).status_code == 200
    client.patch("/api/auth/me", headers=h, json={"exam_target": "upsc"})
    assert client.get("/api/prep/plan", headers=h).json() is None
    assert client.get("/api/prep/syllabus", headers=h).status_code == 404
    client.patch("/api/auth/me", headers=h, json={"exam_target": "jee"})  # back to JEE: the plan is still there
    assert client.get("/api/prep/plan", headers=h).json() is not None


def test_a_paper_left_preparing_by_a_restart_is_picked_up_again(client, monkeypatch):
    """A deploy or restart kills the thread writing a paper: it stayed "preparing" for ever, and asking for the same
    test again handed back the same stuck paper."""
    import threading

    from app.models.mock import MockTest
    from app.services import mock
    from app.services.llm import LLMClient

    h = _student(client, "scope.restart@example.com", "jee")
    me = client.get("/api/auth/me", headers=h).json()
    with SessionLocal() as db:
        test = MockTest(user_id=me["id"], pattern="jee_main_30", title="Full mock #1", duration_min=180, status="preparing",
                        progress=40, question_ids=[], responses={})
        db.add(test)
        db.commit()
        test_id = test.id
    started, done = [], threading.Event()

    def start(t):  # a writer that stays busy until the test lets it go
        started.append(t.id)
        threading.Thread(target=done.wait, name=f"mock-{t.id}", daemon=True).start()

    monkeypatch.setattr(LLMClient, "available", property(lambda self: True))
    monkeypatch.setattr(mock, "_start", start)
    try:
        assert client.get(f"/api/mock/{test_id}", headers=h).json()["status"] == "preparing"
        client.get("/api/mock", headers=h)  # the list polls too: one writer, not two
        assert client.post("/api/mock", headers=h, json={"pattern": "jee_main_30"}).json()["id"] == test_id
        assert started == [test_id]
    finally:
        done.set()


def test_a_lecture_is_filed_only_under_a_subject_of_the_students_exam():
    assert ai._subjects("neet") == "Physics | Chemistry | Biology | General"
    assert ai._subjects("jee") == "Physics | Chemistry | Mathematics | General"
    assert "Economics" not in ai._subjects("ssc_cgl") and "Physics" not in ai._subjects("ssc_cgl")
    assert "Economics" in ai._subjects("other")  # no syllabus: the open list

    assert ai.fit_subject("Economics", "neet") == "General"  # the keyword guess, or an old shared note
    assert ai.fit_subject("Mathematics", "neet") == "General"
    assert ai.fit_subject(" biology ", "neet") == "Biology"
    assert ai.fit_subject(guess_subject("market price and cost"), "jee") == "General"
    assert ai.fit_subject("Economics", "other") == "Economics"
    assert ai.fit_subject(None, "neet") is None


def _boards(n, words=40):
    return [{"topic": f"Topic {i}", "notes_md": f"board{i} " + "word " * words} for i in range(n)]


def test_a_revision_sheet_grows_with_how_much_was_studied():
    assert ai.sheet_size(_boards(2)) == "short"
    assert ai.sheet_size(_boards(8)) == "standard"
    assert ai.sheet_size(_boards(3, 200)) == "standard"  # few boards, but a lot on them
    assert ai.sheet_size(_boards(20)) == "long"
    assert ai.sheet_size(_boards(6, 500)) == "long"
    assert "Lecture map" in ai.SHEET_SHAPES["long"]["shape"] and "Lecture map" not in ai.SHEET_SHAPES["short"]["shape"]
    for shape in ai.SHEET_SHAPES.values():  # (each must survive the format call)
        assert ai.SUMMARY_SYSTEM.format(exam="NEET", subjects="Physics", shape=shape["shape"], cards=shape["cards"])


def test_the_end_of_a_long_lecture_reaches_the_sheet():
    notes = _boards(60, 120)
    text = ai.lecture_material(notes)
    assert len(text) <= ai.SHEET_CHARS
    assert all(f"board{i} " in text for i in range(60))  # every board, not just the first ones

    small = [{"topic": "A", "notes_md": "tiny"}, *_boards(30, 400)]
    assert "tiny" in ai.lecture_material(small)  # a short board keeps all of itself, and leaves the rest to the others
    assert ai.lecture_material(_boards(3)).count("word") == 120  # nothing cut when it fits


def test_a_college_course_outside_the_default_plan_is_kept():
    assert ai.fit_subject("Network Analysis and Synthesis", "college_ece") == "Network Analysis and Synthesis"
    assert ai.fit_subject("Economics", "college_cse") == "Economics"
    assert ai.fit_subject("Science", "cbse_10") == "Science"


def test_the_dashboard_lists_only_the_students_own_subjects(client):
    from sqlalchemy import select

    from app.models.note import Note
    from app.models.quiz_attempt import QuizAttempt
    from app.models.session import StudySession
    from app.models.user import User

    h = _student(client, "dash.scope@example.com", "neet")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "dash.scope@example.com"))
        lecture = StudySession(user_id=user.id, title="Old lecture")
        db.add(lecture)
        db.flush()
        db.add_all(Note(session_id=lecture.id, subject=s, ai_notes="x") for s in ("Economics", "Mathematics", "Biology", None))
        db.add_all(QuizAttempt(user_id=user.id, question="q", correct=False, topic=t, subject=s, exam_target="neet")
                   for t, s in (("Demand", "Economics"), ("Demand", "Economics"), ("Genetics", "Biology"), ("Genetics", "Biology")))
        db.commit()
    data = client.get("/api/analytics/overview", headers=h).json()
    assert [s["subject"] for s in data["subjects"]][0] == "Biology"
    assert {s["subject"] for s in data["subjects"]} == {"Physics", "Chemistry", "Biology"}
    assert [t["topic"] for t in data["weak_topics"]] == ["Genetics"]


def test_a_college_dashboard_has_no_school_subjects(client):
    h = _student(client, "dash.college@example.com", "college_cse")
    names = [s["subject"] for s in client.get("/api/analytics/overview", headers=h).json()["subjects"]]
    assert names and not {"Physics", "Chemistry", "Mathematics", "Computer Science", "General"} & set(names)
