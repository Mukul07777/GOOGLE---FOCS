"""Ask a senior: students taking a course ask the ones who have already done it, college by college.

Who is a senior, and how they prove it, is in services/seniority.py: a confirmed college email for B.Tech students
(who are also seniors for JEE and NEET Physics, Chemistry and Maths), real progress for GATE and placement students.
Anyone may answer; a senior's answer says so. Tips come from seniors only. Two reports hide a post.

A question gets an AI draft the moment it's asked, labelled as such, so no junior waits with nothing; a senior then
checks it ("Checked by a senior (Sem 5)") or corrects it. The asker marks the answer that settled it, and that
counts for its author on the leaderboard. Seniors hear about new questions on their courses in the bell.
"""
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.campus import _names
from app.api.notifications import notify
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models.campus import CampusPost
from app.models.user import User
from app.services import ai, mailer, seniority, syllabus, usage

router = APIRouter(prefix="/campus/ask", tags=["campus"])

HIDE_AFTER_REPORTS = 2
WAITING_MAX = 20
NOTIFY_MAX = 30  # seniors told about one question


class PostIn(BaseModel):
    subject: str = Field(max_length=60)
    kind: Literal["question", "tip"] = "question"
    body: str = Field(min_length=10, max_length=1500)
    chapter: str | None = Field(default=None, max_length=120)


class AnswerIn(BaseModel):
    body: str = Field(min_length=2, max_length=1500)


class CheckIn(BaseModel):
    verdict: Literal["right", "fix"]
    correction: str | None = Field(default=None, max_length=1500)


