"""OCR orchestration: detection → recognition (FocsOCR, PP-OCRv4, or a per-line ensemble)."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import asdict, dataclass, field

import cv2
import numpy as np
from PIL import Image

from app.core.config import settings
from app.services import images
from app.services.ocr.detector import DBNetDetector, MorphDetector, crop_quad, order_boxes

log = logging.getLogger("focs.ocr")

_CJK = re.compile(r"[⺀-鿿가-힯＀-￯]")
_FOCS_ONLY = set("αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΦΨΩ∞∫∑√≤≥≠≈±∓÷→←↔⇒⇔∂∇∝∈∀∃∴∵′″⊥∠∪∩⊂⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ₀₁₂₃₄₅₆₇₈₉½¼¾")
MAX_SIDE = 2200
_LATIN_WORD = re.compile(r"[A-Za-z]{3,}")


def _similar(a: str, b: str) -> float:
    from difflib import SequenceMatcher

    a, b = a.replace(" ", "").lower(), b.replace(" ", "").lower()
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


_SCRIPTS = set("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ₀₁₂₃₄₅₆₇₈₉₊₋½¼¾°")  # normal in formulas and chemistry
_FORMULA_MARKERS = set("=→⇒⇔≤≥≈∝≠")


def looks_like_garbage(text: str) -> bool:
    """Symbol soup: what the Latin+math recogniser makes of Devanagari subtitles, faces or logos."""
    chars = [c for c in text if not c.isspace()]
    if len(chars) < 6 or set(text) & _FORMULA_MARKERS:
        return False
    odd = sum(1 for c in chars
              if c not in _SCRIPTS and not (c.isascii() and (c.isalnum() or c in ".,:;()[]-+/'?!%&*")))
    return odd / len(chars) > 0.25 and len(_LATIN_WORD.findall(text)) < 2


@dataclass
class OcrLine:
    text: str
    confidence: float
    box: list[list[float]]
    engine: str
    candidates: dict[str, dict] = field(default_factory=dict)


@dataclass
class OcrResult:
    lines: list[OcrLine]
    engine: str
    detector: str
    elapsed_ms: int
    width: int
    height: int
    board: str

    @property
    def text(self) -> str:
        return "\n".join(l.text for l in self.lines)

    @property
    def confidence(self) -> float:
        if not self.lines:
            return 0.0
        weights = [max(1, len(l.text)) for l in self.lines]
        return float(np.average([l.confidence for l in self.lines], weights=weights))

    def to_dict(self, include_candidates: bool = False) -> dict:
        lines = []
        for l in self.lines:
            d = asdict(l)
            if not include_candidates:
                d.pop("candidates")
            d["confidence"] = round(d["confidence"], 3)
            lines.append(d)
        return {"text": self.text, "confidence": round(self.confidence, 3), "lines": lines, "engine": self.engine,
                "detector": self.detector, "elapsed_ms": self.elapsed_ms, "width": self.width,
                "height": self.height, "board": self.board}


# ---------------------------------------------------------------------------- image helpers
def decode_image(data: bytes) -> np.ndarray:
    img = images.open_image(data, MAX_SIDE)  # upright, and refused when it would unpack too big to hold
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    return np.asarray(img)


def phash(img: np.ndarray) -> int:
    """64-bit DCT perceptual hash — robust to compression noise, sensitive to new writing."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    dct = cv2.dct(small)[:8, :8]
    bits = (dct > np.median(dct[1:, 1:])).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def classify_board(img: np.ndarray) -> str:
    small = cv2.resize(img, (64, 36), interpolation=cv2.INTER_AREA).astype(np.float32)
    lum = float((small @ np.array([0.299, 0.587, 0.114], np.float32)).mean())
    r, g, b = small.reshape(-1, 3).mean(0)
    if lum < 90:
        return "chalkboard" if g > r + 8 and g > b else "dark board / pen tablet"
    if lum > 185:
        return "whiteboard / slide"
    return "slide / mixed"


