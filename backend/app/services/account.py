"""A student's rights over their data (India's DPDP Act; app-store rules): export everything, delete everything."""
from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.doubt import Doubt
from app.models.flashcard import Flashcard
from app.models.gap import GapTrace
from app.models.lecture import LectureSegment
from app.models.llm_call import LlmCall
from app.models._util import utcnow
from app.models.mentor import GroupSeat, GroupSession, MentorCall, MentorMessage, MentorPayout, MentorProfile, Mentorship
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.mock import MockTest
from app.models.campus import CampusItem
from app.models.classroom import Classroom, ClassMember, ParentLink
from app.models.prep import ChapterRevision, PlanCheck, PlanTask, StudyGoal, TopicProgress
from app.models.quiz_attempt import QuizAttempt
from app.models.resource import Resource
from app.models.room import LectureSignal, Room
from app.models.session import StudySession
from app.models.study_day import StudyDay
from app.models.user import User
from app.models.weak import OutsideTest, WeakTopic
from app.services import live, storage


def _iso(dt) -> str | None:
    return dt.isoformat() + "Z" if dt else None


def export(db: Session, user: User) -> dict[str, Any]:
    sessions = db.scalars(select(StudySession).where(StudySession.user_id == user.id).order_by(StudySession.started_at)).all()
    return {
        "profile": {"name": user.full_name, "email": user.email, "exam": user.exam_target, "class": user.class_level,
                    "plan": user.plan, "joined": _iso(user.created_at), "daily_goal_min": user.daily_goal_min},
        "lectures": [{
            "title": s.title, "subject": s.subject, "source": s.source, "started": _iso(s.started_at), "ended": _iso(s.ended_at),
            "revision_sheet": s.summary,
            "boards": [{"topic": n.topic, "subject": n.subject, "captured": _iso(n.captured_at), "notes": n.ai_notes,
                        "board_text": n.ocr_raw} for n in s.notes],
        } for s in sessions],
        "flashcards": [{"front": c.front, "back": c.back, "topic": c.topic, "subject": c.subject, "due": _iso(c.due_at),
                        "repetitions": c.repetitions}
                       for c in db.scalars(select(Flashcard).where(Flashcard.user_id == user.id))],
        "answers": [{"question": a.question, "type": a.q_type, "topic": a.topic, "subject": a.subject, "correct": a.correct,
                     "score": a.score, "at": _iso(a.attempted_at)}
                    for a in db.scalars(select(QuizAttempt).where(QuizAttempt.user_id == user.id))],
        "doubts": [{"question": d.question, "answer": d.answer, "at": _iso(d.created_at)}
                   for d in db.scalars(select(Doubt).where(Doubt.user_id == user.id))],
        "focus_time": [{"day": d.day.isoformat(), "minutes": d.minutes, "by_activity": d.by_activity}
                       for d in db.scalars(select(StudyDay).where(StudyDay.user_id == user.id).order_by(StudyDay.day))],
        "mock_tests": [{"title": m.title, "pattern": m.pattern, "status": m.status, "started": _iso(m.started_at),
                        "submitted": _iso(m.submitted_at), "score": m.score, "max_score": m.max_score,
                        "result": (m.result or {}).get("total"), "responses": m.responses}
                       for m in db.scalars(select(MockTest).where(MockTest.user_id == user.id))],
        "goal": next(({"exam": g.exam, "track": g.track, "class": g.class_level, "exam_date": g.exam_date.isoformat(),
                       "target": g.target, "dream": g.dream, "weekday_hours": g.weekday_hours,
                       "weekend_hours": g.weekend_hours, "coaching": g.coaching}
                      for g in db.scalars(select(StudyGoal).where(StudyGoal.user_id == user.id))), None),
        "topics_done": [{"topic": t.topic_id, "at": _iso(t.done_at)}
                        for t in db.scalars(select(TopicProgress).where(TopicProgress.user_id == user.id))],
        "revisions": [{"chapter": r.chapter_id, "at": _iso(r.revised_at)}
                      for r in db.scalars(select(ChapterRevision).where(ChapterRevision.user_id == user.id))],
        "outside_tests": [{"title": t.title, "taken_on": t.taken_on.isoformat() if t.taken_on else None, "score": t.score,
                           "max_score": t.max_score, "subjects": t.subjects}
                          for t in db.scalars(select(OutsideTest).where(OutsideTest.user_id == user.id))],
        "weak_spots": [{"chapter": w.chapter_id, "topic": w.topic_id, "questions_lost": w.misses, "status": w.status,
                        "checks": w.checks, "cleared": _iso(w.cleared_at)}
                       for w in db.scalars(select(WeakTopic).where(WeakTopic.user_id == user.id))],
        "plan_edits": next((g.edits or {} for g in db.scalars(select(StudyGoal).where(StudyGoal.user_id == user.id))), {}),
        "own_tasks": [{"day": t.day.isoformat(), "title": t.title, "minutes": t.minutes, "done": bool(t.done)}
                      for t in db.scalars(select(PlanTask).where(PlanTask.user_id == user.id).order_by(PlanTask.day))],
    }


