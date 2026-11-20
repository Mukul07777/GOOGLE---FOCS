"""Reading images with a model that sees them (a lecture board, a test result, a marked answer sheet).

Uses the fallback provider (Gemini, through its OpenAI-compatible endpoint): cheap models that take images, tried in
order (VISION_MODEL), since one is often busy. Without that key callers fall back to local OCR and a text model.
"""
from __future__ import annotations

import base64
import contextvars
import io
import logging
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

import httpx

from app.core.config import settings
from app.services import ledger
from app.services.images import open_image, pdf_page_jpeg
from app.services.llm import LLMUnavailable, ensure_budget, llm, parse_json

log = logging.getLogger("focs.vision")

MAX_SIDE = 1600  # pixels: enough to read a printed report, small enough to be cheap


def _key() -> str:
    return settings.LLM_FALLBACK_API_KEY or settings.GEMINI_API_KEY


def models() -> list[str]:
    """The vision models, in the order they are tried ("groq:<model>" runs on the primary provider)."""
    return [m.strip() for m in settings.VISION_MODEL.split(",")
            if m.strip() and _endpoint(m.strip())[1] and not (settings.GOOGLE_ONLY and m.strip().startswith("groq:"))]


def _endpoint(model: str) -> tuple[str, str, str]:
    """(base URL, key, model name) for one entry of VISION_MODEL."""
    if model.startswith("groq:"):
        return settings.LLM_BASE_URL, settings.llm_api_key, model.removeprefix("groq:")
    return settings.LLM_FALLBACK_BASE_URL, _key(), model


def available() -> bool:
    return bool(models())


def to_jpeg(data: bytes) -> bytes:
    """Any image the browser sends (PNG, WebP, a phone photo) → a reasonably sized JPEG. Raises ValueError."""
    img = open_image(data, MAX_SIDE)
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


def pdf_pages(data: bytes, limit: int) -> list[bytes]:
    """The first pages of a PDF as JPEGs. Raises ValueError."""
    import pymupdf

    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            return [pdf_page_jpeg(doc[i], 110) for i in range(min(limit, doc.page_count))]
    except Exception as exc:  # noqa: BLE001
        raise ValueError("not a readable PDF") from exc


def pdf_page_count(data: bytes) -> int:
    """How many pages a PDF has, after checking its first page can be drawn. Raises ValueError."""
    import pymupdf

    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.page_count < 1:
                raise ValueError("a PDF without pages")
            pdf_page_jpeg(doc[0], 30)
            return doc.page_count
    except Exception as exc:  # noqa: BLE001
        raise ValueError("not a readable PDF") from exc


def _ask(entry: str, content: list[dict], max_tokens: int, timeout: float, feature: str) -> tuple[dict | None, str]:
    """One vision model's answer as JSON, or (None, why) when it is busy, retired, slow or unreadable and the next
    model should try. Raises LLMUnavailable when no model will do better (unreachable, or the request refused)."""
    base, key, model = _endpoint(entry)
    body = {"model": model, "temperature": 0, "max_tokens": max_tokens, "messages": [{"role": "user", "content": content}]}
    try:
        r = llm.client.post(base.rstrip("/") + "/chat/completions", json=body, headers={"Authorization": f"Bearer {key}"}, timeout=timeout)
    except httpx.TimeoutException:
        return None, f"{model} timed out"
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"vision model unreachable: {exc}") from exc
    if r.status_code in (404, 429, 500, 502, 503, 504):
        if r.status_code == 404:
            log.warning("vision model %s is not available (404); check VISION_MODEL", model)
        return None, f"{model} {r.status_code}"
    if r.status_code >= 400:
        raise LLMUnavailable(f"vision model refused ({r.status_code}): {r.text[:200]}")
    try:
        data = r.json()
        text = data["choices"][0]["message"].get("content") or ""
    except (ValueError, KeyError, IndexError):
        return None, f"{model} unreadable"
    ledger.record(feature, model, data.get("usage"))
    try:
        return parse_json(text), ""
    except LLMUnavailable:
        return None, f"{model} not JSON"  # cut off mid-answer, usually: the next model may finish


_pool = ThreadPoolExecutor(max_workers=32, thread_name_prefix="focs-vision")


def _staggered(chain: list[str], ask, head_start: float) -> dict:
    """The models in ``chain`` raced with a head start: the first asked alone, the next one too once the first has
    taken ``head_start`` seconds or failed, and the first good answer wins. The slower call still finishes in the
    background (and is costed: it was paid for). Raises LLMUnavailable when none answers."""
    queue, running, tried = iter(chain), {}, []

    def launch() -> None:
        if (entry := next(queue, None)) is not None:  # each call keeps the request's context: its cost is the student's
            running[_pool.submit(contextvars.copy_context().run, ask, entry)] = entry

    launch()
    while running:
        done, _ = wait(running, timeout=head_start, return_when=FIRST_COMPLETED)
        if not done:
            launch()  # the first is slow: ask the next one too
            continue
        for f in done:
            running.pop(f)
            try:
                data, why = f.result()
            except LLMUnavailable as exc:
                data, why = None, str(exc)
            if data is not None:
                return data
            tried.append(why)
            launch()
    raise LLMUnavailable(f"vision models busy ({', '.join(tried)})")


