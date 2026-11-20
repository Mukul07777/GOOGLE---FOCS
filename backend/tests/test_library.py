"""The notes library: pre-made detailed notes per syllabus topic, written once and shared; boards link into it."""
import pytest

from app.services import syllabus, topic_notes
from app.services.llm import LLMUnavailable

NOTE = """## In one line
Projectile motion is two independent motions at once.

## Core ideas
- **Horizontal** — constant velocity $u\\cos\\theta$.
- **Vertical** — uniform acceleration $g$ downward.

## Formulas and definitions
| Formula or term | Meaning | Use when |
| --- | --- | --- |
| $R = \\frac{u^2 \\sin 2\\theta}{g}$ | Range | level ground |

## Quick recap
- Range is maximum at 45 degrees.
""" + "More words so the note is long enough to count as complete. " * 30


def _student(client, email, exam="jee"):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Library Reader", "password": "correct-horse-1",
                                                "exam_target": exam})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def writer(monkeypatch):
    """Stand in for the AI: count what gets written, or fail when told to."""
    calls: list[str] = []
    state = {"down": False, "reviews": [], "fixes": 0}  # reviews: the second model's verdicts, in order (default: fine)

    def chat(messages, **kwargs):
        if state["down"]:
            raise LLMUnavailable("no model")
        if "second teacher found these problems" in messages[0]["content"]:
            state["fixes"] += 1
            return NOTE.replace("maximum at 45 degrees", f"maximum at 45 degrees (corrected {state['fixes']})"), "test-model"
        calls.append(messages[-1]["content"])
        return NOTE, "test-model"

    def review(messages, **kwargs):
        assert kwargs["skip"] == frozenset({"test-model"})  # never the model that wrote the note
        verdict = state["reviews"].pop(0) if state["reviews"] else {"ok": True, "problems": []}
        if verdict is None:
            raise LLMUnavailable("no second model")
        return verdict, "review-model"

    monkeypatch.setattr(topic_notes.llm, "chat_with_model", chat)
    monkeypatch.setattr(topic_notes.llm, "json_with_model", review)
    return calls, state


# ---------------------------------------------------------------- matching a board to a topic
@pytest.mark.parametrize("subject,title,expected", [
    ("Physics", "Projectile Motion Basics", "physics.kinematics.projectile-motion"),
    ("Physics", "Relative Velocity", "physics.kinematics.relative-velocity-and-river-boat-problems"),
    ("Physics", "Significant figures", "physics.units-measurements-and-errors.significant-figures-and-rounding-off"),
    ("Physics", "Work-Energy Theorem", "physics.work-energy-and-power.kinetic-energy-and-the-work-energy-theorem"),
    (None, "Kinetic energy and work energy theorem", "physics.work-energy-and-power.kinetic-energy-and-the-work-energy-theorem"),
])
def test_boards_find_their_syllabus_topic(subject, title, expected):
    found = topic_notes.match(syllabus.get("jee"), subject, title)
    assert found and found[1].id == expected


@pytest.mark.parametrize("subject,title", [
    ("Physics", "Motion"),                 # one generic word: any of a dozen topics
    ("Physics", "Introduction and overview"),
    ("Physics", "Homework for tomorrow"),
    ("Mathematics", "Projectile motion"),  # a Physics topic on a Maths board
    ("Physics", ""),
])
def test_loose_resemblance_is_not_a_match(subject, title):
    assert topic_notes.match(syllabus.get("jee"), subject, title) is None


