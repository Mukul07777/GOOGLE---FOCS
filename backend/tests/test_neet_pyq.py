"""NEET papers and chapter tests from the bank, exam-aware picking, and the PYQ importer's parsing."""
import importlib.util
from pathlib import Path

import pytest

from app.core.database import SessionLocal
from app.models.mock import BankQuestion
from app.services import mock_patterns as mp
from app.services import question_bank

IMPORTER = Path(__file__).parents[1] / "scripts" / "import_pyq.py"


def _importer():
    spec = importlib.util.spec_from_file_location("import_pyq", IMPORTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _student(client, email, exam):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Bank Student", "password": "correct-horse-1",
                                                "exam_target": exam})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _fill(subject: str, chapters, per_chapter: int, exam: str, tag: str, paper: str | None = None):
    with SessionLocal() as db:
        for c in chapters:
            for i in range(per_chapter):
                text = f"{tag} {subject} {c} question {i}: which option is right?"
                db.add(BankQuestion(exam=exam, subject=subject, chapter=c, qtype="mcq", question=text,
                                    options=["one", "two", "three", "four"], answer="1", solution="Because.", verified=True,
                                    source="pyq" if paper else "ai", paper=paper, year=2021 if paper else None,
                                    fingerprint=question_bank.fingerprint(text)))
        db.commit()


@pytest.fixture(scope="module")
def neet_bank(client):
    """Enough NEET questions for a full 180-question paper (Physics and Chemistry from NEET PYQs, Biology too)."""
    _fill("Physics", mp.SYLLABUS["Physics"], 3, "neet", "neetbank", "NEET 2021")
    _fill("Chemistry", mp.SYLLABUS["Chemistry"], 3, "neet", "neetbank", "NEET 2021")
    _fill("Biology", mp.SYLLABUS["Biology"], 6, "neet", "neetbank", "NEET 2022")
    _fill("Physics", mp.SYLLABUS["Physics"], 3, "jee_main", "jeebank")  # JEE questions the NEET paper should skip


def test_neet_students_get_the_neet_paper_and_biology(client, neet_bank):
    h = _student(client, "neet.paper@example.com", "neet")
    meta = client.get("/api/mock/meta", headers=h).json()
    assert meta["exam"] == "neet" and [p["id"] for p in meta["patterns"]] == ["neet_180"] and meta["default"] == "neet_180"
    assert set(meta["syllabus"]) == {"Physics", "Chemistry", "Biology"} and "Human Reproduction" in meta["syllabus"]["Biology"]
    jee = client.get("/api/mock/meta", headers=_student(client, "jee.paper@example.com", "jee")).json()
    assert {p["id"] for p in jee["patterns"]} == {"jee_main_30", "jee_main_25", "jee_advanced"} and "Biology" not in jee["syllabus"]

    test = client.post("/api/mock", headers=h, json={"pattern": "neet_180"}).json()
    assert test["status"] == "ready", test
    detail = client.post(f"/api/mock/{test['id']}/start", headers=h).json()
    questions = detail["questions"]
    assert len(questions) == 180 and detail["pattern_info"]["duration_min"] == 200
    by_subject = {s: [q for q in questions if q["subject"] == s] for s in ("Physics", "Chemistry", "Botany", "Zoology")}
    assert all(len(v) == 45 for v in by_subject.values())
    with SessionLocal() as db:
        rows = {q.id: q for q in db.query(BankQuestion).filter(BankQuestion.id.in_([q["id"] for q in questions]))}
    assert all(rows[q["id"]].chapter in mp.ZOOLOGY for q in by_subject["Zoology"])
    assert all(rows[q["id"]].chapter in mp.BOTANY for q in by_subject["Botany"])
    assert all(rows[q["id"]].exam == "neet" for q in by_subject["Physics"])  # NEET past questions before JEE ones
    assert all(q["paper"] for q in by_subject["Botany"])  # PYQs carry their paper ("NEET 2022")


def test_neet_chapter_test_on_biology_is_all_mcq(client, neet_bank):
    h = _student(client, "neet.chapter@example.com", "neet")
    t = client.post("/api/mock", headers=h, json={"pattern": "chapter", "subject": "Biology",
                                                  "chapters": ["Evolution", "Ecosystem"], "count": 10}).json()
    assert t["status"] == "ready", t
    detail = client.post(f"/api/mock/{t['id']}/start", headers=h).json()
    assert len(detail["questions"]) == 10 and {q["qtype"] for q in detail["questions"]} == {"mcq"}
    assert detail["pattern_info"]["exam"] == "neet"


# ---------------------------------------------------------------- importer parsing
@pytest.mark.parametrize("tag,expected", [
    ("[JEE (Mains) Online-2014]", ("jee_main", 2014, "JEE Main 2014 (Online)")),
    ("[AIEEE-2010]", ("jee_main", 2010, "AIEEE 2010")),
    ("[JEE(Main)-2019]", ("jee_main", 2019, "JEE Main 2019")),
    ("[JEE Advanced 2020]", ("jee_advanced", 2020, "JEE Advanced 2020")),
    ("[IIT-JEE 2009]", ("jee_advanced", 2009, "IIT-JEE 2009")),
    ("[NEET(UG) 2021]", ("neet", 2021, "NEET 2021")),
    ("[AIPMT 2014]", ("neet", 2014, "AIPMT 2014")),
    ("[AIIMS 2018]", ("neet", 2018, "AIIMS 2018")),
    ("Exercise O-1", None),
    (None, None),
])
def test_exam_tags(tag, expected):
    assert _importer().parse_tag(tag) == expected


def test_headers_keys_and_chapters():
    imp = _importer()
    assert imp._generic("JEE- Mathematics") and imp._generic("Pre-Medical") and not imp._generic("Chemistry : Atomic Structure")
    assert imp._norm_key("(D)") == "4" and imp._norm_key("7") == "7" and imp._norm_key("A,C") == "A,C"
    maths = list(mp.SYLLABUS["Mathematics"])
    assert imp.chapter_from_heading("Limit, Continuity, Differentiability", maths) == "Limits, Continuity & Differentiability"
    assert imp.chapter_from_heading("JEE- Mathematics", maths) is None
    assert imp._official_exam(Path("JEE Main 2024 27 Jan Shift 1.pdf")) == ("jee_main", 2024, "JEE Main 2024 (27 Jan Shift 1)")


def test_open_sets_and_paper_headings():
    imp = _importer()
    assert imp.subject_in("ZOOLOGY") == "Biology" and imp.subject_in("Allen PHYSICS Neet Module") == "Physics"
    assert imp.subject_in("NEET 2020") is None  # a paper of several subjects: its headings decide
    table = imp.md_tables("Truth table:\n" + r"\begin{tabular}{|c|c|}" + "\n" + r"\hline" + "\n" + r"$A$ & $Y$ \\" + "\n"
                          + r"\hline" + "\n" + r"0 & 1 \\" + "\n" + r"1 & 0 \\" + "\n" + r"\hline" + "\n" + r"\end{tabular}")
    assert table == "Truth table:\n\n| $A$ | $Y$ |\n|---|---|\n| 0 | 1 |\n| 1 | 0 |"

    spec = importlib.util.spec_from_file_location("import_open_banks", IMPORTER.parent / "import_open_banks.py")
    ob = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ob)
    stem, options = ob._split_options("The order is\n\n(A) $x<y$\n\n(B) $y<x$\n\n(C) equal\n\n(D) (none) of these")
    assert stem == "The order is" and options == ["$x<y$", "$y<x$", "equal", "(none) of these"]
    assert ob._split_options("No options here (A) only one") is None
