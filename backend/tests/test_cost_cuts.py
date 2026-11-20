"""The AI cost cuts: cheap model first (and waited for), growing boards written up once, shared notes. (Which board
a frame shows, and when a board the lecture left gets its notes: test_board_matching.py.)"""
import pytest

from app.core.config import settings
from app.services import ai, live, shared_notes, vision
from app.services.llm import LLMUnavailable, Provider, RateLimited, llm
from tests.conftest import board_png

BOARD = ["Quadratic equations", "ax^2 + bx + c = 0", "Discriminant D = b^2 - 4ac", "D > 0 two real roots"]


def _student(client, email):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Cost Test", "password": "correct-horse-1",
                                                "exam_target": "jee"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _session(client, h):
    return client.post("/api/sessions", headers=h, json={"title": "Quadratics"}).json()["id"]


def _frame(client, h, sid, lines):
    return client.post(f"/api/capture/{sid}/frame", headers=h, files={"frame": ("f.png", board_png(lines), "image/png")}).json()


@pytest.fixture
def fake_ai(monkeypatch):
    """Count AI note write-ups and make them look like real (paid) AI notes."""
    calls: list[str] = []

    def notes(text, exam, prev_topic=None, offline_only=False, patient=True, board=None):
        calls.append(text)
        return {"is_lecture": True, "topic": "Quadratic equations", "subject": "Mathematics",
                "notes_md": f"## Notes\n{(board or text)[:80]}", "source": "ai"}

    monkeypatch.setattr(ai, "generate_notes", notes)
    return calls


# ---------------------------------------------------------------- 1. the cheap model, waited for
def _chain(monkeypatch, behaviour):
    chain = [Provider("primary:openai/gpt-oss-120b", "https://x", "k", "openai/gpt-oss-120b"),
             Provider("primary:openai/gpt-oss-20b", "https://x", "k", "openai/gpt-oss-20b")]
    monkeypatch.setattr("app.services.llm.providers", lambda: list(chain))
    monkeypatch.setattr("app.services.llm.time.sleep", lambda s: None)
    tried: list[str] = []

    def call(self, p, *a, **k):
        tried.append(p.model)
        return behaviour(p, len(tried))

    monkeypatch.setattr(type(llm), "_call", call)
    return tried


def test_light_job_waits_for_the_cheap_model_instead_of_paying_more(monkeypatch):
    def busy_once(p, n):
        if p.model.endswith("-20b") and n == 1:
            raise RateLimited("20b is rate-limited for ~6s", 6)
        return "ok"

    tried = _chain(monkeypatch, busy_once)
    assert llm.chat_with_model([{"role": "user", "content": "x"}], tier="light", patient=True)[1] == "openai/gpt-oss-20b"
    assert tried == ["openai/gpt-oss-20b", "openai/gpt-oss-20b"]  # the bigger model was never paid for


def test_a_student_waiting_on_a_button_is_never_kept_waiting(monkeypatch):
    def busy_once(p, n):
        if p.model.endswith("-20b") and n == 1:
            raise RateLimited("20b is rate-limited for ~6s", 6)
        return "ok"

    tried = _chain(monkeypatch, busy_once)
    assert llm.chat_with_model([{"role": "user", "content": "x"}], tier="light")[1] == "openai/gpt-oss-120b"
    assert tried == ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]


def test_light_job_moves_on_when_the_cheap_model_is_out_for_long(monkeypatch):
    def long_limit(p, n):
        if p.model.endswith("-20b"):
            raise RateLimited("20b is rate-limited for ~600s", 600)
        return "ok"

    tried = _chain(monkeypatch, long_limit)
    assert llm.chat_with_model([{"role": "user", "content": "x"}], tier="light", patient=True)[1] == "openai/gpt-oss-120b"
    assert tried == ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]


# ---------------------------------------------------------------- 2. a growing board is written up once
def test_growing_board_is_written_up_once_when_it_settles(client, fake_ai):
    h = _student(client, "grow.board@example.com")
    sid = _session(client, h)
    assert _frame(client, h, sid, BOARD)["status"] == "created"
    grown = BOARD + ["D = 0 equal roots"]
    grown_more = grown + ["Sum of roots = -b/a"]
    assert _frame(client, h, sid, grown)["status"] == "growing"
    r = _frame(client, h, sid, grown_more)
    assert r["status"] == "growing" and r["settle_after"] == settings.BOARD_SETTLE_S
    assert len(fake_ai) == 1  # two new lines, no new AI calls yet

    done = client.post(f"/api/capture/{sid}/settle", headers=h).json()
    assert done["status"] == "updated" and "sum of roots" in done["note"]["ocr_raw"].lower()
    assert len(fake_ai) == 2  # one write-up for the finished board
    assert client.post(f"/api/capture/{sid}/settle", headers=h).json()["status"] == "unchanged"  # nothing held now




