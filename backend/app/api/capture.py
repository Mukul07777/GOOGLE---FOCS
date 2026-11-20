"""Frame ingestion: live screen-capture frames and one-off board photos.

Endpoints are sync on purpose: FastAPI runs them in its threadpool, so OCR and LLM calls
never block the event loop that serves everything else (including study-room websockets).
"""
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api import rooms
from app.api._common import note_out, owned_session
from app.core.deps import get_current_user, get_db
from app.core.ratelimit import limit
from app.models.session import StudySession
from app.models.user import User
from app.services import link_lecture, live, perspective, speech, voice
from app.services.ocr import decode_image

router = APIRouter(prefix="/capture", tags=["capture"])

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}


def _read_image(file: UploadFile):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG or WebP image.")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image is larger than 12 MB.")
    try:
        return decode_image(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="That file is not a readable image.") from exc


def _response(result: dict) -> dict:
    for key in ("note", "also_updated"):  # also_updated: a board the lecture moved on from, written up now (also_status)
        if result.get(key) is not None:
            result[key] = note_out(result[key]).model_dump(mode="json")
    return result


def _share_with_room(session: StudySession, result: dict, user: User) -> None:
    if not session.room_code:
        return
    if result.get("also_updated"):
        rooms.broadcast_note(session.room_code, {"status": result.get("also_status", "updated"), "note": result["also_updated"],
                                                 "by": user.full_name})
    if result.get("note") and result.get("status") in ("created", "updated"):
        rooms.broadcast_note(session.room_code, {"status": result["status"], "note": result["note"], "by": user.full_name})


class Clip(BaseModel):
    start_s: float = Field(ge=0, le=86400)
    end_s: float = Field(ge=0, le=86400)


@router.post("/{session_id}/clip", dependencies=[Depends(limit("clip", 20))])
def ingest_clip(session_id: int, body: Clip, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Lecture by link: the stretch of the YouTube lecture just watched, written up as one note (services/link_lecture)."""
    session = owned_session(db, user, session_id)
    if session.source != "link":
        raise HTTPException(status_code=409, detail="This lecture isn't playing from a link.")
    if not session.is_active:
        raise HTTPException(status_code=409, detail="This session has ended. Start a new one to keep taking notes.")
    if body.end_s <= body.start_s:
        raise HTTPException(status_code=422, detail="That stretch of the lecture is empty.")
    return _response(link_lecture.read_clip(db, user, session, body.start_s, body.end_s))


@router.post("/{session_id}/frame", dependencies=[Depends(limit("frame", 40))])
def ingest_frame(
    session_id: int,
    frame: UploadFile = File(...),
    force: bool = Form(False),
    corners: str = Form("", max_length=200),
    camera: bool = Form(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """One captured frame of the lecture. Unchanged/duplicate boards are skipped cheaply.

    Classroom mode (a phone camera on a real board): `corners` are the board's four corners in the frame, marked once
    by the student; the frame is straightened to a front-on board before it's read. `camera` tells the duplicate check
    that a camera's frames never match exactly."""
    session = owned_session(db, user, session_id)
    if not session.is_active and not session.room_code:
        raise HTTPException(status_code=409, detail="This session has ended. Start a new one to keep capturing.")
    db.commit()  # hand the connection back while the image is decoded and read (taken again only to save)
    img = _read_image(frame)
    quad = perspective.parse_corners(corners)
    if quad is not None:
        img = perspective.warp(img, quad)
    result = _response(live.process_frame(db, user, session, img, force=force, camera=camera))
    _share_with_room(session, result, user)
    return result


@router.post("/{session_id}/audio", dependencies=[Depends(limit("audio", 12))])  # ~2.4 a minute, more after a network blip
def ingest_audio(
    session_id: int,
    audio: UploadFile = File(...),
    start_s: float = Form(0),
    end_s: float = Form(0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """About 25 seconds of the lecture's sound (only pieces with speech are sent). Transcribed and dropped: the audio
    is never stored. Returns the caption, and a spoken note when the talk made one."""
    session = owned_session(db, user, session_id)
    if not session.is_active and not session.room_code:
        raise HTTPException(status_code=409, detail="This session has ended.")
    if not (audio.content_type or "").startswith(("audio/", "video/webm")):
        raise HTTPException(status_code=415, detail="That isn't an audio recording.")
    data = audio.file.read(speech.MAX_AUDIO_BYTES + 1)
    if len(data) > speech.MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="That piece of audio is too long.")
    if len(data) < 2000:
        return {"skipped": "silence"}
    result = voice.add(db, user, session, data, audio.filename or "lecture.webm", audio.content_type or "audio/webm", start_s, end_s)
    if result.get("spoken_note") is not None:
        result["spoken_note"] = note_out(result["spoken_note"]).model_dump(mode="json")
    return result


@router.get("/{session_id}/transcript")
def get_transcript(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """What the teacher said, piece by piece, with times (the captions, kept)."""
    owned_session(db, user, session_id)
    return {"segments": [voice.segment_out(s) for s in voice.transcript(db, session_id)], "available": speech.available()}


@router.post("/{session_id}/transcript/summary", dependencies=[Depends(limit("talk_summary", 30))])
def transcript_summary(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """A summary of what the teacher said: kept with the lecture, written again only after more speech came in."""
    return voice.summary(db, user, owned_session(db, user, session_id))


@router.post("/{session_id}/settle", dependencies=[Depends(limit("settle", 20))])
def settle_board(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The board has stopped changing: write up the version the teacher finished (one AI call instead of one per line)."""
    session = owned_session(db, user, session_id)
    result = _response(live.settle(db, user, session))
    _share_with_room(session, result, user)
    return result


@router.post("/photo", dependencies=[Depends(limit("photo", 20))])
def ingest_photo(
    photo: UploadFile = File(...),
    session_id: int | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """A photo of a board or notebook (offline classes). Creates a 'Photo notes' session if needed."""
    img = _read_image(photo)
    if session_id:
        session = owned_session(db, user, session_id)
    else:
        session = StudySession(user_id=user.id, source="upload", is_active=False)
        db.add(session)
        db.commit()
        db.refresh(session)
        session.ended_at = session.started_at
    result = live.process_frame(db, user, session, img, force=True)
    result["session_id"] = session.id
    return _response(result)
