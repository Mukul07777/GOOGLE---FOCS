"""Ask with a photo: a question snapped from a book or a paper is solved step by step, and a handwritten answer
is marked the way an examiner would. Both are read by the model that sees images (services/vision)."""
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models.doubt import Doubt
from app.models.quiz_attempt import QuizAttempt
from app.models.user import User
from app.schemas.auth import Translated
from app.services import ai, syllabus, translate, usage, vision
from app.services.llm import LLMUnavailable, restore_backslashes

router = APIRouter(prefix="/snap", tags=["photo"])

READABLE = ("image/jpeg", "image/png", "image/webp", "application/pdf")
MAX_FILES, MAX_FILE_BYTES, MAX_PAGES = 4, 10 * 1024 * 1024, 4

SOLVE = """A {exam} student photographed a question they are stuck on. Read it from the image{hint} and solve it.
Return ONLY a JSON object:
{{"readable": true or false (false when no question can be read),
  "question": the question exactly as printed, with any options (math in LaTeX inside $...$),
  "subject": the subject it belongs to, one of: {subjects}, "topic": the chapter or topic in a few words,
  "idea": one or two sentences: the concept that unlocks it,
  "steps": ["each step of the working, in order, as a full sentence with its math in $...$"],
  "answer": the final answer, with units (for an MCQ: the option letter and its text),
  "watch_out": the mistake students usually make on this kind of question, or null}}
If several questions are in the photo, solve the first complete one and say so in "idea". Check the arithmetic of
every step before you answer."""

MARK = """You are a strict but fair {exam} examiner. The images are a student's HANDWRITTEN answer{about}.
Mark it out of {marks} the way a board or university examiner does: marks for each correct step, formula, diagram
and the final answer; nothing for what is missing or wrong; no marks off for handwriting. Ask only for the working
this question needs at this level: a correct answer to a one-step question (a sum, a fact, a definition) earns full
marks without written steps.{level}
Return ONLY a JSON object:
{{"readable": true or false (false when the writing cannot be read),
  "question": the question being answered, as far as it can be told,
  "marks": marks awarded (a number, halves allowed), "max_marks": {marks},
  "got_right": ["what earned marks, each in a short sentence"],
  "lost": [{{"where": "the step or part", "why": "what is wrong or missing", "marks": marks lost there}}],
  "model_answer": the answer that would get full marks, in Markdown with math in $...$, as short as full marks allow,
  "next_time": one sentence of advice for the next answer}}
Be specific: quote the student's own line where it goes wrong."""


def _level(exam: str | None) -> str:
    """A young student is marked as their own class is (a Class 1 "7 + 5 = 12" got 2/5 for showing no steps)."""
    n = syllabus.SCHOOL.get(exam or "")
    return f" The student is in Class {n}: expect only what a Class {n} answer shows." if n and n <= 8 else ""


def _pages(files: list[UploadFile]) -> list[bytes]:
    if not 1 <= len(files) <= MAX_FILES:
        raise HTTPException(status_code=422, detail=f"Attach 1 to {MAX_FILES} photos.")
    pages: list[bytes] = []
    for f in files:
        if f.content_type not in READABLE:
            raise HTTPException(status_code=415, detail="Attach photos or screenshots (JPEG, PNG, WebP) or a PDF.")
        data = f.file.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail="Each file can be up to 10 MB.")
        try:
            pages += vision.pdf_pages(data, MAX_PAGES) if "pdf" in f.content_type else [vision.to_jpeg(data)]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="One of those files couldn't be opened. Try a clearer photo.") from exc
    return pages[:MAX_PAGES]


def _see(pages: list[bytes], prompt: str, feature: str) -> dict[str, Any]:
    if not vision.available():
        raise HTTPException(status_code=503, detail="Reading a photo needs the AI that sees images, which isn't set up on this "
                                                    "server. Type your question in the doubt box of a lecture instead.")
    try:
        data = vision.read_json(pages, prompt, feature, max_tokens=3500)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail="Couldn't read that photo right now. Try again in a minute.") from exc
    if not isinstance(data, dict) or data.get("readable") is False:
        raise HTTPException(status_code=422, detail="Couldn't read that. Take the photo straight on, in good light, with the whole "
                                                    "question in the frame.")
    return data


def _text(value: Any, limit_: int = 4000) -> str:
    return restore_backslashes(str(value or "").strip())[:limit_]


