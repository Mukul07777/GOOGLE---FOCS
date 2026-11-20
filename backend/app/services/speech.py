"""Speech to text for spoken answers.

Most browsers (Chrome, Edge, Safari) turn speech into text themselves, for free, and Focs uses that first. This is
the fallback for the rest (Firefox, Brave, or when the browser's own service is unreachable): the recording is
sent to the AI provider's OpenAI-compatible /audio/transcriptions endpoint. Groq and OpenAI have one; Gemini's
compatibility layer doesn't, so with only a Gemini key this fallback is simply off.
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.services import ledger
from app.services.llm import LLMUnavailable, ensure_budget, llm

log = logging.getLogger("focs.speech")

MAX_AUDIO_BYTES = 8 * 1024 * 1024  # ~4 minutes of browser-recorded speech
LANGUAGES = {"en", "hi", "mr", "bn", "ta", "te", "gu"}  # else let the model detect it (Hinglish switches mid-sentence)


def _provider() -> tuple[str, str] | None:
    base, key = settings.LLM_BASE_URL, settings.llm_api_key
    if settings.GOOGLE_ONLY:  # the browser dictates; the server-side fallback runs on Groq/OpenAI, so it is off
        return None
    return (base.rstrip("/"), key) if key and settings.STT_MODEL and ("groq.com" in base or "openai.com" in base) else None


def available() -> bool:
    return _provider() is not None


def transcribe(audio: bytes, filename: str, content_type: str, language: str = "", hint: str = "") -> str:
    """The words in a short recording. ``hint`` (the question being answered) helps with technical terms.
    Raises LLMUnavailable when the service can't be used right now."""
    return transcribe_full(audio, filename, content_type, language, hint)["text"]


def transcribe_full(audio: bytes, filename: str, content_type: str, language: str = "", hint: str = "",
                    feature: str = "dictation") -> dict:
    """``transcribe``, plus the language the recogniser heard and the recording's length: {text, language, duration}.
    ``feature`` names the cost in the ledger (a spoken answer, or a piece of a lecture)."""
    provider = _provider()
    if provider is None:
        raise LLMUnavailable("no speech-to-text provider configured")
    ensure_budget()
    base, key = provider
    data = {"model": settings.STT_MODEL, "response_format": "verbose_json", "temperature": "0"}
    if language in LANGUAGES:
        data["language"] = language
    if hint.strip():
        data["prompt"] = hint.strip()[:400]
    try:
        r = llm.client.post(f"{base}/audio/transcriptions", headers={"Authorization": f"Bearer {key}"}, data=data,
                            files={"file": (filename or "answer.webm", audio, content_type or "audio/webm")})
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"speech-to-text unreachable: {exc}") from exc
    if r.status_code >= 400:
        raise LLMUnavailable(f"speech-to-text rejected the recording ({r.status_code}): {r.text[:200]}")
    try:
        body = r.json()
    except ValueError as exc:
        raise LLMUnavailable("speech-to-text returned an unreadable answer") from exc
    seconds = float(body.get("duration") or 0)
    ledger.record_cost(feature, settings.STT_MODEL, seconds / 3600 * settings.STT_PRICE_USD_PER_HOUR)
    return {"text": str(body.get("text") or "").strip(), "language": str(body.get("language") or ""), "duration": seconds}
