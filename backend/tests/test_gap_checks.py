"""A root-cause check must mark the answer its own working arrives at. A live chain asked for the circumference of a
circle of radius 3 m, worked it out as 6π m, and marked 9π m right: a student who knew it was told they didn't."""
from app.core.database import SessionLocal
from app.models.gap import PrereqMap
from app.services import gaps

CIRCLE = {"q": "The radius of a circle is 3 m. What is its circumference?", "options": ["6π m", "9π m", "12π m", "18π m"],
          "answer": 1, "explain": "C = 2πr = 2π·3 = 6π m."}
SINE = {"q": "What is sin 30°?", "options": ["0.5", "0.707", "1", "0"], "answer": 0, "explain": "sin 30° = 1/2 = 0.5."}


def test_the_answer_follows_the_working():
    assert gaps.agreeing(CIRCLE)["answer"] == 0
    assert gaps.agreeing(SINE) == SINE  # already right: untouched


def test_anything_unsure_is_left_alone():
    words = {**CIRCLE, "explain": "Circumference is two pi times the radius."}  # no "=": nothing to go on
    assert gaps.agreeing(words) == words
    hedged = {**CIRCLE, "explain": "C = 6π m, not 9π m"}  # the working doesn't end on exactly one option
    assert gaps.agreeing(hedged) == hedged
    twins = {**CIRCLE, "options": ["6π m", "6π  m", "12π m", "18π m"]}  # two options match: can't tell
    assert gaps.agreeing(twins) == twins


def test_a_new_check_is_corrected_as_it_comes_in():
    assert gaps._clean_check(CIRCLE)["answer"] == 0


def test_a_chain_kept_before_the_fix_is_corrected_for_everyone(client):  # (client: the tables exist)
    link = {"chapter_id": "mathematics.circles", "name": "Circles", "subject": "Mathematics", "cls": 11,
            "idea": "Radius of a circle", "why": "", "check": CIRCLE}
    syl = None
    with SessionLocal() as db:
        db.merge(PrereqMap(key="test.kept-chain", chain=[link]))
        db.commit()
        target = type("T", (), {"id": "test.kept-chain"})()
        chain, used_ai = gaps.prereq_chain(db, syl, target, None, None)
        assert not used_ai and chain[0]["check"]["answer"] == 0
        db.expire_all()
        assert db.get(PrereqMap, "test.kept-chain").chain[0]["check"]["answer"] == 0  # stored corrected
