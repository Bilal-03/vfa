"""Small supervised models. FinBERT is frozen; these layers are trained."""

import torch
from torch import nn


class ForecastModel(nn.Module):
    def __init__(self, tech_dim=14, mode="gated", hidden=16):
        super().__init__()
        self.mode = mode
        self.temporal = nn.LSTM(tech_dim, hidden, batch_first=True, bidirectional=True)
        self.text = nn.Sequential(nn.Linear(3, hidden * 2), nn.Tanh())
        self.gate = nn.Linear(3, 1)
        self.head = nn.Linear(hidden * (4 if mode == "concat" else 2), 3)

    def forward(self, x, news):
        _, (h, _) = self.temporal(x)
        t = torch.cat([h[-2], h[-1]], dim=1)
        s = self.text(news[:, :3])
        # news: positive, neutral, negative, age/168, log1p(count), disagreement, available
        if self.mode == "technical":
            z = t
        elif self.mode == "sentiment":
            z = s
        elif self.mode == "concat":
            z = torch.cat([t, s * news[:, 6:7]], dim=1)
        else:
            gate_inputs = news[:, 3:6].clone()
            if self.mode == "no_freshness":
                gate_inputs[:, 0] = 0
            g = torch.sigmoid(self.gate(gate_inputs))
            if self.mode != "no_mask":
                g = g * news[:, 6:7]
            z = (1 - g) * t + g * s
        return self.head(z)
