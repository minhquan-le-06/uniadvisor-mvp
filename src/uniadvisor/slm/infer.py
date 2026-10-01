"""Answer typed questions at run time.

SLMJudge      the fine-tuned model in models/slm/ (config.json + adapter.pt), calibrated per question
HeuristicJudge transparent keyword rules, used when no trained model is available and as the
               baseline the SLM has to beat. Its confidence is capped low on purpose, so uncertain
               answers turn into clarifying questions instead of silent guesses.
HybridJudge   what the app uses when a model is present: each question goes to the judge that
               answers it better (SLM_QUESTIONS).

Answers the student gave to clarifying questions (profile.answers) always win over both.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from uniadvisor.build.fields import GENERIC_IN_FREE_TEXT, RULES as FIELD_RULES
from uniadvisor.paths import MODELS
from uniadvisor.slm.questions import BY_ID, INSUFFICIENT
from uniadvisor.slm.state import StudentProfile, model_input
from uniadvisor.slm.synth import CORE_SUBJECTS, FIELD_TEXT, HUB_OF_REGION, REGION_OF, RELATED
from uniadvisor.text import fold

DEFAULT_THRESHOLD = 0.6


@dataclass
class Answer:
    question: str
    probs: dict[str, float]
    label: str
    confidence: float
    escalate: bool
    source: str            # slm | heuristic | student

    def p(self, label: str) -> float:
        return float(self.probs.get(label, 0.0))

    def expected_level(self) -> float | None:
        """For score questions: E[level | sufficient]."""
        q = BY_ID[self.question]
        if q.kind != "score":
            return None
        w = np.array([self.probs.get(l, 0.0) for l in q.labels])
        if w.sum() <= 0:
            return None
        return float(np.dot(w / w.sum(), np.arange(1, len(q.labels) + 1)))


def _student_answer(qid: str, profile: StudentProfile) -> Answer | None:
    v = (profile.answers or {}).get(qid)
    if not v:
        return None
    labels = BY_ID[qid].all_labels
    probs = {l: (1.0 if l == v else 0.0) for l in labels}
    return Answer(qid, probs, v, 1.0, False, "student")


def _finish(qid: str, probs: dict[str, float], source: str, threshold: float) -> Answer:
    total = sum(probs.values()) or 1.0
    probs = {k: v / total for k, v in probs.items()}
    label = max(probs, key=probs.get)
    conf = probs[label]
    return Answer(qid, probs, label, conf, conf < threshold or label == INSUFFICIENT, source)


# ------------------------------------------------------------------ heuristic judge
NEG = ("khong thich", "ghet", "so ", "khong muon", "khong hop", "khong co nang khieu", "chan", "buon ngu", "ngai", "bat em", "bat chau",
       "ko thich", "ko muon", "khong phan doi")
RISK_KW = {
    "an_toan": ("chac chan do", "chac an", "an toan", "so truot", "phai do", "khong dam lieu", "khong cho thi lai", "do la duoc", "khong muon mao hiem"),
    "can_bang": ("can bang", "du phong", "vua suc", "duong lui", "ca phuong an"),
    "mao_hiem": ("lieu", "thi lai", "rui ro", "an ca nga ve khong", "thu suc het minh", "on them mot nam"),
}
PRIORITY_KW = {
    "nganh_yeu_thich": ("dam me", "nganh minh thich", "cai minh yeu thich", "dung nganh"),
    "truong_danh_tieng": ("danh tieng", "truong top", "co tieng", "ten tuoi", "truong xin"),
    "hoc_phi_thap": ("hoc phi re", "hoc phi thap", "lo nhat", "do cho bo me"),
    "gan_nha": ("gan nha", "khong muon di xa", "di xa gia dinh", "phu bo me"),
    "viec_lam_thu_nhap": ("xin viec", "thu nhap cao", "luong cao", "on dinh", "co viec ngay"),
}
POOR = ("kho khan", "ngheo", "khong co dieu kien", "khong kha", "can ngheo", "lam nong", "lo tien hoc")
RICH = ("khong lo ve hoc phi", "thoai mai", "bao nhieu cung lo")


def _sentences(text: str) -> list[str]:
    return [f" {fold(s)} " for s in re.split(r"[.!?\n;]+", text or "") if s.strip()]


@lru_cache(maxsize=1)
def _free_text_lexicon() -> list[tuple[str, tuple[str, ...]]]:
    """Field keywords usable on free text: program-name rules minus generic words, plus the phrase banks."""
    lex = []
    for field, words in FIELD_RULES:
        lex.append((field, tuple(w for w in words if w not in GENERIC_IN_FREE_TEXT)))
    for field, bank in FIELD_TEXT.items():
        lex.append((field, tuple(fold(p) for key in ("want", "career", "hobby", "dislike") for p in bank[key])))
    return lex


def _fields_in(sentence: str) -> set[str]:
    return {field for field, words in _free_text_lexicon() if any(w in sentence for w in words)}


@lru_cache(maxsize=256)
def _likes(text: str) -> tuple[frozenset[str], frozenset[str]]:
    likes, dislikes = set(), set()
    for s in _sentences(text):
        f = _fields_in(s)
        if not f:
            continue
        if any(n in s for n in NEG) and "khong phan doi" not in s:
            dislikes |= f
        else:
            likes |= f
    return frozenset(likes - dislikes), frozenset(dislikes)


@lru_cache(maxsize=256)
def _budget(text: str) -> tuple[str | None, float | None]:
    t = fold(text)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:trieu|tr)\b", t)
    if m and any(k in t for k in ("hoc phi", "tien hoc", "chi duoc", "lo duoc", "dong")):
        v = float(m.group(1).replace(",", ".")) * 1e6
        if re.search(r"\bthang\b", t[m.end(): m.end() + 20]):  # per month -> per (10-month) school year
            v *= 10
        return "number", v
    if any(k in t for k in RICH):
        return "rich", None
    if any(k in t for k in POOR):
        return "poor", None
    return None, None


@lru_cache(maxsize=256)
def _location(text: str, province: str | None) -> str | None:
    t = f" {fold(text)} "
    hn = any(k in t for k in (" ha noi", " hn ", "thu do"))
    hcm = any(k in t for k in ("sai gon", "hcm", "ho chi minh"))
    if "dau cung duoc" in t or "khong quan trong" in t and "dia diem" in t or "bac hay nam" in t:
        return "anywhere"
    if "thanh pho lon" in t:
        return "no_big_city"
    if hn and not hcm:
        return "city:Hà Nội"
    if hcm and not hn:
        return "city:TP. Hồ Chí Minh"
    if any(k in t for k in ("gan nha", "xa nha", "di xa", "di hoc xa")):
        return "near_home"
    return None


class HeuristicJudge:
    name = "heuristic"
    cap = 0.7

    def _one(self, qid: str, profile: StudentProfile, program: dict | None) -> Answer:
        text = profile.free_text or ""
        t = f" {fold(text)} "
        c = self.cap
        labels = BY_ID[qid].all_labels

        def dist(label: str, conf: float = c) -> dict[str, float]:
            rest = (1 - conf) / (len(labels) - 1)
            return {l: (conf if l == label else rest) for l in labels}

        if qid == "risk_tolerance":
            hits = {k: sum(w in t for w in ws) for k, ws in RISK_KW.items()}
            best = max(hits, key=hits.get)
            if hits[best] == 0 or sorted(hits.values())[-2] == hits[best]:
                return _finish(qid, dist(INSUFFICIENT, 0.55), self.name, DEFAULT_THRESHOLD)
            return _finish(qid, dist(best), self.name, DEFAULT_THRESHOLD)
        if qid == "top_priority":
            hits = {k: sum(w in t for w in ws) for k, ws in PRIORITY_KW.items()}
            best = max(hits, key=hits.get)
            return _finish(qid, dist(best if hits[best] else INSUFFICIENT, c if hits[best] else 0.55), self.name, DEFAULT_THRESHOLD)
        assert program is not None
        field = program.get("field") or ""
        if qid == "interest_fit":
            likes, dislikes = _likes(text)
            if field in dislikes:
                return _finish(qid, dist("1"), self.name, DEFAULT_THRESHOLD)
            if field in likes:
                return _finish(qid, dist("5"), self.name, DEFAULT_THRESHOLD)
            if any(field in RELATED.get(g, []) for g in likes):
                return _finish(qid, dist("4", 0.5), self.name, DEFAULT_THRESHOLD)
            if likes:
                return _finish(qid, dist("2", 0.5), self.name, DEFAULT_THRESHOLD)
            return _finish(qid, dist(INSUFFICIENT, 0.5), self.name, DEFAULT_THRESHOLD)
        if qid == "ability_fit":
            core = CORE_SUBJECTS.get(field, ["TO", "VA"])
            have = [profile.scores[s] for s in core if s in profile.scores]
            if not have:
                return _finish(qid, dist(INSUFFICIENT, 0.5), self.name, DEFAULT_THRESHOLD)
            x = float(np.mean(have))
            lvl = "5" if x >= 8.5 else "4" if x >= 7.5 else "3" if x >= 6.5 else "2" if x >= 5 else "1"
            return _finish(qid, dist(lvl), self.name, DEFAULT_THRESHOLD)
        if qid == "budget_ok":
            kind, v = _budget(text)
            tmin, tmax = program.get("tuition_min"), program.get("tuition_max")
            if kind is None or tmin is None or tmin != tmin:
                return _finish(qid, dist(INSUFFICIENT, 0.6), self.name, DEFAULT_THRESHOLD)
            if kind == "rich":
                return _finish(qid, dist("yes"), self.name, DEFAULT_THRESHOLD)
            if kind == "poor":
                return _finish(qid, dist("yes" if tmax <= 15e6 else "no", 0.55), self.name, DEFAULT_THRESHOLD)
            return _finish(qid, dist("yes" if tmax <= v else "no"), self.name, DEFAULT_THRESHOLD)
        if qid == "location_ok":
            loc = _location(text, profile.province)
            city, branch = program.get("city"), bool(program.get("campus"))
            if loc is None:
                return _finish(qid, dist(INSUFFICIENT, 0.6), self.name, DEFAULT_THRESHOLD)
            if loc == "anywhere":
                return _finish(qid, dist("yes"), self.name, DEFAULT_THRESHOLD)
            if loc == "no_big_city":
                return _finish(qid, dist("no", 0.55), self.name, DEFAULT_THRESHOLD)
            if loc.startswith("city:"):
                return _finish(qid, dist("yes" if city == loc[5:] and not branch else "no"), self.name, DEFAULT_THRESHOLD)
            hub = HUB_OF_REGION.get(REGION_OF.get(profile.province or "", ""), None)
            if hub is None:
                return _finish(qid, dist(INSUFFICIENT, 0.5), self.name, DEFAULT_THRESHOLD)
            return _finish(qid, dist("yes" if city == hub else "no", 0.6), self.name, DEFAULT_THRESHOLD)
        if qid == "conditions_ok":
            cond = str(program.get("conditions") or "").lower()
            if not cond or cond == "nan":
                return _finish(qid, dist("yes", 0.8), self.name, DEFAULT_THRESHOLD)
            verdict = "yes"
            if "tiếng anh" in cond:
                en = profile.scores.get("N1")
                if any(k in t for k in ("tieng anh cua em kha", "ielts", "tieng anh tot", "tu tin")) or (en is not None and en >= 7):
                    verdict = "yes"
                elif any(k in t for k in ("tieng anh em rat kem", "mat goc tieng anh", "so nhat la mon tieng anh", "tieng anh kem")) or (en is not None and en < 5):
                    verdict = "no"
                else:
                    verdict = INSUFFICIENT
            if "sư phạm" in cond and any(k in t for k in ("noi lap", "noi ngong")):
                verdict = "no"
            if "thí sinh nam" in cond and profile.gender == "nu" or "thí sinh nữ" in cond and profile.gender == "nam":
                verdict = "no"
            return _finish(qid, dist(verdict, 0.6), self.name, DEFAULT_THRESHOLD)
        raise KeyError(qid)

    def answer(self, items: list[tuple[str, StudentProfile, dict | None]]) -> list[Answer]:
        return [_student_answer(q, p) or self._one(q, p, prog) for q, p, prog in items]


# ------------------------------------------------------------------ fine-tuned model
class SLMJudge:
    name = "slm"

    def __init__(self, model_dir: Path, device: str | None = None, batch_size: int = 32):
        import torch
        from transformers import AutoTokenizer

        from uniadvisor.slm.model import TypedHeadModel
        from uniadvisor.slm.questions import QUESTIONS

        self.torch = torch
        cfg = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
        self.cfg = cfg
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tok = AutoTokenizer.from_pretrained(cfg["base_model"])
        self.model = TypedHeadModel(cfg["base_model"], QUESTIONS, lora_r=cfg["lora_r"], lora_alpha=cfg["lora_alpha"])
        state = torch.load(model_dir / "adapter.pt", map_location="cpu")
        missing, unexpected = self.model.load_state_dict(state, strict=False)
        if unexpected:
            raise RuntimeError(f"unexpected keys in adapter: {unexpected[:5]}")
        self.model.to(self.device).eval()
        self.thresholds = cfg.get("thresholds", {})
        self.bs = batch_size

    def answer(self, items: list[tuple[str, StudentProfile, dict | None]]) -> list[Answer]:
        from uniadvisor.slm.model import probs_from_logits

        out: list[Answer | None] = [_student_answer(q, p) for q, p, _ in items]
        todo = [i for i, a in enumerate(out) if a is None]
        for s in range(0, len(todo), self.bs):
            idx = todo[s:s + self.bs]
            pairs = [model_input(BY_ID[items[i][0]].text_vi, items[i][1], items[i][2]) for i in idx]
            enc = self.tok([a for a, _ in pairs], [b for _, b in pairs], truncation="longest_first",
                           max_length=self.cfg["max_len"], padding=True, return_tensors="pt").to(self.device)
            with self.torch.no_grad():
                res = self.model(enc["input_ids"], enc["attention_mask"], [items[i][0] for i in idx], enc.get("token_type_ids"))
            for qid, (rows, logits) in res.items():
                t = self.model.temperature[self.model.q_index[qid]]
                pr = probs_from_logits(BY_ID[qid].kind, logits.float(), t).cpu().numpy()
                for j, r in enumerate(rows.tolist()):
                    labels = BY_ID[qid].all_labels
                    out[idx[r]] = _finish(qid, dict(zip(labels, map(float, pr[j]))), self.name, self.thresholds.get(qid, DEFAULT_THRESHOLD))
        return out  # type: ignore[return-value]


# Questions the fine-tuned SLM answers better than the keyword rules (test split, first Kaggle run):
# location_ok 0.98 vs 0.66, risk_tolerance 0.94 vs 0.87, budget_ok 0.97 vs 0.96. The rules stay better on
# ability_fit (score arithmetic: 0.84 vs 0.47), interest_fit (0.69 vs 0.49), top_priority (0.89 vs 0.84),
# and tie on conditions_ok, where they are also far cheaper. Override with "route" in models/slm/config.json.
# measured on the frozen gold set labelled by Gemini (data/slm/gold_llm.csv; see README): the SLM wins location_ok,
# risk_tolerance and budget_ok and ties conditions_ok with far better calibration; the keyword rules win ability_fit
# (score arithmetic) and top_priority; interest_fit is a tie, kept on the rules. Re-pick after every retrain.
SLM_QUESTIONS = ("location_ok", "risk_tolerance", "budget_ok", "conditions_ok")


class HybridJudge:
    """Send each question to whichever judge answers it better; the SLM only runs on its questions."""

    name = "hybrid"

    def __init__(self, slm: SLMJudge, heuristic: HeuristicJudge | None = None, slm_questions: tuple[str, ...] | None = None):
        self.slm = slm
        self.heuristic = heuristic or HeuristicJudge()
        self.slm_questions = frozenset(slm_questions if slm_questions is not None else slm.cfg.get("route", SLM_QUESTIONS))
        unknown = self.slm_questions - set(BY_ID)
        if unknown:
            raise ValueError(f"unknown questions in route: {sorted(unknown)}")
        self.thresholds = {q: slm.thresholds.get(q, DEFAULT_THRESHOLD) if q in self.slm_questions else DEFAULT_THRESHOLD for q in BY_ID}

    def answer(self, items: list[tuple[str, StudentProfile, dict | None]]) -> list[Answer]:
        out: list[Answer | None] = [None] * len(items)
        for judge, want_slm in ((self.slm, True), (self.heuristic, False)):
            idx = [i for i, (q, _, _) in enumerate(items) if (q in self.slm_questions) == want_slm]
            if idx:
                for i, a in zip(idx, judge.answer([items[i] for i in idx])):
                    out[i] = a
        return out  # type: ignore[return-value]


LOAD_ERROR: list[str] = []  # why the last load_slm() returned None (shown by `slm-eval`)


def load_slm() -> SLMJudge | None:
    model_dir = Path(os.environ.get("UNIADVISOR_SLM_DIR", MODELS / "slm"))
    LOAD_ERROR.clear()
    if (model_dir / "adapter.pt").exists() and (model_dir / "config.json").exists():
        try:
            return SLMJudge(model_dir)
        except Exception as e:  # noqa: BLE001 - fall back rather than break the app
            LOAD_ERROR.append(f"{type(e).__name__}: {e}")
            print(f"[uniadvisor] could not load SLM from {model_dir}: {e}; using heuristic judge")
    return None


@lru_cache(maxsize=1)
def get_judge() -> HeuristicJudge | HybridJudge:
    slm = load_slm()
    return HybridJudge(slm) if slm is not None else HeuristicJudge()
