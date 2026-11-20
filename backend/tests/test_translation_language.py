"""A translation must really be in the student's language. The cheap model sometimes handed the English back
unchanged, which keeps every formula and number, so the formula check passed it and a Hindi student was shown English
notes labelled Hindi."""
from app.services import translate

EN = "## Ohm's law\n- Current through a conductor is proportional to the voltage across it: $V = IR$."
HI = "## ओम का नियम\n- किसी चालक से बहने वाली धारा उसके सिरों के बीच वोल्टेज के अनुपाती होती है: $V = IR$."
HINGLISH = "## Ohm's law\n- Conductor mein current uske across voltage ke proportional hota hai: $V = IR$."


def test_english_handed_back_is_not_a_translation():
    assert not translate.in_language(EN, EN, "hi")
    assert not translate.in_language(EN, EN, "hinglish")


def test_real_translations_pass():
    assert translate.in_language(EN, HI, "hi")
    assert translate.in_language(EN, HINGLISH, "hinglish")


def test_formulas_and_units_dont_count_against_hindi():
    md = r"- $F = ma$, $1\,\text{N} = 1\,\text{kg m/s}^2$" + "\n- बल द्रव्यमान और त्वरण का गुणनफल है (force)"
    assert translate.in_language(md, md, "hi")


def test_untranslated_answers_fall_back_to_english_with_a_notice(monkeypatch):
    monkeypatch.setattr(translate.llm, "chat", lambda *a, **k: EN)
    assert translate.translate(EN, "hi", "jee") == (EN, False)  # the caller then shows the "showing English" notice
