"""Board snapshot storage: a private Supabase Storage bucket when configured, else a local folder.

Paths are always relative ("frames/<session>/<uuid>.jpg") and identical in both backends, so
snapshots can move between them without touching the database.
"""
from __future__ import annotations

import io
import logging
import shutil
import uuid
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

from app.core.config import settings

log = logging.getLogger("focs.storage")
FRAMES_DIR = settings.STORAGE_DIR / "frames"
_http: httpx.Client | None = None


def _client() -> httpx.Client:
    global _http
    if _http is None:
        key = settings.supabase_server_key
        _http = httpx.Client(base_url=settings.SUPABASE_URL.rstrip("/") + "/storage/v1", timeout=30,
                             headers={"apikey": key, "Authorization": f"Bearer {key}"},
                             transport=httpx.HTTPTransport(retries=3))  # retry dropped connections
    return _http


def backend() -> str:
    return "supabase" if settings.use_supabase_storage else "local"


def ensure_bucket() -> None:
    """Create the private snapshot bucket on first use (no-op when it exists)."""
    if not settings.use_supabase_storage:
        return
    try:
        r = _client().get(f"/bucket/{settings.SUPABASE_BUCKET}")
        if r.status_code == 200:
            return
        r = _client().post("/bucket", json={"id": settings.SUPABASE_BUCKET, "name": settings.SUPABASE_BUCKET, "public": False})
        if r.status_code not in (200, 201, 409):
            log.warning("could not create bucket %s: %s %s", settings.SUPABASE_BUCKET, r.status_code, r.text[:200])
    except httpx.HTTPError as exc:  # never block startup on storage; uploads retry per snapshot
        log.warning("Supabase Storage not reachable right now (%s) - snapshots will retry", exc)


def _encode(img: np.ndarray, max_side: int) -> bytes:
    pil = Image.fromarray(img)
    pil.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=82, optimize=True)
    return buf.getvalue()


def _put(rel_path: str, data: bytes) -> None:
    if settings.use_supabase_storage:
        r = _client().post(f"/object/{settings.SUPABASE_BUCKET}/{rel_path}", content=data,
                           headers={"Content-Type": "image/jpeg", "x-upsert": "true"})
        r.raise_for_status()
    else:
        path = settings.STORAGE_DIR / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def jpeg(img: np.ndarray, max_side: int = 1280) -> bytes:
    """A frame as the JPEG that save_frame stores."""
    return _encode(img, max_side)


def save_frame(session_id: int, img: np.ndarray, max_side: int = 1280) -> str | None:
    """Store a JPEG snapshot and return its relative path (None if the upload failed)."""
    rel = f"frames/{session_id}/{uuid.uuid4().hex}.jpg"
    try:
        _put(rel, _encode(img, max_side))
        return rel
    except Exception as exc:  # a missing snapshot must never lose the student's notes
        log.warning("snapshot upload failed: %s", exc)
        return None


def read(rel_path: str | None) -> bytes | None:
    if not rel_path or ".." in rel_path:
        return None
    if settings.use_supabase_storage:
        try:
            r = _client().get(f"/object/{settings.SUPABASE_BUCKET}/{rel_path}")
            if r.status_code == 200:
                return r.content
        except httpx.HTTPError as exc:
            log.warning("snapshot download failed: %s", exc)
        local = resolve(rel_path)  # snapshots saved before the switch that were not uploaded yet
        return local.read_bytes() if local else None
    local = resolve(rel_path)
    return local.read_bytes() if local else None


def resolve(rel_path: str | None) -> Path | None:
    if not rel_path:
        return None
    path = (settings.STORAGE_DIR / rel_path).resolve()
    root = settings.STORAGE_DIR.resolve()
    if root not in path.parents or not path.exists():
        return None
    return path


def delete(rel_path: str | None) -> None:
    if not rel_path:
        return
    if settings.use_supabase_storage:
        try:
            _client().request("DELETE", f"/object/{settings.SUPABASE_BUCKET}", json={"prefixes": [rel_path]})
        except httpx.HTTPError as exc:
            log.warning("snapshot delete failed: %s", exc)
    path = resolve(rel_path)
    if path:
        path.unlink(missing_ok=True)


def delete_session(session_id: int) -> None:
    """Remove every snapshot of a deleted lecture (individual files are deleted with their notes)."""
    shutil.rmtree(FRAMES_DIR / str(session_id), ignore_errors=True)


def upload_local_snapshots(rel_paths: list[str]) -> int:
    """Copy snapshots that exist only on disk into the bucket (used once after switching)."""
    if not settings.use_supabase_storage:
        return 0
    done = 0
    for rel in rel_paths:
        path = resolve(rel)
        if path:
            try:
                _put(rel, path.read_bytes())
                done += 1
            except Exception as exc:
                log.warning("could not upload %s: %s", rel, exc)
    return done
