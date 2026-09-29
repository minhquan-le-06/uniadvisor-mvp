"""Encoder + LoRA + typed heads.

Base: a small multilingual cross-encoder (default `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`,
Apache-2.0, 12 layers x 384, XLM-R tokenizer that handles Vietnamese). The base weights stay frozen;
LoRA adapters are trained on the attention/FFN projections, plus a shared projection and one head
per question:

  choice: softmax over K labels + 'insufficient'
  bool:   2 sigmoids -> P(insufficient), P(yes | sufficient)
  score:  CORAL ordinal head (shared weight, ordered thresholds) for levels 1..5 + an 'insufficient' sigmoid

All heads output a full distribution over (labels..., insufficient); temperature scaling (one T per
question, fitted on val) is applied to the logits.
"""

from __future__ import annotations

import math

import torch
import torch.nn.functional as F
from torch import nn

from uniadvisor.slm.questions import QUESTIONS, Question

DEFAULT_BASE = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


class LoRALinear(nn.Module):
    def __init__(self, base: nn.Linear, r: int = 16, alpha: int = 32, dropout: float = 0.05):
        super().__init__()
        self.base = base
        for p in self.base.parameters():
            p.requires_grad = False
        self.r, self.scale = r, alpha / r
        self.A = nn.Parameter(torch.empty(r, base.in_features))
        self.B = nn.Parameter(torch.zeros(base.out_features, r))
        nn.init.kaiming_uniform_(self.A, a=math.sqrt(5))
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.base(x) + (self.drop(x) @ self.A.t() @ self.B.t()) * self.scale


def inject_lora(module: nn.Module, targets: tuple[str, ...], r: int, alpha: int, dropout: float) -> int:
    n = 0
    for name, child in list(module.named_children()):
        if isinstance(child, nn.Linear) and name in targets:
            setattr(module, name, LoRALinear(child, r, alpha, dropout))
            n += 1
        else:
            n += inject_lora(child, targets, r, alpha, dropout)
    return n


class OrdinalHead(nn.Module):
    """CORAL: logit_k = w.h + b_k, with b_1 > b_2 > ... so P(level > k) decreases in k."""

    def __init__(self, hidden: int, levels: int):
        super().__init__()
        self.w = nn.Linear(hidden, 1, bias=False)
        self.b1 = nn.Parameter(torch.tensor(1.5))
        self.deltas = nn.Parameter(torch.zeros(levels - 2))
        self.ins = nn.Linear(hidden, 1)

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        b = torch.cat([self.b1.view(1), self.b1 - torch.cumsum(F.softplus(self.deltas) + 0.3, 0)])
        return torch.cat([self.w(h) + b, self.ins(h)], dim=-1)  # [N, levels-1 + 1]


