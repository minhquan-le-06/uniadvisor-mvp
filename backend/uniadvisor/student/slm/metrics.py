"""Metrics for typed answers: accuracy, macro-F1, ECE, escalation rate, per-group quality."""

from __future__ import annotations

import numpy as np
import pandas as pd


def ece(conf: np.ndarray, correct: np.ndarray, bins: int = 10) -> float:
    conf, correct = np.asarray(conf, float), np.asarray(correct, float)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs(conf[m].mean() - correct[m].mean())
    return float(total)


def macro_f1(y_true: list[str], y_pred: list[str]) -> float:
    labels = sorted(set(y_true) | set(y_pred))
    f1s = []
    for lab in labels:
        tp = sum(t == lab and p == lab for t, p in zip(y_true, y_pred))
        fp = sum(t != lab and p == lab for t, p in zip(y_true, y_pred))
        fn = sum(t == lab and p != lab for t, p in zip(y_true, y_pred))
        if tp + fp + fn == 0:
            continue
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return float(np.mean(f1s)) if f1s else 0.0


def summarize(df: pd.DataFrame, thresholds: dict[str, float] | None = None) -> dict:
    """df columns: question, label (target), pred, conf, [score-kind: exp_pred, exp_true], groups..."""
    out = {}
    for q, g in df.groupby("question"):
        correct = (g.pred == g.label).to_numpy()
        row = {"n": int(len(g)), "accuracy": round(float(correct.mean()), 4), "macro_f1": round(macro_f1(list(g.label), list(g.pred)), 4),
               "ece": round(ece(g.conf.to_numpy(), correct), 4)}
        if "abs_level_err" in g and g.abs_level_err.notna().any():
            row["level_mae"] = round(float(g.abs_level_err.dropna().mean()), 4)
        if thresholds and q in thresholds:
            esc = (g.conf < thresholds[q]) | (g.pred == "insufficient")
            row["escalation_rate"] = round(float(esc.mean()), 4)
            row["accuracy_when_not_escalated"] = round(float(correct[~esc.to_numpy()].mean()), 4) if (~esc).any() else None
        out[q] = row
    return out


def by_group(df: pd.DataFrame, group_cols: tuple[str, ...] = ("region", "track", "score_band")) -> dict:
    out = {}
    for col in group_cols:
        if col not in df:
            continue
        out[col] = {str(k): {"n": int(len(g)), "accuracy": round(float((g.pred == g.label).mean()), 4)}
                    for k, g in df.groupby(col) if len(g) >= 30}
    return out
