"""The importer's "scan" stage on the GPU: find which PDF pages carry tagged past questions or answer keys.

Standalone (no app imports) so it can run in its own environment with the DirectML build of ONNX Runtime,
which uses any DirectX 12 GPU on Windows (NVIDIA, AMD, Intel) without installing CUDA:

    python -m venv gpuvenv
    gpuvenv\\Scripts\\pip install onnxruntime-directml rapidocr-onnxruntime pymupdf opencv-python-headless msvc-runtime
    gpuvenv\\Scripts\\python backend\\scripts\\scan_pyq_gpu.py

It writes the same data/pyq/.work/<pdf>/scan.json as `import_pyq.py --stage scan`, resuming where either left off.
"""
import glob
import os
import sys

if sys.platform == "win32":  # current MSVC DLLs (msvc-runtime) before onnxruntime/OpenCV, as in app/__init__.py
    import ctypes

    for dll in sorted(glob.glob(os.path.join(sys.prefix, "*.dll"))):
        try:
            ctypes.WinDLL(dll)
        except OSError:
            pass

import json  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import pymupdf  # noqa: E402
from rapidocr_onnxruntime import RapidOCR  # noqa: E402

ROOT = Path(__file__).resolve().parents[2] / "data" / "pyq"
WORK = ROOT / ".work"
TAG = re.compile(r"(AIEEE|JEE|NEET|AIPMT|IIT|MAIN|ADV|AIIMS|CBSE[- ]?PMT)[^\n]{0,30}(19|20)\d\d", re.I)
KEY = re.compile(r"ANSWER\s*KEY|Que\.?\s*\d+\s+\d+|ANSWERS", re.I)


def workdir(pdf: Path) -> Path:
    d = WORK / re.sub(r"[^\w.-]+", "_", pdf.stem)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def main() -> None:
    import onnxruntime as ort

    gpu = "DmlExecutionProvider" in ort.get_available_providers()
    print("ONNX Runtime providers:", ort.get_available_providers(), "→ GPU" if gpu else "→ CPU only")
    engine = RapidOCR()  # picks DirectML by itself when the DirectML build of ONNX Runtime is installed
    for pdf in sorted(p for p in ROOT.rglob("*.pdf") if ".work" not in p.parts):
        path = workdir(pdf) / "scan.json"
        done = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        doc = pymupdf.open(pdf)
        todo = [p for p in range(doc.page_count) if str(p) not in done]
        if not todo:
            continue
        print(f"{pdf.name}: {len(todo)} pages to scan", flush=True)
        t0 = time.time()
        for i, page in enumerate(todo, 1):
            text = doc[page].get_text()
            if len(text.strip()) < 80:  # a scanned page
                pix = doc[page].get_pixmap(dpi=100, colorspace=pymupdf.csGRAY)
                img = cv2.cvtColor(np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w), cv2.COLOR_GRAY2BGR)
                result, _ = engine(img)
                text = "\n".join(r[1] for r in result or [])
            done[str(page)] = {"tags": len(TAG.findall(text)), "key": bool(KEY.search(text)), "head": text[:160]}
            if i % 25 == 0 or i == len(todo):
                save(path, done)
                rate = i / (time.time() - t0)
                print(f"  {i}/{len(todo)} pages · {rate:.1f} pages/s", flush=True)


if __name__ == "__main__":
    main()
