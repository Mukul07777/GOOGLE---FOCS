"""Export the best checkpoint to ONNX + a model card the API/UI can display.

    python -m focs_ocr.export --run runs/focsocr-v1
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import date
from pathlib import Path

import numpy as np
import torch

from . import __version__, charset
from .imaging import DOWNSAMPLE, HEIGHT
from .model import ExportWrapper, FocsOCRNet

ML_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ML_ROOT.parent / "backend" / "app" / "assets" / "ocr"


def _training_curve(metrics_path: Path, max_points: int = 120) -> tuple[list, list]:
    loss_by_step, eval_by_step = {}, {}
    if metrics_path.exists():
        # keyed by step: a resumed run re-logs steps after its last checkpoint; the latest wins
        for line in metrics_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if "loss" in row:
                loss_by_step[row["step"]] = {"step": row["step"], "loss": row["loss"]}
            if "eval" in row:
                eval_by_step[row["step"]] = {"step": row["step"], **row["eval"]}
    loss = [loss_by_step[k] for k in sorted(loss_by_step)]
    evals = [eval_by_step[k] for k in sorted(eval_by_step)]
    if len(loss) > max_points:
        stride = len(loss) / max_points
        loss = [loss[int(i * stride)] for i in range(max_points)] + [loss[-1]]
    return loss, evals


def export_run(run_dir: Path, out_dir: Path = ASSET_DIR) -> Path:
    run_dir = Path(run_dir)
    ck = torch.load(run_dir / "best.pt", map_location="cpu")
    net = FocsOCRNet(charset.NUM_CLASSES)
    net.load_state_dict(ck["model"])
    net.eval()
    model = ExportWrapper(net).eval()

    out_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = out_dir / "focsocr.onnx"
    dummy = torch.randn(1, 1, HEIGHT, 256)
    export_kwargs = dict(
        input_names=["image"], output_names=["probs"], opset_version=17,
        dynamic_axes={"image": {0: "batch", 3: "width"}, "probs": {0: "batch", 1: "frames"}},
    )
    try:
        torch.onnx.export(model, (dummy,), str(onnx_path), dynamo=False, **export_kwargs)
    except TypeError:  # older torch without the dynamo flag
        torch.onnx.export(model, (dummy,), str(onnx_path), **export_kwargs)

    # parity check: ONNX Runtime must agree with PyTorch on a different width
    import onnxruntime as ort

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    probe = torch.randn(2, 1, HEIGHT, 4 * 97)
    with torch.no_grad():
        ref = model(probe).numpy()
    got = sess.run(None, {"image": probe.numpy()})[0]
    max_diff = float(np.abs(ref - got).max())
    assert max_diff < 1e-3, f"ONNX parity failed: {max_diff}"

    charset.save(out_dir / "charset.json")
    loss_curve, eval_curve = _training_curve(run_dir / "metrics.jsonl")
    summary_path = run_dir / "train_summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    val = ck.get("val", {})
    card = {
        "name": "FocsOCR",
        "version": __version__,
        "exported": date.today().isoformat(),
        "architecture": "ResNet-style CNN (4 stages) → 2-layer BiLSTM (192) → CTC",
        "input": {"height": HEIGHT, "channels": 1, "stride": DOWNSAMPLE},
        "params": sum(p.numel() for p in net.parameters()),
        "charset_size": len(charset.CHARS),
        "best_step": ck.get("step"),
        "validation": {k: val.get(k) for k in ("cer", "wer", "line_acc", "n")},
        "examples": val.get("examples", [])[:8],
        "training": summary,
        "loss_curve": loss_curve,
        "eval_curve": eval_curve,
        "data": {
            "type": "synthetic, rendered on the fly",
            "styles": ["chalkboard", "whiteboard", "pen tablet", "slides", "notebook", "code screen"],
            "degradations": ["capture down-scaling", "JPEG/video compression", "blur", "noise",
                             "rotation/shear", "lighting", "imperfect detector crops"],
        },
        "onnx_parity_max_abs_diff": max_diff,
    }
    (out_dir / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.copy2(onnx_path, run_dir / "focsocr.onnx")
    print(f"exported {onnx_path} ({onnx_path.stat().st_size/1e6:.1f} MB), parity diff {max_diff:.2e}")
    return onnx_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=str(ML_ROOT / "runs" / "focsocr-v1"))
    export_run(Path(ap.parse_args().run))
