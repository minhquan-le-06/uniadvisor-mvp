"""Train and evaluate the group suggester (docs/MODEL.md): `uniadvisor suggest-train`.

1. priors.json (subject lift, O*NET profiles) is built if missing (`rebuild_priors` to force).
2. With `cl`: confident learning (Northcutt et al. 2021) removes training students whose label looks wrong
   (out-of-fold probabilities from 5 folds and per-group thresholds, see `label_issues`). Off by default: it dropped
   about half the students and lowered test Hit@5 on both 1,922 and 5,825 students (docs/MODEL.md, "Data").
3. 10% of the training set is held out to pick lambda (validation loss, early stopping).
4. On the test set minus the rows marked n in the hand check: Hit@5 and Recall@5 of the trained model and of the
   baseline (the two data scores alone, W = 0, alpha = beta = 1), plus the behaviour checks and the pass rate on the
   reviewed cases (review.py, expectations.jsonl).

Reads backend/suggest_data/ (train.jsonl, testset.jsonl, review_sample.csv); writes artifacts/models/suggester/
(model.npz, metrics.json, report.md; cl_issues.jsonl with `cl`). Generation of the sets: ../MLAI_suggester/.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np

from uniadvisor.student.suggest import features as F
from uniadvisor.student.suggest import priors as PR
from uniadvisor.student.suggest.model import Model, fit, targets
from uniadvisor.student.suggest.review import check
from uniadvisor.student.suggest.suggester import Suggester
from unidata.paths import SUGGEST_CONFIG, SUGGEST_DATA

OUT = PR.OUT
TRAIN = SUGGEST_DATA / "train.jsonl"
TEST = SUGGEST_DATA / "testset.jsonl"
REVIEW = [SUGGEST_DATA / "review_sample.csv"]
LAMBDAS = (1e-5, 1e-4, 1e-3)
CL_FOLDS, CL_LAMBDA = 5, 1e-4

def read(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def reviewed(test: list[dict], paths: list[Path]) -> tuple[list[dict], dict]:
    """The test set minus the students marked n in the hand check (column 'dung (y/n)', over all the review files
    given); unchecked rows stay."""
    marks = {r["id"]: "" for r in test}
    for path in paths:
        if path.exists():
            with open(path, encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    mark = (r.get("dung (y/n)") or "").strip().lower()
                    if mark:
                        marks[r["id"]] = mark
    kept = [r for r in test if not marks.get(r["id"], "").startswith("n")]
    return kept, {"marked_y": sum(v.startswith("y") for v in marks.values()),
                  "marked_n": sum(v.startswith("n") for v in marks.values()),
                  "unchecked": sum(not v for v in marks.values())}


class Inputs:
    """Turns rows into (X, A, C, Y) with the text IDF fitted on `fit_rows` only (held-out rows must not shape it)."""

    def __init__(self, fit_rows: list[dict], priors: PR.Priors):
        self.groups = priors.groups
        self.idf = F.Featurizer().fit([r["answers"] for r in fit_rows]).idf
        self.probe = Suggester(self.empty(), priors)

    def empty(self) -> Model:
        k = len(self.groups)
        return Model(np.zeros((k, F.DIM)), np.zeros(k), 1.0, 1.0, self.idf, self.groups)

    def __call__(self, rows: list[dict]) -> tuple:
        X, A, C = self.probe.inputs([r["answers"] for r in rows])
        return X, A, C, targets([r["groups"] for r in rows], self.groups)


def holdout(rows: list[dict], seed: int) -> tuple[list[dict], list[dict]]:
    """(validation 10%, the rest)."""
    order = np.random.default_rng(seed).permutation(len(rows))
    n_val = max(1, len(rows) // 10)
    return [rows[i] for i in order[:n_val]], [rows[i] for i in order[n_val:]]


def out_of_fold(rows: list[dict], priors: PR.Priors, epochs: int, folds: int = CL_FOLDS) -> np.ndarray:
    """P[i, k]: probability of group k for student i from a model that never saw student i (fixed lambda, early
    stopping on 10% of the other folds)."""
    fold = np.random.default_rng(1).permutation(len(rows)) % folds
    P = np.zeros((len(rows), len(priors.groups)))
    for f in range(folds):
        held = np.flatnonzero(fold == f)
        val, fit_rows = holdout([rows[i] for i in np.flatnonzero(fold != f)], seed=100 + f)
        mk = Inputs(fit_rows, priors)
        m = fit(*mk(fit_rows), groups=priors.groups, idf=mk.idf, lam=CL_LAMBDA, epochs=epochs, val=mk(val))
        P[held] = m.proba(*mk([rows[i] for i in held])[:3])
        print(f"confident learning: fold {f + 1}/{folds} done", flush=True)
    return P


def label_issues(P: np.ndarray, labels: list[list[int]]) -> tuple[list[int], np.ndarray]:
    """Confident learning (Northcutt, Jiang & Chuang 2021). Group j's threshold t_j is the mean out-of-fold
    probability of j over the students labelled with j; j is confident for student i when P[i, j] >= t_j. Student i
    is a label issue when none of its own groups is confident but some other group is. This is the conservative
    reading of the paper's confident joint for students with 1-3 groups: a student whose own group is confident is
    kept even when a neighbouring group is too, because neighbouring groups overlap.
    Returns the issue indices and the thresholds (inf for a group nobody is labelled with)."""
    t = np.full(P.shape[1], np.inf)
    for j in range(P.shape[1]):
        mine = [i for i, ls in enumerate(labels) if j in ls]
        if mine:
            t[j] = P[mine, j].mean()
    confident = P >= t
    issues = [i for i, ls in enumerate(labels) if not confident[i, ls].any() and confident[i].any()]
    return issues, t


def confident_learning(rows: list[dict], priors: PR.Priors, epochs: int) -> tuple[list[dict], dict]:
    """Drops the label issues; logs them to out/cl_issues.jsonl with the groups the model is confident about."""
    groups = priors.groups
    index = {g: i for i, g in enumerate(groups)}
    labels = [[index[g] for g in r["groups"] if g in index] for r in rows]
    P = out_of_fold(rows, priors, epochs)
    issues, t = label_issues(P, labels)
    with open(OUT / "cl_issues.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for i in issues:
            conf = sorted((j for j in range(len(groups)) if P[i, j] >= t[j]), key=lambda j: -P[i, j])
            f.write(json.dumps({"id": rows[i]["id"], "groups": rows[i]["groups"],
                                "own_proba": [round(float(P[i, j]), 3) for j in labels[i]],
                                "confident_instead": [[groups[j], round(float(P[i, j]), 3)] for j in conf[:3]],
                                "answers": rows[i]["answers"]}, ensure_ascii=False) + "\n")
    drop = set(issues)
    per_group = Counter(g for i in issues for g in rows[i]["groups"])
    stats = {"folds": CL_FOLDS, "lambda": CL_LAMBDA, "checked": len(rows), "dropped": len(issues),
             "dropped_share": round(len(issues) / max(len(rows), 1), 4),
             "dropped_by_writer": dict(Counter(rows[i].get("writer", "?") for i in issues)),
             "groups_most_dropped": per_group.most_common(8)}
    return [r for i, r in enumerate(rows) if i not in drop], stats


def topk_metrics(s: Suggester, P: np.ndarray, labels: list[list[str]], k: int = 5) -> dict:
    hits, found, total = 0, 0, 0
    for row, ys in zip(P, labels):
        top = {s.m.groups[i] for i in s.ranked(row)[:k]}
        hits += bool(top & set(ys))
        found += len(top & set(ys))
        total += len(ys)
    return {f"hit@{k}": round(hits / max(len(labels), 1), 4), f"recall@{k}": round(found / max(total, 1), 4)}


def subject_weights() -> np.ndarray:
    """How often each subject is drawn in the behaviour check: 2026 exam candidates per subject
    (backend/config/suggest/subject_counts.csv; the languages other than English are not published, so each is set to
    the rarest observed subject)."""
    with open(SUGGEST_CONFIG / "subject_counts.csv", encoding="utf-8") as f:
        n = {r["subject"]: float(r["candidates"]) for r in csv.DictReader(f)}
    w = np.array([n[s] for s in F.SUBJ])
    return w / w.sum()


def random_answers(n: int, seed: int = 0, weights: np.ndarray | None = None) -> list[dict]:
    """Random answer sets; subjects uniform, or drawn by `weights` (subject_weights())."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        a = {}
        if rng.random() < 0.8:
            a["subjects"] = list(rng.choice(F.SUBJ, size=rng.integers(1, 4), replace=False, p=weights))
        if rng.random() < 0.7:
            a["work_types"] = list(rng.choice(F.WORK, size=rng.integers(1, 3), replace=False))
        if rng.random() < 0.7:
            a["hobbies"] = list(rng.choice(F.HOBBY, size=rng.integers(1, 5), replace=False))
        if rng.random() < 0.5:
            a["workplace"] = list(rng.choice(F.PLACE, size=rng.integers(1, 3), replace=False))
        out.append(a or {"subjects": [str(rng.choice(F.SUBJ))]})
    return out


