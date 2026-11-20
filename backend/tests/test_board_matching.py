"""Which board a frame shows. Measured on real PW lectures (2026-10-20): handwriting OCR returns the same board's lines in
another order, split differently, with characters changed from frame to frame, so one question worked over nine
minutes became fifteen "new boards", each with its own paid write-up. The pipeline now compares the strokes on the
frames (services/ocr/ink.py), and the OCR text only for its memory of what isn't a board (the teacher's camera).
The text frames below are that lecture's real OCR output: two questions, five frames of the first and four of the
second."""
import json
from itertools import combinations
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.services import live
from app.services.ocr import decode_image
from app.services.ocr.ink import ink_map, same_board as same_strokes
from app.services.text_utils import same_board, similarity
from tests.conftest import board_png
from tests.test_cost_cuts import _session, _student, fake_ai  # noqa: F401  (fixture)

FRAMES = json.loads((Path(__file__).parent / "data" / "handwritten_board_frames.json").read_text(encoding="utf-8"))
FIRST, SECOND = FRAMES[:5], FRAMES[5:]
PAGE = ["Q. Find the area under y = x^2 from 0 to 2", "A = integral of x^2 dx from 0 to 2", "= [x^3 / 3] from 0 to 2",
        "= 8/3 - 0", "= 8/3 square units", "Check: the curve lies above the x-axis", "so no part is negative",
        "Next: area between y = x and y = x^2", "They meet where x = x^2", "x = 0 or x = 1"]


def _font(size=50):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def scene(lines, scroll=0, teacher=None, seed=None) -> np.ndarray:
    """A pen-tablet lecture frame: a dark page of writing (scrolled down by ``scroll`` px), and the teacher standing in
    front of it at x = ``teacher``. ``seed``: a close-up of the teacher instead (a different one for each seed)."""
    if seed is not None:  # the teacher at the camera: a face filling the frame, never twice the same
        rng = np.random.default_rng(seed)
        img = Image.new("RGB", (1280, 720), (20, 20, 24))
        d = ImageDraw.Draw(img)
        x = int(rng.integers(300, 700))
        d.ellipse((x, 60, x + 520, 700), fill=(150, 112, 92))
        for _ in range(60):  # hair, beard, glasses, a hand: fine detail that moves with every gesture
            a, b = rng.integers(0, 1280), rng.integers(0, 720)
            d.line((a, b, a + rng.integers(-60, 60), b + rng.integers(-60, 60)), fill=(230, 220, 200), width=3)
        return np.asarray(img)
    page = Image.new("RGB", (1280, 720 + 100 * len(PAGE)), (14, 16, 18))
    d = ImageDraw.Draw(page)
    for i, line in enumerate(lines):
        d.text((90, 90 + 100 * i), line, font=_font(), fill=(235, 235, 225))
    img = page.crop((0, scroll, 1280, scroll + 720))
    if teacher is not None:
        d = ImageDraw.Draw(img)
        d.rectangle((teacher, 300, teacher + 300, 720), fill=(18, 18, 22))  # a dark T-shirt
        d.ellipse((teacher + 80, 160, teacher + 220, 320), fill=(150, 112, 92))
    return np.asarray(img)


# ------------------------------------------------------------------ OCR text: the "not a board" memory
def test_frames_of_one_board_match_and_different_boards_dont():
    assert all(similarity(a, b) < 0.85 for a, b in zip(FIRST, FIRST[1:]))  # what made them "new" boards
    assert all(same_board(a, b) for a, b in combinations(FIRST, 2))
    assert all(same_board(a, b) for a, b in combinations(SECOND, 2))
    assert not any(same_board(a, b) for a in FIRST for b in SECOND)
    assert not same_board("Kinematics", "Kinematics")  # a heading alone: too little to tell


@pytest.mark.parametrize("a,b", [("x^2 - 5x + 6 > 0 so x < 2 or x > 3", "x^2 - 5x + 6 < 0 so 2 < x < 3")])
def test_boards_that_differ_by_a_sign_are_not_merged(a, b):
    assert not same_board(a, b)


# ------------------------------------------------------------------ strokes: which board a frame shows
def test_the_teacher_in_front_of_the_board_is_still_that_board():
    left, right, none = ink_map(scene(PAGE[:6], teacher=150)), ink_map(scene(PAGE[:6], teacher=800)), ink_map(scene(PAGE[:6]))
    assert same_strokes(none, left) and same_strokes(left, right) and same_strokes(right, none)


def test_more_writing_and_a_scrolled_page_are_the_same_board():
    assert same_strokes(ink_map(scene(PAGE[:3])), ink_map(scene(PAGE[:6], teacher=700)))
    assert same_strokes(ink_map(scene(PAGE[:7])), ink_map(scene(PAGE, scroll=260)))  # the tablet's page scrolled on