# ---------------------------------------------------------------- the library
def test_a_topic_note_is_written_once_and_then_shared(client, writer):
    calls, _ = writer
    tid = "physics.kinematics.projectile-motion"
    a, b = _student(client, "lib.a@example.com"), _student(client, "lib.b@example.com")
    assert client.get(f"/api/prep/topics/{tid}", headers=a).json()["notes_ready"] is False

    first = client.post(f"/api/prep/topics/{tid}/notes", headers=a).json()
    assert first["written_now"] and first["title"] == "Projectile motion" and "## Core ideas" in first["notes_md"]
    assert "Projectile motion" in calls[0] and len(calls) == 1
    assert client.get("/api/usage", headers=a).json()["window"]["used"] == 2  # writing it cost the first reader

    again = client.post(f"/api/prep/topics/{tid}/notes", headers=b).json()  # another student: straight from the library
    assert not again["written_now"] and again["notes_md"] == first["notes_md"] and len(calls) == 1
    assert client.get("/api/usage", headers=b).json()["window"]["used"] == 0
    assert client.get(f"/api/prep/topics/{tid}", headers=b).json()["notes_ready"] is True
    tree = client.get("/api/prep/syllabus", headers=b).json()
    topics = {t["id"]: t for s in tree["subjects"] for u in s["units"] for c in u["chapters"] for t in c["topics"]}
    assert topics[tid]["has_notes"] and not topics["physics.kinematics.motion-in-a-plane"]["has_notes"]

    # NEET teaches the same topic at its own depth: its own note
    n = _student(client, "lib.n@example.com", exam="neet")
    assert client.post(f"/api/prep/topics/{tid}/notes", headers=n).json()["written_now"] and len(calls) == 2
    assert client.post("/api/prep/topics/physics.kinematics.nope/notes", headers=a).status_code == 404


def test_when_the_ai_is_down_only_unwritten_notes_are_unavailable(client, writer):
    calls, state = writer
    h = _student(client, "lib.down@example.com")
    client.post("/api/prep/topics/physics.kinematics.uniform-circular-motion/notes", headers=h)
    state["down"] = True
    assert client.post("/api/prep/topics/physics.kinematics.uniform-circular-motion/notes", headers=h).status_code == 200
    r = client.post("/api/prep/topics/physics.kinematics.motion-in-a-plane/notes", headers=h)
    assert r.status_code == 503 and "library" in r.json()["detail"]
    assert client.get("/api/usage", headers=h).json()["window"]["used"] == 2  # nothing charged for the failure


def test_a_second_model_checks_every_note_and_its_problems_are_corrected(client, writer):
    calls, state = writer
    h = _student(client, "lib.review@example.com")
    wrong = {"ok": False, "problems": ["Worked example: t should be 5.07 s, not 4.73 s"]}

    state["reviews"] = [wrong, {"ok": True}]  # one problem found, corrected, then it passes
    r = client.post("/api/prep/topics/physics.gravitation.satellites-and-kepler-s-laws/notes", headers=h).json()
    assert r["checked"] and "(corrected 1)" in r["notes_md"] and state["fixes"] == 1

    state["reviews"] = [wrong, wrong, wrong]  # never satisfied: corrected twice, then published as not checked
    r = client.post("/api/prep/topics/physics.gravitation.escape-and-orbital-velocity/notes", headers=h).json()
    assert not r["checked"] and "(corrected 3)" in r["notes_md"] and state["fixes"] == 3

    state["reviews"] = [None]  # no second model reachable: the note is still given, just not marked as checked
    r = client.post("/api/prep/topics/physics.gravitation.gravitational-potential-energy/notes", headers=h).json()
    assert r["written_now"] and not r["checked"] and state["fixes"] == 3
    again = client.post("/api/prep/topics/physics.gravitation.satellites-and-kepler-s-laws/notes", headers=h).json()
    assert again["checked"] and not again["written_now"]  # the verdict is kept with the note


def test_a_correction_that_drops_a_section_is_thrown_away(client, monkeypatch):
    def chat(messages, **kwargs):
        if "second teacher found these problems" in messages[0]["content"]:
            return NOTE.split("## Quick recap")[0] + "Padding so it is still long enough. " * 20, "test-model"  # lost its ending
        return NOTE, "test-model"

    monkeypatch.setattr(topic_notes.llm, "chat_with_model", chat)
    monkeypatch.setattr(topic_notes.llm, "json_with_model", lambda m, **k: ({"ok": False, "problems": ["a slip"]}, "review-model"))
    h = _student(client, "lib.dropped@example.com")
    r = client.post("/api/prep/topics/physics.gravitation.gravitational-field-and-potential/notes", headers=h).json()
    assert "## Quick recap" in r["notes_md"] and not r["checked"]  # the whole note, honestly marked as not checked


def test_an_incomplete_answer_is_never_stored(client, monkeypatch):
    monkeypatch.setattr(topic_notes.llm, "chat_with_model", lambda *a, **k: ("Sorry, I can't help with that.", "m"))
    h = _student(client, "lib.short@example.com")
    assert client.post("/api/prep/topics/physics.laws-of-motion.constraint-relations/notes", headers=h).status_code == 503
    assert client.get("/api/prep/topics/physics.laws-of-motion.constraint-relations", headers=h).json()["notes_ready"] is False


