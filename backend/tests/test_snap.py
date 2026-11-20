"""Ask with a photo: a snapped question solved, a handwritten answer marked."""
from app.services import vision
from tests.conftest import board_png

PHOTO = {"files": ("q.png", board_png(["Find the area of a circle", "of radius 7 cm"]), "image/png")}


def _student(client, email, exam="cbse_12"):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Snap Student", "password": "correct-horse-1", "exam_target": exam})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_without_a_model_that_sees_it_says_so(client):
    h = _student(client, "snap.none@example.com")
    for path in ("/api/snap/doubt", "/api/snap/answer"):
        r = client.post(path, headers=h, files=PHOTO)
        assert r.status_code == 503 and "isn't set up" in r.json()["detail"]
    assert client.post("/api/snap/doubt", headers=h, files={"files": ("a.txt", b"hello", "text/plain")}).status_code == 415
    assert client.post("/api/snap/doubt", headers=h, files={"files": ("a.png", b"not an image", "image/png")}).status_code == 400


def test_a_snapped_question_is_solved_and_kept(client, monkeypatch):
    h = _student(client, "snap.solve@example.com")
    seen = {}

    def read(images, prompt, feature, max_tokens=3000):
        seen.update(prompt=prompt, pages=len(images), feature=feature)
        return {"readable": True, "question": "Find the area of a circle of radius 7 cm.", "subject": "Mathematics", "topic": "Mensuration",
                "idea": "Area is pi r squared.", "steps": ["$A = pi r^2$", "$A = 22/7 times 49 = 154$"], "answer": "154 cm^2", "watch_out": None}

    monkeypatch.setattr(vision, "available", lambda: True)
    monkeypatch.setattr(vision, "read_json", read)
    out = client.post("/api/snap/doubt", headers=h, files=PHOTO, data={"note": "use 22/7"}).json()
    assert out["answer"] == "154 cm^2" and len(out["steps"]) == 2 and out["subject"] == "Mathematics" and out["id"]
    assert "CBSE Class 12 student" in seen["prompt"] and "use 22/7" in seen["prompt"] and seen["pages"] == 1
    history = client.get("/api/companion/history", headers=h).json()
    assert history[0]["question"].startswith("Find the area") and "**Answer:** 154" in history[0]["answer"]
    monkeypatch.setattr(vision, "read_json", lambda *a, **k: {"readable": False})
    assert client.post("/api/snap/doubt", headers=h, files=PHOTO).status_code == 422


def test_a_handwritten_answer_is_marked(client, monkeypatch):
    h = _student(client, "snap.mark@example.com", exam="college_me")
    seen = {}

    def read(images, prompt, feature, max_tokens=3000):
        seen["prompt"] = prompt
        return {"readable": True, "question": "State the first law of thermodynamics.", "marks": 3.2, "max_marks": 5,
                "got_right": ["Stated energy conservation."], "lost": [{"where": "sign convention", "why": "Work done by the system taken as negative.", "marks": 2}],
                "model_answer": "$dQ = dU + dW$", "next_time": "State the sign convention."}

    monkeypatch.setattr(vision, "available", lambda: True)
    monkeypatch.setattr(vision, "read_json", read)
    out = client.post("/api/snap/answer", headers=h, files=PHOTO, data={"question": "State the first law.", "max_marks": "5"}).json()
    assert out["marks"] == 3.0 and out["max_marks"] == 5 and out["percent"] == 60 and out["lost"][0]["marks"] == 2
    assert "B.Tech ME examiner" in seen["prompt"] and "out of 5" in seen["prompt"] and "State the first law." in seen["prompt"]
    assert client.get("/api/quiz/redo", headers=h).json() == []  # 60%: not sent back for a redo
    monkeypatch.setattr(vision, "read_json", lambda *a, **k: {"readable": True, "marks": 1, "lost": [], "model_answer": "x"})
    assert client.post("/api/snap/answer", headers=h, files=PHOTO, data={"max_marks": "10"}).json()["percent"] == 10
    assert len(client.get("/api/quiz/redo", headers=h).json()) == 1


def test_a_snapped_solution_is_said_again_in_hindi_once_and_kept(client, monkeypatch):
    """Photo doubts were English only. A Hindi or Hinglish student switches the solution to their language: written
    once (an answer still in English is refused, not shown as Hindi), then kept."""
    from app.services import ai

    h = _student(client, "snap.hindi@example.com")
    monkeypatch.setattr(vision, "available", lambda: True)
    monkeypatch.setattr(vision, "read_json", lambda *a, **k: {
        "readable": True, "question": "Find the area of a circle of radius 7 cm.", "subject": "Mathematics", "topic": "Mensuration",
        "idea": "Area is pi r squared.", "steps": [r"$A = \pi r^2 = 154$"], "answer": "154 cm^2", "watch_out": None})
    doubt = client.post("/api/snap/doubt", headers=h, files=PHOTO).json()["id"]
    calls = []

    def explain(solution, question, language, exam):
        calls.append(language)
        return r"क्षेत्रफल $A = \pi r^2$ से निकलता है, इसलिए उत्तर 154 वर्ग सेमी है।" if language == "hi" else solution

    monkeypatch.setattr(ai, "explain_in", explain)
    url = f"/api/snap/doubt/{doubt}/explain"
    first = client.post(url, headers=h, json={"language": "hi"}).json()
    assert first["language"] == "hi" and "क्षेत्रफल" in first["solution"]
    assert client.post(url, headers=h, json={"language": "hi"}).json() == first and calls == ["hi"]  # kept, no second call
    assert client.post(url, headers=h, json={"language": "hinglish"}).status_code == 503  # came back in English twice
    assert client.post(url, headers=_student(client, "snap.other@example.com"), json={"language": "hi"}).status_code == 404
    assert client.post(url, headers=h, json={"language": "fr"}).status_code == 422
