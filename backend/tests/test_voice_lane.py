"""W2: the voice lane. The lecture's sound becomes captions and notes; the audio itself is never kept."""
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.lecture import LectureSegment
from app.models.note import Note
from app.services import ai, live, speech
from app.services.llm import llm

LINES = iter([])


def _student(client, email):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Voice Student", "password": "correct-horse-1", "exam_target": "jee"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _speech(monkeypatch, heard):
    """The recogniser hears these lines, one per piece, in Hindi."""
    lines = iter(heard)
    monkeypatch.setattr(speech, "available", lambda: True)
    monkeypatch.setattr(speech, "transcribe_full", lambda *a, **k: {"text": next(lines), "language": "hindi", "duration": 25})


def _send(client, h, sid, start, size=3000):
    return client.post(f"/api/capture/{sid}/audio", headers=h, data={"start_s": str(start), "end_s": str(start + 25)},
                       files={"audio": ("piece.webm", b"\x1a" * size, "audio/webm")}).json()


TALK = "Dekho, projectile ka range maximum hota hai jab angle pentalis degree hota hai, yeh exam mein baar baar aata hai"


def test_talk_without_a_board_becomes_a_spoken_note(client, monkeypatch):
    h = _student(client, "voice1@example.com")
    sid = client.post("/api/sessions", headers=h, json={"title": "Projectile motion"}).json()["id"]
    _speech(monkeypatch, ["Thank you."] + [f"{TALK} ({i})" for i in range(6)])
    monkeypatch.setattr(llm, "chat", lambda *a, **k: "TOPIC: Projectile range\n- Range is greatest at $45^\\circ$\n- Comes up in exams often")

    assert _send(client, h, sid, 0, size=500)["skipped"] == "silence"  # too short to hold speech: not even transcribed
    assert _send(client, h, sid, 0)["skipped"] == "silence"            # Whisper's "Thank you." on music
    made = None
    for i in range(6):  # 6 x 25 s of talk with no board on screen
        r = _send(client, h, sid, 25 * (i + 1))
        assert r["segment"]["language"] == "hi" and r["segment"]["text"].startswith("Dekho")
        made = made or r.get("spoken_note")
    assert made and made["topic"] == "Projectile range" and "45^\\circ" in made["ai_notes"]
    transcript = client.get(f"/api/capture/{sid}/transcript", headers=h).json()["segments"]
    assert len(transcript) == 6 and transcript[0]["start_s"] == 25


def test_what_the_teacher_said_joins_the_board_it_was_said_over(client, monkeypatch):
    h = _student(client, "voice2@example.com")
    sid = client.post("/api/sessions", headers=h, json={"title": "Work and energy"}).json()["id"]
    with SessionLocal() as db:
        board = Note(session_id=sid, topic="Work", ai_notes="- $W = Fd\\cos\\theta$", ocr_raw="W = F d cos theta")
        db.add(board)
        db.commit()
        board_id = board.id
    live._state(sid).last_note_id = board_id
    _speech(monkeypatch, [f"{TALK} ({i})" for i in range(3)])
    seen = []
    monkeypatch.setattr(llm, "chat", lambda messages, **k: seen.append(messages[0]["content"]) or "TOPIC: Work\n- Work is zero when force is perpendicular")
    for i in range(2):
        assert "spoken_note" in _send(client, h, sid, 25 * i)
    with SessionLocal() as db:
        assert db.get(Note, board_id).spoken_md is None  # still on that board, not two minutes yet
    live._state(sid).last_note_id = board_id + 1000  # the lecture moved to the next board
    _send(client, h, sid, 50)
    with SessionLocal() as db:
        assert db.get(Note, board_id).spoken_md == "- Work is zero when force is perpendicular"
        assert all(s.folded for s in db.scalars(select(LectureSegment).where(LectureSegment.note_id == board_id)))
    assert "already has these notes" in seen[0] and "W = Fd" in seen[0]  # told not to repeat the board

    captured = {}
    monkeypatch.setattr(ai, "summarize_session", lambda notes, *a, **k: captured.setdefault("notes", notes) and
                        {"summary_md": "", "key_formulas": [], "flashcards": [], "source": "ai"})
    client.post(f"/api/sessions/{sid}/end", headers=h)
    assert "What the teacher said" in captured["notes"][0]["notes_md"]  # the revision sheet hears the teacher too


def test_spoken_notes_survive_how_models_dress_them_up(monkeypatch):
    from app.services.llm import fix_latex

    seen = "**TOPIC: Projectile range**\n- Range: \\[ R = \\frac{u^2\\sin 2\\theta}{g} \\]\n- Greatest at \\(\\theta = 45^\\circ\\)"
    monkeypatch.setattr(llm, "chat", lambda *a, **k: seen)
    out = ai.speech_notes("talk", None, "jee")
    assert out["topic"] == "Projectile range"
    assert "$$R = \\frac{u^2\\sin 2\\theta}{g}$$" in out["notes_md"] and "$\\theta = 45^\\circ$" in out["notes_md"]
    assert fix_latex("a \\\\ b $x$") == "a \\\\ b $x$"  # a LaTeX row break is not a delimiter


def test_no_speech_service_or_no_allowance_just_pauses_the_voice(client, monkeypatch):
    h = _student(client, "voice3@example.com")
    sid = client.post("/api/sessions", headers=h, json={"title": "Optics"}).json()["id"]
    monkeypatch.setattr(speech, "available", lambda: False)
    assert _send(client, h, sid, 0)["skipped"] == "unavailable"
    monkeypatch.setattr(speech, "available", lambda: True)
    from app.services import usage
    monkeypatch.setattr(usage, "can_spend", lambda *a, **k: False)
    assert _send(client, h, sid, 25)["skipped"] == "allowance"