def _give_back(db: Session, payment_id: int | None) -> None:
    """A payment for something that won't happen now: marked for the admin to refund (or dropped, if never paid)."""
    p = db.get(Payment, payment_id) if payment_id else None
    if p is not None and p.status == "paid":
        p.status = "refund_due"
    elif p is not None and p.status == "created":
        p.status = "failed"


def _mentor_leaving(db: Session, profile: MentorProfile) -> None:
    """A mentor deleting their account: students with a call or a seat still to come are refunded what they paid and told."""
    now = utcnow()
    told: dict[tuple[int, str], str] = {}  # (student, what to tell them): where to look; once per thing that's off
    calls = db.scalars(select(MentorCall).where(MentorCall.mentor_id == profile.id, MentorCall.status.in_(("held", "booked")),
                                                MentorCall.starts_at > now)).all()
    for c in calls:
        _give_back(db, c.payment_id)
        told[(c.student_id, "Your mentor closed their account, so your upcoming call with them is off. Anything you paid will be refunded.")] = "/app/mentors?tab=mine"
    hosted = db.scalars(select(GroupSession).where(GroupSession.mentor_id == profile.id, GroupSession.status == "scheduled",
                                                   GroupSession.starts_at > now)).all()
    for s in hosted:
        for seat in db.scalars(select(GroupSeat).where(GroupSeat.session_id == s.id, GroupSeat.status.in_(("held", "booked")))):
            _give_back(db, seat.payment_id)
            told[(seat.user_id, f"The master session \"{s.topic}\" is off: its mentor closed their account. Anything you paid will be refunded.")] = "/app/mentors?tab=sessions"
    for (student, text), link in told.items():
        db.add(Notification(user_id=student, kind="session_cancelled", text=text[:300], link=link))


def _delete_mentoring(db: Session, uid: int) -> None:
    """Mentorships they were in (as a student or, for a mentor account, as the mentor), with their messages and calls;
    their seats in master sessions; and a mentor's profile, sessions and payout records."""
    profile = db.scalar(select(MentorProfile).where(MentorProfile.user_id == uid))
    if profile is not None:
        _mentor_leaving(db, profile)
    pid = profile.id if profile else -1
    ships = list(db.scalars(select(Mentorship.id).where((Mentorship.student_id == uid) | (Mentorship.mentor_id == pid))))
    if ships:
        db.execute(delete(MentorMessage).where(MentorMessage.mentorship_id.in_(ships)))
        db.execute(delete(MentorCall).where(MentorCall.mentorship_id.in_(ships)))
        db.execute(delete(Mentorship).where(Mentorship.id.in_(ships)))
    db.execute(delete(MentorMessage).where(MentorMessage.sender_id == uid))
    db.execute(delete(GroupSeat).where(GroupSeat.user_id == uid))
    if profile is not None:
        hosted = list(db.scalars(select(GroupSession.id).where(GroupSession.mentor_id == pid)))
        if hosted:
            db.execute(delete(GroupSeat).where(GroupSeat.session_id.in_(hosted)))
            db.execute(delete(GroupSession).where(GroupSession.id.in_(hosted)))
        db.execute(delete(MentorPayout).where(MentorPayout.mentor_id == pid))
        for path in (profile.proof_path, profile.photo_path, profile.photo_pending):
            storage.delete(path)
        db.delete(profile)