def test_boards_laid_out_alike_are_different_boards():
    """Same font, same margin, lines in the same places: only the strokes themselves differ."""
    a = ink_map(decode_image(board_png(["Quadratic equations", "ax^2 + bx + c = 0", "Discriminant D = b^2 - 4ac"])))
    b = ink_map(decode_image(board_png(["Projectile motion", "Range R = u^2 sin 2t / g", "Max height H = u^2 / 2g"])))
    assert not same_strokes(a, b) and not same_strokes(b, a)


def test_a_busy_frame_does_not_match_every_board():
    noise = (np.random.default_rng(1).random((720, 1280, 3)) * 255).astype(np.uint8)  # a photo-heavy slide, at worst
    assert not same_strokes(ink_map(scene(PAGE[:5])), ink_map(noise))
    assert not same_strokes(ink_map(scene(PAGE[:5])), ink_map(scene([], seed=3)))


# ------------------------------------------------------------------ the pipeline
@pytest.fixture
def clock(client, monkeypatch):
    """The pipeline's clock, moved by hand; and no notes shared from another test's board (they would cost nothing)."""
    from sqlalchemy import delete

    from app.core.database import SessionLocal
    from app.models.shared_note import SharedNote

    with SessionLocal() as db:
        db.execute(delete(SharedNote))
        db.commit()
    now = [1000.0]
    monkeypatch.setattr(live, "time", SimpleNamespace(monotonic=lambda: now[0]))
    return now


def _send(client, h, sid, img):
    from io import BytesIO

    buf = BytesIO()
    Image.fromarray(img).save(buf, format="JPEG", quality=90)
    return client.post(f"/api/capture/{sid}/frame", headers=h, files={"frame": ("f.jpg", buf.getvalue(), "image/jpeg")}).json()


def test_a_question_worked_down_a_scrolling_page_is_not_a_new_board_every_frame(client, fake_ai, clock):  # noqa: F811
    h = _student(client, "scrolling.page@example.com")
    sid = _session(client, h)
    statuses = []
    for n in range(3, len(PAGE) + 1):  # a line every 5 s, the page scrolling on as it fills, the teacher walking about
        statuses.append(_send(client, h, sid, scene(PAGE[:n], scroll=max(0, (n - 6) * 90), teacher=100 + 90 * n))["status"])
        clock[0] += 5
    assert statuses[0] == "created" and "created" not in statuses[1:], statuses  # the first board at once, then no more
    assert len(fake_ai) == 1
    client.post(f"/api/sessions/{sid}/end", headers=h)
    notes = client.get(f"/api/sessions/{sid}", headers=h).json()["notes"]
    # the page scrolled on past what the first note covers: the rest gets a note of its own, the question's is kept
    assert len(notes) == 2 and len(fake_ai) == 2 and "find the area" in notes[0]["ocr_raw"].lower()


def test_the_teacher_at_the_camera_costs_nothing(client, fake_ai, clock):  # noqa: F811
    """A PW teacher walks up to the camera every few minutes for half a minute; then goes on writing."""
    h = _student(client, "close.up@example.com")
    sid = _session(client, h)
    assert _send(client, h, sid, scene(PAGE[:4], teacher=200))["status"] == "created"
    for seed in range(6):  # 30 s at the camera, a different picture every frame
        clock[0] += 5
        r = _send(client, h, sid, scene([], seed=seed))
        assert r["status"] == "growing" and "also_updated" not in r
    clock[0] += 5
    back = _send(client, h, sid, scene(PAGE[:4], teacher=900))  # (what the teacher had hidden is new: notes later)
    assert back["status"] in ("growing", "duplicate") and "also_updated" not in back and len(fake_ai) == 1


def test_a_board_gets_its_notes_a_minute_after_the_lecture_moves_on(client, fake_ai, clock):  # noqa: F811
    h = _student(client, "moved.on@example.com")
    sid = _session(client, h)
    first = _send(client, h, sid, scene(PAGE[:3]))["note"]
    clock[0] += 5
    assert _send(client, h, sid, scene(PAGE[:5], teacher=600))["status"] == "growing"
    other = ["Projectile motion", "Range R = u^2 sin 2t / g", "Max height H = u^2 sin^2 t / 2g", "Time of flight T = 2u sin t / g"]
    clock[0] += 5
    assert _send(client, h, sid, scene(other))["status"] == "growing"  # a new view: not yet the board
    clock[0] += settings.BOARD_MIN_S
    assert _send(client, h, sid, scene(other, teacher=700))["status"] == "growing"  # it held: the board now
    assert len(fake_ai) == 1  # the board before waits, in case the lecture goes back to it
    clock[0] += settings.BOARD_AWAY_S
    r = _send(client, h, sid, scene(other, teacher=200))
    assert r["also_status"] == "updated" and r["also_updated"]["id"] == first["id"] and len(fake_ai) == 2