def test_captions_have_their_own_weekly_minutes(client, monkeypatch):
    """Speech to text is paid by the minute, so captions stop at the week's minutes while the board notes carry on."""
    from app.core.config import settings
    h = _student(client, "voice-minutes@example.com")
    sid = client.post("/api/sessions", headers=h, json={"title": "Optics"}).json()["id"]
    monkeypatch.setattr(settings, "CAPTION_MINUTES_FREE_WEEK", 1)  # one minute: three 25-second pieces
    _speech(monkeypatch, [f"{TALK} ({i})" for i in range(5)])
    monkeypatch.setattr(llm, "chat", lambda *a, **k: "TOPIC: Optics\n- Light bends towards the normal")
    assert all("segment" in _send(client, h, sid, 25 * i) for i in range(3))  # 75 s heard: past the minute now
    assert _send(client, h, sid, 75)["skipped"] == "captions"
    meter = client.get("/api/usage", headers=h).json()["captions"]
    assert meter["used"] == 1 and meter["limit"] == 1 and meter["resets_at"]
    # Pro has more caption time; the plans say how much
    monkeypatch.setattr(settings, "CAPTION_MINUTES_PRO_WEEK", 360)
    client.post("/api/billing/dev-upgrade", headers=h, json={"plan": "pro"})
    assert "segment" in _send(client, h, sid, 100)
    plans = client.get("/api/billing/plans").json()
    assert plans["captions_min_week"] == {"free": 1, "pro": 360}
    assert "Lecture captions: 6 hours a week" in next(p for p in plans["plans"] if p["id"] == "pro")["features"]


def test_what_the_teacher_said_is_summarised_once_and_again_after_more_talk(client, monkeypatch):
    """Students want what was said in short, not every word: one summary of the talk, kept with the lecture and
    written again only after more speech came in; when it can't be written, the last one, marked stale."""
    h = _student(client, "voice.summary@example.com")
    sid = client.post("/api/sessions", headers=h, json={"title": "Projectile motion"}).json()["id"]
    url = f"/api/capture/{sid}/transcript/summary"
    assert client.post(url, headers=h).json() == {"summary_md": None, "pieces": 0}  # no talk, nothing written
    with SessionLocal() as db:
        db.add_all([LectureSegment(session_id=sid, start_s=25 * i, end_s=25 * (i + 1), text=f"{TALK} ({i})") for i in range(3)])
        db.commit()
    calls: list[int] = []
    monkeypatch.setattr(ai, "talk_summary", lambda pieces, *a, **k: calls.append(len(pieces)) or f"- Range is greatest at $45^\\circ$ ({len(pieces)})")

    first = client.post(url, headers=h).json()
    assert first == {"summary_md": "- Range is greatest at $45^\\circ$ (3)", "pieces": 3, "source": "ai"}
    assert client.post(url, headers=h).json()["source"] == "kept" and calls == [3]  # kept, not written again
    assert client.post(url, headers=_student(client, "voice.summary.other@example.com")).status_code == 404

    with SessionLocal() as db:
        db.add(LectureSegment(session_id=sid, start_s=75, end_s=100, text=f"{TALK} (3)"))
        db.commit()
    monkeypatch.setattr(ai, "talk_summary", lambda *a, **k: None)  # the AI is busy
    busy = client.post(url, headers=h).json()
    assert busy["summary_md"].endswith("(3)") and busy["stale"] and busy["reason"] == "busy"
    monkeypatch.setattr(ai, "talk_summary", lambda pieces, *a, **k: f"- all {len(pieces)} pieces")
    assert client.post(url, headers=h).json() == {"summary_md": "- all 4 pieces", "pieces": 4, "source": "ai"}


def test_a_long_talk_is_summarised_in_parts_and_merged(monkeypatch):
    prompts: list[str] = []
    monkeypatch.setattr(llm, "chat", lambda messages, **k: prompts.append(messages[0]["content"]) or "- a point")
    assert ai.talk_summary(["word " * 500] * 5, "Optics", "jee", boards="$n = c / v$") == "- a point"
    assert len(prompts) == 4  # three parts of about 6000 characters, then one merge
    assert "part 1 of 3" in prompts[0] and "$n = c / v$" in prompts[0] and prompts[-1].startswith("Below are summaries")


def test_what_the_teacher_said_goes_with_the_lecture_and_the_account(client):
    """Deleting a lecture, or the whole account, deletes its transcript too (on Postgres, a transcript left behind
    would also block the delete). The student's "I'm lost" taps stay on the host's confusion map, unnamed."""
    from app.models.room import LectureSignal

    h = _student(client, "voice.delete@example.com")
    uid = client.get("/api/auth/me", headers=h).json()["id"]
    first, second = (client.post("/api/sessions", headers=h, json={"title": t}).json()["id"] for t in ("Optics", "Waves"))
    with SessionLocal() as db:
        db.add_all([LectureSegment(session_id=sid, start_s=0, end_s=25, text=TALK) for sid in (first, second)])
        db.add(LectureSignal(room_code="ABC123", user_id=uid, kind="lost"))
        db.commit()
    assert client.delete(f"/api/sessions/{first}", headers=h).status_code == 204
    assert client.post("/api/auth/delete-account", headers=h, json={"password": "correct-horse-1", "confirm": "DELETE"}).status_code == 204
    with SessionLocal() as db:
        assert db.scalars(select(LectureSegment).where(LectureSegment.session_id.in_([first, second]))).all() == []
        assert [s.user_id for s in db.scalars(select(LectureSignal).where(LectureSignal.room_code == "ABC123"))] == [None]
