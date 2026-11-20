"""Campus: sharing past papers and notes for a course, college by college."""
import pymupdf

from app.services import vision
from tests.conftest import board_png


def _pdf(pages=2):
    doc = pymupdf.open()
    for n in range(pages):
        doc.new_page().insert_text((72, 72), f"Q{n + 1}. Explain deadlock.")
    return doc.tobytes()


def _student(client, email, exam="college_cse", **extra):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Riya Sharma", "password": "correct-horse-1", "exam_target": exam, **extra})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _share(client, h, **over):
    data = {"kind": "paper", "subject": "Operating Systems", "title": "OS end-sem 2024", "year": "2024", "exam_kind": "end", **over}
    return client.post("/api/campus", headers=h, data=data, files={"file": ("os.pdf", _pdf(), "application/pdf")})


def test_share_browse_open_vote_report_and_remove(client, monkeypatch):
    dtu = _student(client, "campus.dtu@example.com", college="dtu", semester=3)
    mate = _student(client, "campus.mate@example.com", college="dtu", semester=3)
    nsut = _student(client, "campus.nsut@example.com", college="nsut", semester=4)
    assert client.get("/api/campus", headers=_student(client, "campus.jee@example.com", exam="jee")).status_code == 404

    item = _share(client, dtu)
    assert item.status_code == 201 and item.json()["pages"] == 2 and item.json()["by"] == "Riya S." and item.json()["mine"]
    iid = item.json()["id"]
    for bad in ({"subject": "Astrology"}, {"title": "x"}, {"year": "1900"}, {"kind": "video"}):
        assert _share(client, dtu, **bad).status_code == 422, bad
    assert client.post("/api/campus", headers=dtu, data={"kind": "notes", "subject": "Operating Systems", "title": "My notes"},
                       files={"file": ("n.txt", b"hello", "text/plain")}).status_code == 415
    notes = client.post("/api/campus", headers=mate, data={"kind": "notes", "subject": "Operating Systems", "title": "Unit 3 notes", "year": "2024"},
                        files={"file": ("n.png", board_png(["Paging"]), "image/png")}).json()
    assert notes["kind"] == "notes" and notes["year"] is None and notes["pages"] == 1

    seen = client.get("/api/campus", headers=mate).json()  # the same college, a subject of this semester
    assert seen["college"] == "dtu" and [i["title"] for i in seen["items"]] == ["OS end-sem 2024", "Unit 3 notes"] and not seen["items"][0]["mine"]
    assert [i["id"] for i in client.get("/api/campus?kind=notes", headers=mate).json()["items"]] == [notes["id"]]
    assert client.get("/api/campus?subject=Operating Systems", headers=nsut).json()["items"] == []  # another college's shelf
    assert len(client.get("/api/campus?subject=Operating Systems&scope=all", headers=nsut).json()["items"]) == 2

    got = client.get(f"/api/campus/{iid}/file", headers=mate)
    assert got.status_code == 200 and got.headers["content-type"] == "application/pdf" and got.content[:4] == b"%PDF"
    for n, status in ((1, 200), (2, 200), (3, 404), (0, 404)):  # page by page, as pictures
        shown = client.get(f"/api/campus/{iid}/page/{n}", headers=mate)
        assert shown.status_code == status and (status != 200 or shown.content[:3] == b"\xff\xd8\xff"), n
    assert client.get(f"/api/campus/{notes['id']}/page/1", headers=mate).headers["content-type"] == "image/jpeg"
    assert client.post(f"/api/campus/{iid}/vote", headers=mate).json() == {"votes": 1, "voted": True}
    assert client.post(f"/api/campus/{iid}/vote", headers=mate).json() == {"votes": 0, "voted": False}

    # a paper's questions are read once and then kept
    assert client.post(f"/api/campus/{notes['id']}/questions", headers=mate).status_code == 422
    assert client.post(f"/api/campus/{iid}/questions", headers=mate).status_code == 503  # no model that sees, in tests
    calls = []
    monkeypatch.setattr(vision, "available", lambda: True)
    monkeypatch.setattr(vision, "read_json", lambda pages, prompt, feature, max_tokens=3000: calls.append(len(pages)) or {
        "questions": [{"no": "1", "text": "Explain the four conditions for deadlock.", "marks": 5}, {"no": "2", "text": "x"}]})
    read = client.post(f"/api/campus/{iid}/questions", headers=mate).json()
    assert read["questions"] == [{"no": "1", "text": "Explain the four conditions for deadlock.", "marks": 5.0}]
    assert client.post(f"/api/campus/{iid}/questions", headers=nsut).json()["questions"] == read["questions"] and calls == [2]

    assert client.delete(f"/api/campus/{iid}", headers=mate).status_code == 404  # not theirs
    client.post(f"/api/campus/{notes['id']}/report", headers=dtu)
    assert len(client.get("/api/campus", headers=dtu).json()["items"]) == 2  # one report isn't enough
    client.post(f"/api/campus/{notes['id']}/report", headers=nsut)
    assert [i["id"] for i in client.get("/api/campus", headers=dtu).json()["items"]] == [iid]
    assert client.delete(f"/api/campus/{iid}", headers=dtu).status_code == 204
    assert client.get(f"/api/campus/{iid}/file", headers=dtu).status_code == 404
