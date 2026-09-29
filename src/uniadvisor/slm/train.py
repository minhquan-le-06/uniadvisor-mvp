"""Fine-tune the SLM (LoRA + typed heads), calibrate it, evaluate it, save it.

Runs on CPU (slow, use --limit for a smoke test) or GPU (Kaggle T4/P100: a few minutes per epoch).

  python -m uniadvisor.slm.train --data data/slm --out models/slm --epochs 3
  python -m uniadvisor.slm.train --limit 2000 --epochs 1          # quick local smoke test

Writes to --out: adapter.pt (trainable weights only), config.json (base model, heads, temperatures,
thresholds), metrics.json (val/test metrics before/after calibration, per group).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from uniadvisor.slm.metrics import by_group, summarize
from uniadvisor.slm.model import DEFAULT_BASE, TypedHeadModel, probs_from_logits, soft_loss
from uniadvisor.slm.questions import BY_ID, INSUFFICIENT, QUESTIONS


def load_jsonl(path: Path, limit: int | None = None, seed: int = 0) -> list[dict]:
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    if limit and len(rows) > limit:
        random.Random(seed).shuffle(rows)
        rows = rows[:limit]
    return rows


def target_vec(row: dict) -> list[float]:
    q = BY_ID[row["question"]]
    return [float(row["soft_label"].get(k, 0.0)) for k in q.all_labels]


class Batcher:
    def __init__(self, rows: list[dict], tokenizer, max_len: int, bs: int, shuffle: bool, seed: int = 0):  # noqa: ANN001
        self.rows, self.tok, self.max_len, self.bs, self.shuffle = rows, tokenizer, max_len, bs, shuffle
        self.rng = random.Random(seed)

    def __len__(self) -> int:
        return math.ceil(len(self.rows) / self.bs)

    def __iter__(self):  # noqa: ANN204
        idx = list(range(len(self.rows)))
        if self.shuffle:
            self.rng.shuffle(idx)
        for s in range(0, len(idx), self.bs):
            chunk = [self.rows[i] for i in idx[s:s + self.bs]]
            enc = self.tok([r["text_a"] for r in chunk], [r["text_b"] for r in chunk], truncation="longest_first",
                           max_length=self.max_len, padding=True, return_tensors="pt")
            yield chunk, enc


@torch.no_grad()
def predict(model: TypedHeadModel, rows: list[dict], tok, max_len: int, bs: int, device: str, calibrated: bool = True) -> tuple[list[np.ndarray], dict[str, list]]:  # noqa: ANN001
    """-> per-row probability vectors, and raw logits per question (for temperature fitting)."""
    model.eval()
    probs: list[np.ndarray | None] = [None] * len(rows)
    raw: dict[str, list] = {}
    order = {id(r): i for i, r in enumerate(rows)}
    for chunk, enc in Batcher(rows, tok, max_len, bs, shuffle=False):
        enc = {k: v.to(device) for k, v in enc.items()}
        with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=device == "cuda"):
            out = model(enc["input_ids"], enc["attention_mask"], [r["question"] for r in chunk], enc.get("token_type_ids"))
        for qid, (idx, logits) in out.items():
            logits = logits.float()
            t = model.temperature[model.q_index[qid]] if calibrated else 1.0
            p = probs_from_logits(BY_ID[qid].kind, logits, t).cpu().numpy()
            for j, i in enumerate(idx.tolist()):
                row = chunk[i]
                probs[order[id(row)]] = p[j]
                raw.setdefault(qid, []).append((logits[j].cpu(), torch.tensor(target_vec(row))))
    return probs, raw


def fit_temperatures(model: TypedHeadModel, raw: dict[str, list]) -> dict[str, float]:
    """One temperature per question, minimising soft NLL on validation logits."""
    temps = {}
    for qid, pairs in raw.items():
        logits = torch.stack([p[0] for p in pairs])
        target = torch.stack([p[1] for p in pairs])
        best, best_t = float("inf"), 1.0
        for t in np.exp(np.linspace(np.log(0.3), np.log(5.0), 60)):
            pr = probs_from_logits(BY_ID[qid].kind, logits, float(t)).clamp(min=1e-7)
            nll = float(-(target * pr.log()).sum(-1).mean())
            if nll < best:
                best, best_t = nll, float(t)
        temps[qid] = best_t
        model.temperature[model.q_index[qid]] = best_t
    return temps


def frame(rows: list[dict], probs: list[np.ndarray]) -> pd.DataFrame:
    recs = []
    for r, p in zip(rows, probs):
        q = BY_ID[r["question"]]
        labels = q.all_labels
        pred = labels[int(np.argmax(p))]
        rec = {"question": q.id, "label": r["label"], "pred": pred, "conf": float(np.max(p)),
               "region": r.get("region"), "track": r.get("track"), "score_band": r.get("score_band")}
        if q.kind == "score" and r["label"] != INSUFFICIENT and pred != INSUFFICIENT:
            rec["abs_level_err"] = abs(int(pred) - int(r["label"]))
        recs.append(rec)
    return pd.DataFrame(recs)


def choose_thresholds(df: pd.DataFrame, target_acc: float = 0.9) -> dict[str, float]:
    """Lowest confidence threshold per question whose non-escalated accuracy reaches target_acc on val."""
    th = {}
    for q, g in df.groupby("question"):
        th[q] = 0.95
        for t in np.linspace(0.3, 0.95, 27):
            keep = (g.conf >= t) & (g.pred != INSUFFICIENT)
            if keep.sum() >= max(20, 0.2 * len(g)) and (g.pred[keep] == g.label[keep]).mean() >= target_acc:
                th[q] = round(float(t), 3)
                break
    return th


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/slm")
    ap.add_argument("--out", default="models/slm")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--lr", type=float, default=5e-4)
    ap.add_argument("--max-len", type=int, default=320)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--limit", type=int, default=None, help="cap train examples (smoke test)")
    ap.add_argument("--eval-limit", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--target-acc", type=float, default=0.9)
    ap.add_argument("--threads", type=int, default=0)
    args = ap.parse_args(argv)

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    if args.threads:
        torch.set_num_threads(args.threads)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    data, out = Path(args.data), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    train = load_jsonl(data / "train.jsonl", args.limit, args.seed)
    val = load_jsonl(data / "val.jsonl", args.eval_limit, args.seed)
    test = load_jsonl(data / "test.jsonl", args.eval_limit, args.seed)
    print(f"device={device} train={len(train)} val={len(val)} test={len(test)}", flush=True)

    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.base)
    model = TypedHeadModel(args.base, QUESTIONS, lora_r=args.lora_r, lora_alpha=2 * args.lora_r).to(device)
    params = [p for p in model.parameters() if p.requires_grad]
    print(f"LoRA layers={model.n_lora} trainable params={sum(p.numel() for p in params):,}", flush=True)
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.01)
    steps = args.epochs * math.ceil(len(train) / args.bs)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / max(1, int(0.06 * steps))) * max(0.0, 1 - s / steps))
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")

    history = []
    for epoch in range(args.epochs):
        model.train()
        t0, total, n = time.time(), 0.0, 0
        for step, (chunk, enc) in enumerate(Batcher(train, tok, args.max_len, args.bs, shuffle=True, seed=args.seed + epoch)):
            enc = {k: v.to(device) for k, v in enc.items()}
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=device == "cuda"):
                outs = model(enc["input_ids"], enc["attention_mask"], [r["question"] for r in chunk], enc.get("token_type_ids"))
            loss = 0.0
            for qid, (idx, logits) in outs.items():
                tgt = torch.tensor([target_vec(chunk[i]) for i in idx.tolist()], device=device)
                loss = loss + soft_loss(BY_ID[qid].kind, logits.float(), tgt) * len(idx) / len(chunk)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            total, n = total + float(loss.detach()) * len(chunk), n + len(chunk)
            if step % 50 == 0:
                print(f"epoch {epoch + 1} step {step} loss {total / n:.4f} {time.time() - t0:.0f}s", flush=True)
        vp, _ = predict(model, val, tok, args.max_len, 2 * args.bs, device, calibrated=False)
        vdf = frame(val, vp)
        history.append({"epoch": epoch + 1, "train_loss": round(total / n, 4), "val_accuracy": round(float((vdf.pred == vdf.label).mean()), 4)})
        print(history[-1], flush=True)

    # calibration on val, thresholds on val, final numbers on test
    val_uncal, raw = predict(model, val, tok, args.max_len, 2 * args.bs, device, calibrated=False)
    temps = fit_temperatures(model, raw)
    val_cal, _ = predict(model, val, tok, args.max_len, 2 * args.bs, device)
    thresholds = choose_thresholds(frame(val, val_cal), args.target_acc)
    test_uncal, _ = predict(model, test, tok, args.max_len, 2 * args.bs, device, calibrated=False)
    test_cal, _ = predict(model, test, tok, args.max_len, 2 * args.bs, device)
    tdf_u, tdf = frame(test, test_uncal), frame(test, test_cal)
    metrics = {
        "history": history, "temperatures": temps, "thresholds": thresholds,
        "val": summarize(frame(val, val_cal), thresholds),
        "test_uncalibrated": summarize(tdf_u), "test": summarize(tdf, thresholds), "test_by_group": by_group(tdf),
        "note": "Labels are from the rubric teacher on synthetic students (see data/slm/stats.json). Report the human gold set separately (uniadvisor slm-eval --gold).",
    }
    torch.save(model.trainable_state(), out / "adapter.pt")
    config = {"base_model": args.base, "max_len": args.max_len, "lora_r": args.lora_r, "lora_alpha": 2 * args.lora_r,
              "questions": [{"id": q.id, "kind": q.kind, "labels": list(q.all_labels)} for q in QUESTIONS],
              "temperatures": temps, "thresholds": thresholds, "train_examples": len(train), "epochs": args.epochs}
    (out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metrics["test"], indent=1), flush=True)
    return metrics


if __name__ == "__main__":
    main()
