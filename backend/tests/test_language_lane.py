"""W3: the lecture in the student's language: notes, library, quizzes, with every formula and number intact."""
import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.library import TopicNote
from app.models.shared_note import SharedNote
from app.models.user import User
from app.services import ai, live, translate
from app.services.llm import LLMUnavailable, llm

EN = "### Key ideas\n- Range of a projectile: $R = \\frac{u^2 \\sin 2\\theta}{g}$\n- Maximum at 45 degrees, 2 times the height"
HI = "### मुख्य बातें\n- प्रक्षेप्य की परास: $R = \\frac{u^2 \\sin 2\\theta}{g}$\n- 45 डिग्री पर अधिकतम, ऊँचाई का 2 गुना"


def test_signature_catches_changed_formulas_and_numbers():
    assert translate.faithful(EN, HI)
    assert translate.faithful(EN, HI.replace("\\frac{u^2", "\\frac{ u^2"))  # spacing inside a formula doesn't matter
    assert not translate.faithful(EN, HI.replace("2\\theta", "\\theta"))  # a formula changed
    assert not translate.faithful(EN, HI.replace("45", "90"))  # a number changed
    assert not translate.faithful(EN, "")


def test_translate_retries_once_then_falls_back_to_english(monkeypatch):
    answers = iter([HI.replace("45", "40"), HI])
    monkeypatch.setattr(llm, "chat", lambda *a, **k: next(answers))
    assert translate.translate(EN, "hi", "jee") == (HI, True)
    monkeypatch.setattr(llm, "chat", lambda *a, **k: HI.replace("45", "40"))
    assert translate.translate(EN, "hi", "jee") == (EN, False)

    def down(*a, **k):
        raise LLMUnavailable("no key")
    monkeypatch.setattr(llm, "chat", down)
    assert translate.translate(EN, "hinglish", "jee") == (EN, False)
    assert translate.translate(EN, "en", "jee") == (EN, True)  # English needs nothing
    assert "Hindi" in translate.notice("hi")


def _student(client, email, language):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Lane Student", "password": "correct-horse-1", "exam_target": "jee"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    client.patch("/api/auth/me", headers=h, json={"language": language})
    return h


def test_board_notes_are_shared_in_english_and_translated_once(client, monkeypatch):
    for email, lang in (("lane.hi@example.com", "hi"), ("lane.en@example.com", "en"), ("lane.hi2@example.com", "hi")):
        _student(client, email, lang)
    board = "Range of a projectile R equals u squared sin 2 theta over g maximum at 45 degrees"
    written = {"is_lecture": True, "topic": "Projectile range", "subject": "Physics", "notes_md": EN, "source": "ai"}
    monkeypatch.setattr(ai, "generate_notes", lambda *a, **k: dict(written))
    calls = []
    monkeypatch.setattr(llm, "chat", lambda *a, **k: calls.append(1) or HI)

    with SessionLocal() as db:
        users = {u.email: u for u in db.scalars(select(User).where(User.email.like("lane.%")))}
        hindi, _ = live._write_notes(db, users["lane.hi@example.com"], board, None)
        db.commit()
        assert hindi["notes_md"] == HI and hindi["language"] == "hi" and len(calls) == 1
        english, _ = live._write_notes(db, users["lane.en@example.com"], board, None)
        assert english["notes_md"] == EN and "language" not in english  # the shared original stays English
        again, _ = live._write_notes(db, users["lane.hi2@example.com"], board, None)
        assert again["notes_md"] == HI and len(calls) == 1  # the kept translation: no second AI call
        row = db.scalar(select(SharedNote).where(SharedNote.topic == "Projectile range"))
        assert row.notes_md == EN and row.translations == {"hi": HI}


def test_when_the_ai_is_down_hindi_readers_get_english_with_a_notice(client, monkeypatch):
    _student(client, "lane.down@example.com", "hinglish")
    monkeypatch.setattr(ai, "generate_notes", lambda *a, **k: {"is_lecture": True, "topic": "Work", "subject": "Physics",
                                                              "notes_md": "Work $W = Fd$ done over 3 metres", "source": "ai"})

    def down(*a, **k):
        raise LLMUnavailable("rate limited")
    monkeypatch.setattr(llm, "chat", down)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "lane.down@example.com"))
        notes, _ = live._write_notes(db, user, "Work equals force times displacement W = F d three metres example", None)
    assert notes["notes_md"].startswith("Work $W = Fd$") and "Hinglish" in notes["language_note"]


def test_ai_writers_are_told_the_language(monkeypatch):
    seen = []
    monkeypatch.setattr(llm, "json", lambda messages, **k: seen.append(messages[0]["content"]) or {"cards": [{"front": "क्या?", "back": "हाँ"}]})
    ai.flashcards("material about torque", "jee", 2, language="hi")
    ai.flashcards("material about torque", "jee", 2)
    assert "Devanagari" in seen[0] and "Devanagari" not in seen[1]


def test_doubts_repeat_the_language_after_the_question(monkeypatch):
    """With the rule only in the system prompt, "difference between X and Y" came back as an all-English table."""
    seen = []
    monkeypatch.setattr(llm, "chat", lambda messages, **k: seen.append(messages) or "Process apna alag memory space rakhta hai.")
    ai.companion("Difference between a process and a thread?", "", [], "college_cse", language="hinglish")
    ai.companion("Difference between a process and a thread?", "", [], "college_cse")
    hinglish, english = seen
    assert hinglish[0]["content"].rstrip().endswith("table cells.") and "Hinglish" in hinglish[0]["content"]
    assert hinglish[-1]["content"].startswith("Difference between a process") and "Reply in Hinglish" in hinglish[-1]["content"]
    assert english[-1]["content"] == "Difference between a process and a thread?" and "Hinglish" not in english[0]["content"]


@pytest.fixture
def library_note():
    with SessionLocal() as db:
        db.add(TopicNote(exam="jee", kind="capsule", ref_id="physics.lane-test", content_md=EN, source="ai", checked=True, reported_by=[]))
        db.commit()


def test_library_notes_are_translated_once_and_kept(client, monkeypatch, library_note):
    from app.api import _common
    from app.services.syllabus import Chapter

    chapter = Chapter(id="physics.lane-test", subject="Physics", unit="Mechanics", name="Lane test", cls=11, hours=1, weight=1,
                      foundation=False, topics=())
    _student(client, "lane.lib@example.com", "hi")
    monkeypatch.setattr(llm, "chat", lambda *a, **k: HI)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "lane.lib@example.com"))
        out = _common.library_capsule(db, user, "jee", chapter)
        assert out["notes_md"] == HI and out["language"] == "hi"
        assert db.scalar(select(TopicNote).where(TopicNote.ref_id == "physics.lane-test")).translations == {"hi": HI}
