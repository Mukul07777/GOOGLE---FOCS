"""Reading a live board: the vision models' fallback chain, and the light OCR pass beside them.

Seen on 2026-10-19 with real Physics Wallah boards: gemini-3.1-flash-lite answered 503 "high demand" for three of
four boards (after up to 20 s each), the notes were then written from garbled OCR, and one board was dropped as
"not a lecture". And the two-model OCR ensemble on every frame took 15 CPU-seconds a board, which stalled the
lecture video playing on the same laptop."""
import threading

import httpx

from app.core.config import settings
from app.services import ai, ledger, vision
from app.services.llm import llm
from app.services.ocr import ocr_engine
from tests.conftest import board_png


class _Reply:
    def __init__(self, status: int, content: str = "", usage: dict | None = None):
        self.status_code, self.headers, self.text = status, {}, content
        self._json = {"choices": [{"message": {"content": content}}], "usage": usage or {"prompt_tokens": 1300, "completion_tokens": 120}}

    def json(self):
        return self._json


def test_a_busy_vision_model_hands_over_to_the_next_without_json_mode(monkeypatch):
    monkeypatch.setattr(settings, "VISION_MODEL", "model-a,model-b")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "k")
    sent, recorded = [], []
    reading = '```json\n{"board": "$\\\\frac{(x-1)^{4}}{x^{2024}} \\\\ge 0$"}\n```'  # fenced, LaTeX escaped as models do

    def post(url, json, headers, timeout):
        sent.append((json["model"], timeout, "response_format" in json))
        return _Reply(503, "high demand") if json["model"] == "model-a" else _Reply(200, reading)

    monkeypatch.setattr(llm.client, "post", post)
    monkeypatch.setattr(ledger, "record", lambda feature, model, usage: recorded.append((feature, model)))
    board = vision.read_board(b"jpeg")
    assert board == r"$\frac{(x-1)^{4}}{x^{2024}} \ge 0$"  # every backslash kept
    assert sent == [("model-a", vision.BOARD_TIMEOUT_S, False), ("model-b", vision.BOARD_TIMEOUT_S, False)]
    assert recorded == [("board_read", "model-b")]  # costed as the model that answered

    # a model that doesn't answer in time, or is retired, is skipped too; when none answers the caller gets None
    def slow(url, json, headers, timeout):
        sent.append(json["model"])
        if json["model"] == "model-a":
            raise httpx.ReadTimeout("slow")
        return _Reply(404, "not found")

    sent.clear()
    monkeypatch.setattr(llm.client, "post", slow)
    assert vision.read_board(b"jpeg") is None and sent == ["model-a", "model-b"]

    # one model alone gets a single retry, as before
    monkeypatch.setattr(settings, "VISION_MODEL", "model-a")
    monkeypatch.setattr("app.services.vision.time.sleep", lambda s: None)
    calls = iter([_Reply(503), _Reply(200, '{"board": "F = ma"}')])
    monkeypatch.setattr(llm.client, "post", lambda url, json, headers, timeout: next(calls))
    assert vision.read_board(b"jpeg") == "F = ma"


def test_a_slow_first_model_doesnt_keep_a_waiting_student_waiting(monkeypatch):
    """On 2026-10-23 gemini-3.1-flash-lite took up to 30 s on a first board while the next model answered in 1.5 s.
    A student waiting gets the next model's answer once the first has had its head start; the slow call is still
    costed, to the student who asked."""
    from app.services.ledger import current_user

    monkeypatch.setattr(settings, "VISION_MODEL", "slow,quick")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(vision, "BOARD_HEAD_START_S", 0.05)
    release, recorded = threading.Event(), []
    monkeypatch.setattr(ledger, "record", lambda feature, model, usage: recorded.append((model, current_user.get())))

    def post(url, json, headers, timeout):
        if json["model"] == "slow":
            release.wait(5)
            return _Reply(200, '{"board": "late"}')
        return _Reply(200, '{"board": "F = ma"}')

    monkeypatch.setattr(llm.client, "post", post)
    token = current_user.set(42)
    try:
        assert vision.read_board(b"jpeg") == "F = ma"
    finally:
        current_user.reset(token)
    release.set()
    for _ in range(100):
        if len(recorded) == 2:
            break
        threading.Event().wait(0.02)
    assert sorted(recorded) == [("quick", 42), ("slow", 42)]

    # in the background nothing is raced: the cheap model is waited for
    recorded.clear()
    release.clear()
    threading.Timer(0.2, release.set).start()
    assert vision.read_board(b"jpeg", patient=True) == "late" and recorded == [("slow", None)]


