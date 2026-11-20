import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api._common import owned_note, owned_session
from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models.quiz_attempt import QuizAttempt
from app.models.user import User
from app.schemas.practice import AttemptIn, EvaluateIn, QuizGenerate, RedoItem, TeachBackIn
from app.api.snap import _pages
from app.services import ai, syllabus, topic_notes, usage, vision, weak
from app.services.llm import LLMUnavailable

router = APIRouter(prefix="/quiz", tags=["quiz"])


@router.post("/generate", dependencies=[Depends(limit("quiz", 12))])
def generate(body: QuizGenerate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    syllabus_topic = None  # (chapter, topic, its library notes) when practising a syllabus topic
    if body.session_id:
        session = owned_session(db, user, body.session_id)
        material = "\n\n".join(f"## {n.topic or 'Board'}\n{n.ai_notes or ''}" for n in session.notes)
        if session.summary:
            material = f"{session.summary}\n\n{material}"
    elif body.note_ids:
        notes = [owned_note(db, user, nid) for nid in body.note_ids[:20]]
        material = "\n\n".join(f"## {n.topic or 'Board'}\n{n.ai_notes or ''}" for n in notes)
    elif body.topic_id:
        syllabus_topic = chapter, topic, library = _syllabus_topic(db, user, body.topic_id)
        material = (f"Syllabus topic: {topic.name}\nChapter: {chapter.name} ({syllabus.place(chapter)})\n\n"
                    + (library or "No notes are attached. Write every question from standard syllabus knowledge of exactly "
                                  "this topic, at the depth this exam asks it.")
                    + weak.aim(db, user.id, topic.id))
    else:
        material = body.text or ""
    if len(material.strip()) < 40:
        raise HTTPException(status_code=422, detail="There isn't enough material yet — capture a few boards first.")
    usage.require(db, user, "practice_set")
    quiz = ai.generate_quiz(material, user.exam_target, body.difficulty, body.n_mcq, body.n_tf, body.n_subjective,
                           language=user.language)
    if syllabus_topic:
        chapter, topic, library = syllabus_topic
        if quiz.get("source") != "ai" and not library:  # nothing to build offline questions from: don't invent any
            raise HTTPException(status_code=503, detail="Practice on this topic needs the AI, which can't be reached "
                                                        "right now. Try again in a minute.")
        quiz.update(topic=topic.name, subject=chapter.subject, topic_id=topic.id)
    usage.charge(db, user, "practice_set", quiz.get("source"))
    quiz["session_id"] = body.session_id
    quiz["notice"] = _shortfall(quiz, body)
    return quiz


def _shortfall(quiz: dict, body: QuizGenerate) -> str | None:
    """What a student is told when they got fewer questions than they asked for, and why."""
    got, asked = len(quiz.get("mcq") or []), body.n_mcq
    if quiz.get("source") != "ai":
        why = "Your AI allowance is used up or the AI can't be reached, so these are basic questions built from your notes."
    else:
        why = "The rest didn't pass Focs's answer check, so they were left out rather than risk a wrong answer key."
    if got < asked:
        return f"Only {got} of {asked} multiple-choice questions could be written. {why}"
    return why if quiz.get("source") != "ai" else None


def _syllabus_topic(db: Session, user: User, topic_id: str):
    """(chapter, topic, its notes if the library has them) for a topic of the student's own exam."""
    syl = syllabus.of(user, whole=True)  # any course's topic can be practised, not only this semester's
    found = syl.topic(topic_id) if syl else None
    if found is None:
        raise HTTPException(status_code=404, detail="Topic not found.")
    chapter, topic = found
    row = topic_notes.get(db, syl.library, "detailed", topic.id)
    return chapter, topic, topic.notes or (row.content_md if row else "")


@router.post("/teach-back", dependencies=[Depends(limit("evaluate", 20))])
def teach_back(body: TeachBackIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """A topic explained back in the student's own words (typed or spoken), checked against what was taught:
    the lecture's boards on it, or the topic's note in the library."""
    name, subject, reference = body.topic.strip(), body.subject, []
    if body.session_id:
        session = owned_session(db, user, body.session_id)
        boards = [n for n in session.notes if (n.topic or "").strip().lower() == name.lower()] or session.notes[-2:]
        reference += [n.ai_notes or "" for n in boards[-4:]]
        subject = subject or (boards[-1].subject if boards else "") or session.subject or ""
    if body.topic_id:
        chapter, topic, notes = _syllabus_topic(db, user, body.topic_id)
        name, subject = f"{topic.name} ({chapter.name}, {chapter.subject})", chapter.subject
        reference.append(notes)
    usage.require(db, user, "grade_answer")
    try:
        result = ai.teach_back(name, body.answer, "\n\n".join(r for r in reference if r.strip()), user.exam_target,
                              language=user.language)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail="Your explanation can't be checked right now: the AI is unreachable. "
                                                    "It's still here, so try again in a minute.") from exc
    correct = result["score"] >= 6
    db.add(QuizAttempt(user_id=user.id, session_id=body.session_id, topic=body.topic.strip()[:120],
                       question=f"Explain in your own words: {body.topic.strip()}", q_type="subjective", correct=correct,
                       score=result["score"], exam_target=user.exam_target, subject=subject, needs_redo=not correct))
    db.commit()
    usage.charge(db, user, "grade_answer", result.get("source"))
    return result


@router.post("/attempt", status_code=201)
def record_attempt(body: AttemptIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempt = QuizAttempt(user_id=user.id, exam_target=user.exam_target, needs_redo=not body.correct, **body.model_dump())
    db.add(attempt)
    db.commit()
    return {"id": attempt.id, "needs_redo": attempt.needs_redo}


@router.post("/evaluate", dependencies=[Depends(limit("evaluate", 20))])
def evaluate(body: EvaluateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    usage.require(db, user, "grade_answer")
    result = ai.evaluate_answer(body.question, body.student_answer, body.key_points, body.model_answer, user.exam_target,
                                language=user.language)
    correct = result["score"] >= 6
    db.add(QuizAttempt(user_id=user.id, session_id=body.session_id, topic=body.topic, question=body.question,
                       q_type="subjective", correct=correct, score=result["score"], exam_target=user.exam_target,
                       subject=body.subject, needs_redo=not correct))
    db.commit()
    usage.charge(db, user, "grade_answer", result.get("source"))
    return result


READ_ANSWER = """This is a photo of a student's handwritten answer to the question below. Copy out exactly what the
student wrote, line by line, in reading order: words as written, every expression, sign and step in LaTeX ($...$).
Correct nothing and add nothing, even where the student is wrong; mark a word you can't read as [?].
Question: {question}
Return JSON: {"readable": true or false (false when there is no handwritten answer or it can't be read), "answer": "..."}"""


@router.post("/evaluate-photo", dependencies=[Depends(limit("evaluate", 20))])
def evaluate_photo(question: str = Form(..., max_length=4000), key_points: str = Form("[]"), model_answer: str = Form(""),
                   topic: str = Form(""), subject: str = Form(""), session_id: int | None = Form(None),
                   files: list[UploadFile] = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """A written answer sent as a photo (maths is slow to type): the vision model copies it out, then it is graded
    exactly like a typed answer. The copy comes back too, so the student sees what was read."""
    try:
        points = [str(k) for k in json.loads(key_points)][:8]
    except (ValueError, TypeError):
        points = []
    pages = _pages(files)
    usage.require(db, user, "grade_answer")
    if not vision.available():
        raise HTTPException(status_code=503, detail="Reading a photo needs the AI that sees images, which isn't set up on "
                                                    "this server. Type your answer instead.")
    try:
        read = vision.read_json(pages, READ_ANSWER.replace("{question}", question[:1500]), "answer_photo", max_tokens=2000, head_start=4.0)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail="Couldn't read that photo right now. Try again in a minute.") from exc
    text = str(read.get("answer") or "").strip() if isinstance(read, dict) else ""
    if not text or read.get("readable") is False:
        raise HTTPException(status_code=422, detail="Focs couldn't read an answer in that photo. Try a sharper, well-lit "
                                                    "photo of just the answer.")
    result = ai.evaluate_answer(question, text, points, model_answer, user.exam_target, language=user.language)
    correct = result["score"] >= 6
    db.add(QuizAttempt(user_id=user.id, session_id=session_id, topic=topic[:120] or None, question=question,
                       q_type="subjective", correct=correct, score=result["score"], exam_target=user.exam_target,
                       subject=subject or None, needs_redo=not correct))
    db.commit()
    usage.charge(db, user, "grade_answer", result.get("source"))
    return {**result, "read_answer": text}


@router.get("/redo", response_model=list[RedoItem])
def redo_queue(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(
        select(QuizAttempt).where(QuizAttempt.user_id == user.id, QuizAttempt.needs_redo.is_(True))
        .order_by(QuizAttempt.attempted_at.desc()).limit(30)
    ).all()


@router.post("/redo/{attempt_id}/done", status_code=204)
def redo_done(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempt = db.get(QuizAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Attempt not found")
    attempt.needs_redo = False
    db.commit()
