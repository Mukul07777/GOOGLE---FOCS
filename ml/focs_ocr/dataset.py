"""On-the-fly synthetic dataset + CTC collate."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

from . import charset
from .corpus import Corpus
from .imaging import DOWNSAMPLE, HEIGHT, prepare_line
from .synth import LineRenderer, discover_fonts

WIDTH_BUCKET = 64  # pad batch width to a multiple of this so the GPU sees few distinct shapes
MAX_TRAIN_WIDTH = 1024
# Every sample in a batch draws from the same text-length band, so batch images have similar
# widths: far less padding (wasted FLOPs) and a bounded, predictable GPU memory peak.
LENGTH_BANDS = [(1, 10), (8, 20), (16, 32), (28, 48)]
BAND_WEIGHTS = [0.22, 0.32, 0.30, 0.16]


class SynthLines(Dataset):
    """Deterministic per-index samples: index ``i`` always renders the same image.

    ``ramp`` samples of curriculum: difficulty climbs from 0.3 to 1.0 over the first
    ``ramp`` indices so early training sees cleaner lines.
    """

    def __init__(self, length: int, seed: int, db_path: Path | None = None, ramp: int = 0, batch_size: int = 64):
        self.length = length
        self.seed = seed
        self.db_path = db_path
        self.ramp = ramp
        self.batch_size = batch_size
        self._renderer: LineRenderer | None = None
        self._corpus: Corpus | None = None

    def _lazy(self):
        # fonts/corpus are built inside each worker process (cheap to pickle the dataset)
        if self._renderer is None:
            self._renderer = LineRenderer(discover_fonts())
            self._corpus = Corpus(self.db_path)

    def __len__(self):
        return self.length

    def difficulty(self, i: int) -> float:
        if self.ramp <= 0:
            return 1.0
        return float(min(1.0, 0.3 + 0.7 * i / self.ramp))

    def __getitem__(self, i: int):
        self._lazy()
        band_rng = np.random.default_rng((self.seed, 10_000_019, i // self.batch_size))
        lo, hi = LENGTH_BANDS[int(band_rng.choice(len(LENGTH_BANDS), p=BAND_WEIGHTS))]
        rng = np.random.default_rng((self.seed, i))
        for _ in range(10):
            text = self._corpus.sample(rng, max_len=hi, min_len=lo)
            img = self._renderer.render(text, rng, self.difficulty(i))
            if img is None:
                continue
            arr = prepare_line(img)
            if arr.shape[1] > MAX_TRAIN_WIDTH:
                continue
            # CTC needs at least one frame per label (+1 between repeats)
            frames = arr.shape[1] // DOWNSAMPLE
            repeats = sum(1 for a, b in zip(text, text[1:]) if a == b)
            if frames >= len(text) + repeats + 2:
                return arr, text
        arr = prepare_line(np.full((HEIGHT, 64), 255, np.uint8))
        return arr, ""


def collate(batch):
    widths = [a.shape[1] for a, _ in batch]
    max_w = int(np.ceil(max(widths) / WIDTH_BUCKET) * WIDTH_BUCKET)
    imgs = torch.ones(len(batch), 1, HEIGHT, max_w)  # pad with "paper" (+1.0 = white)
    targets, target_lens, input_lens, texts = [], [], [], []
    for k, (arr, text) in enumerate(batch):
        imgs[k, 0, :, : arr.shape[1]] = torch.from_numpy(arr)
        enc = charset.encode(text)
        targets.extend(enc)
        target_lens.append(len(enc))
        input_lens.append(max(1, arr.shape[1] // DOWNSAMPLE))
        texts.append(text)
    return (
        imgs,
        torch.tensor(targets, dtype=torch.long),
        torch.tensor(target_lens, dtype=torch.long),
        torch.tensor(input_lens, dtype=torch.long),
        texts,
    )