def _student(client, email):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Board Student", "password": "correct-horse-1", "exam_target": "jee"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_live_frames_use_the_light_ocr_and_the_full_one_only_when_vision_fails(client, monkeypatch):
    for t in threading.enumerate():  # the start-up warm-up reads one line too: let it finish before counting reads
        if t.name == "ocr-warmup":
            t.join(timeout=120)
    modes, real_run = [], ocr_engine.run

    def spy(img, mode=None, keep_candidates=False):
        modes.append(mode)
        return real_run(img, mode, keep_candidates)

    monkeypatch.setattr(ocr_engine, "run", spy)
    monkeypatch.setattr(vision, "available", lambda: True)
    monkeypatch.setattr(settings, "OCR_TRUST_CONFIDENCE", 1.01)  # a clean synthetic board would be routed past vision
    monkeypatch.setattr(ai, "generate_notes", lambda text, exam, prev_topic=None, offline_only=False, patient=True, board=None: {
        "is_lecture": True, "topic": "Optics", "subject": "Physics", "notes_md": f"## {(board or text)[:60]}", "source": "ai"})
    if ocr_engine.resolve_mode(None) != "auto":  # both OCR models are installed wherever Focs runs; skip the rest if not
        return

    h = _student(client, "light.ocr@example.com")
    sid = client.post("/api/sessions", headers=h, json={"title": "Optics"}).json()["id"]
    monkeypatch.setattr(vision, "read_board", lambda jpeg, patient=False: "Snell's law: $n_1 \\sin\\theta_1 = n_2 \\sin\\theta_2$")
    r = client.post(f"/api/capture/{sid}/frame", headers=h,
                    files={"frame": ("f.png", board_png(["Refraction of light", "Snell's law n1 sin i = n2 sin r", "Critical angle sin C = 1/n"]), "image/png")}).json()
    assert r["status"] == "created" and modes == ["focs"]  # the vision model read it: FocsOCR alone decided it was new
    assert r["note"]["ocr_raw"].startswith("Snell's law")

    modes.clear()
    monkeypatch.setattr(vision, "read_board", lambda jpeg, patient=False: None)  # every vision model busy
    sid = client.post("/api/sessions", headers=h, json={"title": "Waves"}).json()["id"]
    r = client.post(f"/api/capture/{sid}/frame", headers=h,
                    files={"frame": ("f.png", board_png(["Wave optics", "Fringe width beta = lambda D / d", "Young double slit experiment"]), "image/png")}).json()
    assert r["status"] == "created" and modes == ["focs", "auto"]  # read again by both models for the notes
    assert "fringe" in r["note"]["ocr_raw"].lower()


def test_a_slide_read_surely_by_focsocr_skips_the_vision_model(client, monkeypatch):
    from types import SimpleNamespace

    from app.services.live import ocr_is_enough

    def result(conf, n=5, engine="focs", text="Refraction of light\nTotal internal reflection"):
        return SimpleNamespace(engine=engine, confidence=conf, lines=[None] * n, text=text)

    assert ocr_is_enough(result(0.99))
    assert not ocr_is_enough(result(0.99, text="D > 0 : two real roots"))  # math stays with the vision model
    assert not ocr_is_enough(result(0.93))            # handwriting reads below the bar
    assert not ocr_is_enough(result(0.99, n=1))       # one sure line on a board says little
    assert not ocr_is_enough(result(0.99, engine="auto"))

    asked = []
    monkeypatch.setattr(vision, "available", lambda: True)
    monkeypatch.setattr(vision, "read_board", lambda jpeg, patient=False: asked.append(1) or "from vision")
    monkeypatch.setattr(ai, "generate_notes", lambda text, exam, prev_topic=None, offline_only=False, patient=True, board=None: {
        "is_lecture": True, "topic": "Optics", "subject": "Physics", "notes_md": f"## {(board or text)[:60]}", "source": "ai"})
    monkeypatch.setattr("app.services.live.ocr_is_enough", lambda ocr: True)
    h = _student(client, "routed.slide@example.com")
    sid = client.post("/api/sessions", headers=h, json={"title": "Optics"}).json()["id"]
    r = client.post(f"/api/capture/{sid}/frame", headers=h,
                    files={"frame": ("f.png", board_png(["Refraction of light", "Snell's law n1 sin i = n2 sin r", "Critical angle sin C = 1/n"]), "image/png")}).json()
    assert r["status"] == "created" and not asked and "from vision" not in r["note"]["ocr_raw"]


