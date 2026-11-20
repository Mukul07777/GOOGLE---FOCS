"""Writing questions for a paper: a batch is checked in one call, and a rate limit is waited out, not failed on."""
import time

import pytest

from app.services import question_bank as qb
from app.services.llm import LLMUnavailable

CHAPTER = "Kinematics"


def _item(n, answer=1):
    return {"chapter": CHAPTER, "difficulty": "medium", "answer_index": answer,
            "question": f"A particle moves along a line with constant acceleration (variant {n}). What is its displacement?",
            "options": [f"{n} m", f"{n + 1} m", f"{n + 2} m", f"{n + 3} m"], "solution": "Use s = ut + at^2/2 with the given values."}


def test_a_batch_is_written_then_checked_in_one_call(monkeypatch):
    calls = []

    def answer(messages, **kwargs):
        calls.append(kwargs)
        if kwargs["feature"] == "question_bank":
            return {"questions": [_item(1), _item(2), _item(3)]}, "writer"
        assert kwargs["skip"] == frozenset({"writer"}) and "Question 3:" in messages[1]["content"]  # another model, all three at once
        return {"answers": [{"n": 1, "answer_index": 1}, {"n": 2, "answer_index": 3}]}, "checker"   # agrees, disagrees, says nothing

    monkeypatch.setattr(qb.llm, "json_with_model", answer)
    got = qb.generate_batch("Physics", "mcq", [CHAPTER], n=3)
    assert [c["feature"] for c in calls] == ["question_bank", "question_verify"]
    assert [(q["options"][0], q["verified"]) for q in got] == [("1 m", True), ("3 m", False)]
    # what one request asks for stays inside a free tier's per-minute budget (reasoning models add 1,024 at low effort)
    assert calls[0]["max_tokens"] + 1024 < 6000 and calls[0]["effort"] == "low"


def test_no_second_opinion_keeps_the_questions_unverified(monkeypatch):
    def answer(messages, **kwargs):
        if kwargs["feature"] == "question_verify":
            raise LLMUnavailable("All configured models are rate-limited right now")
        return {"questions": [_item(1), _item(2)]}, "writer"

    monkeypatch.setattr(qb.llm, "json_with_model", answer)
    got = qb.generate_batch("Physics", "mcq", [CHAPTER], n=2)
    assert len(got) == 2 and not any(q["verified"] for q in got)
    assert qb.verify_batch([], "writer") == []


def test_a_rate_limit_is_waited_out_when_a_paper_is_being_prepared(monkeypatch):
    tries, slept = [], []

    def answer(messages, **kwargs):
        tries.append(kwargs["feature"])
        if len(tries) == 1:
            raise LLMUnavailable("All configured models are rate-limited right now")
        return ({"questions": [_item(1)]}, "writer") if kwargs["feature"] == "question_bank" else ({"answers": [{"n": 1, "answer_index": 1}]}, "checker")

    monkeypatch.setattr(qb.llm, "json_with_model", answer)
    monkeypatch.setattr(qb, "next_free_in", lambda skip=frozenset(): 12.0)   # a model is free in 12 s
    monkeypatch.setattr(qb.time, "sleep", slept.append)
    got = qb.generate_batch("Physics", "mcq", [CHAPTER], n=1, deadline=time.monotonic() + 300)
    assert len(got) == 1 and got[0]["verified"] and slept == [12.5] and tries == ["question_bank", "question_bank", "question_verify"]

    # nobody waits when there is no deadline (a student pressed a button), when the wait would pass the deadline,
    # or when no model is resting (the failure is something else: waiting would not help)
    for deadline, free_in in ((None, 12.0), (time.monotonic() + 5, 12.0), (time.monotonic() + 300, 0.0)):
        slept.clear()
        monkeypatch.setattr(qb, "next_free_in", lambda skip=frozenset(), f=free_in: f)
        with pytest.raises(LLMUnavailable):
            qb._patient(lambda: (_ for _ in ()).throw(LLMUnavailable("busy")), deadline)
        assert slept == []
