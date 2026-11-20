# FocsOCR — model card & training guide

FocsOCR is the text-line recogniser behind Focs. Generic OCR models are trained on documents and
scene text; lecture boards are different: chalk grain, marker glare, pen-tablet canvases, compressed
video frames, and a lot of mathematics. FocsOCR is trained for exactly that.

## Model

| | |
| --- | --- |
| Task | Single text line → string (CTC). Line **detection** is done by PP-OCRv4 DBNet (or a morphology fallback) |
| Architecture | CNN 1→32→64 (stride 4 in width) → 128/192 channel residual stages → (3×1) conv → 2-layer BiLSTM (192) → linear |
| Parameters | 3.08 M · ONNX file 12 MB · CPU inference via ONNX Runtime |
| Input | grayscale, 48 px high, width ∝ aspect ratio (≤ 1280 px), polarity-normalised so light-on-dark and dark-on-light look the same |
| Output | 192 classes (191 symbols + CTC blank), greedy decoding, per-character confidence |
| Charset | printable ASCII · Greek `αβγδεθλμπρστφωΔΣΩ…` · `∞ ∫ ∑ √ ≤ ≥ ≠ ≈ ± ∓ × ÷ → ← ⇒ ⇔ ∂ ∇ ° ∝ ∈ ∀ ∃ ∴ ∵ ⊥ ∠ ∪ ∩ ⊂` · `⁰–⁹ ⁺ ⁻ ⁿ ₀–₉` · `½ ¼ ¾` |

## Data (synthetic, rendered on the fly)

Every training line is generated at load time (`focs_ocr/synth.py`), so the model never sees the same
image twice:

* **Text** (`corpus.py`): textbook formulas and chemistry, randomised equations, exam phrasing
  ("Q.14", "Assertion (A):", "Take g = 10 m/s²"), 300+ syllabus terms, the 10k most common English
  words, Hinglish board words, random symbol soup, and clean lines from existing Focs notes.
* **Styles**: chalkboard · whiteboard · pen tablet (PW/Unacademy-style dark canvas) · slides ·
  ruled notebook · code editor.
* **Fonts**: 61 — 30 open fonts pulled from `google/fonts` on GitHub (16 handwriting) plus Windows
  system fonts. Each text is only rendered with fonts that actually contain its glyphs.
* **Degradations**: capture down-scaling to 14–56 px line height, JPEG/video compression, blur,
  motion blur, noise, rotation/shear, uneven lighting, detector-style crops (tight, loose, clipped),
  and ascenders/descenders poking in from neighbouring lines.
* **Curriculum**: difficulty ramps from clean to fully degraded over the first 25% of training.

## Training

```bat
train_ocr.bat                    :: full run: 22,000 steps × 80 = 1.76 M lines (~1 h on RTX 4050)
train_ocr.bat --steps 3000       :: quick run
```

* AdamW + OneCycle (max LR 1.5e-3), fp16 autocast with gradient scaling, grad-clip 5.
* Batches are **length-banded** (every sample in a batch comes from the same text-length band) and
  padded to multiples of 64 px — this cut padding waste and GPU memory enough to run 4× faster on a
  6 GB laptop GPU.
* fp16, not bf16: cuDNN's fused LSTM kernel doesn't run in bf16, and the unrolled fallback is ~3× slower.
* Checkpoints, metrics and the ONNX export land in `ml/runs/focsocr-v1/`; the best checkpoint is
  exported to `backend/app/assets/ocr/` together with `charset.json` and `model_card.json`
  (an ONNX-vs-PyTorch parity check runs on export).

## Evaluation

**Validation** — 2,000 held-out synthetic lines (all six styles, full degradation), best checkpoint
(step 20,000 of 22,000; 1.76 M lines seen, 63 min on an RTX 4050):

| CER | WER | Exact lines |
| --- | --- | --- |
| **1.43 %** | 3.61 % | 91.2 % |

**End-to-end frame benchmark** — 240 full 1280×720 lecture frames, 1,075 lines, rendered with a seed
never used in training and degraded as whole frames (720p/480p re-scaling + video JPEG) rather than
line by line. Detection (PP-OCRv4 DBNet) is shared, so this compares recognisers; whitespace ignored.
Reproduce with `backend\.venv\Scripts\python backend\scripts\benchmark_ocr.py`.

| Engine | CER ↓ | Exact lines ↑ | CPU time / frame |
| --- | --- | --- | --- |
| **FocsOCR** | **0.48 %** | **96.9 %** | 652 ms |
| Ensemble (FocsOCR + PP-OCRv4) | 0.51 % | 96.7 % | 1,304 ms |
| PP-OCRv4 (en/ch) | 7.27 % | 63.3 % | 674 ms |

Accuracy refreshed 1 Oct 2026 (with the subtitle/garbage filters). CPU times were measured before detection
moved to a 1024 px copy, which is about 2.3x faster.

CER by style, FocsOCR vs PP-OCRv4 (30 Sep run): chalkboard 0.9 % vs 8.3 % · whiteboard 0.2 % vs 7.8 % ·
pen tablet 0.2 % vs 7.0 % · slides 0.6 % vs 7.4 % · notebook 0.1 % vs 7.9 % · code screen 0.8 % vs 6.7 %.

**Read these numbers honestly.** The benchmark is synthetic and in-distribution for FocsOCR, and a
large share of PP-OCRv4's errors are symbols its charset cannot express (Greek letters, super/subscripts,
`√ ∫ ≤ ∝`). On real handwriting, which varies more than any font, expect FocsOCR's error rate to be
higher; that is why the default engine keeps PP-OCRv4 in the loop as an ensemble.

## Limitations

* Latin script only — Devanagari (Hindi) boards are not read yet.
* Trained on synthetic data; real handwriting varies more than fonts do. Collecting a few thousand
  real board crops (Focs already stores snapshots) and fine-tuning is the next step.
* Diagrams, graphs and 2-D math layout (stacked fractions, matrices) are out of scope; those lines
  are read left-to-right.