def test_the_board_goes_into_the_notes_word_for_word():
    """Asked only to copy the board's steps, the notes models still added sign charts of their own, wrong in up to
    three intervals. With the board read off the frame, its text is placed in the notes as it is."""
    md = ("Context line.\n\n### Key ideas\n- odd powers flip the sign\n\n### Worked example\nthe model's own chart\n\n"
          "### On the board\nthe model's copy\n\n### Exam tip\nExclude the poles.")
    board = ("# Trick: coeff of x\n+ - + - +\n1. Find x\n" r"$x \in [-3, -2) \cup \{1\}$" "\n"
             r"$\# \text{ Trick: } x \rightarrow \text{(+ve)}" "\n" r"odd \quad even \rightarrow \text{sign change}")
    out = ai.with_board(md, board)
    assert "the model's own chart" not in out and "the model's copy" not in out and out.count("### On the board") == 1
    assert out.index("- odd powers flip") < out.index("### On the board") < out.index("### Exam tip")
    # each line its own paragraph, nothing Markdown would turn into a heading or a list, and every line's maths
    # closed on that line (an unclosed $ ran on through the next lines; LaTeX outside $...$ showed as code)
    # (a sign chart's row stays spaced out, as code, since OCR often runs its signs together)
    assert ("\\# Trick: coeff of x\n\n`+  −  +  −  +`\n\n1\\. Find x\n\n" r"$x \in [-3, -2) \cup \{1\}$" "\n\n"
            r"$\# \text{ Trick: } x \rightarrow \text{(+ve)}$" "\n\n" r"$odd \quad even \rightarrow \text{sign change}$") in out
    assert ai.with_board("Just a line.", "F = ma").endswith("Just a line.\n\n### On the board\nF = ma")


def test_board_notes_skip_the_light_model_and_never_drop_a_board_that_was_read(monkeypatch):
    seen = []
    monkeypatch.setattr(llm, "json", lambda messages, **k: seen.append((messages, k)) or {"is_lecture": False})
    notes = ai.generate_notes("Phys Qty Lngth Scale", "jee", board="Physical Quantity\nLength | Scale\nMass | Weighing Machine")
    assert notes["is_lecture"] and "Weighing Machine" in notes["notes_md"]  # the light model's "not a lecture" is overruled
    messages, kwargs = seen[0]
    assert set(settings.LLM_LIGHT_MODEL.split(",")) <= kwargs["skip"] and "tier" not in kwargs
    assert "don't copy the board out" in messages[0]["content"]


def test_unreadable_json_goes_to_the_next_model_before_json_mode(monkeypatch):
    """JSON mode deletes LaTeX backslashes: a JSON-mode retry of board notes came back with "ge0", "cup", "infty"."""
    calls = []

    def chat(messages, **k):
        calls.append((frozenset(k.get("skip", ())), k.get("json_mode", False)))
        if not k.get("skip"):
            return r"Sure! Here are the notes: $x \ge 0$", "model-a"
        return r'{"notes_md": "$x \\ge 0$, $A \\cup B$"}', "model-b"

    monkeypatch.setattr(llm, "chat_with_model", chat)
    data, model = llm.json_with_model([{"role": "system", "content": "notes"}], max_tokens=10)
    assert model == "model-b" and data["notes_md"] == r"$x \ge 0$, $A \cup B$"
    assert calls == [(frozenset(), False), (frozenset({"model-a"}), False)]


def test_a_board_written_in_the_background_waits_for_the_cheap_models(monkeypatch):
    """On 2026-10-20 the cheap Geminis were overloaded or slow for most boards and Qwen, twice the price, read them.
    In the background each model but the last gets a second try, with time to answer."""
    monkeypatch.setattr(settings, "VISION_MODEL", "cheap,cheaper-still,dear")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "k")
    monkeypatch.setattr("app.services.vision.time.sleep", lambda s: None)
    monkeypatch.setattr(ledger, "record", lambda feature, model, usage: None)
    sent = []
    replies = iter([_Reply(503), _Reply(200, '{"board": "v = u + at"}')])

    def post(url, json, headers, timeout):
        sent.append((json["model"], timeout))
        return next(replies)

    monkeypatch.setattr(llm.client, "post", post)
    assert vision.read_board(b"jpeg", patient=True) == "v = u + at"
    assert sent == [("cheap", vision.BOARD_PATIENT_TIMEOUT_S), ("cheap", vision.BOARD_PATIENT_TIMEOUT_S)]

    sent.clear()
    replies = iter([_Reply(503)] * 4 + [_Reply(200, '{"board": "s = ut"}')])
    assert vision.read_board(b"jpeg", patient=True) == "s = ut"
    assert [m for m, _ in sent] == ["cheap", "cheap", "cheaper-still", "cheaper-still", "dear"]  # the dear one once, last
