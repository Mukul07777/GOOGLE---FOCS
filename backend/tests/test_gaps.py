"""Root-cause gap tracing: the chain, the diagnosis, the fix, and what it costs."""
import pytest

from app.services import gaps, syllabus


def _q(answer=1):
    return {"q": "Which is right?", "options": ["a", "b", "c", "d"], "answer": answer, "explain": "because"}


@pytest.fixture
def jee_rotation():
    syl = syllabus.get("jee")
    target = next(c for c in syl.chapters if c.id == "physics.rotational-motion")
    pool = gaps.candidates(syl, target)
    kin = next(c for c in pool if c.id == "physics.kinematics")
    trig10 = next(c for c in pool if c.cls == 10 and "trigonometry" in c.id)
    ratio7 = next(c for c in pool if c.cls == 7 and c.subject == "Mathematics")
    return syl, target, kin, trig10, ratio7


def test_the_pool_reaches_back_into_school_and_stays_on_subject(jee_rotation):
    syl, target, *_ = jee_rotation
    pool = gaps.candidates(syl, target)
    assert target not in pool
    assert {c.subject for c in pool} <= {"Physics", "Mathematics", "Science"}  # never English or History
    assert min(c.cls for c in pool) <= 7 and any(c.cls == 10 for c in pool)


def test_trace_diagnose_fix(client, auth, monkeypatch, jee_rotation):
    syl, target, kin, trig10, ratio7 = jee_rotation
    calls = []

    def fake_json(messages, **kw):
        calls.append(kw.get("feature"))
        if kw.get("feature") == "gap_lesson":
            return {"lesson_md": "Ratios are fractions: $3:4 = 3/4$.\n\nHow this unlocks torque: ...", "check": _q(2)}
        return {"chain": [
            {"chapter_id": kin.id, "idea": "angular velocity", "why": "used directly", "check": _q(1)},
            {"chapter_id": "physics.made-up-chapter", "idea": "invented", "why": "x", "check": _q()},  # not a real chapter
            {"chapter_id": trig10.id, "idea": "sin and cos", "why": "components", "check": {"q": "broken", "options": ["a"]}},  # bad question
            {"chapter_id": trig10.id, "idea": "sin and cos of an angle", "why": "components", "check": _q(0)},
            {"chapter_id": ratio7.id, "idea": "ratios as fractions", "why": "trig ratios are ratios", "check": _q(3)},
        ]}

    monkeypatch.setattr(gaps.llm, "json", fake_json)
    monkeypatch.setattr(syllabus, "of", lambda user, whole=False: syl)

    t = client.post("/api/gaps", headers=auth, json={"chapter_id": target.id})
    assert t.status_code == 200, t.text
    trace = t.json()
    # only real chapters with sound questions, going down through the classes
    assert [link["chapter_id"] for link in trace["chain"]] == [kin.id, trig10.id, ratio7.id]
    assert all("answer" not in link["check"] for link in trace["chain"])  # answers stay on the server

    # right on kinematics, wrong on trig, wrong on ratios: the root is the deepest miss (Class 7 ratios)
    done = client.post(f"/api/gaps/{trace['id']}/answers", headers=auth, json={"answers": [1, 2, 0]}).json()
    assert done["status"] == "found" and done["root"] == 2
    assert done["chain"][2]["check"]["answer"] == 3  # revealed once answered
    assert client.post(f"/api/gaps/{trace['id']}/answers", headers=auth, json={"answers": [1, 1, 3]}).status_code == 400

    fix = client.post(f"/api/gaps/{trace['id']}/lesson", headers=auth).json()
    assert "How this unlocks" in fix["lesson"]["md"] and "answer" not in fix["lesson"]["check"]
    wrong = client.post(f"/api/gaps/{trace['id']}/check", headers=auth, json={"choice": 0}).json()
    assert wrong["status"] == "found" and wrong["lesson"]["result"] == "wrong"
    assert "answer" not in wrong["lesson"]["check"]  # "not yet": the next try is a real one, not a copy of the answer
    fixed = client.post(f"/api/gaps/{trace['id']}/check", headers=auth, json={"choice": 2}).json()
    assert fixed["status"] == "fixed" and fixed["lesson"]["check"]["answer"] == 2
    assert client.post(f"/api/gaps/{trace['id']}/check", headers=auth, json={"choice": 1}).status_code == 400  # stays closed
    assert calls == ["gap_trace", "gap_lesson"]

    # the next student who traces the same chapter, and has the same gap, costs no AI at all
    other = client.post("/api/auth/register", json={"accepted_terms": True, "email": "second.tracer@example.com", "full_name": "Second Tracer",
                                                     "password": "correct-horse-1", "exam_target": "jee"}).json()
    h2 = {"Authorization": f"Bearer {other['access_token']}"}
    t2 = client.post("/api/gaps", headers=h2, json={"chapter_id": target.id}).json()
    client.post(f"/api/gaps/{t2['id']}/answers", headers=h2, json={"answers": [1, 0, 0]})
    assert client.post(f"/api/gaps/{t2['id']}/lesson", headers=h2).json()["lesson"]["md"].startswith("Ratios")
    assert calls == ["gap_trace", "gap_lesson"]
    # and one student never sees another's trace
    assert client.get(f"/api/gaps/{trace['id']}", headers=h2).status_code == 400


