"""Demo accounts with everything the demo touches made in advance, so a slow AI or a rate limit can't stall it live.

    python scripts/seed_demo.py [--password ...] [--reset]

Runs through the app itself (the real endpoints, in-process) on the database in backend/.env:
  - a JEE student (Hinglish) and a Hindi-medium student, each with a finished live lecture: boards read, notes
    written in their language, revision sheet and flashcards made
  - a teacher's live class with its boards and a confusion map ("I'm lost" taps, wrong answers, doubts)
  - the teacher's batch with root-cause traces: two students stuck on Rotational Motion share the same earlier gap
    (the root-gap map's "teach first"), and the JEE student's five-minute fix (in Hinglish) passed its re-check, taking
    Rotational Motion from 1 of 3 to 3 of 3
  - a mock test for the JEE student that lost marks in Current Electricity, Electrostatics and Magnetic Effects,
    so the Root cause page opens with "Focs noticed": all three rest on Class 10 Electricity
  - a verified B.Tech senior, and an "Ask a senior" question with Focs's draft checked and a senior's answer accepted

Every account is named "Demo …" with a demo.focs.*@example.com address, and every post starts with "[Demo]", so
nobody mistakes them for real students. Run it once with the AI key the demo will use (notes and translations are
written then and kept); --reset deletes the demo accounts and everything in them first.
"""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from demo_metrics import BOARDS, board  # noqa: E402

DOMAIN = "example.com"
ACCOUNTS = {
    "student": {"full_name": "Demo Student (JEE)", "exam_target": "jee", "class_level": "Class 12", "language": "hinglish"},
    "hindi": {"full_name": "Demo Student (Hindi)", "exam_target": "jee", "class_level": "Class 12", "language": "hi"},
    "teacher": {"full_name": "Demo Teacher", "exam_target": "jee", "class_level": "Class 12"},
    "senior": {"full_name": "Demo Senior (B.Tech)", "exam_target": "college_cse", "college": "nsut", "semester": 5},
    "classmate": {"full_name": "Demo Classmate", "exam_target": "jee", "class_level": "Class 12"},
}
LECTURE = "Demo: Newton's laws and energy"
ROOM = "Demo: Work and energy"


def email(key: str) -> str:
    return f"demo.focs.{key}@{DOMAIN}"


