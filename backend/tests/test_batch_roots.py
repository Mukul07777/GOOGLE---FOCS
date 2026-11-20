"""Innovation #2 for teachers: where a batch's trouble really starts. Each student's root-cause traces are added up by
the earlier chapter they led to, so a teacher sees "most of the students stuck on Rotational Motion are missing Class 10
trigonometry", with nobody named."""
from app.core.database import SessionLocal
from app.models.gap import GapTrace
from app.services import gaps


def _user(client, email, name):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": name,
                                                "password": "correct-horse-1", "exam_target": "jee"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]["id"]


def _link(chapter_id, name, cls, idea, result):
    return {"chapter_id": chapter_id, "name": name, "subject": "Mathematics", "cls": cls, "idea": idea, "why": "",
            "check": {"q": "?", "options": ["a", "b"], "answer": 0}, "result": result}


TRIG = ("cbse_10.maths.trigonometry", "Introduction to Trigonometry", 10, "sin, cos and tan of an angle")
RATIOS = ("cbse_7.maths.ratios", "Comparing Quantities", 7, "ratios and proportion")


def _trace(uid, title, root, status="found", deeper_ok=True):
    """A trace whose deepest wrong link is ``root`` (None: every link right)."""
    chain = [_link(*TRIG[:3], TRIG[3], "wrong" if root == TRIG else "right"),
             _link(*RATIOS[:3], RATIOS[3], "wrong" if root == RATIOS else "right")]
    index = None if root is None else (0 if root == TRIG else 1)
    return GapTrace(user_id=uid, chapter_id="jee.physics.rotational-motion", title=title, chain=chain, root=index,
                    status=status if root else "clear")


def test_a_teacher_sees_where_the_batch_gaps_start(client):
    teacher, _ = _user(client, "roots.teacher@example.com", "Meera Rao")
    room = client.post("/api/classes", headers=teacher, json={"name": "JEE 2027 batch A"}).json()
    code, class_id = room["code"], room["id"]
    ids = []
    for i in range(5):
        h, uid = _user(client, f"roots.student{i}@example.com", f"Student {i}")
        assert client.post("/api/classes/join", headers=h, json={"code": code}).status_code == 200
        ids.append(uid)
    outsider_h, outsider = _user(client, "roots.outsider@example.com", "Not In Class")
    with SessionLocal() as db:
        db.add_all([
            _trace(ids[0], "Rotational Motion", TRIG),
            _trace(ids[1], "Rotational Motion", TRIG, status="fixed"),
            _trace(ids[2], "Projectile Motion", TRIG),
            _trace(ids[2], "Rotational Motion", TRIG),  # the same student twice counts once
            _trace(ids[3], "Laws of Motion", RATIOS),
            _trace(ids[4], "Rotational Motion", None),  # traced, nothing missing
            _trace(outsider, "Rotational Motion", RATIOS),  # not in the class: not counted
            GapTrace(user_id=ids[4], chapter_id="x", title="Still answering", chain=[], status="checking"),
        ])
        db.commit()
    roots = client.get(f"/api/classes/{class_id}", headers=teacher).json()["roots"]
    assert (roots["traced"], roots["with_root"], roots["fixed"]) == (5, 4, 1)
    first, second = roots["roots"]
    assert first["name"] == "Introduction to Trigonometry" and first["cls"] == 10 and first["students"] == 3
    assert first["fixed"] == 1 and first["share"] == 75 and first["idea"] == "sin, cos and tan of an angle"
    assert first["stuck_on"][0] == "Rotational Motion" and "Projectile Motion" in first["stuck_on"]
    assert second["name"] == "Comparing Quantities" and second["students"] == 1 and second["share"] == 25
    keys = {"chapter_id", "name", "subject", "cls", "idea", "students", "fixed", "share", "stuck_on"}
    assert all(set(r) == keys for r in roots["roots"])  # counts and chapters only: no student ids or names
    # only the class's teacher sees it
    assert client.get(f"/api/classes/{class_id}", headers=outsider_h).status_code in (403, 404)


def test_an_empty_class_has_an_empty_map():
    with SessionLocal() as db:
        assert gaps.batch_roots(db, []) == {"traced": 0, "with_root": 0, "fixed": 0, "roots": []}


