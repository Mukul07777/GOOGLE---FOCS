"""Fixes from the focs.in hard test of 27 October 2026."""
from app.services import mock_patterns
from app.services.mailer import greeting_name


def test_email_greeting_carries_no_html_or_links():
    assert greeting_name("Mukul Sharma") == "Mukul"
    assert greeting_name("<a href=http://x.co>Click</a>") == "a"
    assert "<" not in greeting_name("<script>alert(1)</script>")
    assert ":" not in greeting_name("http://evil.com/login") and "." not in greeting_name("http://evil.com/login")
    assert greeting_name("मुकुल शर्मा") == "मुकुल"  # Hindi keeps its vowel signs
    assert greeting_name("O'Brien") == "O'Brien"
    assert greeting_name("") == greeting_name(None) == greeting_name("<>") == "there"


def test_jee_default_is_the_current_nta_paper():
    # the 90-question paper's "any 5 of 10 numericals" was dropped by NTA in 2025; students got stuck on it
    p = mock_patterns.PATTERNS[mock_patterns.DEFAULT_PATTERNS["jee"]]
    assert p.id == "jee_main_25" and all(s.attempt == s.count for s in p.sections)


def test_mcq_options_are_shuffled_per_paper_and_marked_by_what_was_shown():
    from app.models.mock import BankQuestion, MockTest
    from app.services import mock
    q = BankQuestion(id=901, exam="neet", subject="Physics", chapter="Kinematics", qtype="mcq", question="?",
                     options=["right", "w1", "w2", "w3"], answer="0", solution="Because.")
    new = MockTest(id=77, shuffled=True)
    order = mock.option_order(new, q)
    assert sorted(order) == [0, 1, 2, 3] and order == mock.option_order(new, q)  # the same order on every load
    shown = order.index(0)  # where "right" ended up on screen
    assert mock._is_correct(q, str(shown), order) and not mock._is_correct(q, str((shown + 1) % 4), order)
    assert not mock._is_correct(q, "9", order)
    # across many papers the right answer lands in every position
    spots = {mock.option_order(MockTest(id=i, shuffled=True), q).index(0) for i in range(40)}
    assert spots == {0, 1, 2, 3}
    # a paper made before the change keeps the stored order its saved answers point at
    assert mock.option_order(MockTest(id=78, shuffled=None), q) is None
    # options that point at each other stay as written
    q.options = ["A", "B", "Both (a) and (b)", "None of these"]
    assert mock.option_order(new, q) is None
