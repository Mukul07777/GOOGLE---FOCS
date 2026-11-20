"""Speak or write: explaining a topic back, practice on a syllabus topic, and the server's speech-to-text fallback."""
import httpx
import pytest

from app.core.config import settings
from app.services import ai, speech, topic_notes
from app.services.llm import LLMUnavailable, llm

TOPIC = "physics.laws-of-motion.pseudo-force-and-non-inertial-frames"
LIBRARY_NOTE = """## Core ideas
- **Non-inertial frame** — a frame that accelerates, where Newton's laws need a pseudo force.
- **Pseudo force** — equals mass times the frame's acceleration, directed opposite to that acceleration.
- **Lift problems** — apparent weight increases when the lift accelerates upward.

## Formulas and definitions
| Formula or term | Meaning | Use when |
| --- | --- | --- |
| $F_p = -ma_0$ | pseudo force | working in the accelerating frame |
"""


def _student(client, email, exam="jee"):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Speaker", "password": "correct-horse-1",
                                                "exam_target": exam})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _library(note=LIBRARY_NOTE, topic_id=TOPIC):
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        if topic_notes.get(db, "jee", "detailed", topic_id) is None:
            topic_notes._store(db, "jee", "detailed", topic_id, note, "test-model", True)


@pytest.fixture
def grader(monkeypatch):
    """The AI examiner: records what it was shown and answers with a fixed grading (or is down)."""
    seen: list[dict] = []
    state = {"down": False}

    def fake(messages, **kwargs):
        if state["down"]:
            raise LLMUnavailable("no model")
        seen.append({"system": messages[0]["content"], "user": messages[-1]["content"]})
        return {"score": "8", "grade": "Good", "points_covered": ["Pseudo force acts opposite to the frame's acceleration"],
                "points_missed": ["Its magnitude is m times a0"], "feedback": "Right idea. Add the magnitude."}

    monkeypatch.setattr(ai.llm, "json", fake)
    return seen, state


# ---------------------------------------------------------------- explaining a topic back
def test_explaining_a_syllabus_topic_is_checked_against_its_library_note(client, grader):
    seen, state = grader
    _library()
    h = _student(client, "speak.topic@example.com")
    spoken = "um so in an accelerating frame we add a pseudo force opposite to the acceleration, like in a lift"
    r = client.post("/api/quiz/teach-back", headers=h, json={"topic": "Pseudo force", "topic_id": TOPIC, "answer": spoken})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["score"] == 8 and body["source"] == "ai" and body["points_missed"]
    assert "Non-inertial frame" in seen[0]["user"] and spoken in seen[0]["user"]          # judged against the note
    assert "Pseudo force and non-inertial frames (Laws of Motion, Physics)" in seen[0]["system"]
    assert "spoken and transcribed" in seen[0]["system"] and "Hinglish" in seen[0]["system"]
    assert client.get("/api/usage", headers=h).json()["window"]["used"] == 2
    assert client.get("/api/quiz/redo", headers=h).json() == []                            # 8/10: nothing to redo

    # the AI is down: the note is still there to compare with, so the student isn't left without an answer
    state["down"] = True
    r = client.post("/api/quiz/teach-back", headers=h, json={"topic": "Pseudo force", "topic_id": TOPIC, "answer": "no idea"}).json()
    assert r["source"] == "offline" and r["score"] < 6
    assert [x["question"] for x in client.get("/api/quiz/redo", headers=h).json()] == ["Explain in your own words: Pseudo force"]
    assert client.get("/api/usage", headers=h).json()["window"]["used"] == 2               # offline grading is free

    # no note and no AI: nothing honest to say, and nothing is recorded
    r = client.post("/api/quiz/teach-back", headers=h, json={
        "topic": "Constraint relations", "topic_id": "physics.laws-of-motion.constraint-relations", "answer": "strings stay taut"})
    assert r.status_code == 503 and "try again" in r.json()["detail"]
    assert len(client.get("/api/quiz/redo", headers=h).json()) == 1
    assert client.post("/api/quiz/teach-back", headers=h, json={"topic": "x", "topic_id": "physics.nope.nope", "answer": "y"}).status_code == 404


def test_explaining_a_lecture_topic_is_checked_against_that_lectures_boards(client, grader):
    from app.core.database import SessionLocal
    from app.models.note import Note

    seen, _ = grader
    h = _student(client, "speak.lecture@example.com", exam="other")
    sid = client.post("/api/sessions", headers=h, json={"title": "Polity"}).json()["id"]
    with SessionLocal() as db:
        db.add(Note(session_id=sid, topic="Fundamental Rights", subject="General", ai_notes="- Articles 12 to 35.\n- Enforceable in court."))
        db.add(Note(session_id=sid, topic="Directive Principles", subject="General", ai_notes="- Part IV, not enforceable."))
        db.commit()
    r = client.post("/api/quiz/teach-back", headers=h, json={"topic": "fundamental rights", "session_id": sid,
                                                             "answer": "They are in articles 12 to 35 and courts enforce them"})
    assert r.status_code == 200 and "Articles 12 to 35" in seen[0]["user"] and "Part IV" not in seen[0]["user"]
    other = _student(client, "speak.stranger@example.com")
    assert client.post("/api/quiz/teach-back", headers=other, json={"topic": "x", "session_id": sid, "answer": "y"}).status_code == 404