def seed(client, password: str, reset: bool = False) -> dict:
    """Create the demo. Returns {key: email} and the room code. Raises if the accounts exist and reset is False."""
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.core import ratelimit
    from app.models._util import utcnow
    from app.models.gap import GapTrace
    from app.models.user import User
    from app.services import account, confusion

    with SessionLocal() as db:
        existing = db.scalars(select(User).where(User.email.in_([email(k) for k in ACCOUNTS]))).all()
        if existing and not reset:
            raise SystemExit("The demo accounts already exist. Run with --reset to delete and recreate them.")
        for user in existing:
            account.delete_everything(db, user)  # their rooms go too (a running server drops them when it next looks)
        db.commit()

    h: dict[str, dict] = {}
    for key, spec in ACCOUNTS.items():
        body = {k: v for k, v in spec.items() if k != "language"}
        r = client.post("/api/auth/register", json={**body, "email": email(key), "password": password, "accepted_terms": True})
        r.raise_for_status()
        h[key] = {"Authorization": f"Bearer {r.json()['access_token']}"}
        if spec.get("language"):
            client.patch("/api/auth/me", headers=h[key], json={"language": spec["language"]}).raise_for_status()

    with SessionLocal() as db:  # Pro, so a judge trying an account doesn't run into the free allowance mid-demo
        for user in db.scalars(select(User).where(User.email.in_([email(k) for k in ACCOUNTS]))):
            user.plan = "pro"
            if user.email == email("senior"):  # the college email check, done for the demo (no inbox to read a code from)
                user.college_email, user.college_verified_at, user.verified_semester = "demo.focs.senior@nsut.ac.in", utcnow() - timedelta(days=1), 5
        db.commit()

    def lecture(who: str, title: str, boards: list[list[str]], room_session: int | None = None) -> int:
        ratelimit.reset()
        sid = room_session or client.post("/api/sessions", headers=h[who], json={"title": title, "subject": "Physics", "source": "screen"}).json()["id"]
        for lines in boards:
            r = client.post(f"/api/capture/{sid}/frame", headers=h[who], files={"frame": ("board.jpg", board(lines), "image/jpeg")},
                            data={"force": "true"})
            r.raise_for_status()
            print(f"  {who}: board '{lines[0]}' -> {r.json()['status']}")
        if room_session is None:
            end = client.post(f"/api/sessions/{sid}/end", headers=h[who]).json()
            print(f"  {who}: lecture ended, revision sheet ({end.get('source')}), {end.get('flashcards_created', 0)} flashcards")
        return sid

    print("Live lectures (notes in each student's language):")
    lecture("student", LECTURE, BOARDS[:3])
    lecture("hindi", LECTURE, BOARDS[:3])

    print("A teacher's live class with its confusion map:")
    room = client.post("/api/rooms", headers=h["teacher"], json={"name": ROOM, "topic": "Work, energy and power", "max_members": 60}).json()
    code = room["code"]
    for key in ("student", "hindi", "classmate"):
        client.post("/api/rooms/join", headers=h[key], json={"code": code}).raise_for_status()
    sid = client.post(f"/api/rooms/{code}/notes/start", headers=h["teacher"]).json()["session_id"]
    lecture("teacher", ROOM, BOARDS[1:4], room_session=sid)
    with SessionLocal() as db:
        boards = confusion.room_boards(db, code)
        ids = {k: db.scalar(select(User.id).where(User.email == email(k))) for k in ACCOUNTS}
    if len(boards) >= 2:
        hard, last = boards[1], boards[-1]
        for i, key in enumerate(("student", "hindi", "classmate", "student", "classmate")):  # the second board lost the room
            confusion.record(code, "lost", user_id=ids[key], t_s=300 + i * 20, note_id=hard.id)
        confusion.record(code, "lost", user_id=ids["hindi"], t_s=520, note_id=last.id)
        confusion.record(code, "quiz", note_id=hard.id, text="[Demo] A force acts perpendicular to the motion. The work it does is…",
                         data={"options": ["Positive", "Negative", "Zero", "Depends on the speed"], "counts": [1, 0, 1, 1],
                               "answer_index": 2, "answered": 3, "correct": 1})
        confusion.record(code, "wrong", user_id=ids["student"], note_id=hard.id, data={"sure": True})
        confusion.record(code, "wrong", user_id=ids["classmate"], note_id=hard.id, data={"sure": False})
        confusion.record(code, "doubt", user_id=ids["hindi"], note_id=hard.id, ref="demo-1",
                         text="[Demo] Why is the work zero when the force is perpendicular?", data={"votes": 3, "resolved": False})
        confusion.record(code, "doubt", user_id=ids["classmate"], note_id=last.id, ref="demo-2",
                         text="[Demo] Is kinetic energy ever negative?", data={"votes": 1, "resolved": True})
    print(f"  room {code}: {len(boards)} boards, confusion map at /app/rooms/{code}/report")

    print("Root-cause traces and a class:")
    ratelimit.reset()
    made = client.post("/api/classes", headers=h["teacher"], json={"name": "Demo: JEE 2027 batch"})
    made.raise_for_status()
    batch = made.json()
    for key in ("student", "hindi", "classmate"):
        client.post("/api/classes/join", headers=h[key], json={"code": batch["code"]}).raise_for_status()
    traced = 0
    # (student, chapter, the check they miss): the two Rotational Motion students miss the same earlier idea (sine and
    # cosine, behind torque = rF sin θ, when the AI's chain has it), so the map says to teach it first
    for key, chapter_id, miss in (("student", "physics.rotational-motion", "trigonometry"), ("classmate", "physics.rotational-motion", "trigonometry"),
                                  ("hindi", "physics.laws-of-motion", "nearest")):
        r = client.post("/api/gaps", headers=h[key], json={"chapter_id": chapter_id})
        if r.status_code != 200:
            print(f"  {key}: no trace ({r.status_code}): tracing a chapter needs the AI once")
            continue
        trace_id = r.json()["id"]
        with SessionLocal() as db:
            made = db.get(GapTrace, trace_id)
            chain, retest = made.chain, made.retest
        wrong = 0 if miss == "nearest" else next((i for i, c in enumerate(chain) if miss in c["name"].lower()), len(chain) - 1)
        picks = [(c["check"]["answer"] + 1) % len(c["check"]["options"]) if i == wrong else c["check"]["answer"]
                 for i, c in enumerate(chain)]
        # the stuck topic itself first: one of three right (the "before" of before-and-after), when the bank had questions
        before = None
        if retest:
            keys = [item["answer"] for item in retest["before"]["items"]]
            before = [k if i == 0 else (k + 1) % 4 for i, k in enumerate(keys)]
        client.post(f"/api/gaps/{trace_id}/answers", headers=h[key], json={"answers": picks, "before": before}).raise_for_status()
        traced += 1
        if key == "student":  # the five-minute fix in their language, and the re-check passed
            if client.post(f"/api/gaps/{trace_id}/lesson", headers=h[key]).status_code == 200:
                with SessionLocal() as db:
                    right = db.get(GapTrace, trace_id).lesson["check"]["answer"]
                client.post(f"/api/gaps/{trace_id}/check", headers=h[key], json={"choice": right}).raise_for_status()
                if retest:  # and the stuck topic again: three of three now
                    after = [item["answer"] for item in retest["after"]["items"]]
                    client.post(f"/api/gaps/{trace_id}/after", headers=h[key], json={"answers": after}).raise_for_status()
    print(f"  class {batch['code']}: 3 students, {traced} traces; the root-gap map at /app/classes/{batch['id']}")

    print("Silent tracing:")
    from datetime import date

    from app.services import gaps as gap_service, syllabus as syl_service, weak as weak_service
    with SessionLocal() as db:  # a mock that lost marks in three chapters which all rest on Class 10 Electricity
        user = db.scalar(select(User).where(User.email == email("student")))
        syl = syl_service.get("jee")
        weak_service.save_test(db, user.id, syl, title="[Demo] Minor Test 3 (Physics)", taken_on=date.today() - timedelta(days=2),
                               score=118, max_score=300, subjects=[{"name": "Physics", "score": 22, "max": 100}], source="manual",
                               weak=[{"chapter_id": "physics.current-electricity", "misses": 4, "note": "Kirchhoff loops and power"},
                                     {"chapter_id": "physics.electrostatics", "misses": 3, "note": "Potential and capacitors"},
                                     {"chapter_id": "physics.magnetic-effects-of-current-and-magnetism", "misses": 2, "note": "Field of a current loop"}])
        sus = gap_service.suspects(db, user.id, syl)
    print("  Focs noticed: " + (f"{', '.join(sus[0]['because'])} all rest on {sus[0]['name']}" if sus
                                else "nothing yet (run scripts/warm_chains.py first, so the chains exist)"))

    print("Ask a senior:")
    ratelimit.reset()
    q = client.post("/api/campus/ask", headers=h["student"],
                    json={"subject": "Physics", "body": "[Demo] How did you revise rotational motion for JEE without getting lost in the formulas?"})
    q.raise_for_status()
    asked = client.get("/api/campus/ask?subject=Physics", headers=h["student"]).json()["questions"][0]
    draft = next((a for a in asked["answers"] if a.get("ai")), None)
    if draft:
        client.post(f"/api/campus/ask/{draft['id']}/check", headers=h["senior"], json={"verdict": "right"}).raise_for_status()
        print("  Focs's AI draft: checked by the senior")
    else:
        print("  no AI draft (AI off): the senior's answer stands alone")
    a = client.post(f"/api/campus/ask/{asked['id']}/answers", headers=h["senior"],
                    json={"body": "[Demo] Derive each formula once from torque = I α, then do ten mixed problems a day. "
                                  "Rolling without slipping (v = ω r) is where most marks go."})
    a.raise_for_status()
    client.post(f"/api/campus/ask/{a.json()['id']}/accept", headers=h["student"]).raise_for_status()
    print("  the senior's answer: accepted by the student")
    return {"accounts": {k: email(k) for k in ACCOUNTS}, "room": code}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--password", default="focs-demo-2026", help="one password for every demo account")
    ap.add_argument("--reset", action="store_true", help="delete the demo accounts and their data first")
    args = ap.parse_args()

    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.main import app

    if len(args.password) < 8:
        raise SystemExit("Use a password of 8+ characters.")
    with TestClient(app) as client:
        out = seed(client, args.password, args.reset)
    print(f"\nDemo ready on {settings.DATABASE_URL.split('@')[-1]} · password for every account: {args.password}")
    for key, address in out["accounts"].items():
        print(f"  {key:<9} {address}")
    print(f"  live class code: {out['room']}  (the teacher's confusion map: /app/rooms/{out['room']}/report)")


if __name__ == "__main__":
    main()
