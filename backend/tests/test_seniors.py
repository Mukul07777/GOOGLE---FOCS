"""Ask a senior: juniors ask about a course, verified students who have done it answer, check Focs's AI drafts and
leave tips; aspirants ask B.Tech students; the bell tells each side."""
from datetime import timedelta


def _student(client, email, semester, exam="college_cse", name="College Student", college="iitd"):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": name, "password": "correct-horse-1",
                                                 "exam_target": exam, "college": college, "semester": semester})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _verify(client, h, email):
    r = client.post("/api/campus/ask/verify/start", headers=h, json={"email": email})
    assert r.status_code == 200, r.text
    code = r.json()["dev_code"]  # no email server in tests: development shows the code
    r = client.post("/api/campus/ask/verify/confirm", headers=h, json={"code": code})
    assert r.status_code == 200 and r.json()["verified"], r.text


def test_juniors_ask_seniors_answer(client):
    junior = _student(client, "junior@example.com", 3, name="Kabir Mehta")
    senior = _student(client, "senior@example.com", 5, name="Nisha Rao")
    third = _student(client, "third@example.com", 5)

    board = client.get("/api/campus/ask", headers=junior).json()
    subject, chapter = board["subject"], board["chapters"][0]
    assert board["senior"] is None and board["questions"] == [] and board["waiting"] == []
    assert board["verification"]["needed"] and board["verification"]["domains"] == ["@iitd.ac.in", "@iitd.ernet.in"]

    # in semester 5, but not a senior until the college email is confirmed
    assert client.get(f"/api/campus/ask?subject={subject}", headers=senior).json()["senior"] is None
    _verify(client, senior, "nisha.rao@iitd.ac.in")

    q = client.post("/api/campus/ask", headers=junior, json={"subject": subject, "chapter": chapter,
                                                             "body": "Which units matter most for the end-sem?"})
    assert q.status_code == 201 and q.json()["chapter"] == chapter and q.json()["senior"] is None
    qid = q.json()["id"]
    tip = {"subject": subject, "kind": "tip", "body": "Solve the last five years' papers: half the questions repeat."}
    assert client.post("/api/campus/ask", headers=junior, json=tip).status_code == 403  # not done it yet
    assert client.post("/api/campus/ask", headers=junior, json={"subject": "Astrology", "body": "Is this a real course?"}).status_code == 422

    # the senior did this course in semester 3: the question waits for them, and the bell says so
    seen = client.get(f"/api/campus/ask?subject={subject}", headers=senior).json()
    assert seen["senior"] == "Did it in Sem 3 · verified"
    assert [w["id"] for w in seen["waiting"]] == [qid] and seen["waiting"][0]["by"] == "Kabir M."
    bell = client.get("/api/notifications", headers=senior).json()
    assert bell["unread"] == 1 and bell["items"][0]["kind"] == "asked" and "Which units" in bell["items"][0]["text"]
    assert client.post("/api/notifications/read", headers=senior).status_code == 204
    assert client.get("/api/notifications", headers=senior).json()["unread"] == 0
    assert client.get("/api/notifications", headers=third).json()["unread"] == 0  # not verified: not told

    a = client.post(f"/api/campus/ask/{qid}/answers", headers=senior, json={"body": "Units 2 and 4. Practise the numericals."})
    assert a.status_code == 201 and a.json()["senior"] == "Did it in Sem 3 · verified"
    assert client.get("/api/notifications", headers=junior).json()["items"][0]["text"].startswith("A senior answered")
    assert client.post("/api/campus/ask", headers=senior, json=tip).json()["kind"] == "tip"
    assert client.get("/api/campus/ask", headers=senior).json()["waiting"] == []  # answered: off the list

    board = client.get(f"/api/campus/ask?subject={subject}", headers=junior).json()
    asked = board["questions"][0]
    reply = asked["answers"][0]
    assert asked["mine"] and reply["body"].startswith("Units 2") and reply["by"] == "Nisha R."
    assert board["tips"][0]["senior"] == "Did it in Sem 3 · verified"

    # the asker marks the answer that settled it: it counts for the senior
    assert client.post(f"/api/campus/ask/{reply['id']}/accept", headers=third).status_code == 403
    assert client.post(f"/api/campus/ask/{reply['id']}/accept", headers=junior).json() == {"accepted": True}
    again = client.get(f"/api/campus/ask?subject={subject}", headers=junior).json()["questions"][0]["answers"][0]
    assert again["accepted"] and again["helped"] == 1
    assert client.get("/api/notifications", headers=senior).json()["items"][0]["kind"] == "accepted"
    lb = client.get("/api/leaderboard?scope=everyone", headers=senior).json()
    assert lb["me"]["helped"] == 1 and lb["me"]["xp"] >= 25

    assert client.post(f"/api/campus/ask/{reply['id']}/vote", headers=junior).json() == {"votes": 1, "voted": True}
    assert client.post(f"/api/campus/ask/{reply['id']}/vote", headers=junior).json()["voted"] is False
    tip_id = board["tips"][0]["id"]
    for h in (junior, third):  # two reports hide a post
        assert client.post(f"/api/campus/ask/{tip_id}/report", headers=h).status_code == 204
    assert client.get(f"/api/campus/ask?subject={subject}", headers=junior).json()["tips"] == []

    assert client.delete(f"/api/campus/ask/{qid}", headers=senior).status_code == 404  # not theirs
    assert client.delete(f"/api/campus/ask/{qid}", headers=junior).status_code == 204
    assert client.get(f"/api/campus/ask?subject={subject}", headers=junior).json()["questions"] == []


