"""The model of docs/MODEL.md: multinomial logistic regression over the groups plus one weight for each data
score,

    z_k(x) = w_k . phi(x) + b_k + alpha a_k(x) + beta c_k(x),      f(x) = softmax(z(x))

trained on the loss L = -(1/N) sum_i (1/|y_i|) sum_{k in y_i} log f(x_i)_k + lambda ||W||^2 with Adam (plain numpy
and scipy.sparse). Same data and seed, same model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import sparse


def softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


@dataclass
class Model:
    W: np.ndarray            # K x d
    b: np.ndarray            # K
    alpha: float
    beta: float
    idf: np.ndarray
    groups: list[str]
    history: list[dict] = field(default_factory=list)

    def scores(self, X: sparse.csr_matrix, A: np.ndarray, C: np.ndarray) -> np.ndarray:
        return X @ self.W.T + self.b + self.alpha * A + self.beta * C

    def proba(self, X: sparse.csr_matrix, A: np.ndarray, C: np.ndarray) -> np.ndarray:
        return softmax(self.scores(X, A, C))

    def save(self, path: Path) -> None:
        np.savez_compressed(path, W=self.W.astype(np.float32), b=self.b, ab=np.array([self.alpha, self.beta]),
                            idf=self.idf.astype(np.float32), groups=np.array(self.groups))

    @classmethod
    def load(cls, path: Path) -> "Model":
        d = np.load(path)
        return cls(d["W"].astype(np.float64), d["b"], float(d["ab"][0]), float(d["ab"][1]), d["idf"].astype(np.float64),
                   [str(g) for g in d["groups"]])


def targets(labels: list[list[str]], groups: list[str]) -> np.ndarray:
    """Each student's fitting groups, each counting equally (rows sum to 1)."""
    index = {g: i for i, g in enumerate(groups)}
    Y = np.zeros((len(labels), len(groups)))
    for i, ys in enumerate(labels):
        ks = [index[g] for g in ys if g in index]
        Y[i, ks] = 1.0 / len(ks) if ks else 0.0
    return Y


def loss(m: Model, X, A, C, Y, lam: float) -> float:  # noqa: ANN001
    P = m.proba(X, A, C)
    return float(-(Y * np.log(P + 1e-12)).sum() / len(Y) + lam * (m.W ** 2).sum())


def fit(X: sparse.csr_matrix, A: np.ndarray, C: np.ndarray, Y: np.ndarray, groups: list[str], idf: np.ndarray,
        lam: float = 1e-3, epochs: int = 200, lr: float = 0.05, batch: int = 256, seed: int = 0,
        val: tuple | None = None, patience: int = 15) -> Model:
    """Mini-batch Adam on L. With `val` = (X, A, C, Y), stops when the validation loss has not improved for `patience`
    epochs and keeps the best epoch."""
    rng = np.random.default_rng(seed)
    n, d = X.shape
    K = Y.shape[1]
    m = Model(np.zeros((K, d)), np.zeros(K), 1.0, 1.0, idf, groups)
    params = ["W", "b", "alpha", "beta"]
    mom = {p: np.zeros_like(np.asarray(getattr(m, p), dtype=float)) for p in params}
    vel = {p: np.zeros_like(np.asarray(getattr(m, p), dtype=float)) for p in params}
    b1, b2, eps, t = 0.9, 0.999, 1e-8, 0
    best, best_state, bad = np.inf, None, 0
    for epoch in range(epochs):
        order = rng.permutation(n)
        for s in range(0, n, batch):
            idx = order[s:s + batch]
            Xb, Ab, Cb, Yb = X[idx], A[idx], C[idx], Y[idx]
            G = (m.proba(Xb, Ab, Cb) - Yb) / len(idx)          # d L / d z
            grads = {"W": np.asarray((Xb.T @ G).T) + 2 * lam * m.W, "b": G.sum(axis=0),
                     "alpha": float((G * Ab).sum()), "beta": float((G * Cb).sum())}
            t += 1
            for p in params:
                mom[p] = b1 * mom[p] + (1 - b1) * grads[p]
                vel[p] = b2 * vel[p] + (1 - b2) * np.square(grads[p])
                step = lr * (mom[p] / (1 - b1 ** t)) / (np.sqrt(vel[p] / (1 - b2 ** t)) + eps)
                setattr(m, p, getattr(m, p) - step if p in ("W", "b") else float(getattr(m, p) - step))
        rec = {"epoch": epoch + 1, "train_loss": round(loss(m, X, A, C, Y, lam), 4)}
        if val is not None:
            rec["val_loss"] = round(loss(m, *val, lam=0.0), 4)
            if rec["val_loss"] < best - 1e-4:
                best, bad = rec["val_loss"], 0
                best_state = (m.W.copy(), m.b.copy(), m.alpha, m.beta, epoch + 1)
            else:
                bad += 1
        m.history.append(rec)
        if val is not None and bad >= patience:
            break
    if best_state is not None:
        m.W, m.b, m.alpha, m.beta, kept = best_state
        m.history.append({"kept_epoch": kept})
    return m