def test_all_right_means_the_foundations_hold(client, monkeypatch, jee_rotation):
    syl, target, kin, trig10, _ = jee_rotation
    monkeypatch.setattr(gaps.llm, "json", lambda messages, **kw: {"chain": [
        {"chapter_id": kin.id, "idea": "angular velocity", "why": "", "check": _q(1)},
        {"chapter_id": trig10.id, "idea": "sin and cos", "why": "", "check": _q(0)}]})
    monkeypatch.setattr(syllabus, "of", lambda user, whole=False: syl)
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": "solid.base@example.com", "full_name": "Solid Base",
                                                 "password": "correct-horse-1", "exam_target": "jee"}).json()
    h = {"Authorization": f"Bearer {r['access_token']}"}
    from app.core.database import SessionLocal
    from app.models.gap import PrereqMap
    with SessionLocal() as db:  # a fresh chain for this test (the one above is shared and cached)
        db.query(PrereqMap).delete()
        db.commit()
    t = client.post("/api/gaps", headers=h, json={"chapter_id": target.id}).json()
    out = client.post(f"/api/gaps/{t['id']}/answers", headers=h, json={"answers": [1, 0]}).json()
    assert out["status"] == "clear" and out["root"] is None
    assert client.post(f"/api/gaps/{t['id']}/lesson", headers=h).status_code == 400  # nothing to fix


def _bank(n, chapter="Rotational Motion"):
    from app.core.database import SessionLocal
    from app.models.mock import BankQuestion

    with SessionLocal() as db:
        db.add_all([BankQuestion(exam="jee_main", subject="Physics", chapter=chapter, qtype="mcq", question=f"Bank question {i} on {chapter}?",
                                 options=["w", "x", "y", "z"], answer=str(i % 4), solution="worked", verified=True, source="seed",
                                 fingerprint=f"retest-{chapter}-{i}") for i in range(n)])
        db.commit()


def _retest_answers(trace_id, phase):
    from app.core.database import SessionLocal
    from app.models.gap import GapTrace

    with SessionLocal() as db:
        return [item["answer"] for item in db.get(GapTrace, trace_id).retest[phase]["items"]]


def test_the_stuck_topic_before_and_after_the_fix(client, auth, monkeypatch, jee_rotation):
    """Three bank questions on the stuck topic before the trace, three others after the fix: did fixing the root help?
    No AI for these (the question bank), the answers stay on the server until given, and the "after" stays hidden
    until the root is fixed."""
    syl, target, kin, trig10, ratio7 = jee_rotation
    _bank(8)

    def fake_json(messages, **kw):
        if kw.get("feature") == "gap_lesson":
            return {"lesson_md": "Sine is opposite over hypotenuse.", "check": _q(2)}
        return {"chain": [{"chapter_id": kin.id, "idea": "angular velocity", "why": "used directly", "check": _q(1)},
                          {"chapter_id": trig10.id, "idea": "sin and cos", "why": "components", "check": _q(0)}]}

    monkeypatch.setattr(gaps.llm, "json", fake_json)
    monkeypatch.setattr(syllabus, "of", lambda user, whole=False: syl)
    trace = client.post("/api/gaps", headers=auth, json={"chapter_id": target.id}).json()
    before = trace["retest"]["before"]
    assert before["total"] == 3 and all("answer" not in item for item in before["items"]) and before["right"] is None
    assert trace["retest"]["after"] == {"items": [], "choices": None, "right": None, "total": 3}  # hidden until fixed

    keys = _retest_answers(trace["id"], "before")
    picks = [keys[0], (keys[1] + 1) % 4, None]  # one right, one wrong, one skipped
    done = client.post(f"/api/gaps/{trace['id']}/answers", headers=auth, json={"answers": [1, 1], "before": picks}).json()
    assert done["status"] == "found" and done["retest"]["before"]["right"] == 1 and "answer" in done["retest"]["before"]["items"][0]
    assert client.post(f"/api/gaps/{trace['id']}/after", headers=auth, json={"answers": [0, 0, 0]}).status_code == 400  # not fixed yet

    client.post(f"/api/gaps/{trace['id']}/lesson", headers=auth)
    fixed = client.post(f"/api/gaps/{trace['id']}/check", headers=auth, json={"choice": 2}).json()
    assert fixed["status"] == "fixed" and len(fixed["retest"]["after"]["items"]) == 3
    assert all("answer" not in item for item in fixed["retest"]["after"]["items"])
    after = client.post(f"/api/gaps/{trace['id']}/after", headers=auth, json={"answers": _retest_answers(trace["id"], "after")}).json()
    assert after["retest"]["before"]["right"] == 1 and after["retest"]["after"]["right"] == 3
    assert client.post(f"/api/gaps/{trace['id']}/after", headers=auth, json={"answers": [0, 0, 0]}).status_code == 400  # once

    from app.core.database import SessionLocal
    from app.models.gap import GapTrace

    with SessionLocal() as db:
        numbers = gaps.summarize([db.get(GapTrace, trace["id"])], started=1, chains=1, usd=0.0)
    assert (numbers["retest_pairs"], numbers["retest_before"], numbers["retest_after"]) == (1, 33, 100)


def test_a_short_bank_means_no_before_and_after_but_the_trace_works(client, auth, monkeypatch, jee_rotation):
    syl, target, kin, *_ = jee_rotation
    monkeypatch.setattr(gaps.llm, "json", lambda messages, **kw: {"chain": [{"chapter_id": kin.id, "idea": "v", "why": "w", "check": _q(1)}]})
    monkeypatch.setattr(syllabus, "of", lambda user, whole=False: syl)
    monkeypatch.setattr(gaps.question_bank, "pick", lambda *a, **k: ([], {}))
    trace = client.post("/api/gaps", headers=auth, json={"chapter_id": target.id}).json()
    assert trace["retest"] is None
    answered = client.post(f"/api/gaps/{trace['id']}/answers", headers=auth, json={"answers": [1] * len(trace["chain"])}).json()
    assert answered["status"] in ("found", "clear") and answered["retest"] is None  # (the chain may be shared from before)
