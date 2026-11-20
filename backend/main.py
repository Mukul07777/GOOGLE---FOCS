"""Entry point:  python main.py   (or: uvicorn main:app --reload)"""
import uvicorn

from app.core.config import settings
from app.main import app  # noqa: F401  (re-exported for `uvicorn main:app`)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, log_level="warning")
