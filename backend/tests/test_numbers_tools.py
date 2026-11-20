"""The scripts that produce the pitch numbers: warm_chains (by real attempts, dry run, export/import), bench_working
--init, and evidence's chain coverage and checked-working source split. No real AI."""
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.models.gap import PrereqMap
from app.models.user import User
from app.models.weak import WeakTopic
from app.models.working import WorkingCheck
from app.services import gaps, syllabus, vision
from app.services.real_students import chapter_activity, real_students

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _own_chains():
    with SessionLocal() as db:
        before = set(db.scalars(select(PrereqMap.key)))
    yield
    with SessionLocal() as db:
        db.execute(delete(PrereqMap).where(PrereqMap.key.not_in(before)))
        db.commit()


def _link(cid="n.root", cls=9):
    return {"chapter_id": cid, "name": cid, "subject": "Physics", "cls": cls, "idea": "i", "why": "",
            "check": {"q": "?", "options": ["a", "b"], "answer": 0}}


def _users(db, emails):
    ids = []
    for email in emails:
        u = User(email=email, full_name="N", hashed_pw="x", exam_target="jee", role="student")
        db.add(u)
        db.flush()
        ids.append(u.id)
    return ids


def _png(path):
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buf, format="PNG")
    path.write_bytes(buf.getvalue())


def test_ranking_counts_real_students_only_and_falls_back_to_weight(client):
    wc = _load("warm_chains")
    syl = syllabus.get("jee")
    a, b = syl.chapters[40], syl.chapters[41]
    with SessionLocal() as db:
        real = _users(db, [f"rk.real{i}@school.in" for i in range(2)])
        fake = _users(db, ["demo.focs.rk@school.in", "rk.t@example.com", "rk.t@x.invalid"])
        db.add_all([WeakTopic(user_id=real[0], chapter_id=a.id, misses=2, checks=[]),
                    WeakTopic(user_id=real[1], chapter_id=b.id, misses=1, checks=[])])
        db.add_all([WeakTopic(user_id=f, chapter_id=b.id, misses=50, checks=[]) for f in fake])
        db.commit()
        ids = {u.id for u in real_students(db)}
        assert not (ids & set(fake)) and set(real) <= ids
        act = chapter_activity(db, ids, 60)
        assert act[a.id] >= 2 and act[b.id] < 50  # demo, test and .invalid accounts did not count
        db.execute(delete(WeakTopic).where(WeakTopic.user_id.in_(real + fake)))
        db.commit()
    chosen, fell = wc.choose(syl, {a.id: 5, b.id: 3}, "attempts", 2)
    assert [c.id for c in chosen] == [a.id, b.id] and not fell
    by_weight = [c.id for c in sorted(syl.chapters, key=lambda c: -c.weight)[:2]]
    chosen, fell = wc.choose(syl, {}, "attempts", 2)
    assert fell and [c.id for c in chosen] == by_weight
    chosen, fell = wc.choose(syl, {a.id: 99}, "weight", 2)
    assert not fell and [c.id for c in chosen] == by_weight


def test_dry_run_makes_no_ai_calls_and_builds_nothing(client, monkeypatch, capsys):
    wc = _load("warm_chains")

    def boom(*a, **k):
        raise AssertionError("AI called in a dry run")

    monkeypatch.setattr(gaps, "_ask_chain", boom)
    monkeypatch.setattr(sys, "argv", ["warm_chains.py", "--dry-run", "--top", "3", "--exams", "jee"])
    with SessionLocal() as db:
        before = db.query(PrereqMap).count()
    wc.main()
    out = capsys.readouterr().out
    assert "would build" in out and "dry run: nothing built" in out
    with SessionLocal() as db:
        assert db.query(PrereqMap).count() == before


