"""YouTube helpers for study rooms: video id, title (oEmbed, no API key) and caption windows.

Captions let room questions be about what the teacher said in the last few minutes rather than
the topic in general. Everything here is best-effort: a video without captions still works.
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache

import httpx

log = logging.getLogger("focs.youtube")
_ID = re.compile(r"(?:youtu\.be/|youtube(?:-nocookie)?\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/|v/))([A-Za-z0-9_-]{11})")


def video_id(url: str) -> str | None:
    url = (url or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url
    m = _ID.search(url)
    return m.group(1) if m else None


@lru_cache(maxsize=512)
def title(vid: str) -> str | None:
    try:
        r = httpx.get("https://www.youtube.com/oembed", params={"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"},
                      timeout=10)
        return r.json().get("title") if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None


@lru_cache(maxsize=64)
def _captions(vid: str) -> tuple[tuple[float, str], ...]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        api = YouTubeTranscriptApi()
        try:
            fetched = api.fetch(vid, languages=["en", "en-IN", "hi", "hi-IN"])
        except Exception:
            # any language the video has (auto-generated captions included)
            first = next(iter(api.list(vid)))
            fetched = first.fetch()
        return tuple((float(s.start), s.text.replace("\n", " ")) for s in fetched)
    except Exception as exc:  # no captions, blocked, package missing: questions fall back to the topic
        log.info("no captions for %s: %s", vid, type(exc).__name__)
        return ()


def caption_window(vid: str | None, position: float, span: float = 300) -> str:
    """What was said in the `span` seconds before `position` (empty string if unknown)."""
    if not vid:
        return ""
    lines = [text for start, text in _captions(vid) if position - span <= start <= position]
    return " ".join(lines)[-4000:]


def has_captions(vid: str | None) -> bool:
    return bool(vid and _captions(vid))