def top5_shares(s: Suggester, answers: list[dict]) -> dict:
    """The 5 groups shown most often over these answer sets, with the share of sets that show them."""
    share = np.zeros(len(s.m.groups))
    for row in s.proba(answers):
        share[s.ranked(row)[:5]] += 1
    share /= len(answers)
    return {s.m.groups[i]: round(float(share[i]), 3) for i in np.argsort(-share)[:5]}


def behaviour(s: Suggester, pool: list[dict]) -> dict:
    """Every group reachable; no group in the top 5 of more than ~25% of random answer sets (subjects drawn as often
    as 2026 candidates take them); nothing in, nothing out; same input, same output. The uniform draw is reported too:
    with every subject equally likely, rare languages (lift of 4-5 for the few groups admitting D02-D07) are 6 of 18
    draws and push those groups up (docs/MODEL.md, "Behaviour")."""
    singles = ([{"subjects": [x]} for x in F.SUBJ] + [{"work_types": [x]} for x in F.WORK]
               + [{"hobbies": [x]} for x in F.HOBBY] + [{"workplace": [x]} for x in F.PLACE])
    rand = random_answers(2000, weights=subject_weights())
    uniform = random_answers(2000)
    reach = set()
    for answers in (pool, singles, rand, uniform):
        if answers:
            for row in s.proba(answers):
                reach |= {s.m.groups[i] for i in s.ranked(row)[:5]}
    heavy = top5_shares(s, rand)
    probe = rand[0]
    return {"unreachable_groups": sorted(set(s.m.groups) - reach), "top5_share_highest": heavy,
            "groups_over_25pct": [g for g, v in heavy.items() if v > 0.25],
            "top5_share_uniform_subjects": top5_shares(s, uniform),
            "empty_input_gives_nothing": s.suggest({}) == [],
            "deterministic": s.suggest(probe) == s.suggest(probe)}