def test_reported_notes_are_rewritten_after_three_students(client, writer):
    calls, _ = writer
    tid = "physics.laws-of-motion.static-and-kinetic-friction"
    readers = [_student(client, f"lib.report{i}@example.com") for i in range(3)]
    client.post(f"/api/prep/topics/{tid}/notes", headers=readers[0])
    for _ in range(3):  # one student pressing it three times is still one report
        assert client.post(f"/api/prep/topics/{tid}/notes/report", headers=readers[0]).status_code == 204
    assert client.get(f"/api/prep/topics/{tid}", headers=readers[0]).json()["notes_ready"] is True
    for h in readers[1:]:
        client.post(f"/api/prep/topics/{tid}/notes/report", headers=h)
    assert client.get(f"/api/prep/topics/{tid}", headers=readers[0]).json()["notes_ready"] is False
    assert client.post(f"/api/prep/topics/{tid}/notes", headers=readers[1]).json()["written_now"]


def test_seed_notes_are_loaded_once(client, tmp_path, monkeypatch):
    import json

    from app.core.database import SessionLocal

    (tmp_path / "jee.json").write_text(json.dumps([
        {"exam": "jee", "kind": "detailed", "ref_id": "physics.gravitation.newton-s-law-of-gravitation", "content_md": NOTE, "checked": True},
        {"exam": "jee", "kind": "capsule", "ref_id": "physics.gravitation", "content_md": NOTE},
        {"exam": "jee", "ref_id": "physics.gravitation.empty", "content_md": "  "},
    ]), encoding="utf-8")
    monkeypatch.setattr(topic_notes, "SEED_DIR", tmp_path)
    with SessionLocal() as db:
        assert topic_notes.load_seed(db) == 2 and topic_notes.load_seed(db) == 0
        assert topic_notes.get(db, "jee", "detailed", "physics.gravitation.newton-s-law-of-gravitation").checked
        assert {n["ref_id"] for n in topic_notes.export(db, "jee")} >= {"physics.gravitation", "physics.gravitation.newton-s-law-of-gravitation"}


# ---------------------------------------------------------------- a board's optional detailed version
def _board(client, h, topic, subject, notes="### Key ideas\n- A body thrown at an angle follows a parabola.\n- Range depends on the angle."):
    from app.core.database import SessionLocal
    from app.models.note import Note

    sid = client.post("/api/sessions", headers=h, json={"title": "Lecture"}).json()["id"]
    with SessionLocal() as db:
        note = Note(session_id=sid, topic=topic, subject=subject, ai_notes=notes, ocr_raw="R = u^2 sin 2theta / g")
        db.add(note)
        db.commit()
        return note.id


def test_a_board_on_a_syllabus_topic_gets_the_library_note(client, writer):
    calls, _ = writer
    h = _student(client, "lib.board@example.com")
    nid = _board(client, h, "Motion graphs", "Physics")
    r = client.post(f"/api/notes/{nid}/detailed", headers=h).json()
    assert r["source"] == "library" and r["topic_id"] == "physics.kinematics.motion-graphs-x-t-v-t-a-t" and r["chapter"] == "Kinematics"
    assert client.post(f"/api/prep/topics/{r['topic_id']}/notes", headers=h).json()["written_now"] is False  # the same note


def test_any_other_board_gets_its_own_detailed_notes(client, writer):
    calls, state = writer
    h = _student(client, "lib.own@example.com", exam="other")  # no syllabus for this exam: always the board's own
    nid = _board(client, h, "Fundamental Rights", "General", "### Key ideas\n- Articles 12 to 35 of the Constitution.\n- Enforceable by courts.")
    r = client.post(f"/api/notes/{nid}/detailed", headers=h).json()
    assert r["source"] == "board" and r["written_now"] and "Articles 12 to 35" in calls[-1]
    state["down"] = True  # kept on the board: no second write, and no AI needed
    again = client.post(f"/api/notes/{nid}/detailed", headers=h).json()
    assert again["notes_md"] == r["notes_md"] and not again["written_now"]
    empty = _board(client, h, "Blank", "General", "x")
    assert client.post(f"/api/notes/{empty}/detailed", headers=h).status_code == 422
    other = _student(client, "lib.other@example.com")
    assert client.post(f"/api/notes/{nid}/detailed", headers=other).status_code == 404  # someone else's board