def test_ending_the_lecture_keeps_the_last_lines(client, fake_ai):
    h = _student(client, "end.board@example.com")
    sid = _session(client, h)
    _frame(client, h, sid, BOARD)
    assert _frame(client, h, sid, BOARD + ["D = 0 equal roots", "Vertex x = -b/2a"])["status"] == "growing"
    client.post(f"/api/sessions/{sid}/end", headers=h)
    notes = client.get(f"/api/sessions/{sid}", headers=h).json()["notes"]
    assert len(notes) == 1 and "vertex" in notes[0]["ocr_raw"].lower()


def test_a_slowly_growing_board_still_refreshes(client, fake_ai, monkeypatch):
    monkeypatch.setattr(settings, "BOARD_REFRESH_S", 0)  # as if the last write-up was long ago
    h = _student(client, "slow.board@example.com")
    sid = _session(client, h)
    _frame(client, h, sid, BOARD)
    assert _frame(client, h, sid, BOARD + ["D = 0 equal roots", "Vertex x = -b/2a"])["status"] == "updated"


# ---------------------------------------------------------------- 3. notes shared across students
def test_second_student_on_the_same_board_costs_nothing(client, fake_ai):
    a, b = _student(client, "first.viewer@example.com"), _student(client, "second.viewer@example.com")
    board = ["Shared board test", "Coulomb's law F = k q1 q2 / r^2", "k = 9 x 10^9 N m^2 / C^2"]
    first = _frame(client, a, _session(client, a), board)
    assert first["status"] == "created" and len(fake_ai) == 1
    used = client.get("/api/usage", headers=b).json()

    second = _frame(client, b, _session(client, b), board)
    assert second["status"] == "created" and len(fake_ai) == 1  # no new AI call
    assert second["note"]["ai_notes"] == first["note"]["ai_notes"] and second["ai_source"] == "shared"
    assert client.get("/api/usage", headers=b).json() == used  # and no allowance used


def test_near_identical_boards_match_and_other_exams_dont(client):  # client: the app (and its tables) is up
    from app.core.database import SessionLocal

    text = ("Quadratic equations ax^2 + bx + c = 0. Discriminant D = b^2 - 4ac. If D > 0 two distinct real roots, "
            "if D = 0 equal roots, if D < 0 complex roots. Sum of roots = -b/a, product = c/a.")
    noisy = text.replace("distinct", "distinet").replace("product", "prodvct")  # what OCR does to a re-read board
    notes = {"is_lecture": True, "topic": "Quadratics", "subject": "Mathematics", "notes_md": "## Q", "source": "ai"}
    with SessionLocal() as db:
        shared_notes.store(db, text, "jee", notes)
        db.commit()
        hit = shared_notes.lookup(db, noisy, "jee")
        assert hit is not None and hit["notes_md"] == "## Q" and hit["source"] == "shared"
        assert shared_notes.lookup(db, noisy, "neet") is None  # written for another exam's syllabus
        assert shared_notes.lookup(db, "Projectile motion. Range = u^2 sin 2t / g. Height = u^2 sin^2 t / 2g.", "jee") is None
        shared_notes.store(db, "short", "jee", notes)
        assert shared_notes.lookup(db, "short", "jee") is None  # tiny boards are never shared
        two_lines = "Quadratic equations\nax^2 + bx + c = 0"
        shared_notes.store(db, two_lines, "jee", notes)
        db.commit()
        assert shared_notes.lookup(db, two_lines, "jee") is not None  # a short board matches exactly...
        assert shared_notes.lookup(db, "Quadratic equations\nax^2 + bx + d = 0", "jee") is None  # ...or not at all
        offline = {**notes, "source": "offline"}
        shared_notes.store(db, text + " basic", "cbse", offline)
        assert shared_notes.lookup(db, text + " basic", "cbse") is None  # only real AI notes are shared