def test_the_proof_numbers_come_from_real_traces(client):
    """The pitch's numbers are the app's own records: roots found, fixes that held on the re-check, time to fix,
    chains reused for free, and the AI cost per student. Nothing is estimated."""
    from datetime import timedelta

    from app.models._util import utcnow
    from app.models.gap import PrereqMap
    from app.models.llm_call import LlmCall

    _, a = _user(client, "proof.a@example.com", "Proof A")
    _, b = _user(client, "proof.b@example.com", "Proof B")
    start = utcnow() - timedelta(minutes=10)
    with SessionLocal() as db:
        before = gaps.proof(db)
        fixed = _trace(a, "Rotational Motion", TRIG, status="fixed")
        fixed.lesson = {"md": "...", "check": {"q": "?", "options": ["a", "b"], "answer": 0}, "result": "right"}
        fixed.created_at, fixed.updated_at = start, start + timedelta(minutes=6)
        missed = _trace(b, "Laws of Motion", RATIOS)
        missed.lesson = {"md": "...", "check": {"q": "?", "options": ["a", "b"], "answer": 0}, "result": "wrong"}
        db.add_all([fixed, missed, _trace(b, "Projectile Motion", None),
                    PrereqMap(key="proof.test.chain", chain=[]),
                    LlmCall(user_id=a, feature="gap_trace", model="m", cost_usd=0.004),
                    LlmCall(user_id=b, feature="gap_lesson", model="m", cost_usd=0.002),
                    LlmCall(user_id=b, feature="doubt", model="m", cost_usd=1.0)])  # not a gap feature: not counted
        db.commit()
        after = gaps.proof(db)
    assert after["students"] - before["students"] == 2 and after["traces"] - before["traces"] == 3
    assert after["with_root"] - before["with_root"] == 2 and after["fixed"] - before["fixed"] == 1
    assert after["chains_built"] - before["chains_built"] == 1
    assert round(after["ai_usd"] - before["ai_usd"], 4) == 0.006
    # the exact figures, from the same three traces alone: 2 of 3 found a root, 1 of 2 re-checks held, 6 minutes to fix
    exact = gaps.summarize([fixed, missed, _trace(b, "Projectile Motion", None)], started=4, chains=1, usd=0.006)
    assert exact["root_rate"] == 67 and exact["recheck_pass"] == 50 and exact["median_minutes_to_fix"] == 6.0
    assert exact["reused"] == 75 and exact["ai_usd_per_student"] == 0.003  # 4 traces started, 1 chain built
    assert sorted(c["cls"] for c in exact["root_classes"]) == [7, 10]


def test_demo_accounts_never_count_in_the_proof(client):
    """The seeded demo students (scripts/seed_demo.py) are for showing the product, not for the numbers."""
    _, demo = _user(client, "demo.focs.roots@example.com", "Demo Student (Roots)")
    with SessionLocal() as db:
        before = gaps.proof(db)
        db.add(_trace(demo, "Rotational Motion", TRIG, status="fixed"))
        db.commit()
        after = gaps.proof(db)
    assert after == before


def test_teach_first_makes_the_batch_a_recap_from_the_shared_lesson(client, monkeypatch):
    """The class page's "teach first" button: the lesson on the batch's shared gap, in the teacher's language, with its
    check question and answer. A lesson students already got costs nothing; otherwise the AI writes it once."""
    from app.models.gap import PrereqMap

    teacher, _ = _user(client, "recap.teacher@example.com", "Recap Teacher")
    room = client.post("/api/classes", headers=teacher, json={"name": "Recap batch"}).json()
    ids = []
    for i in range(2):
        h, uid = _user(client, f"recap.student{i}@example.com", f"Recap Student {i}")
        client.post("/api/classes/join", headers=h, json={"code": room["code"]})
        ids.append(uid)
    other, _ = _user(client, "recap.other@example.com", "Other Teacher")
    with SessionLocal() as db:
        db.add_all([_trace(ids[0], "Rotational Motion", TRIG), _trace(ids[1], "Rotational Motion", TRIG, status="fixed")])
        key = f"lesson:{TRIG[0]}:{TRIG[3][:80]}:jee.physics.rotational-motion:en"
        db.merge(PrereqMap(key=key, chain={"md": "Sine is opposite over hypotenuse.", "check": {"q": "sin 30°?", "options": ["0.5", "1", "0", "2"], "answer": 0}}))
        db.commit()

    def no_ai(*a, **k):
        raise AssertionError("the lesson students already got should be reused")

    monkeypatch.setattr(gaps.llm, "json", no_ai)
    url = f"/api/classes/{room['id']}/recap"
    made = client.post(url, headers=teacher, json={"chapter_id": TRIG[0]})
    assert made.status_code == 200, made.text
    recap = made.json()
    assert recap["md"].startswith("Sine") and recap["check"]["answer"] == 0 and recap["students"] == 2 and recap["cls"] == 10
    assert client.post(url, headers=teacher, json={"chapter_id": RATIOS[0]}).status_code == 400  # nobody in the class has it
    assert client.post(url, headers=other, json={"chapter_id": TRIG[0]}).status_code in (403, 404)  # only the class's teacher

    # in another language, nobody has it yet: the AI writes it once, then it is kept
    calls = []

    def lesson_ai(messages, **k):
        calls.append(messages[0]["content"])
        return {"lesson_md": "साइन कोण के सामने की भुजा बटा कर्ण है।", "check": {"q": "sin 30°?", "options": ["0.5", "1", "0", "2"], "answer": 0}}

    monkeypatch.setattr(gaps.llm, "json", lesson_ai)
    assert client.patch("/api/auth/me", headers=teacher, json={"language": "hi"}).status_code == 200
    assert client.post(url, headers=teacher, json={"chapter_id": TRIG[0]}).json()["md"].startswith("साइन")
    assert client.post(url, headers=teacher, json={"chapter_id": TRIG[0]}).status_code == 200 and len(calls) == 1
    assert "Devanagari" in calls[0]


def test_the_proof_counts_the_first_re_check_not_a_retry():
    check = {"q": "?", "options": ["a", "b", "c", "d"], "answer": 0}
    retried = _trace(1, "Rotational Motion", TRIG, status="fixed")
    retried.lesson = {"md": "...", "check": check, "result": "right", "first": "wrong"}  # right only on the second try
    first_time = _trace(2, "Laws of Motion", RATIOS, status="fixed")
    first_time.lesson = {"md": "...", "check": check, "result": "right", "first": "right"}
    figures = gaps.summarize([retried, first_time], started=2, chains=1, usd=0.0)
    assert figures["fixed"] == 2 and figures["recheck_pass"] == 50