def test_verification_rules(client):
    from app.core.database import SessionLocal
    from app.models.user import User

    h = _student(client, "verify.rules@example.com", 3, name="Ira Sen")
    bad = client.post("/api/campus/ask/verify/start", headers=h, json={"email": "ira@gmail.com"})
    assert bad.status_code == 422 and "@iitd.ac.in" in bad.json()["detail"]
    assert client.post("/api/campus/ask/verify/start", headers=h, json={"email": "ira@cse.iitd.ac.in"}).status_code == 200  # a subdomain
    assert client.post("/api/campus/ask/verify/confirm", headers=h, json={"code": "000000"}).status_code in (200, 400)
    other = _student(client, "verify.other@example.com", 3, college="other")
    assert client.post("/api/campus/ask/verify/start", headers=other, json={"email": "me@example.com"}).status_code == 422
    assert client.post("/api/campus/ask/verify/start", headers=other, json={"email": "me@abc.ac.in"}).status_code == 200

    # seniority follows time since the check, not the semester a student types in later
    _verify(client, h, "ira.sen@iitd.ac.in")
    client.patch("/api/auth/me", headers=h, json={"semester": 8})
    board = client.get("/api/campus/ask", headers=h).json()
    assert board["done"] and all(c in client.get("/api/campus/ask", headers=h).json()["catalogue"] for c in board["done"])
    sem5 = [c for c in board["catalogue"] if client.get(f"/api/campus/ask?subject={c}", headers=h).json()["senior"]]
    assert all("Sem 1" in client.get(f"/api/campus/ask?subject={c}", headers=h).json()["senior"]
               or "Sem 2" in client.get(f"/api/campus/ask?subject={c}", headers=h).json()["senior"] for c in sem5)
    with SessionLocal() as db:  # a year later: two semesters on
        u = db.query(User).filter(User.email == "verify.rules@example.com").one()
        u.college_verified_at = u.college_verified_at - timedelta(days=370)
        db.commit()
    later = client.get("/api/campus/ask", headers=h).json()["done"]
    assert len(later) > len(board["done"])