class TypedHeadModel(nn.Module):
    def __init__(self, base_name: str = DEFAULT_BASE, questions: list[Question] = QUESTIONS, lora_r: int = 16,
                 lora_alpha: int = 32, lora_dropout: float = 0.05,
                 lora_targets: tuple[str, ...] = ("query", "key", "value", "dense"), dropout: float = 0.1,
                 local_files_only: bool = False):
        super().__init__()
        from transformers import AutoModel

        self.encoder = AutoModel.from_pretrained(base_name, local_files_only=local_files_only)
        for p in self.encoder.parameters():
            p.requires_grad = False
        self.n_lora = inject_lora(self.encoder.encoder, lora_targets, lora_r, lora_alpha, lora_dropout)
        hidden = self.encoder.config.hidden_size
        self.proj = nn.Sequential(nn.Dropout(dropout), nn.Linear(2 * hidden, hidden), nn.GELU(), nn.Dropout(dropout))
        self.questions = {q.id: q for q in questions}
        self.heads = nn.ModuleDict()
        for q in questions:
            if q.kind == "choice":
                self.heads[q.id] = nn.Linear(hidden, len(q.labels) + 1)
            elif q.kind == "bool":
                self.heads[q.id] = nn.Linear(hidden, 2)
            elif q.kind == "score":
                self.heads[q.id] = OrdinalHead(hidden, len(q.labels))
        self.register_buffer("temperature", torch.ones(len(questions)))
        self.q_index = {q.id: i for i, q in enumerate(questions)}

    def trainable_state(self) -> dict[str, torch.Tensor]:
        keep = {n for n, p in self.named_parameters() if p.requires_grad} | {"temperature"}
        return {k: v.detach().cpu() for k, v in self.state_dict().items() if k in keep}

    def encode(self, input_ids, attention_mask, token_type_ids=None) -> torch.Tensor:  # noqa: ANN001
        kw = {"input_ids": input_ids, "attention_mask": attention_mask}
        if token_type_ids is not None and getattr(self.encoder.config, "type_vocab_size", 1) > 1:
            kw["token_type_ids"] = token_type_ids
        hs = self.encoder(**kw).last_hidden_state
        mask = attention_mask.unsqueeze(-1).to(hs.dtype)
        mean = (hs * mask).sum(1) / mask.sum(1).clamp(min=1.0)
        return self.proj(torch.cat([hs[:, 0], mean], dim=-1))

    def forward(self, input_ids, attention_mask, qids: list[str], token_type_ids=None) -> dict[str, tuple[torch.Tensor, torch.Tensor]]:  # noqa: ANN001
        """-> {qid: (row indices in batch, raw logits)}"""
        h = self.encode(input_ids, attention_mask, token_type_ids)
        out = {}
        for qid in dict.fromkeys(qids):
            idx = torch.tensor([i for i, q in enumerate(qids) if q == qid], device=h.device)
            out[qid] = (idx, self.heads[qid](h.index_select(0, idx)))
        return out


# ------------------------------------------------------------------ logits -> probabilities, losses
def probs_from_logits(kind: str, logits: torch.Tensor, temperature: float | torch.Tensor = 1.0) -> torch.Tensor:
    """Distribution over (labels..., insufficient)."""
    z = logits / temperature
    if kind == "choice":
        return F.softmax(z, dim=-1)
    p_ins = torch.sigmoid(z[:, -1:])
    if kind == "bool":
        p_yes = torch.sigmoid(z[:, :1])
        return torch.cat([(1 - p_ins) * p_yes, (1 - p_ins) * (1 - p_yes), p_ins], dim=-1)
    cum = torch.sigmoid(z[:, :-1])  # P(level > k), k = 1..K-1
    ones, zeros = torch.ones_like(cum[:, :1]), torch.zeros_like(cum[:, :1])
    upper = torch.cat([ones, cum], dim=-1)
    lower = torch.cat([cum, zeros], dim=-1)
    levels = (upper - lower).clamp(min=1e-6)
    levels = levels / levels.sum(-1, keepdim=True)
    return torch.cat([(1 - p_ins) * levels, p_ins], dim=-1)


def soft_loss(kind: str, logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """target: soft distribution over (labels..., insufficient), rows sum to 1."""
    eps = 1e-6
    if kind == "choice":
        return -(target * F.log_softmax(logits, dim=-1)).sum(-1).mean()
    t_ins = target[:, -1]
    loss = F.binary_cross_entropy_with_logits(logits[:, -1], t_ins, reduction="none")
    suff = (1 - t_ins).clamp(min=0)
    if kind == "bool":
        t_yes = target[:, 0] / (target[:, 0] + target[:, 1] + eps)
        loss = loss + suff * F.binary_cross_entropy_with_logits(logits[:, 0], t_yes, reduction="none")
        return loss.mean()
    levels = target[:, :-1] / (target[:, :-1].sum(-1, keepdim=True) + eps)
    t_gt = 1 - torch.cumsum(levels, dim=-1)[:, :-1]  # P(level > k)
    ord_loss = F.binary_cross_entropy_with_logits(logits[:, :-1], t_gt.clamp(0, 1), reduction="none").mean(-1)
    return (loss + suff * ord_loss).mean()
