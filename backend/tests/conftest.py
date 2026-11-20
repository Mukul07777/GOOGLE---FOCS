import io
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Isolated database/storage and no LLM, set before the app is imported.
_TMP = Path(tempfile.mkdtemp(prefix="focs-test-"))
# FOCS_TEST_DATABASE_URL runs the suite against a real Postgres (must be an empty database)
os.environ["DATABASE_URL"] = os.environ.get("FOCS_TEST_DATABASE_URL") or f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(_TMP / "storage")
os.environ["GROQ_API_KEY"] = ""
os.environ["SENTRY_DSN"] = ""  # tests never send error reports
os.environ["LLM_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["LLM_FALLBACK_API_KEY"] = ""
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_ANON_KEY"] = ""
os.environ["SUPABASE_SECRET_KEY"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["SUPABASE_DB_URL"] = ""
os.environ["RAZORPAY_KEY_ID"] = ""  # tests pay with the dev button, never through a real Razorpay account
os.environ["RAZORPAY_KEY_SECRET"] = ""
os.environ["RAZORPAY_WEBHOOK_SECRET"] = ""
os.environ["LLM_BASE_URL"] = "https://llm.invalid/v1"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-at-least-32-bytes-long"
os.environ["DEV_FEATURES_LOCAL_ONLY"] = "false"  # the test client isn't a loopback address
os.environ["LIVE_WRITE_BEHIND"] = "false"  # board notes written while the frame waits (one test turns it back on)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth(client):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": "asha@example.com", "full_name": "Asha Verma",
                                                 "password": "correct-horse-1", "exam_target": "jee"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def board_png(lines: list[str], dark: bool = True, size=(1280, 720)) -> bytes:
    """Render a lecture-board-like image for OCR tests."""
    from PIL import Image, ImageDraw, ImageFont

    bg, fg = ((28, 52, 42), (240, 240, 235)) if dark else ((250, 250, 250), (20, 30, 120))
    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 54)
    except OSError:
        font = ImageFont.load_default()
    y = 80
    for line in lines:
        draw.text((90, y), line, font=font, fill=fg)
        y += 100
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """Each test starts with empty rate-limit buckets (the suite registers many users from one IP)."""
    from app.core import ratelimit

    ratelimit.reset()
