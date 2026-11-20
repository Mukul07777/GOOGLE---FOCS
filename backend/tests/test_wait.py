"""While the AI works, one small task from the student's own material: a due card, else a redo, else a formula."""
from datetime import timedelta


def test_wait_task_prefers_the_topic_and_falls_back_in_order(client):
    from app.core.database import SessionLocal
    from app.models._util import utcnow
    from app.models.flashcard import Flashcard
    from app.models.note import Note
    from app.models.quiz_attempt import QuizAttempt
    from app.models.session import StudySession

    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": "wait.task@example.com", "full_name": "Neha Rao",
                                                 "password": "correct-horse-1", "exam_target": "jee"})
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
    uid = r.json()["user"]["id"]
    assert client.get("/api/wait/task", headers=auth).json() == {"kind": "none"}

    with SessionLocal() as db:
        s = StudySession(user_id=uid, is_active=False, title="Kinematics")
        db.add(s)
        db.flush()
        db.add(Note(session_id=s.id, topic="Projectile motion", subject="Physics",
                    ai_notes="## Projectile motion\n### Formulas\n- $R = \\frac{u^2 \\sin 2\\theta}{g}$"))
        db.commit()
    formula = client.get("/api/wait/task?topic=projectile", headers=auth).json()
    assert formula["kind"] == "formula" and "\\sin 2\\theta" in formula["formula"] and formula["topic"] == "Projectile motion"
    assert client.get(f"/api/wait/task?skip=formula:{formula['id']}", headers=auth).json() == {"kind": "none"}

    with SessionLocal() as db:
        db.add(QuizAttempt(user_id=uid, topic="Optics", question="What is total internal reflection?", correct=False, needs_redo=True))
        db.commit()
    assert client.get("/api/wait/task", headers=auth).json()["kind"] == "redo"

    with SessionLocal() as db:
        db.add_all([
            Flashcard(user_id=uid, front="Unit of torque?", back="N m", topic="Rotation", due_at=utcnow() - timedelta(hours=2)),
            Flashcard(user_id=uid, front="Range formula?", back="u² sin 2θ / g", topic="Projectile motion", due_at=utcnow() - timedelta(hours=1)),
            Flashcard(user_id=uid, front="Not due yet", back="-", topic="Projectile motion", due_at=utcnow() + timedelta(days=3)),
        ])
        db.commit()
    on_topic = client.get("/api/wait/task?topic=Projectile motion", headers=auth).json()
    assert on_topic["kind"] == "card" and on_topic["front"] == "Range formula?"
    oldest = client.get("/api/wait/task", headers=auth).json()
    assert oldest["front"] == "Unit of torque?"  # no topic: the card due longest
    nxt = client.get(f"/api/wait/task?topic=Projectile motion&skip=card:{on_topic['id']}", headers=auth).json()
    assert nxt["kind"] == "card" and nxt["front"] == "Unit of torque?"
