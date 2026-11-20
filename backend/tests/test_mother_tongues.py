"""Innovation #3: a student learns in their mother tongue. Tamil, Bengali, Marathi, Telugu and Gujarati join Hindi and
Hinglish: every sentence in the language's own script, every formula and number untouched, and an answer handed back
in English, or in the wrong script, is caught before any student sees it."""
import pytest

from app.schemas.auth import Language
from app.services import ai, translate
from app.services.llm import llm

EN = "## Ohm's law\n- Current through a conductor is proportional to the voltage across it: $V = IR$, at 2 ohms."
IN = {
    "ta": "## ஓமின் விதி\n- ஒரு கடத்தியின் வழியே செல்லும் மின்னோட்டம் மின்னழுத்தத்திற்கு நேர்விகிதத்தில் உள்ளது: $V = IR$, 2 ohms இல்.",
    "bn": "## ওহমের সূত্র\n- পরিবাহীর মধ্য দিয়ে প্রবাহিত তড়িৎ প্রবাহ বিভব পার্থক্যের সমানুপাতিক: $V = IR$, 2 ohms এ।",
    "te": "## ఓమ్ నియమం\n- వాహకం ద్వారా ప్రవహించే విద్యుత్ ప్రవాహం వోల్టేజ్‌కు అనులోమానుపాతంలో ఉంటుంది: $V = IR$, 2 ohms వద్ద.",
    "gu": "## ઓહ્મનો નિયમ\n- વાહકમાંથી વહેતો પ્રવાહ તેના છેડા વચ્ચેના વોલ્ટેજના સમપ્રમાણમાં હોય છે: $V = IR$, 2 ohms પર.",
    "mr": "## ओहमचा नियम\n- वाहकातून जाणारा प्रवाह त्याच्या टोकांमधील व्होल्टेजच्या समप्रमाणात असतो आणि तो नियम आहे: $V = IR$, 2 ohms ला.",
}
HI = "## ओम का नियम\n- किसी चालक से बहने वाली धारा वोल्टेज के अनुपाती होती है और यह नियम है: $V = IR$, 2 ohms पर।"


def test_every_language_is_known_everywhere():
    """One list: the AI rules, the reminder after the question, the translation rules, the names, and what the API takes."""
    codes = {"hinglish", "hi", "mr", "bn", "ta", "te", "gu"}
    assert set(ai.LANGUAGES) == set(ai.REPLY_IN) == set(translate.TRANSLATE_RULE) == set(translate.NAMES) == codes
    assert set(Language.__args__) == codes | {"en"}
    for code, (name, script, _) in ai.MOTHER_TONGUES.items():
        assert name in ai.language_rule(code) and f"{script} script" in ai.language_rule(code)
        assert "formula" in ai.language_rule(code) and name in ai.REPLY_IN[code]


@pytest.mark.parametrize("code", list(IN))
def test_a_real_translation_passes_and_english_does_not(code):
    assert translate.in_language(EN, IN[code], code)
    assert translate.faithful(EN, IN[code])  # the formula and the number came through
    assert not translate.in_language(EN, EN, code)


def test_the_wrong_script_is_caught():
    """A Tamil student handed Hindi, or a Gujarati one handed Bengali, is not reading their language."""
    assert not translate.in_language(EN, HI, "ta")
    assert not translate.in_language(EN, IN["bn"], "gu")
    assert not translate.in_language(EN, IN["te"], "ta")


def test_marathi_that_slipped_into_hindi_is_caught():
    """Both are Devanagari, so the script alone can't tell them apart: the everyday words can."""
    assert translate.in_language(EN, IN["mr"], "mr")
    assert not translate.in_language(EN, HI, "mr")
    assert translate.in_language(EN, HI, "hi")
    # का is Marathi's "why" (a live answer opened "45° का सर्वाधिक अंतर देते"): not a sign of Hindi
    assert translate.in_language("Why 45?", "## 45° का सर्वाधिक अंतर देते - कारण sin 2θ हे 1 असते", "mr")
    assert "not Hindi" in ai.language_rule("mr") and "not Hindi" in translate.TRANSLATE_RULE["mr"]


def test_notes_are_translated_into_tamil_once_checked(monkeypatch):
    seen = []
    monkeypatch.setattr(llm, "chat", lambda messages, **k: seen.append(messages) or IN["ta"])
    assert translate.translate(EN, "ta", "jee") == (IN["ta"], True)
    system, ask = seen[0][0]["content"], seen[0][1]["content"]
    assert "Tamil script" in system and ask.rstrip().endswith("Nothing before or after it.)") and "into Tamil" in ask
    monkeypatch.setattr(llm, "chat", lambda *a, **k: HI)  # Hindi twice: the student gets English with a notice
    assert translate.translate(EN, "ta", "jee") == (EN, False)
    assert "Tamil" in translate.notice("ta")


def _register(client, email):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Kavya Raman",
                                                "password": "correct-horse-1", "exam_target": "jee"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_a_student_picks_tamil_and_the_doubt_comes_back_in_tamil(client, monkeypatch):
    h = _register(client, "tamil.student@example.com")
    for code in ("ta", "bn", "mr", "te", "gu", "en"):
        assert client.patch("/api/auth/me", headers=h, json={"language": code}).json()["language"] == code
    assert client.patch("/api/auth/me", headers=h, json={"language": "fr"}).status_code == 422
    assert client.patch("/api/auth/me", headers=h, json={"language": "ta"}).status_code == 200

    seen = []
    monkeypatch.setattr(llm, "chat", lambda messages, **k: seen.append(messages) or "திருப்புவிசை ஒரு சுழற்சி விளைவு: τ = rF.")
    r = client.post("/api/companion/ask", headers=h, json={"question": "What is torque?", "mode": "explain", "history": []})
    assert r.status_code == 200 and "திருப்புவிசை" in r.json()["answer"]
    assert "Tamil script" in seen[0][0]["content"] and "Reply in Tamil" in seen[0][-1]["content"]


def test_the_working_tutor_gets_the_mother_tongue_rule():
    assert "Tamil" in ai.language_rule("ta")
    assert "Marathi" in ai.language_rule("mr") and "Hindi" in ai.language_rule("mr")
    for code in ("mr", "bn", "ta", "te", "gu"):
        assert ai.REPLY_IN.get(code)