def test_one_failure_does_not_stop_the_rest_and_export_import_roundtrip(client, monkeypatch, tmp_path, capsys):
    wc = _load("warm_chains")
    calls = []

    def fake(syl, target, topic_name):
        calls.append(target.id)
        if len(calls) == 1:
            raise RuntimeError("no luck")
        return [_link()]

    monkeypatch.setattr(gaps, "_ask_chain", fake)
    out_file = tmp_path / "chains.json"
    monkeypatch.setattr(sys, "argv", ["warm_chains.py", "--exams", "jee", "--top", "2", "--by", "weight",
                                      "--export", str(out_file)])
    wc.main()
    text = capsys.readouterr().out
    assert "FAILED" in text and "built 1" in text and len(calls) == 2
    built = calls[1]
    assert built in json.loads(out_file.read_text(encoding="utf-8"))
    with SessionLocal() as db:
        db.execute(delete(PrereqMap).where(PrereqMap.key == built))
        db.commit()
        added, _ = wc.import_chains(db, out_file)
        assert added >= 1 and db.get(PrereqMap, built).chain == [_link()]
        added2, skipped2 = wc.import_chains(db, out_file)  # already there: skipped
        assert added2 == 0 and skipped2 >= 1
        db.get(PrereqMap, built).chain = [_link("n.other")]
        db.commit()
        wc.import_chains(db, out_file)
        assert db.get(PrereqMap, built).chain[0]["chapter_id"] == "n.other"  # kept
        wc.import_chains(db, out_file, overwrite=True)
        assert db.get(PrereqMap, built).chain[0]["chapter_id"] == "n.root"


def test_bench_init_creates_and_extends_labels(tmp_path):
    bench = _load("bench_working")
    _png(tmp_path / "a.png")
    _png(tmp_path / "b.JPG")
    (tmp_path / "notes.txt").write_text("x")
    assert bench.init_labels(tmp_path) == 2
    lines = (tmp_path / "labels.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("file,question") and lines[1].startswith("a.png,") and len(lines) == 3
    text = (tmp_path / "labels.csv").read_text(encoding="utf-8").replace("a.png,,", 'a.png,"Torque?",', 1)
    (tmp_path / "labels.csv").write_text(text.rstrip("\r\n"), encoding="utf-8")  # no trailing newline
    _png(tmp_path / "c.webp")
    assert bench.init_labels(tmp_path) == 1
    assert bench.init_labels(tmp_path) == 0
    rows = (tmp_path / "labels.csv").read_text(encoding="utf-8").splitlines()
    assert 'a.png,"Torque?"' in "\n".join(rows) and len(rows) == 4  # the existing row is kept


def test_bench_compare_runs_twice_when_a_solution_is_given(tmp_path, monkeypatch):
    bench = _load("bench_working")
    _png(tmp_path / "a.png")
    (tmp_path / "labels.csv").write_text(
        'file,question,options,answer,chosen,first_wrong,kind,solution\na.png,"Q?",,,,2,gap,"x=2"\n', encoding="utf-8")
    answers = iter([{"verdict": "wrong", "first_wrong": 1, "error_type": "concept", "steps": [{"text": "s"}, {"text": "t"}]},
                    {"verdict": "wrong", "first_wrong": 0, "error_type": "concept", "steps": [{"text": "s"}, {"text": "t"}]}])
    monkeypatch.setattr(vision, "available", lambda: True)
    monkeypatch.setattr(vision, "models", lambda: ["m"])
    monkeypatch.setattr(vision, "read_json", lambda *a, **k: next(answers))
    monkeypatch.setattr(sys, "argv", ["bench_working.py", str(tmp_path), "--compare"])
    bench.main()
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "1/1 = 100%" in summary and "0/1 = 0%" in summary and "with, " in summary


def test_evidence_reports_chain_coverage_and_the_source_split_behind_the_floor(client):
    ev = _load("evidence")
    syl = syllabus.get("jee")
    a, b = syl.chapters[50].id, syl.chapters[51].id
    with SessionLocal() as db:
        db.merge(PrereqMap(key=a, chain=[_link()]))
        real = _users(db, [f"ev2.real{i}@school.in" for i in range(8)])
        for i, uid in enumerate(real):
            db.add(WeakTopic(user_id=uid, chapter_id=a, misses=1, checks=[]))
            db.add(WorkingCheck(user_id=uid, chapter_id=b, question="q", verdict="wrong", error_type="sign",
                                result={"source": "photo"} if i < 2 else {}))
        db.commit()
        lines, data = ev.report(db)
        text = "\n".join(lines)
        assert "Chain coverage" in text and data["chain_coverage"]["share_with_chain"]
        split = data["working"]["by_source"]
        assert split["photo"] == "<5"  # two photo checks: under the floor, hidden
        assert isinstance(split["pad"], int) and split["pad"] >= 5
        assert "from a photo of paper" in text
        db.execute(delete(WorkingCheck).where(WorkingCheck.user_id.in_(real)))
        db.execute(delete(WeakTopic).where(WeakTopic.user_id.in_(real)))
        db.commit()
