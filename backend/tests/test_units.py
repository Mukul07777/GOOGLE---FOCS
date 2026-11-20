from app.models.flashcard import Flashcard
from app.services import offline, srs
from app.services.llm import LLMUnavailable, parse_json
from app.services.text_utils import clean_ocr, containment, guess_subject, topics_differ


def test_clean_ocr_drops_browser_chrome():
    raw = "Lectiq Al product strategy x | Focs-swagger ut x | +\nhttps://127.0.0.1:8000/docs\nF = ma\nNewton's second law"
    assert clean_ocr(raw) == "F = ma\nNewton's second law"


def test_containment_detects_growing_board():
    old = "Kinematics\nv = u + at"
    new = "Kinematics\nv = u + at\ns = ut + 1/2 at^2"
    assert containment(old, new) == 1.0
    assert containment(old, "Thermodynamics\nQ = mc dT") < 0.5


def test_subject_and_topic_helpers():
    assert guess_subject("the enthalpy of reaction and gibbs free energy at equilibrium") == "Chemistry"
    assert topics_differ("Thermal Expansion", "Stress and Strain")
    assert not topics_differ("Thermal Expansion", "Thermal expansion of solids")


def test_parse_json_tolerates_fences():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Sure! {"a": 2} hope that helps') == {"a": 2}
    try:
        parse_json("no json here")
        raise AssertionError("should fail")
    except LLMUnavailable:
        pass


def test_sanitize_quiz_normalises_legacy_schema():
    q = offline.sanitize_quiz({"mcq": [{"q": "?", "opts": ["A) x", "B) y", "C) z", "D) w"], "ans": 2}],
                               "true_false": [{"statement": "s", "ans": "true"}]})
    assert q["mcq"][0]["options"] == ["x", "y", "z", "w"] and q["mcq"][0]["answer_index"] == 2
    assert q["true_false"][0]["answer"] is True


def test_sm2_schedule_grows():
    card = Flashcard(ease=2.5, interval_days=0, repetitions=0, lapses=0)
    intervals = []
    for _ in range(4):
        srs.review(card, "good")
        intervals.append(card.interval_days)
    assert intervals[0] == 1 and intervals[1] == 2 and intervals[2] > intervals[1] and intervals[3] > intervals[2]
    srs.review(card, "again")
    assert card.repetitions == 0 and card.lapses == 1 and card.ease >= 1.3


def test_rate_limiter_blocks_after_limit():
    import pytest
    from fastapi import HTTPException

    from app.core import ratelimit

    ratelimit.reset()
    for _ in range(3):
        ratelimit._check("t:1", 3, 60)
    with pytest.raises(HTTPException) as exc:
        ratelimit._check("t:1", 3, 60)
    assert exc.value.status_code == 429
    ratelimit.reset()


def test_backfill_topic_from_markdown():
    from app.services.maintenance import _topic_from_markdown

    assert _topic_from_markdown("### Lecture Notes\n#### Mechanical and Thermal Properties\n* x") == "Mechanical and Thermal Properties"
    assert _topic_from_markdown("no headings") is None


def test_containment_survives_line_splits():
    old = "Rotational Motion\nTorque t = r x F"
    new = "Rotational Motion\nTorque\nt =rx F\nAngular momentum L = Iw"
    assert containment(old, new) >= 0.9


def test_llm_falls_back_when_primary_is_rate_limited(monkeypatch):
    import json as _json

    import httpx

    from app.core.config import settings
    from app.services.llm import llm, reset_cooldowns

    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = _json.loads(request.content)
        seen.append((request.url.host, body))
        if "groq" in request.url.host:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}]})

    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_test")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "gemini_test")
    monkeypatch.setattr(llm, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        assert llm.json([{"role": "user", "content": "hi"}]) == {"ok": True}
    finally:
        monkeypatch.setattr(llm, "_client", None)
        reset_cooldowns()
    (groq_host, groq_body), (gem_host, gem_body) = seen
    assert "groq" in groq_host and groq_body["reasoning_effort"] == "low" and groq_body["include_reasoning"] is False
    assert "googleapis" in gem_host and gem_body["model"] == settings.LLM_FALLBACK_MODEL.split(",")[0].strip() and "reasoning_effort" not in gem_body


def test_llm_rotates_models_and_cools_down_rate_limited_one(monkeypatch):
    import json as _json

    import httpx

    from app.core.config import settings
    from app.services.llm import llm, reset_cooldowns

    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        model = _json.loads(request.content)["model"]
        calls.append(model)
        if model == "openai/gpt-oss-120b":  # daily quota for this model used up
            return httpx.Response(429, headers={"x-ratelimit-reset-requests": "5m0s"}, json={"error": "rate limited"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "answer"}}]})

    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_test")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "openai/gpt-oss-120b, openai/gpt-oss-20b")
    monkeypatch.setattr(llm, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    reset_cooldowns()
    try:
        assert llm.chat([{"role": "user", "content": "q1"}]) == "answer"
        assert llm.chat([{"role": "user", "content": "q2"}]) == "answer"
    finally:
        monkeypatch.setattr(llm, "_client", None)
        reset_cooldowns()
    # first call: 120b refused, 20b answered; second call skips the cooling 120b entirely
    assert calls == ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "openai/gpt-oss-20b"]


