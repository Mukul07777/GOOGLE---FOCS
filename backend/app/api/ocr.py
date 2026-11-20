"""OCR Lab: run any image through the engines, compare them line by line, inspect the model card."""
import json
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.capture import _read_image
from app.core.config import settings
from app.core.deps import get_current_user
from app.core.ratelimit import limit
from app.models.user import User
from app.services.ocr import ocr_engine

router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.get("/model")
def model_info(user: User = Depends(get_current_user)):
    info = ocr_engine.status()
    bench = settings.OCR_MODEL_DIR / "benchmark.json"
    info["benchmark"] = json.loads(bench.read_text(encoding="utf-8")) if bench.exists() else None
    real = settings.OCR_MODEL_DIR / "benchmark_real.json"  # frames from real lectures and classrooms (scripts/benchmark_ocr.py --set real)
    info["benchmark_real"] = json.loads(real.read_text(encoding="utf-8")) if real.exists() else None
    return info


@router.post("/run", dependencies=[Depends(limit("ocr", 30))])
def run_ocr(
    image: UploadFile = File(...),
    engine: Literal["auto", "focs", "rapid"] = Form("auto"),
    user: User = Depends(get_current_user),
):
    img = _read_image(image)
    status = ocr_engine.status()
    if not status["engines"]:
        raise HTTPException(status_code=503, detail="No OCR engine is available on this server.")
    return ocr_engine.run(img, engine, keep_candidates=True).to_dict(include_candidates=True)
