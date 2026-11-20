"""A fingerprint of the code a server process is running, so the launcher can tell a stale server from a current one."""
from __future__ import annotations

import hashlib

from app.core.config import BACKEND_DIR, settings


def fingerprint() -> str:
    h = hashlib.sha1(settings.APP_VERSION.encode())
    for path in sorted((BACKEND_DIR / "app").rglob("*.py")):
        st = path.stat()
        h.update(f"{path.relative_to(BACKEND_DIR).as_posix()}:{st.st_size}:{int(st.st_mtime)}".encode())
    index = settings.FRONTEND_DIST / "index.html"
    if index.exists():
        h.update(str(int(index.stat().st_mtime)).encode())
    return h.hexdigest()[:12]