def run(train_path: Path = TRAIN, test_path: Path = TEST, review: list[Path] | None = None, cl: bool = False,
        rebuild_priors: bool = False, epochs: int = 200) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    if rebuild_priors or not PR.PRIORS.exists():
        PR.build()
    priors = PR.Priors()
    groups = priors.groups

    train = read(train_path)
    test, checked = reviewed(read(test_path), REVIEW if review is None else review)
    cl_stats = {"skipped": True}
    if cl:
        train, cl_stats = confident_learning(train, priors, epochs)
    val, fit_rows = holdout(train, seed=0)
    mk = Inputs(fit_rows, priors)
    tr, va, te = mk(fit_rows), mk(val), mk(test)
    runs = []
    for lam in LAMBDAS:
        m = fit(*tr, groups=groups, idf=mk.idf, lam=lam, epochs=epochs, val=va)
        best_val = min(h["val_loss"] for h in m.history if "val_loss" in h)
        runs.append((best_val, lam, m))
        print(f"lambda {lam:g}: best val loss {best_val:.4f} at epoch {m.history[-1].get('kept_epoch')}", flush=True)
    best_val, lam, model = min(runs, key=lambda r: r[0])
    s = Suggester(model, priors)
    base = Suggester(mk.empty(), priors, popularity=0.0)      # the two data scores alone, as before
    labels = [r["groups"] for r in test]
    metrics = {
        "n_train": len(fit_rows), "n_val": len(val), "n_test": len(test), "test_review": checked,
        "confident_learning": cl_stats, "lambda": lam, "alpha": round(model.alpha, 3), "beta": round(model.beta, 3),
        "popularity": s.popularity, "writers": dict(Counter(r.get("writer", "?") for r in fit_rows + val)),
        "model": topk_metrics(s, s.proba_of(*te[:3]), labels),
        "model_without_popularity": topk_metrics(s, s.m.proba(*te[:3]), labels),
        "baseline": topk_metrics(base, base.proba_of(*te[:3]), labels),
        "val_model": topk_metrics(s, s.proba_of(*va[:3]), [r["groups"] for r in val]),
        "behaviour": behaviour(s, [r["answers"] for r in test]),
        "review": check(s),
    }
    metrics["beats_baseline"] = metrics["model"]["hit@5"] > metrics["baseline"]["hit@5"]
    model.save(OUT / "model.npz")
    (OUT / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    examples = "\n".join(f"- groups {r['groups']}: " + "; ".join(
        f"{x['code']} ({x['score']:.2f}: {', '.join(x['reasons'])})" for x in s.suggest(r["answers"])) for r in test[:5])
    (OUT / "report.md").write_text(
        f"# Suggester run\n\n```json\n{json.dumps(metrics, ensure_ascii=False, indent=1)}\n```\n\nFirst test students:\n"
        f"{examples}\n", encoding="utf-8")
    return metrics
