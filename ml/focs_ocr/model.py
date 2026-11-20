"""FocsOCR network: residual CNN encoder → BiLSTM → CTC head.

Input  (B, 1, 48, W)  normalised grayscale line image, W multiple of 4 (padded)
Output (B, W/4, C)    per-frame class scores (C = charset + blank)
"""
from __future__ import annotations

import torch
from torch import nn


class ConvBNAct(nn.Sequential):
    def __init__(self, cin: int, cout: int, k=3, s=1, p=1):
        super().__init__(nn.Conv2d(cin, cout, k, s, p, bias=False), nn.BatchNorm2d(cout), nn.SiLU(inplace=True))


class ResBlock(nn.Module):
    def __init__(self, c: int):
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(c, c, 3, 1, 1, bias=False), nn.BatchNorm2d(c), nn.SiLU(inplace=True),
            nn.Conv2d(c, c, 3, 1, 1, bias=False), nn.BatchNorm2d(c),
        )
        self.act = nn.SiLU(inplace=True)

    def forward(self, x):
        return self.act(x + self.body(x))


class FocsOCRNet(nn.Module):
    def __init__(self, num_classes: int, hidden: int = 192, dropout: float = 0.15):
        super().__init__()
        # Cheap convs at full resolution, residual capacity only after the width is down to W/4.
        self.encoder = nn.Sequential(
            ConvBNAct(1, 32), nn.MaxPool2d(2, 2),                        # 24 x W/2
            ConvBNAct(32, 64), nn.MaxPool2d(2, 2),                       # 12 x W/4
            ConvBNAct(64, 128), ResBlock(128), nn.MaxPool2d((2, 1)),     # 6 x W/4
            ConvBNAct(128, 192), ResBlock(192), nn.MaxPool2d((2, 1)),    # 3 x W/4
            ConvBNAct(192, 256, k=(3, 1), p=0),                          # 1 x W/4
            nn.Dropout2d(dropout),
        )
        self.rnn = nn.LSTM(256, hidden, num_layers=2, bidirectional=True, batch_first=True, dropout=dropout)
        self.head = nn.Linear(hidden * 2, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        f = self.encoder(x)            # B, 256, 1, T
        f = f.squeeze(2).transpose(1, 2)  # B, T, 256
        f, _ = self.rnn(f)
        return self.head(f)             # B, T, C (logits)


class ExportWrapper(nn.Module):
    """Adds softmax so the ONNX graph emits probabilities directly."""

    def __init__(self, net: FocsOCRNet):
        super().__init__()
        self.net = net

    def forward(self, x):
        return torch.softmax(self.net(x), dim=-1)