def read_json(images: list[bytes], prompt: str, feature: str, max_tokens: int = 3000, timeout: float = 90.0,
              patient: bool = False, head_start: float | None = None) -> dict:
    """Ask the vision models one question about some images; the answer is JSON. Raises LLMUnavailable.

    Each model in VISION_MODEL is tried in turn when one is busy (429/5xx), retired (404), slow (``timeout`` seconds)
    or answers something unreadable; a single model gets one retry, and with ``patient`` every model but the last does
    (an overloaded Gemini usually answers a few seconds later, for half what the next model costs). With
    ``head_start`` (a student is waiting) the next model doesn't wait for a slow one to time out: see _staggered.
    No JSON mode: provider JSON mode drops the backslashes of LaTeX (\\frac arrives as "frac"), and parse_json repairs
    and reads plain output."""
    if not available():
        raise LLMUnavailable("no vision model configured")
    ensure_budget()
    content = [{"type": "text", "text": prompt}] + [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(img).decode()}} for img in images]
    chain = models() if len(models()) > 1 else models() * 2
    if patient:
        chain = [m for m in chain[:-1] for _ in (0, 1)] + chain[-1:]
    if head_start and len(set(chain)) > 1:
        return _staggered(chain, lambda entry: _ask(entry, content, max_tokens, timeout, feature), head_start)
    tried: list[str] = []
    for i, entry in enumerate(chain):
        if i and chain[i - 1] == entry:  # the same model again: give it a moment
            time.sleep(3)
        data, why = _ask(entry, content, max_tokens, timeout, feature)
        if data is not None:
            return data
        tried.append(why)
    raise LLMUnavailable(f"vision models busy ({', '.join(tried)})")


BOARD_TIMEOUT_S = 8.0  # per model: a good read takes 2-4 s, and a student waiting shouldn't wait 30 s for two slow ones
BOARD_PATIENT_TIMEOUT_S = 30.0  # in the background: Gemini 3.5 timed out at 8 s on 12 of 25 boards on 2026-10-20
# a student waiting: the next model is asked too once the first has taken this long. On 2026-10-23 gemini-3.1-flash-lite
# took 4-30 s on first boards while the next two models answered in 0.3-1.7 s
BOARD_HEAD_START_S = 3.0

BOARD_PROMPT = """This is one frame of a lecture video or a photo of a class board (blackboard, whiteboard, pen tablet or slide).
Copy out everything academic on it exactly as written, top to bottom.
- Math in LaTeX inside $...$. Keep every fraction as \\frac{..}{..} with its own numerator and denominator, and every
  power, sign and relation (>, <, \\ge, \\le, =, \\ne) exactly where it is. Never solve, simplify or correct anything.
- A question or problem statement word for word. Handwritten working: one step per line, as far as it is legible.
- Small labels written beside, above or below an expression (root values, arrows, "odd"/"even", ticks) go together
  on one line after it, never into its exponents or subscripts. A number line is one line of its points and one
  line of its signs.
- Plain lines only: no LaTeX environments (array, tabular, align) and no \\stackrel or \\underset.
- Leave out the video player, toolbars, logos, watermarks, channel and teacher names, and subtitles (the captions of
  what is being said, often in Hindi along the bottom).
Return JSON: {"board": "<the content, lines separated by \\n>"}, or {"board": ""} if nothing academic is on it."""


def read_board(jpeg: bytes, patient: bool = False) -> str | None:
    """What a lecture frame says, read by the vision model. Unlike line-by-line OCR it keeps a fraction's numerator
    over its denominator and the sign between two fractions. "" when there is nothing academic on the frame (the
    teacher's camera). None without a vision model or when it fails: the caller then goes by the OCR text alone.
    ``patient``: written in the background, so each model may take up to
    BOARD_PATIENT_TIMEOUT_S and gets a second try."""
    if not available():
        return None
    try:  # a student waiting can't: after BOARD_HEAD_START_S the next model is asked too, and the first answer wins
        data = read_json([jpeg], BOARD_PROMPT, "board_read", max_tokens=2000,
                         timeout=BOARD_PATIENT_TIMEOUT_S if patient else BOARD_TIMEOUT_S, patient=patient,
                         head_start=None if patient else BOARD_HEAD_START_S)
    except LLMUnavailable as exc:
        log.info("board read failed, using OCR text: %s", exc)
        return None
    return str(data.get("board") or "").strip()