# ---------------------------------------------------------------- exam questions that go with a note
def _db():
    from app.core.database import SessionLocal

    return SessionLocal()


def _ch(chapter_id):
    return syllabus.get("jee").by_id[chapter_id]


def _bank(rows):
    from app.core.database import SessionLocal
    from app.models.mock import BankQuestion

    with SessionLocal() as db:
        ids = []
        for i, r in enumerate(rows):
            q = BankQuestion(exam=r.get("exam", "jee_main"), subject=r.get("subject", "Physics"), chapter=r["chapter"], qtype=r.get("qtype", "mcq"),
                             question=r["question"], options=r.get("options", ["1", "2", "3", "4"]), answer=r.get("answer", "1"),
                             solution=r.get("solution", "Worked out."), verified=True, source=r.get("source", "pyq"), year=r.get("year"),
                             paper=r.get("paper"), reports=r.get("reports", 0), fingerprint=f"lib-test-{r['chapter']}-{i}-{r['question'][:20]}")
            db.add(q)
            db.flush()
            ids.append(q.id)
        db.commit()
        return ids


def test_notes_come_with_real_past_questions_on_the_topic(client, writer):
    calls, _ = writer
    chapter = "Electromagnetic Waves"
    old, new, other, reported, own = _bank([
        {"chapter": chapter, "question": "The displacement current through a capacitor being charged is…", "year": 2017, "paper": "JEE Main 2017"},
        {"chapter": chapter, "question": "Displacement current arises due to a time-varying electric flux. Its value is…", "year": 2022,
         "paper": "JEE Main 2022 (June)", "options": ["zero", "equal to conduction current", "infinite", "negative"], "answer": "1"},
        {"chapter": chapter, "question": "Arrange the electromagnetic spectrum by wavelength: X-rays, microwaves…", "year": 2020, "paper": "JEE Main 2020"},
        {"chapter": chapter, "question": "Displacement current in vacuum (reported as wrong)", "year": 2023, "paper": "JEE Main 2023", "reports": 2},
        {"chapter": chapter, "question": "Displacement current practice question written by Focs", "source": "ai"},
    ])
    h = _student(client, "lib.pyq@example.com")
    r = client.post("/api/prep/topics/physics.electromagnetic-waves.displacement-current/notes", headers=h).json()
    qs = r["questions"]
    assert [q["id"] for q in qs] == [new, old, own]                     # real ones first, newest first; the reported one is out
    solved = NOTE + "\n## Worked example\n**JEE Main 2022 (June)**\nDisplacement current arises due to a time-varying electric flux. Its value is…"
    em = _ch("physics.electromagnetic-waves")
    with _db() as db:  # the question the note itself works through isn't offered again to try
        assert [q["id"] for q in topic_notes.exam_questions(db, "jee", em, em.topics[0], solved_in=solved)] == [old, own]
    assert qs[0] == {**qs[0], "real": True, "paper": "JEE Main 2022 (June)", "year": 2022, "match": "topic", "answer": "1"}
    assert qs[2]["real"] is False and qs[2]["paper"] is None             # Focs's own question is never called a past question
    assert other not in [q["id"] for q in qs]
    # the newest past question became the note's worked example, with its confirmed answer
    assert "JEE Main 2022 (June)" in calls[0] and "(B) equal to conduction current" in calls[0] and "time-varying electric flux" in calls[0]

    # a topic of the chapter with no question of its own: a couple of real ones from the chapter, marked as such
    r = client.post("/api/prep/topics/physics.electromagnetic-waves.characteristics-of-em-waves/notes", headers=h).json()
    assert r["questions"] and all(q["real"] for q in r["questions"] if q["match"] == "chapter")
    if not any(q["match"] == "topic" and q["real"] for q in r["questions"]):
        assert "past exam question" not in calls[-1]  # and nothing was passed off as the worked example

    # a capsule is about the whole chapter: its questions are the chapter's, past papers first
    capsule = client.post("/api/prep/chapters/physics.electromagnetic-waves/capsule", headers=h).json()["questions"]
    assert [q["id"] for q in capsule][:3] == [new, other, old] and {q["match"] for q in capsule} == {"chapter"}
