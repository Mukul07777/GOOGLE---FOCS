"""scripts/evidence.py: real students' aggregates only, small groups hidden, demo/test accounts left out, and silent
tracing run over real weak chapters with no quiz and no AI."""
import importlib.util
from pathlib import Path

from app.core.database import SessionLocal
from app.models.gap import PrereqMap
from app.models.user import User
from app.models.weak import WeakTopic
from app.services import syllabus

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evidence.py"


def _load():
    spec = importlib.util.spec_from_file_location("evidence", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _link(cid, name, cls):
    return {"chapter_id": cid, "name": name, "subject": "Mathematics", "cls": cls, "idea": name, "why": "", "check": {"q": "?", "options": ["a", "b"], "answer": 0}}


def test_the_report_counts_real_students_and_hides_small_groups(client):
    ev = _load()
    a, b = [c.id for c in syllabus.get("jee").chapters[30:32]]
    with SessionLocal() as db:
        db.merge(PrereqMap(key=a, chain=[_link("ev.elec10", "Electricity EV", 10)]))
        db.merge(PrereqMap(key=b, chain=[_link("ev.elec10", "Electricity EV", 10)]))
        made = []
        for i in range(6):  # six real students weak in both chapters, which rest on the same Class 10 chapter
            u = User(email=f"ev.real{i}@school.in", full_name=f"Real {i}", hashed_pw="x", exam_target="jee", role="student")
            db.add(u)
            db.flush()
            made.append(u.id)
            db.add_all([WeakTopic(user_id=u.id, chapter_id=a, misses=2, checks=[]), WeakTopic(user_id=u.id, chapter_id=b, misses=1, checks=[])])
        db.add(User(email="demo.focs.ev@example.com", full_name="Demo", hashed_pw="x", exam_target="jee", role="student"))
        db.add(User(email="ev.mentor@school.in", full_name="Mentor", hashed_pw="x", exam_target="jee", role="mentor"))
        db.commit()
        lines, data = ev.report(db)
    text = "\n".join(lines)
    assert data["students"]["total"] >= 6 and "demo.focs" not in text and "@" not in text  # no addresses, ever
    assert data["silent_tracing"]["students_with_suspect"] >= 6
    assert any(name == "Electricity EV" and n >= 6 for name, _, n in data["silent_tracing"]["top_roots"])
    assert "Electricity EV (Class 10): " in text
    with SessionLocal() as db:  # five is the floor: below it, the root isn't named
        for uid in made[:2]:
            db.query(WeakTopic).filter(WeakTopic.user_id == uid).delete()
        db.commit()
        _, data = ev.report(db)
    assert all(name != "Electricity EV" for name, _, _ in data["silent_tracing"]["top_roots"])
    with SessionLocal() as db:  # the shared test database keeps no chain of ours
        db.query(PrereqMap).filter(PrereqMap.key.in_([a, b])).delete()
        db.commit()