# ---------------------------------------------------------------------------- engine
class OcrEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded = False
        self.detector = None
        self.focs = None
        self.rapid_rec = None
        self.errors: dict[str, str] = {}

    def _load(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            try:
                dbnet = DBNetDetector()
                self.detector, self.rapid_rec = dbnet, dbnet.rec
            except Exception as exc:  # rapidocr missing or failed to load
                self.errors["rapid"] = str(exc)
                log.warning("DBNet/PP-OCR unavailable (%s); using morphology detector", exc)
                self.detector = MorphDetector()
            try:
                from app.services.ocr.recognizer import FocsRecognizer

                if (settings.OCR_MODEL_DIR / "focsocr.onnx").exists():
                    self.focs = FocsRecognizer(settings.OCR_MODEL_DIR)
                else:
                    self.errors["focs"] = "model file not found — run train_ocr.bat"
            except Exception as exc:
                self.errors["focs"] = str(exc)
                log.warning("FocsOCR unavailable: %s", exc)
            self._loaded = True

    # -- info -----------------------------------------------------------------------------
    def status(self) -> dict:
        self._load()
        card_path = settings.OCR_MODEL_DIR / "model_card.json"
        card = json.loads(card_path.read_text(encoding="utf-8")) if card_path.exists() else None
        engines = []
        if self.focs and self.rapid_rec:
            engines.append("auto")
        if self.focs:
            engines.append("focs")
        if self.rapid_rec:
            engines.append("rapid")
        return {"default": self.resolve_mode(None), "engines": engines, "detector": getattr(self.detector, "name", None),
                "errors": self.errors, "model_card": card}

    def resolve_mode(self, mode: str | None) -> str:
        mode = (mode or settings.OCR_ENGINE or "auto").lower()
        if mode == "auto" and not (self.focs and self.rapid_rec):
            mode = "focs" if self.focs else "rapid"
        if mode == "focs" and not self.focs:
            mode = "rapid"
        if mode == "rapid" and not self.rapid_rec:
            mode = "focs"
        return mode

    def warm_up(self) -> None:
        """Load the models and read one small made-up line, at start-up: the first read after loading costs several
        CPU-seconds more than any later one, and it shouldn't land on a lecture's first board."""
        self.status()
        img = np.full((96, 480, 3), 255, np.uint8)
        cv2.putText(img, "F = m a", (20, 64), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 0, 0), 3)
        try:
            self.run(img)
        except Exception:  # noqa: BLE001 - a failed warm-up only means the first board is slower
            log.exception("OCR warm-up failed")

    # -- recognition ----------------------------------------------------------------------
    def _rapid(self, crops: list[np.ndarray]) -> list[tuple[str, float]]:
        # PP-OCR expects BGR
        res, _ = self.rapid_rec([c[..., ::-1].copy() if c.ndim == 3 else c for c in crops])
        out = []
        for item in res:
            text, score = str(item[0]), float(item[1])
            if _CJK.search(text):  # Chinese-English model hallucinating CJK on handwriting
                text = _CJK.sub("", text).strip()
                score *= 0.6
            out.append((text, score))
        return out

    @staticmethod
    def _pick(focs: tuple[str, float], rapid: tuple[str, float],
              margin: float | None = None, math_bonus: float | None = None) -> tuple[str, float, str]:
        (tf, cf), (tr, cr) = focs, rapid
        if not tf:
            return tr, cr, "rapid"
        if not tr:
            return tf, cf, "focs"
        if tf.replace(" ", "") == tr.replace(" ", ""):
            return (tf, max(cf, cr), "focs") if cf >= cr else (tr, max(cf, cr), "rapid")
        # PP-OCR's English charset has no Greek letters / super- and subscripts; when FocsOCR reads
        # them with reasonable confidence it is almost certainly seeing math PP-OCR cannot express.
        margin = settings.OCR_ENSEMBLE_MARGIN if margin is None else margin
        math_bonus = settings.OCR_MATH_BONUS if math_bonus is None else math_bonus
        score = cf + margin + (math_bonus if set(tf) & _FOCS_ONLY and cf >= 0.6 else 0.0)
        return (tf, cf, "focs") if score >= cr else (tr, cr, "rapid")

    def run(self, img: np.ndarray, mode: str | None = None, keep_candidates: bool = False) -> OcrResult:
        self._load()
        mode = self.resolve_mode(mode)
        t0 = time.perf_counter()
        h, w = img.shape[:2]
        boxes = order_boxes(self.detector.detect(img)) if self.detector else []
        crops = [crop_quad(img, b) for b in boxes]

        focs_res = self.focs.recognize(crops) if self.focs and mode in ("auto", "focs") else [("", 0.0)] * len(crops)
        rapid_res = self._rapid(crops) if self.rapid_rec and mode in ("auto", "rapid") and crops else [("", 0.0)] * len(crops)

        lines: list[OcrLine] = []
        for box, fr, rr in zip(boxes, focs_res, rapid_res):
            if mode == "auto":
                # Strong disagreement with no confident engine = neither can read it (subtitles in
                # another script, a face, a logo): drop rather than invent text.
                if max(fr[1], rr[1]) < 0.85 and (not fr[0] or not rr[0] or _similar(fr[0], rr[0]) < 0.4):
                    continue
                text, conf, used = self._pick(fr, rr)
            elif mode == "focs":
                (text, conf), used = fr, "focs"
            else:
                (text, conf), used = rr, "rapid"
            text = " ".join(text.split())
            if not text or conf < settings.OCR_MIN_LINE_CONFIDENCE or looks_like_garbage(text):
                continue
            candidates = {"focs": {"text": fr[0], "confidence": round(fr[1], 3)},
                          "rapid": {"text": rr[0], "confidence": round(rr[1], 3)}} if keep_candidates else {}
            lines.append(OcrLine(text, float(conf), box.round(1).tolist(), used, candidates))

        return OcrResult(lines=lines, engine=mode, detector=getattr(self.detector, "name", "none"),
                         elapsed_ms=int((time.perf_counter() - t0) * 1000), width=w, height=h,
                         board=classify_board(img))


ocr_engine = OcrEngine()
