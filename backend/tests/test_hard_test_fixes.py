"""Fixes from the 28 October hard test (HANDOVER 7l): offline practice sets built from facts, not prompt headers;
no near-copies in one paper; study hours and goals sized to a school class; JEE Advanced papers kept to Advanced."""
from app.services import offline, planner, question_bank

MATERIAL = """Syllabus topic: Square Numbers
Chapter: A Square and A Cube (Mathematics, Class 8)
| $1^2$ | 1 | the first square |
Mistake: Adding consecutive odd numbers wrongly
A square number is the product of a whole number with itself.
The square of an even number is always an even number too.
Perfect squares never end in the digits two, three, seven or eight.
Square numbers grow quickly as numbers grow larger."""


def test_offline_practice_never_asks_about_the_prompt_header_or_table_rows():
    quiz = offline.quiz(MATERIAL, 3, 2, 1)
    text = " ".join([q["q"] for q in quiz["mcq"]] + [s["statement"] for s in quiz["true_false"]])
    assert quiz["mcq"] and "Syllabus topic" not in text and "Chapter:" not in text and "|" not in text and "Mistake" not in text
    for q in quiz["mcq"]:  # the answer isn't offered twice as "Square" and "squares"
        stems = [o.lower().rstrip("s") for o in q["options"]]
        assert len(stems) == len(set(stems))


def test_near_copies_count_as_one_question():
    same = question_bank._words("What is the next number in the pattern 2, 4, 8, 16?")
    again = question_bank._words("What is the next number in the pattern 2, 4, 8, 16 ?")
    other = question_bank._words("What is the smallest number by which 72 must be multiplied to make a perfect cube?")
    assert question_bank.near_duplicate(same, again) and not question_bank.near_duplicate(same, other)


def test_a_young_class_is_not_told_to_study_like_a_board_class():
    assert planner.target_info("cbse_1", "pct_90")["hours"] == 1
    assert planner.target_info("cbse_12", "pct_90")["hours"] == 4
    assert "JEE" not in planner.target_info("cbse_5", "pct_75")["hint"]


def test_an_advanced_paper_takes_only_advanced_questions():
    assert question_bank.exam_family("jee_advanced", "Physics") == ("jee_advanced",)
    assert question_bank.own_first("jee_advanced", "jee_advanced") == 0