def test_copy_database_handles_orphans_and_is_one_shot(tmp_path):
    import sqlite3

    from sqlalchemy import create_engine, func, select

    from app.core.database import Base
    from app.core.migrate import copy_database
    from app.models import Flashcard, Note, StudySession, User

    src = tmp_path / "old.db"
    con = sqlite3.connect(src)
    con.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR, full_name VARCHAR, hashed_pw VARCHAR,
                            plan VARCHAR, exam_target VARCHAR, is_active BOOLEAN, created_at DATETIME);
        CREATE TABLE study_sessions (id INTEGER PRIMARY KEY, user_id INTEGER, course_id INTEGER, video_url VARCHAR,
                                     started_at DATETIME, ended_at DATETIME, is_active BOOLEAN);
        CREATE TABLE notes (id INTEGER PRIMARY KEY, session_id INTEGER, ocr_raw TEXT, ai_notes TEXT,
                            board_hash VARCHAR, captured_at DATETIME);
        INSERT INTO users VALUES (1, 'a@x.com', 'A', 'h', 'free', 'jee', 1, '2026-06-03 00:12:00.123456');
        INSERT INTO study_sessions VALUES (5, 1, 99, '', '2026-06-03 01:00:00', NULL, 0);   -- course 99 missing
        INSERT INTO notes VALUES (7, 5, 'ocr', '### Kinematics', NULL, '2026-06-03 01:05:00');
        INSERT INTO notes VALUES (8, 42, 'orphan', 'x', NULL, '2026-06-03 01:06:00');         -- session 42 missing
    """)
    con.commit(); con.close()

    dst = create_engine(f"sqlite:///{(tmp_path / 'new.db').as_posix()}")
    Base.metadata.create_all(dst)
    counts = copy_database(f"sqlite:///{src.as_posix()}", dst)
    assert counts["users"] == 1 and counts["study_sessions"] == 1 and counts["notes"] == 1
    with dst.connect() as c:
        s = c.execute(select(StudySession)).one()
        assert s.course_id is None and s.is_active is False and s.started_at.year == 2026
        assert c.execute(select(Note.id)).scalars().all() == [7]
        assert c.execute(select(func.count()).select_from(Flashcard)).scalar() == 0
    assert copy_database(f"sqlite:///{src.as_posix()}", dst) == {}  # never runs twice
    assert User.__tablename__ == "users"


def test_parse_json_keeps_latex_and_real_escapes():
    raw = r'{"a": "$\tau = \mathbf{r}\times\mathbf{F}$, $\frac{1}{2}mv^2$, $\beta\rho\nu$, $\nabla$ \(x\)\nNext\tend \u00b2 \theta"}'
    value = parse_json(raw)["a"]
    # (\( x \) arrives as $x$: the renderer reads only $ delimiters)
    assert value.startswith(r"$\tau = \mathbf{r}\times\mathbf{F}$, $\frac{1}{2}mv^2$, $\beta\rho\nu$, $\nabla$ $x$")
    assert "\nNext\tend" in value and "²" in value and value.endswith(r"\theta")


def test_garbage_filter_drops_soup_keeps_formulas():
    from app.services.ocr.engine import looks_like_garbage

    for soup in ["g∂ θι ∂ sqΦ #∂f∂ig)π ∂iq∂ f∂q,", "αgσ Φgσ ΦqΦξT8I g∀ dif39T Φ} 3mξ"]:
        assert looks_like_garbage(soup)
    for real in ["6CO₂ + 6H₂O → C₆H₁₂O₆ + 6O₂", "P(A∪B) = P(A) + P(B) - P(A∩B)", "Angular momentum L = Iω",
                 "θ = 30°, g = 9.8 m/s²", "Potentiometer", "Case II:", "Δ ABC ~ Δ PQR", "C₆H₁₂O₆"]:
        assert not looks_like_garbage(real), real


def test_fix_latex_undoubles_commands_only():
    from app.services.llm import fix_latex

    assert fix_latex(r"$\\mathbf{r}\\times\\mathbf{F}$") == r"$\mathbf{r}\times\mathbf{F}$"
    assert fix_latex(r"a \\ b \\ 2") == r"a \\ b \\ 2"          # real line breaks untouched
    assert fix_latex({"x": [r"\\frac{1}{2}"]}) == {"x": [r"\frac{1}{2}"]}
    assert fix_latex(r"$\tau$") == r"$\tau$"


def test_fix_latex_restores_backslashes_json_mode_dropped():
    from app.services.llm import fix_latex

    # what Groq's JSON mode actually returned for "$\omega_0$" and "$\displaystyle \tau = ...$"
    assert fix_latex(r"speed $omega_0$ and $alpha$") == r"speed $\omega_0$ and $\alpha$"
    assert fix_latex(r"$displaystyle \tau = frac{tfrac12 mR^2}{t}$") == r"$\displaystyle \tau = \frac{\tfrac12 mR^2}{t}$"
    assert fix_latex(r"$mathbf{F} = m mathbf{a}$") == r"$\mathbf{F} = m \mathbf{a}$"
    # prose outside math, \text{} contents and look-alike subscripts are left alone
    assert fix_latex("the alpha particle costs $5") == "the alpha particle costs $5"
    assert fix_latex(r"$text{sum of torques} = 0$") == r"$\text{sum of torques} = 0$"
    assert fix_latex(r"$E_{int} + E_{max}$") == r"$E_{int} + E_{max}$"
    assert fix_latex(r"$\beta + \eta$") == r"$\beta + \eta$"


def test_fix_latex_over_escaped_and_literal_newlines():
    from app.services.llm import fix_latex

    # what a model returned after escaping a matrix twice
    assert fix_latex(r"$\\begin{pmatrix} 3 & 2 \\\\ 5 & 7 \\end{pmatrix}$") == r"$\begin{pmatrix} 3 & 2 \\ 5 & 7 \end{pmatrix}$"
    assert fix_latex(r"Vandermonde. \n $\det A = 540$") == "Vandermonde. \n $\\det A = 540$"
    assert fix_latex(r"$\nu = \neq$ stays") == r"$\nu = \neq$ stays"
    assert fix_latex(r"$a \\ b$") == r"$a \\ b$"  # a real row break, nothing doubled


def test_wrap_formula_bullets():
    from app.services.llm import wrap_formula_bullets

    md = "\n".join([
        "### Key ideas",
        r"- Torque \tau causes rotation of the body about an axis",
        "### Formulas",
        r"- \tau = \mathbf{r}\times\mathbf{F}",
        r"- **Torque:** \tau = I\alpha",
        "- F = ma",
        r"- Already fine: $L = I\omega$",
        r"- If there is no external torque acting then angular momentum stays constant",
        "### Exam tip",
        "- v = u + at is for constant acceleration only, never for variable forces",
    ])
    out = wrap_formula_bullets(md).split("\n")
    assert out[1] == r"- Torque \tau causes rotation of the body about an axis"   # not a formulas section
    assert out[3] == r"- $\tau = \mathbf{r}\times\mathbf{F}$"
    assert out[4] == r"- **Torque:** $\tau = I\alpha$"
    assert out[5] == "- $F = ma$"
    assert out[6] == r"- Already fine: $L = I\omega$"
    assert out[7] == "- If there is no external torque acting then angular momentum stays constant"
    assert out[9] == "- v = u + at is for constant acceleration only, never for variable forces"


def test_formula_book_extracts_and_dedupes():
    from types import SimpleNamespace

    from app.services import formulas

    md = "intro\n### Key ideas\n- not a formula\n### Formulas\n- $F = ma$\n- **Torque:** $\tau = r F$\n### Exam tip\n- nope"
    assert formulas.extract(md) == ["$F = ma$", "**Torque:** $\tau = r F$"]
    notes = [SimpleNamespace(id=1, session_id=9, subject="Physics", topic="Laws of Motion", captured_at=1, ai_notes=md),
             SimpleNamespace(id=2, session_id=9, subject="Physics", topic="Dynamics", captured_at=2, ai_notes="## Formulas\n- $F=ma$")]
    book = formulas.book(notes)
    assert book[0]["subject"] == "Physics" and book[0]["count"] == 2  # "$F=ma$" and "$F = ma$" are one formula
    assert book[0]["topics"][0]["topic"] == "Dynamics"  # newest first