def test_boards_that_differ_in_a_sign_or_number_never_share_notes(client):
    """Only letters and digits used to be compared, so "x^2 - 5x + 6" and "x^2 - 5x - 6", or "> 0" and "< 0", were
    one board and the second student got notes solving the first one's problem."""
    from app.core.database import SessionLocal

    board = ("Rational inequality: solve (x^2 - 5x + 6)(x + 1) / ((x^2 - 16)(x + 11)) > 0 by the wavy curve method. "
             "Mark the critical points on the number line and check the sign in each interval.")
    notes = {"is_lecture": True, "topic": "Wavy curve", "subject": "Mathematics", "notes_md": "## Plus six, greater than", "source": "ai"}
    with SessionLocal() as db:
        shared_notes.store(db, board, "jee", notes)
        db.commit()
        assert shared_notes.lookup(db, board.replace("+ 6", "- 6"), "jee") is None
        assert shared_notes.lookup(db, board.replace(") > 0", ") < 0"), "jee") is None
        assert shared_notes.lookup(db, board.replace("x + 11", "x + 12"), "jee") is None
        assert shared_notes.lookup(db, board.replace("> 0", ">= 0"), "jee") is None
        # OCR noise in the words is still the same board, and one sign written two ways is one sign
        assert shared_notes.lookup(db, board.replace("interval", "lnterval"), "jee") is not None
        assert shared_notes.lookup(db, board.replace("x^2 - 5x", "x^2 − 5x"), "jee") is not None


def teardown_module():
    live._states.clear()






def test_capture_now_never_waits(client, fake_ai):
    h = _student(client, "force.board@example.com")
    sid = _session(client, h)
    r = client.post(f"/api/capture/{sid}/frame", headers=h, data={"force": "true"},
                    files={"frame": ("f.png", board_png(["Ohm's law V = I R"]), "image/png")}).json()
    assert r["status"] == "created"


def test_a_board_is_read_from_the_frame_when_a_vision_model_is_set_up(client, fake_ai, monkeypatch):
    """Line-by-line OCR splits a fraction over two lines and loses the sign between two fractions, and the notes then
    answered a different question. With a vision model the notes are written from the board read off the image,
    and the note keeps that reading; when the vision model fails, the OCR text is used as before."""
    read = r"Find the set of all $x$ for which $\frac{2x}{2x^2+5x+2} > \frac{1}{x+1}$."
    monkeypatch.setattr(vision, "available", lambda: True)
    monkeypatch.setattr(vision, "read_json", lambda images, prompt, feature, max_tokens=3000, **k: {"board": read})
    h = _student(client, "fraction.board@example.com")
    r = _frame(client, h, _session(client, h), ["Rational inequality", "2x", "Find the set of all x for which", "2x^2 + 5x + 2", "x + 1"])
    assert r["status"] == "created" and r["note"]["ocr_raw"] == read and r["note"]["ai_notes"] == f"## Notes\n{read[:80]}"

    def down(*a, **k):
        raise LLMUnavailable("vision model busy (429)")

    monkeypatch.setattr(vision, "read_json", down)
    h = _student(client, "fraction.board.ocr@example.com")
    r = _frame(client, h, _session(client, h), ["Wave optics", "Fringe width beta = lambda D / d", "Young double slit experiment"])
    assert r["status"] == "created" and "fringe" in r["note"]["ocr_raw"].lower() and r["note"]["ocr_raw"] != read


def test_a_shared_board_shows_the_vision_reading_not_the_ocr_text(client, fake_ai, monkeypatch):
    """FocsOCR reads "D > 0" as "D ≥ 0" on some boards. The notes were written from the vision model's reading, but the
    second student on a board got the shared notes beside the OCR text, so the board they saw had the wrong sign."""
    read = "Discriminant $D = b^2 - 4ac$\n$D > 0$ : two distinct real roots\n$D < 0$ : no real roots"
    monkeypatch.setattr(vision, "available", lambda: True)
    monkeypatch.setattr(vision, "read_json", lambda images, prompt, feature, max_tokens=3000, **k: {"board": read})
    lines = ["Discriminant D = b^2 - 4ac", "D >= 0 two distinct real roots", "D <= 0 no real roots"]
    a, b = _student(client, "sign.first@example.com"), _student(client, "sign.second@example.com")
    assert _frame(client, a, _session(client, a), lines)["note"]["ocr_raw"] == read
    second = _frame(client, b, _session(client, b), lines)
    assert second["ai_source"] == "shared" and second["note"]["ocr_raw"] == read and len(fake_ai) == 1