def test_a_new_slide_left_still_gets_notes_when_it_settles(client, fake_ai, clock):  # noqa: F811
    h = _student(client, "still.slide@example.com")
    sid = _session(client, h)
    _send(client, h, sid, scene(PAGE[:3]))
    clock[0] += 5
    assert _send(client, h, sid, decode_image(board_png(["Ohm's law V = I R"])))["status"] == "growing"
    clock[0] += settings.BOARD_SETTLE_S
    done = client.post(f"/api/capture/{sid}/settle", headers=h).json()
    assert done["status"] == "created" and "ohm" in done["note"]["ocr_raw"].lower() and len(fake_ai) == 2


def test_the_teachers_camera_is_judged_once(client, monkeypatch):
    """A PW lecture keeps cutting to the teacher talking, with a little text on screen (a channel name, a caption):
    the AI says "not a board" once, and the same view seen again costs nothing."""
    from app.services import ai

    calls = []

    def notes(text, exam, prev_topic=None, offline_only=False, patient=True, board=None):
        calls.append(text)
        return {"is_lecture": False, "source": "ai"}

    monkeypatch.setattr(ai, "generate_notes", notes)
    h = _student(client, "camera@example.com")
    sid = _session(client, h)
    hashes = iter([0, 2**64 - 1, 0])
    monkeypatch.setattr(live, "phash", lambda img: next(hashes))
    frame = board_png(["Rajwant Sir Physics", "Live Class Newton Laws of Motion", "Join the batch for notes and DPPs"])
    statuses = [client.post(f"/api/capture/{sid}/frame", headers=h, files={"frame": ("f.png", frame, "image/png")}).json()["status"]
                for _ in range(3)]
    assert statuses == ["not_lecture"] * 3 and len(calls) == 1


def test_lecture_time_is_counted_with_long_pauses_as_a_minute(client, fake_ai, clock):  # noqa: F811
    from app.core.database import SessionLocal
    from app.models.user import User

    h = _student(client, "lecture.time@example.com")
    sid = _session(client, h)
    for i, step in enumerate([0, 5, 5, 600]):  # three frames 5 s apart, then the tab left alone for ten minutes
        clock[0] += step
        _send(client, h, sid, scene(PAGE[:3 + i]))
    with SessionLocal() as db:
        assert db.query(User).filter(User.email == "lecture.time@example.com").one().lecture_day_seconds == 5 + 5 + 60
    assert client.get("/api/usage", headers=h).json()["lecture"]["used"] == 1  # (in minutes)


def test_a_left_board_is_written_in_the_background_and_reported_with_a_later_frame(client, clock, monkeypatch):
    """LIVE_WRITE_BEHIND: the lecture's frames don't wait for the AI; the note comes back with the next frame, and its
    cost goes on the student's own account (the per-student 30-day ceiling counts it)."""
    from app.services import ai, ledger

    monkeypatch.setattr(settings, "LIVE_WRITE_BEHIND", True)
    seen = []

    def notes(text, exam, prev_topic=None, offline_only=False, patient=True, board=None):
        seen.append((ledger.current_user.get(), patient))
        return {"is_lecture": True, "topic": f"Board {len(seen)}", "subject": "Physics", "notes_md": "## Notes", "source": "ai"}

    monkeypatch.setattr(ai, "generate_notes", notes)
    h = _student(client, "write.behind@example.com")
    me = client.get("/api/auth/me", headers=h).json()["id"]
    sid = _session(client, h)
    first = _send(client, h, sid, scene(PAGE[:3]))["note"]  # the first board: at once, while the student waits
    clock[0] += 5
    _send(client, h, sid, scene(PAGE[:6], teacher=500))
    other = ["Projectile motion", "Range R = u^2 sin 2t / g", "Max height H = u^2 sin^2 t / 2g", "Time of flight T = 2u sin t / g"]
    for step in (5, settings.BOARD_MIN_S, settings.BOARD_AWAY_S):
        clock[0] += step
        r = _send(client, h, sid, scene(other, teacher=200 + step))
        assert "also_updated" not in r  # the board before is being written behind the lecture, not in this request
    for job in live._state(sid).jobs:
        job.result(timeout=30)
    clock[0] += 5
    r = _send(client, h, sid, scene(other, teacher=900))
    assert r["also_updated"]["id"] == first["id"] and r["also_status"] == "updated"
    assert seen[-1] == (me, True)  # on the student's account, and patient
