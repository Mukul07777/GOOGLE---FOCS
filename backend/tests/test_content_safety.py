from app.services import ai
from app.services.math_text import clean_option


def test_an_interval_written_with_latex_delimiters_keeps_its_closing_bracket():
    assert clean_option(r"\displaystyle [-\tfrac{7}{2},\,19\]") == r"$[-\frac{7}{2},\,19]$"
    assert clean_option(r"\(x^2\)") == "$x^2$"
    assert clean_option("[-7/2, 19)") == "[-7/2, 19)"


def test_maths_that_cannot_be_drawn_becomes_plain_text():
    out = clean_option(r"$\frac{7}{2$")
    assert "$" not in out and "{" not in out


def test_a_question_whose_options_the_checker_rejects_is_dropped(monkeypatch):
    q = {"question": "Solve -3 < 2x-5 <= 7", "options": ["a", "b", "c", "d"], "answer_index": 1, "explanation": "x"}
    monkeypatch.setattr(ai, "_checked_mcqs", lambda mcq, exam, gen: [])
    assert ai._sound_question(q, "jee", "m") is None
    monkeypatch.setattr(ai, "_checked_mcqs", lambda mcq, exam, gen: [{**mcq[0], "checked": True}])
    assert ai._sound_question(q, "jee", "m")["answer_index"] == 1


def test_flashcards_the_checker_rejects_are_dropped(monkeypatch):
    cards = [{"front": "f1", "back": "b1"}, {"front": "f2", "back": "b2"}]
    monkeypatch.setattr(ai.llm.__class__, "available", property(lambda self: True))
    monkeypatch.setattr(ai.llm, "json", lambda *a, **k: {"cards": [{"n": 1, "ok": True}, {"n": 2, "ok": False}]})
    assert ai._checked_cards(cards, "jee") == [cards[0]]


def _mcq(key=0):
    return {"q": "Pick", "options": ["a", "b", "c", "d"], "answer_index": key, "explanation": "gen"}


def test_a_disputed_key_is_fixed_when_a_third_model_agrees_with_the_checker(monkeypatch):
    calls = []

    def round_(asked, system, n, skip):
        calls.append(skip)
        return {1: {"correct": [2], "working": "checker work"}}, f"m{len(calls)}"
    monkeypatch.setattr(ai, "_check_round", round_)
    out = ai._checked_mcqs([_mcq(0)], "jee", "gen")
    assert out[0]["answer_index"] == 2 and out[0]["explanation"] == "checker work" and len(calls) == 2


def test_a_key_the_third_model_backs_is_kept(monkeypatch):
    answers = iter([{1: {"correct": [2]}}, {1: {"correct": [0]}}])
    monkeypatch.setattr(ai, "_check_round", lambda *a: (next(answers), "m"))
    assert ai._checked_mcqs([_mcq(0)], "jee", "gen")[0]["answer_index"] == 0


def test_no_correct_option_drops_the_question(monkeypatch):
    monkeypatch.setattr(ai, "_check_round", lambda *a: ({1: {"correct": []}}, "m"))
    assert ai._checked_mcqs([_mcq(0)], "jee", "gen") == []


def test_a_true_false_key_two_models_reject_is_flipped(monkeypatch):
    monkeypatch.setattr(ai, "_check_round", lambda *a: ({1: {"true": False, "reason": "because"}}, "m"))
    out = ai._checked_statements([{"statement": "s", "answer": True, "explanation": ""}], "jee")
    assert out == [{"statement": "s", "answer": False, "explanation": "because"}]


def test_a_photographed_answer_is_read_then_graded(client, auth, monkeypatch):
    from app.api import quiz as quiz_api
    from tests.conftest import board_png
    monkeypatch.setattr(quiz_api.vision, "available", lambda: True)
    monkeypatch.setattr(quiz_api.vision, "read_json", lambda *a, **k: {"readable": True, "answer": "$x = 2$ and $x = 3$"})
    seen = {}

    def grade(question, answer, *a, **k):
        seen["answer"] = answer
        return {"score": 8, "grade": "Good", "points_covered": [], "points_missed": [], "feedback": "ok", "source": "ai"}
    monkeypatch.setattr(quiz_api.ai, "evaluate_answer", grade)
    r = client.post("/api/quiz/evaluate-photo", headers=auth, data={"question": r"Solve $rac{1}{2}x = 1$", "key_points": '["x=2"]'},
                    files={"files": ("a.png", board_png(["x = 2"]), "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["read_answer"] == "$x = 2$ and $x = 3$" and seen["answer"] == "$x = 2$ and $x = 3$"