def test_gate_seniors_need_real_progress_and_aspirants_ask_btech_students(client, monkeypatch):
    from app.core.database import SessionLocal
    from app.models.prep import TopicProgress
    from app.models.user import User
    from app.services import ai, syllabus

    gate = _student(client, "gate.senior@example.com", None, exam="gate_cs")
    board = client.get("/api/campus/ask", headers=gate).json()
    course = board["subject"]
    assert board["senior"] is None  # nothing studied yet
    with SessionLocal() as db:
        uid = db.query(User).filter(User.email == "gate.senior@example.com").one().id
        for ch in syllabus._course_chapters(course, 0)[:1]:
            for t in ch.topics[:3]:
                db.add(TopicProgress(user_id=uid, chapter_id=ch.id, topic_id=t.id))
        db.commit()
    assert client.get(f"/api/campus/ask?subject={course}", headers=gate).json()["senior"] == "GATE aspirant · studied it here"

    # a JEE aspirant gets a shelf of their own subjects, and an AI draft at once
    monkeypatch.setattr(ai, "companion", lambda *a, **k: {"answer": "Revise rotational dynamics from the NCERT first.", "source": "ai"})
    jee = client.post("/api/auth/register", json={"accepted_terms": True, "email": "jee.ask@example.com", "full_name": "Arjun Das", "password": "correct-horse-1",
                                                   "exam_target": "jee"}).json()["access_token"]
    jh = {"Authorization": f"Bearer {jee}"}
    jboard = client.get("/api/campus/ask?subject=Physics", headers=jh).json()
    assert jboard["shelf"] == "school" and jboard["subject"] == "Physics" and jboard["verification"]["needed"] is False
    q = client.post("/api/campus/ask", headers=jh, json={"subject": "Physics", "body": "How did you prepare rotation for JEE?"})
    assert q.status_code == 201 and q.json()["college"] == "jee"
    asked = client.get("/api/campus/ask?subject=Physics", headers=jh).json()["questions"][0]
    draft = asked["answers"][0]
    assert draft["ai"] and draft["by"] == "Focs (AI draft)" and draft["checked"] is None and not draft["mine"]

    # a verified B.Tech student sees it waiting, checks the draft, and the aspirant is told
    btech = _student(client, "btech.helper@example.com", 5, name="Riya Kapoor", college="nsut")
    unverified = _student(client, "btech.unverified@example.com", 5, college="nsut")
    assert all(w["id"] != asked["id"] for w in client.get("/api/campus/ask", headers=unverified).json()["waiting"])
    assert client.post(f"/api/campus/ask/{draft['id']}/check", headers=unverified, json={"verdict": "right"}).status_code == 403
    _verify(client, btech, "riya.k@nsut.ac.in")
    assert asked["id"] in [w["id"] for w in client.get("/api/campus/ask", headers=btech).json()["waiting"]]
    checked = client.post(f"/api/campus/ask/{draft['id']}/check", headers=btech, json={"verdict": "right"}).json()
    assert checked["answers"][0]["checked"] == "Checked by a senior (B.Tech, Sem 5)"
    assert client.get("/api/campus/ask", headers=btech).json()["waiting"] == []  # settled
    assert client.get("/api/notifications", headers=jh).json()["items"][0]["kind"] == "checked"

    # a correction becomes the senior's own answer
    q2 = client.post("/api/campus/ask", headers=jh, json={"subject": "Chemistry", "body": "Is organic or physical chemistry more scoring?"}).json()
    d2 = client.get("/api/campus/ask?subject=Chemistry", headers=jh).json()["questions"][0]["answers"][0]
    assert client.post(f"/api/campus/ask/{d2['id']}/check", headers=btech, json={"verdict": "fix", "correction": "x"}).status_code == 422
    fixed = client.post(f"/api/campus/ask/{d2['id']}/check", headers=btech,
                        json={"verdict": "fix", "correction": "Physical: its numericals are the surest marks."}).json()
    assert fixed["id"] == q2["id"] and fixed["answers"][0]["senior"] == "B.Tech, Sem 5 · verified"
    assert any(a["checked"] == "A senior corrected this: see their answer" for a in fixed["answers"])

    # other exams have no shelf
    cbse = client.post("/api/auth/register", json={"accepted_terms": True, "email": "upsc.ask@example.com", "full_name": "U", "password": "correct-horse-1",
                                                    "exam_target": "jee"}).json()["access_token"]
    client.patch("/api/auth/me", headers={"Authorization": f"Bearer {cbse}"}, json={"exam_target": "upsc"})  # (closed to new sign-ups)
    assert client.get("/api/campus/ask", headers={"Authorization": f"Bearer {cbse}"}).status_code == 404
