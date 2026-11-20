"""The Gap Genome: every shared chain joined into one map of what exam chapters rest on, weighted only by real
students' traces (the seeded demo accounts never count), with nobody named."""
from app.core.database import SessionLocal
from app.models.gap import GapTrace, PrereqMap
from app.services import gaps


def _user(client, email):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Student",
                                                "password": "correct-horse-1", "exam_target": "jee"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]["id"]


def _link(cid, name, cls):
    return {"chapter_id": cid, "name": name, "subject": "Mathematics", "cls": cls, "idea": name, "why": "",
            "check": {"q": "?", "options": ["a", "b"], "answer": 0}}


TRIG = _link("school.trig", "Trigonometry", 10)
RATIO = _link("school.ratio", "Ratios", 7)


def test_the_genome_joins_chains_and_counts_only_real_roots(client):
    h, uid = _user(client, "genome.real@example.com")
    _, demo = _user(client, f"{gaps.DEMO_PREFIX}genome@example.com")
    exam = list(gaps._exam_by_id())[:2]
    with SessionLocal() as db:
        db.merge(PrereqMap(key=exam[0], chain=[TRIG, RATIO]))
        db.merge(PrereqMap(key=exam[1], chain=[RATIO]))
        db.merge(PrereqMap(key=f"lesson:school.ratio:x:{exam[0]}:en", chain=[RATIO]))  # a lesson, not a chain
        for who in (uid, demo):
            db.add(GapTrace(user_id=who, chapter_id=exam[0], title="t", chain=[TRIG, RATIO], root=1, status="fixed"))
        db.commit()

    g = client.get("/api/gaps/genome", headers=h).json()
    nodes = {n["id"]: n for n in g["nodes"]}
    assert nodes["school.ratio"]["underpins"] == 2      # both exam chapters rest on ratios
    assert nodes["school.trig"]["underpins"] == 1
    assert nodes["school.ratio"]["roots"] == 1          # the demo account's trace is left out
    assert nodes["school.ratio"]["fixed"] == 1
    assert g["top"][0]["id"] == "school.ratio"
    assert {(e["from"], e["to"]) for e in g["edges"]} >= {(exam[0], "school.trig"), ("school.trig", "school.ratio"), (exam[1], "school.ratio")}
    assert g["students"] >= 1 and "@" not in str(g)  # counts only: nobody named


def test_the_genome_needs_a_sign_in(client):
    assert client.get("/api/gaps/genome").status_code == 401