# ---------------------------------------------------------------- practice on the topic just studied
def test_practice_set_for_a_syllabus_topic(client, monkeypatch):
    asked: list[str] = []

    def quiz(material, exam, difficulty="medium", n_mcq=5, n_tf=3, n_subj=1, language=None):
        asked.append(material)
        return {"topic": "something else", "subject": "General", "source": "ai", "true_false": [],
                "mcq": [{"q": "In a lift accelerating up, apparent weight…", "options": ["rises", "falls", "same", "zero"],
                         "answer_index": 0, "explanation": "N = m(g + a)"}],
                "subjective": [{"q": "Explain pseudo force.", "key_points": ["opposite to a0"], "model_answer": "…"}]}

    monkeypatch.setattr(ai, "generate_quiz", quiz)
    _library()
    h = _student(client, "speak.practice@example.com")
    q = client.post("/api/quiz/generate", headers=h, json={"topic_id": TOPIC, "n_mcq": 4, "n_tf": 0, "n_subjective": 1}).json()
    assert q["topic"] == "Pseudo force and non-inertial frames" and q["subject"] == "Physics" and q["topic_id"] == TOPIC
    assert "Chapter: Laws of Motion (Physics, Class 11)" in asked[0] and "Non-inertial frame" in asked[0]  # from the library note
    # a topic with no note yet: still practised, from syllabus knowledge
    client.post("/api/quiz/generate", headers=h, json={"topic_id": "physics.laws-of-motion.constraint-relations"})
    assert "No notes are attached" in asked[1] and "Constraint relations" in asked[1]
    assert client.post("/api/quiz/generate", headers=h, json={"topic_id": "physics.nope.nope"}).status_code == 404
    assert client.post("/api/quiz/generate", headers=_student(client, "speak.ca@example.com", exam="other"),
                       json={"topic_id": TOPIC}).status_code == 404  # no syllabus for this exam


def test_topic_practice_never_invents_questions_without_material_or_ai(client):
    _library()
    h = _student(client, "speak.offline@example.com")  # the test server has no AI configured
    r = client.post("/api/quiz/generate", headers=h, json={"topic_id": "physics.laws-of-motion.constraint-relations"})
    assert r.status_code == 503 and "needs the AI" in r.json()["detail"]
    assert client.post("/api/quiz/generate", headers=h, json={"topic_id": TOPIC}).status_code == 200  # the note carries it
    assert client.get("/api/usage", headers=h).json()["window"]["used"] == 0


# ---------------------------------------------------------------- the server's speech-to-text fallback
AUDIO = b"\x1aE\xdf\xa3" + b"\x00" * 4000  # the size of a short clip; the provider is faked below


def _post(client, h, data=AUDIO, content_type="audio/webm;codecs=opus", **form):
    return client.post("/api/speech/transcribe", headers=h, files={"audio": ("answer.webm", data, content_type)}, data=form)


def test_speech_fallback_is_off_without_a_provider(client):
    h = _student(client, "speak.off@example.com")
    assert client.get("/api/speech/status", headers=h).json() == {"server": False}
    assert _post(client, h).status_code == 503
    assert client.get("/api/speech/status").status_code in (401, 403)


def test_a_recorded_answer_is_transcribed(client, monkeypatch):
    sent: list[dict] = []
    reply = {"status": 200, "json": {"text": " torque is r cross F ", "duration": 9.0}}

    def post(url, headers=None, data=None, files=None, **kw):
        sent.append({"url": url, "auth": headers["Authorization"], "data": data, "file": files["file"]})
        return httpx.Response(reply["status"], json=reply["json"], request=httpx.Request("POST", url))

    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setattr(llm.client, "post", post)
    h = _student(client, "speak.on@example.com")
    assert client.get("/api/speech/status", headers=h).json() == {"server": True}

    r = _post(client, h, language="hi", hint="Define torque")
    assert r.status_code == 200 and r.json() == {"text": "torque is r cross F"}
    call = sent[0]
    assert call["url"] == "https://api.groq.com/openai/v1/audio/transcriptions" and call["auth"] == "Bearer test-key"
    assert call["data"]["model"] == settings.STT_MODEL and call["data"]["language"] == "hi" and call["data"]["prompt"] == "Define torque"
    assert call["file"][1] == AUDIO
    assert "language" not in (_post(client, h, language="auto"), sent[1])[1]["data"]  # anything else: detect it
    assert client.get("/api/usage", headers=h).json()["window"]["used"] == 2           # one unit per recording

    assert _post(client, h, data=b"tiny").status_code == 422                            # nothing recorded
    assert _post(client, h, content_type="image/png").status_code == 415
    assert _post(client, h, data=b"\x00" * (speech.MAX_AUDIO_BYTES + 1)).status_code == 413
    reply["json"] = {"text": "  ", "duration": 2.0}
    assert _post(client, h).status_code == 422                                          # silence
    reply["status"], reply["json"] = 429, {"error": "rate limited"}
    r = _post(client, h)
    assert r.status_code == 503 and "type your answer" in r.json()["detail"]
    assert client.get("/api/usage", headers=h).json()["window"]["used"] == 2           # failures cost nothing


def test_speech_cost_reaches_the_ledger(monkeypatch):
    from app.services import ledger

    queued: list[dict] = []
    monkeypatch.setattr(ledger._queue, "put", queued.append)
    monkeypatch.setattr(ledger, "_ensure_writer", lambda: None)
    ledger.record_cost("dictation", "whisper-large-v3-turbo", 90 / 3600 * 0.04)
    assert queued[0]["feature"] == "dictation" and queued[0]["cost_usd"] == pytest.approx(0.001) and queued[0]["prompt_tokens"] == 0