class VerifyStart(BaseModel):
    email: str = Field(min_length=6, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class VerifyConfirm(BaseModel):
    code: str = Field(min_length=6, max_length=6)


# ------------------------------------------------------------------ who's asking, and from which shelf
def _shelf_of(user: User) -> tuple[str, str]:
    """("courses", exam) for B.Tech / GATE / placement students, ("school", "jee"|"neet") for aspirants."""
    exam = syllabus.exam_of(user.exam_target)
    if syllabus.family(exam) == "college":
        return "courses", exam  # type: ignore[return-value]
    if exam in syllabus.ENTRANCE:
        return "school", exam  # type: ignore[return-value]
    raise HTTPException(status_code=404, detail="Ask a senior is for B.Tech, GATE, placement, JEE and NEET students. "
                                                "Set one of those as what you're preparing for in Settings.")


def _library(user: User) -> dict[str, list[str]]:
    """The subjects this student can ask about, with their chapters."""
    kind, exam = _shelf_of(user)
    if kind == "school":
        syl = syllabus.of(user, whole=True)
        return {s: [c.name for c in syl.subject_chapters(s)] for s in (syl.subjects if syl else ())}
    return {name: [c["name"] for c in course["chapters"]] for name, course in syllabus.courses().items()}


def _label(db: Session, user: User, post: CampusPost) -> str | None:
    """`user`'s senior label for the course of `post` (a question, or the question an answer belongs to)."""
    shelf = post.college if post.college in syllabus.ENTRANCE else "college"
    return seniority.label(db, user, post.subject, shelf)


def _visible(p: CampusPost) -> bool:
    return len(p.reporters or []) < HIDE_AFTER_REPORTS


def _helped(db: Session, ids: list[int]) -> dict[int, int]:
    """Answers each author wrote that an asker marked as the one that settled it."""
    if not ids:
        return {}
    rows = db.execute(select(CampusPost.user_id, func.count(CampusPost.id)).where(
        CampusPost.user_id.in_(ids), CampusPost.accepted.is_(True), CampusPost.ai.isnot(True)).group_by(CampusPost.user_id)).all()
    return {uid: n for uid, n in rows}


def _out(p: CampusPost, user: User, names: dict[int, str], helped: dict[int, int] | None = None) -> dict[str, Any]:
    by = "Focs (AI draft)" if p.ai else "You" if p.user_id == user.id else names.get(p.user_id, "A student")
    return {"id": p.id, "kind": p.kind, "subject": p.subject, "chapter": p.chapter, "body": p.body, "senior": p.senior,
            "college": p.college, "by": by, "mine": p.user_id == user.id and not p.ai, "votes": len(p.voters or []),
            "voted": user.id in (p.voters or []), "ai": bool(p.ai), "checked": p.checked_label, "accepted": bool(p.accepted),
            "helped": 0 if p.ai else (helped or {}).get(p.user_id, 0),
            "created_at": p.created_at.isoformat() + "Z" if p.created_at else None}


def _with_answers(db: Session, user: User, questions: list[CampusPost]) -> list[dict[str, Any]]:
    ids = [q.id for q in questions]
    answers = [a for a in db.scalars(select(CampusPost).where(CampusPost.parent_id.in_(ids))) if _visible(a)] if ids else []
    names = _names(db, [*questions, *answers])
    helped = _helped(db, list({p.user_id for p in [*questions, *answers]}))
    by_q: dict[int, list[CampusPost]] = {}
    for a in answers:
        by_q.setdefault(a.parent_id, []).append(a)
    out = []
    for q in questions:
        # the accepted answer first, then seniors', then the most helpful; an unchecked AI draft last
        replies = sorted(by_q.get(q.id, []), key=lambda a: (not a.accepted, bool(a.ai) and not a.checked_label, a.senior is None,
                                                            -len(a.voters or []), a.id))
        out.append({**_out(q, user, names, helped), "answers": [_out(a, user, names, helped) for a in replies]})
    return out


def _settled(db: Session, question_ids: list[int]) -> set[int]:
    """Questions a person has answered, or whose AI draft a senior has checked."""
    if not question_ids:
        return set()
    rows = db.execute(select(CampusPost.parent_id, CampusPost.ai, CampusPost.checked_label)
                      .where(CampusPost.parent_id.in_(question_ids))).all()
    return {pid for pid, is_ai, checked in rows if not is_ai or checked}


def _waiting(db: Session, user: User, college: str) -> list[dict[str, Any]]:
    """Questions still waiting for a senior, on courses this student has done (and JEE/NEET science, for a verified
    B.Tech student)."""
    courses = seniority.courses_done(db, user)
    asked: list[CampusPost] = []
    if courses:
        stmt = select(CampusPost).where(CampusPost.kind == "question", CampusPost.subject.in_(courses), CampusPost.user_id != user.id,
                                        CampusPost.college.notin_(syllabus.ENTRANCE))
        if college != "other":
            stmt = stmt.where(CampusPost.college == college)
        asked += list(db.scalars(stmt.order_by(CampusPost.created_at.desc()).limit(200)))
    if syllabus.is_college(syllabus.exam_of(user.exam_target)) and seniority.effective_semester(user):
        asked += list(db.scalars(select(CampusPost).where(CampusPost.kind == "question", CampusPost.college.in_(syllabus.ENTRANCE),
                                                          CampusPost.subject.in_(seniority.SCHOOL_SUBJECTS), CampusPost.user_id != user.id)
                                 .order_by(CampusPost.created_at.desc()).limit(100)))
    asked = [q for q in asked if _visible(q)]
    settled = _settled(db, [q.id for q in asked])
    return _with_answers(db, user, [q for q in asked if q.id not in settled][:WAITING_MAX])


def _mask(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    name, domain = email.split("@", 1)
    return f"{name[:2]}{'•' * max(1, len(name) - 2)}@{domain}"


def _verification(user: User) -> dict[str, Any]:
    kind, exam = _shelf_of(user)
    college = syllabus.college_of(user.college)
    own = seniority.DOMAINS.get(college)
    return {"verified": seniority.verified(user), "email": _mask(user.college_email),
            "needed": kind == "courses" and syllabus.is_college(exam) and not seniority.verified(user),
            "domains": [f"@{d}" for d in own] if own else ["an .ac.in, .edu.in or .edu address"],
            "pending": bool(user.verify_pending)}


# ------------------------------------------------------------------ the board
@router.get("")
def board(subject: str | None = Query(None, max_length=60), scope: Literal["mine", "all"] = "mine",
          db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """A course's tips from seniors and its questions with their answers; and what juniors are waiting on from you."""
    kind, exam = _shelf_of(user)
    library = _library(user)
    mine = syllabus.of(user)
    subject = subject if subject in library else (mine.subjects[0] if mine and mine.subjects and mine.subjects[0] in library else next(iter(library)))
    if kind == "school":
        shelf, shelf_name = exam, syllabus.label(user.exam_target)
        stmt = select(CampusPost).where(CampusPost.subject == subject, CampusPost.parent_id.is_(None), CampusPost.college == exam)
    else:
        shelf = syllabus.college_of(user.college)
        shelf_name = syllabus.COLLEGES[shelf]["name"]
        stmt = select(CampusPost).where(CampusPost.subject == subject, CampusPost.parent_id.is_(None),
                                        CampusPost.college.notin_(syllabus.ENTRANCE))
        if scope == "mine" and shelf != "other":
            stmt = stmt.where(CampusPost.college == shelf)
    posts = [p for p in db.scalars(stmt.order_by(CampusPost.created_at.desc()).limit(200)) if _visible(p)]
    tips = sorted((p for p in posts if p.kind == "tip"), key=lambda p: -len(p.voters or []))
    names = _names(db, tips)
    helped = _helped(db, list({t.user_id for t in tips}))
    return {"subject": subject, "chapters": library[subject], "shelf": kind,
            "college": shelf, "college_name": shelf_name,
            "subjects": [s for s in (mine.subjects if mine else ()) if s in library] or list(library),
            "done": seniority.courses_done(db, user) if kind == "courses" else [], "catalogue": sorted(library),
            "senior": seniority.label(db, user, subject) if kind == "courses" else None,
            "tips": [_out(p, user, names, helped) for p in tips],
            "questions": _with_answers(db, user, [p for p in posts if p.kind == "question"]),
            "waiting": _waiting(db, user, shelf) if kind == "courses" else [],
            "verification": _verification(user)}


# ------------------------------------------------------------------ proving you're at the college
@router.post("/verify/start", dependencies=[Depends(limit("campus-verify", 3))])
def verify_start(body: VerifyStart, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Send a one-time code to a college email. The address must be the college's own (any academic one for
    "another college")."""
    kind, exam = _shelf_of(user)
    if kind != "courses" or not syllabus.is_college(exam):
        raise HTTPException(status_code=422, detail="College email checks are for B.Tech students.")
    if not seniority.domain_ok(user.college, body.email):
        hint = ", ".join(_verification(user)["domains"])
        raise HTTPException(status_code=422, detail=f"Use your college email ({hint}).")
    code = seniority.start(user, body.email)
    db.commit()
    text = (f"Your Focs code is {code}. It confirms {body.email} is yours, so your answers in Ask a senior show "
            f"you've done the course. It works for {seniority.CODE_MINUTES} minutes. If you didn't ask for it, ignore this.")
    if mailer.configured():
        if not mailer.send(body.email, "Your Focs college email code", text):
            raise HTTPException(status_code=502, detail="The email couldn't be sent right now. Try again in a minute.")
        return {"sent": True}
    if settings.is_production:
        raise HTTPException(status_code=503, detail="Email isn't set up on this server yet, so college emails can't be checked.")
    return {"sent": False, "dev_code": code}  # local development without email: the code is shown on screen


@router.post("/verify/confirm", dependencies=[Depends(limit("campus-verify-code", 10))])
def verify_confirm(body: VerifyConfirm, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    problem = seniority.confirm(user, body.code)
    db.commit()
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    return _verification(user)


# ------------------------------------------------------------------ asking, answering, checking
def _seniors_for(db: Session, question: CampusPost) -> list[int]:
    """Verified students who can speak as seniors to this question: the ones to tell."""
    stmt = select(User).where(User.college_verified_at.isnot(None), User.id != question.user_id)
    if question.college not in syllabus.ENTRANCE and question.college != "other":
        stmt = stmt.where(User.college == question.college)
    out = []
    for u in db.scalars(stmt.limit(400)):
        if _label(db, u, question):
            out.append(u.id)
            if len(out) >= NOTIFY_MAX:
                break
    return out


def _link(post: CampusPost) -> str:
    return f"/app/campus?tab=ask&subject={post.subject}"


def _draft(question_id: int, asker_id: int) -> None:
    """Right after a question is asked: Focs's own answer, labelled as an AI draft until a senior checks it."""
    with SessionLocal() as db:
        q, asker = db.get(CampusPost, question_id), db.get(User, asker_id)
        if q is None or asker is None or not usage.can_spend(db, asker, "doubt"):
            return
        where = f"{q.subject}{f', chapter {q.chapter}' if q.chapter else ''}"
        context = (f"A student asks their seniors about {where}. Answer as a helpful senior would: what matters, how it is "
                   "examined, how to prepare, and the key idea if they ask about one. Short, practical, no preamble.")
        try:
            result = ai.companion(q.body, context, [], asker.exam_target, "explain", asker.language)
        except Exception:  # the draft is a bonus: a failure never touches the question
            return
        if result.get("source") != "ai" or not (result.get("answer") or "").strip():
            return
        db.add(CampusPost(user_id=asker.id, college=q.college, subject=q.subject, chapter=q.chapter, kind="answer",
                          parent_id=q.id, body=result["answer"].strip()[:4000], senior=None, voters=[], reporters=[], ai=True))
        db.commit()
        usage.charge(db, asker, "doubt", "ai")


@router.post("", status_code=201, dependencies=[Depends(limit("campus-ask", 10))])
def ask(body: PostIn, background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    kind, exam = _shelf_of(user)
    library = _library(user)
    if body.subject not in library:
        raise HTTPException(status_code=422, detail="Choose the course this is about.")
    chapter = body.chapter if body.chapter in library[body.subject] else None
    shelf = exam if kind == "school" else syllabus.college_of(user.college)
    senior = None if kind == "school" else seniority.label(db, user, body.subject)
    if body.kind == "tip" and senior is None:
        raise HTTPException(status_code=403, detail="Tips come from students who have done this course. Ask a question instead.")
    post = CampusPost(user_id=user.id, college=shelf, subject=body.subject, chapter=chapter,
                      kind=body.kind, body=body.body.strip(), senior=senior, voters=[], reporters=[])
    db.add(post)
    db.flush()
    if body.kind == "question":
        notify(db, _seniors_for(db, post), "asked", f"A junior asked about {post.subject}: “{post.body[:120]}”", _link(post))
        background.add_task(_draft, post.id, user.id)
    db.commit()
    return {**_out(post, user, {}), "answers": []}


def _post(db: Session, post_id: int) -> CampusPost:
    post = db.get(CampusPost, post_id)
    if post is None or not _visible(post):
        raise HTTPException(status_code=404, detail="That post isn't here any more.")
    return post


@router.post("/{post_id}/answers", status_code=201, dependencies=[Depends(limit("campus-ask", 10))])
def answer(post_id: int, body: AnswerIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    _shelf_of(user)
    question = _post(db, post_id)
    if question.kind != "question":
        raise HTTPException(status_code=422, detail="Only a question can be answered.")
    reply = CampusPost(user_id=user.id, college=question.college, subject=question.subject, chapter=question.chapter,
                       kind="answer", parent_id=question.id, body=body.body.strip(), senior=_label(db, user, question),
                       voters=[], reporters=[])
    db.add(reply)
    if question.user_id != user.id:
        who = "A senior" if reply.senior else "Someone"
        notify(db, [question.user_id], "answered", f"{who} answered your question on {question.subject}", _link(question))
    db.commit()
    return _out(reply, user, {})


@router.post("/{post_id}/check")
def check(post_id: int, body: CheckIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """A senior on Focs's AI draft: it's right ("Checked by a senior"), or here's the correction."""
    _shelf_of(user)
    draft = _post(db, post_id)
    question = db.get(CampusPost, draft.parent_id) if draft.parent_id else None
    if not draft.ai or draft.kind != "answer" or question is None:
        raise HTTPException(status_code=422, detail="Only Focs's AI drafts are checked.")
    senior = _label(db, user, question)
    if senior is None:
        raise HTTPException(status_code=403, detail="Only a senior for this course can check Focs's answer.")
    if body.verdict == "right":
        draft.checked_label = f"Checked by a senior ({senior.split(' · ')[0]})"
    else:
        fix = (body.correction or "").strip()
        if len(fix) < 10:
            raise HTTPException(status_code=422, detail="Write the correction: what's wrong and what's right.")
        db.add(CampusPost(user_id=user.id, college=question.college, subject=question.subject, chapter=question.chapter,
                          kind="answer", parent_id=question.id, body=fix, senior=senior, voters=[], reporters=[]))
        draft.checked_label = "A senior corrected this: see their answer"
    draft.checked_by = user.id
    notify(db, [question.user_id], "checked", f"A senior checked the AI answer to your question on {question.subject}", _link(question))
    db.commit()
    return _with_answers(db, user, [question])[0]


@router.post("/{post_id}/accept")
def accept(post_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """The asker: "this answered it" (and again to take it back). It counts for the answer's author."""
    reply = _post(db, post_id)
    question = db.get(CampusPost, reply.parent_id) if reply.parent_id else None
    if reply.kind != "answer" or question is None or question.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the student who asked can mark the answer that settled it.")
    reply.accepted = not reply.accepted
    if reply.accepted and not reply.ai and reply.user_id != user.id:
        notify(db, [reply.user_id], "accepted", f"Your answer on {question.subject} settled a junior's question. Thank you.", _link(question))
    db.commit()
    return {"accepted": bool(reply.accepted)}


@router.post("/{post_id}/vote")
def vote(post_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """"This helped": once per student, and again to take it back."""
    _shelf_of(user)
    post = _post(db, post_id)
    voters = list(post.voters or [])
    post.voters = [v for v in voters if v != user.id] if user.id in voters else [*voters, user.id]
    db.commit()
    return {"votes": len(post.voters), "voted": user.id in post.voters}


@router.post("/{post_id}/report", status_code=204)
def report(post_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    _shelf_of(user)
    post = _post(db, post_id)
    post.reporters = sorted({*(post.reporters or []), user.id})
    db.commit()


@router.delete("/{post_id}", status_code=204)
def remove(post_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    post = db.get(CampusPost, post_id)
    if post is None or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="That isn't yours to remove.")
    for reply in db.scalars(select(CampusPost).where(CampusPost.parent_id == post.id)):
        db.delete(reply)
    db.delete(post)
    db.commit()
