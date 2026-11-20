"""Spoken answers: speech to text for browsers that can't do it themselves (see services/speech)."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models.user import User
from app.services import speech, usage
from app.services.llm import LLMUnavailable

router = APIRouter(prefix="/speech", tags=["speech"])


@router.get("/status")
def status(_: User = Depends(get_current_user)) -> dict[str, bool]:
    """Whether the server can transcribe a recording (the browser's own dictation is always tried first)."""
    return {"server": speech.available()}


@router.post("/transcribe", dependencies=[Depends(limit("speech", 20))])
def transcribe(audio: UploadFile = File(...), language: str = Form(""), hint: str = Form(""),
               db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, str]:
    if not speech.available():
        raise HTTPException(status_code=503, detail="Voice answers aren't available on this server. Type your answer instead.")
    if not (audio.content_type or "").startswith(("audio/", "video/webm")):
        raise HTTPException(status_code=415, detail="That isn't an audio recording.")
    data = audio.file.read(speech.MAX_AUDIO_BYTES + 1)
    if len(data) > speech.MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="That recording is too long. Keep a spoken answer under four minutes.")
    if len(data) < 800:
        raise HTTPException(status_code=422, detail="Nothing was recorded. Check your microphone and try again.")
    usage.require(db, user, "dictation")
    try:
        text = speech.transcribe(data, audio.filename or "answer.webm", audio.content_type or "audio/webm", language, hint)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail="Couldn't turn that recording into text right now. Try again, or type your answer.") from exc
    if not text:
        raise HTTPException(status_code=422, detail="Couldn't make out any words. Speak a little closer to the microphone.")
    usage.charge(db, user, "dictation")
    return {"text": text}