def delete_everything(db: Session, user: User) -> list[str]:
    """Delete the account and all of its data. Returns the codes of rooms it hosted (to close them live)."""
    uid = user.id
    sessions = db.scalars(select(StudySession).where(StudySession.user_id == uid)).all()
    for s in sessions:
        for n in s.notes:
            storage.delete(n.image_path)
        storage.delete_session(s.id)
        live.forget(s.id)  # a new lecture can get a deleted one's id (SQLite reuses them): it must start clean
    session_ids = [s.id for s in sessions]
    if session_ids:  # other people's rows may point at these lectures: detach them first
        db.execute(update(Flashcard).where(Flashcard.session_id.in_(session_ids)).values(session_id=None, note_id=None))
        db.execute(update(QuizAttempt).where(QuizAttempt.session_id.in_(session_ids)).values(session_id=None))
        db.execute(update(Doubt).where(Doubt.session_id.in_(session_ids)).values(session_id=None))
        db.execute(delete(LectureSegment).where(LectureSegment.session_id.in_(session_ids)))  # what the teacher said in them
    # their "I'm lost" taps stay on the host's confusion map, as anonymous as they always were
    db.execute(update(LectureSignal).where(LectureSignal.user_id == uid).values(user_id=None))
    db.execute(delete(Flashcard).where(Flashcard.user_id == uid))
    db.execute(delete(QuizAttempt).where(QuizAttempt.user_id == uid))
    db.execute(delete(Doubt).where(Doubt.user_id == uid))
    db.execute(delete(MockTest).where(MockTest.user_id == uid))
    db.execute(delete(StudyDay).where(StudyDay.user_id == uid))
    for path in db.scalars(select(CampusItem.file_path).where(CampusItem.user_id == user.id)):  # what they shared goes with them
        storage.delete(path)
    for model in (StudyGoal, TopicProgress, ChapterRevision, PlanCheck, PlanTask, WeakTopic, OutsideTest, CampusItem, ClassMember, ParentLink,
                  GapTrace):  # (their root-cause traces too)
        db.execute(delete(model).where(model.user_id == uid))
    taught = list(db.scalars(select(Classroom.id).where(Classroom.owner_id == uid)))  # the classes they ran close with them
    if taught:
        db.execute(delete(ClassMember).where(ClassMember.class_id.in_(taught)))
        db.execute(delete(Classroom).where(Classroom.id.in_(taught)))
    for s in sessions:
        db.delete(s)  # cascades to its notes
    course_ids = list(db.scalars(select(Course.id).where(Course.owner_id == uid)))
    if course_ids:
        db.execute(update(StudySession).where(StudySession.course_id.in_(course_ids)).values(course_id=None))
        db.execute(delete(Resource).where(Resource.course_id.in_(course_ids)))
        db.execute(delete(Course).where(Course.id.in_(course_ids)))
    _delete_mentoring(db, uid)
    db.execute(delete(Notification).where(Notification.user_id == uid))
    db.execute(update(LlmCall).where(LlmCall.user_id == uid).values(user_id=None))  # keep cost history, anonymised
    rooms = list(db.scalars(select(Room.code).where(Room.host_id == uid)))
    db.execute(delete(Room).where(Room.host_id == uid))
    # a checkout opened and never paid is nothing to keep; money that moved is kept for the accounts (tax records),
    # so that account stays as an empty, signed-out row with no name or email
    db.execute(delete(Payment).where(Payment.user_id == uid, Payment.status.in_(("created", "failed"))))
    if db.scalar(select(Payment.id).where(Payment.user_id == uid).limit(1)) is None:
        db.delete(user)
    else:
        user.email, user.full_name, user.hashed_pw = f"deleted-{uid}@deleted.invalid", "Deleted account", "!"
        user.is_active, user.subjects, user.class_level = False, None, None
    db.commit()
    return rooms
