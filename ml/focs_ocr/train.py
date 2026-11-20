"""Train FocsOCR on synthetic lecture-board lines.

    python -m focs_ocr.train --steps 30000 --batch 96

Checkpoints and metrics land in ml/runs/<name>/. At the end the best checkpoint is exported
to ONNX and copied into backend/app/assets/ocr/ where the API picks it up.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from . import __version__, charset
from .dataset import SynthLines, collate
from .metrics import score
from .model import FocsOCRNet

ML_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ML_ROOT.parent
DB_PATH = REPO_ROOT / "backend" / "focs.db"


def worker_init(_):
    # One thread per worker: OpenCV/numpy default to all cores and 8 workers x 12 threads thrash.
    import cv2
    cv2.setNumThreads(1)
    torch.set_num_threads(1)


def greedy_decode(logits: torch.Tensor, input_lens: torch.Tensor) -> list[tuple[str, float]]:
    probs = logits.float().softmax(-1)
    conf, idx = probs.max(-1)
    out = []
    for b in range(idx.shape[0]):
        n = int(input_lens[b])
        out.append(charset.decode_greedy(idx[b, :n].tolist(), conf[b, :n].tolist()))
    return out


@torch.no_grad()
def evaluate(model: nn.Module, batches, device) -> dict:
    model.eval()
    preds, gts = [], []
    for imgs, _, _, input_lens, texts in batches:
        with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"):
            logits = model(imgs.to(device, non_blocking=True))
        preds.extend(t for t, _ in greedy_decode(logits, input_lens))
        gts.extend(texts)
    model.train()
    result = score(preds, gts)
    result["examples"] = [{"gt": g, "pred": p} for p, g in list(zip(preds, gts))[:12]]
    return result


def build_val(size: int, batch: int, workers: int) -> list:
    ds = SynthLines(size, seed=20260930, db_path=DB_PATH, batch_size=batch)
    loader = DataLoader(ds, batch_size=batch, num_workers=workers, collate_fn=collate, worker_init_fn=worker_init)
    return list(loader)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=30000)
    ap.add_argument("--batch", type=int, default=96)
    ap.add_argument("--lr", type=float, default=1.5e-3)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--val-size", type=int, default=2000)
    ap.add_argument("--eval-every", type=int, default=1000)
    ap.add_argument("--name", default="focsocr-v1")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--no-export", action="store_true")
    args = ap.parse_args()

    # Widths are bucketed to multiples of 64 in collate(), so cuDNN only plans ~20 shapes.
    torch.backends.cudnn.benchmark = False
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    run_dir = ML_ROOT / "runs" / args.name
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = run_dir / "metrics.jsonl"

    model = FocsOCRNet(charset.NUM_CLASSES).to(device)
    params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=args.steps, pct_start=0.06,
                                                div_factor=20, final_div_factor=200)
    ctc = nn.CTCLoss(blank=charset.BLANK, zero_infinity=True)
    # fp16 (not bf16): cuDNN's fused LSTM kernel only runs in fp16/fp32; under bf16 autocast the
    # BiLSTM silently unrolls into thousands of small matmuls and training gets ~3x slower.
    scaler = torch.amp.GradScaler(device.type, enabled=device.type == "cuda")

    start_step, best_cer = 0, math.inf
    if args.resume and (run_dir / "last.pt").exists():
        ck = torch.load(run_dir / "last.pt", map_location=device)
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"]); sched.load_state_dict(ck["sched"])
        start_step, best_cer = ck["step"], ck.get("best_cer", math.inf)
        print(f"resumed from step {start_step}")
    elif metrics_path.exists():
        metrics_path.unlink()

    print(f"device={device} ({torch.cuda.get_device_name(0) if device.type == 'cuda' else 'cpu'}) "
          f"params={params/1e6:.2f}M classes={charset.NUM_CLASSES}")
    print("building validation set ...")
    val = build_val(args.val_size, 64, args.workers)

    total = args.steps * args.batch
    train_ds = SynthLines(total, seed=7, db_path=DB_PATH, ramp=int(total * 0.25), batch_size=args.batch)
    indices = list(range(start_step * args.batch, total))
    worker_opts = {"persistent_workers": True, "prefetch_factor": 4} if args.workers > 0 else {}
    loader = DataLoader(
        torch.utils.data.Subset(train_ds, indices), batch_size=args.batch, shuffle=False,
        num_workers=args.workers, collate_fn=collate, pin_memory=device.type == "cuda",
        drop_last=True, worker_init_fn=worker_init, **worker_opts,
    )

    t0 = time.time()
    ema = None
    step = start_step
    for imgs, targets, target_lens, input_lens, _ in loader:
        imgs = imgs.to(device, non_blocking=True)
        with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"):
            logits = model(imgs)
        logp = logits.float().log_softmax(-1).transpose(0, 1)  # T, B, C for CTC
        loss = ctc(logp, targets.to(device), input_lens.to(device), target_lens.to(device))
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        scaler.step(opt); scaler.update(); sched.step()
        step += 1
        ema = loss.item() if ema is None else ema * 0.98 + loss.item() * 0.02

        if step % 100 == 0:
            elapsed = time.time() - t0
            rate = (step - start_step) * args.batch / max(elapsed, 1e-6)
            eta = (args.steps - step) * args.batch / max(rate, 1e-6) / 60
            print(f"step {step:>6}/{args.steps}  loss {ema:.4f}  lr {sched.get_last_lr()[0]:.2e}  "
                  f"{rate:,.0f} img/s  eta {eta:.1f} min", flush=True)
            with metrics_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"step": step, "loss": round(ema, 5), "lr": sched.get_last_lr()[0]}) + "\n")

        if step % args.eval_every == 0 or step == args.steps:
            if device.type == "cuda":
                torch.cuda.empty_cache()
            res = evaluate(model, val, device)
            improved = res["cer"] < best_cer
            best_cer = min(best_cer, res["cer"])
            print(f"  eval @ {step}: CER {res['cer']:.4f}  WER {res['wer']:.4f}  line-acc {res['line_acc']:.3f}"
                  f"{'  * best' if improved else ''}")
            for ex in res["examples"][:4]:
                print(f"     gt: {ex['gt']!r}\n     pr: {ex['pred']!r}")
            with metrics_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"step": step, "eval": {k: res[k] for k in ('cer', 'wer', 'line_acc')}}) + "\n")
            state = {"model": model.state_dict(), "opt": opt.state_dict(), "sched": sched.state_dict(),
                     "step": step, "best_cer": best_cer, "val": res, "charset": charset.CHARS}
            torch.save(state, run_dir / "last.pt")
            if improved:
                torch.save({"model": model.state_dict(), "step": step, "val": res, "charset": charset.CHARS},
                           run_dir / "best.pt")
        if step >= args.steps:
            break

    train_minutes = (time.time() - t0) / 60
    print(f"training finished in {train_minutes:.1f} min, best CER {best_cer:.4f}")
    summary = {
        "version": __version__, "params": params, "steps": step, "batch": args.batch,
        "samples_seen": step * args.batch, "train_minutes": round(train_minutes, 1),
        "device": torch.cuda.get_device_name(0) if device.type == "cuda" else "cpu",
    }
    (run_dir / "train_summary.json").write_text(json.dumps(summary, indent=2))
    if not args.no_export:
        from .export import export_run
        export_run(run_dir)


if __name__ == "__main__":
    main()