@router.post("/doubt", dependencies=[Depends(limit("snap", 12))])
def solve(files: list[UploadFile] = File(...), note: str = Form("", max_length=400), db: Session = Depends(get_db),
          user: User = Depends(get_current_user)) -> dict[str, Any]:
    """A photographed question, solved step by step. Kept with the student's other doubts."""
    pages = _pages(files)
    usage.require(db, user, "doubt")
    hint = f'. The student adds: "{note.strip()}"' if note.strip() else ""
    data = _see(pages, SOLVE.format(exam=syllabus.label(user.exam_target), hint=hint, subjects=ai._subjects(user.exam_target)), "photo_doubt")
    steps = [_text(s, 1200) for s in data.get("steps") or [] if str(s).strip()][:14]
    out = {"question": _text(data.get("question")), "subject": _text(data.get("subject"), 60), "topic": _text(data.get("topic"), 80),
           "idea": _text(data.get("idea"), 800), "steps": steps, "answer": _text(data.get("answer"), 800),
           "watch_out": _text(data.get("watch_out"), 500) or None}
    if not out["question"] or not (steps or out["answer"]):
        raise HTTPException(status_code=422, detail="Couldn't make out a question in that photo. Try a closer, sharper one.")
    answer = "\n".join([out["idea"], "", *(f"{i}. {s}" for i, s in enumerate(steps, 1)), "", f"**Answer:** {out['answer']}"]).strip()
    doubt = Doubt(user_id=user.id, question=out["question"][:4000], answer=answer)
    db.add(doubt)
    db.commit()
    usage.charge(db, user, "doubt", "ai")
    return {"id": doubt.id, **out}


class ExplainIn(BaseModel):
    language: Translated


@router.post("/doubt/{doubt_id}/explain", dependencies=[Depends(limit("snap-explain", 20))])
def explain_doubt(doubt_id: int, body: ExplainIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """A photographed question's solution said again in the student's language: the same steps and answer, the math
    untouched. Solved in English first (the most reliable), written in a language once, then kept with the doubt."""
    doubt = db.get(Doubt, doubt_id)
    if doubt is None or doubt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Doubt not found")
    done = (doubt.explained or {}).get(body.language)
    if done:
        return {"language": body.language, "solution": done}
    usage.require(db, user, "doubt")
    try:
        text = translate.explained(doubt.answer, doubt.question, body.language, user.exam_target)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail="The AI that explains solutions is unreachable. Try again in a minute.") from exc
    if text is None:
        raise HTTPException(status_code=503, detail=f"Couldn't write it in {translate.NAMES[body.language]} just now. Try again in a minute.")
    doubt.explained = {**(doubt.explained or {}), body.language: text}
    db.commit()
    usage.charge(db, user, "doubt")
    return {"language": body.language, "solution": text}


@router.post("/answer", dependencies=[Depends(limit("snap", 12))])
def mark(files: list[UploadFile] = File(...), question: str = Form("", max_length=1500), max_marks: float = Form(5, ge=1, le=100),
         db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """A handwritten answer, marked like an examiner would: what earned marks, where they were lost, a model answer."""
    pages = _pages(files)
    usage.require(db, user, "grade_answer")
    about = f' to this question:\n"""{question.strip()}"""' if question.strip() else " (the question is written with it, or is clear from it)"
    data = _see(pages, MARK.format(exam=syllabus.label(user.exam_target), about=about, marks=f"{max_marks:g}",
                                    level=_level(user.exam_target)), "answer_check")
    try:
        marks = max(0.0, min(float(max_marks), round(float(data.get("marks")) * 2) / 2))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Couldn't mark that. Try a clearer photo of the whole answer.") from exc
    lost = []
    for row in data.get("lost") or []:
        if isinstance(row, dict) and str(row.get("why") or "").strip():
            try:
                cut = float(row.get("marks") or 0)
            except (TypeError, ValueError):
                cut = 0.0
            lost.append({"where": _text(row.get("where"), 200), "why": _text(row.get("why"), 600), "marks": cut})
    out = {"question": _text(data.get("question")) or question.strip(), "marks": marks, "max_marks": float(max_marks),
           "percent": round(100 * marks / float(max_marks)),
           "got_right": [_text(s, 400) for s in data.get("got_right") or [] if str(s).strip()][:10], "lost": lost[:10],
           "model_answer": _text(data.get("model_answer"), 6000), "next_time": _text(data.get("next_time"), 400) or None}
    ok = out["percent"] >= 60
    db.add(QuizAttempt(user_id=user.id, topic="Written answer", question=out["question"][:2000], q_type="subjective", correct=ok,
                       score=round(10 * marks / float(max_marks), 1), exam_target=user.exam_target, subject="", needs_redo=not ok))
    db.commit()
    usage.charge(db, user, "grade_answer", "ai")
    return out
