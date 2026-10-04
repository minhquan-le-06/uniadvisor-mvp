"""phi(x): one student's questionnaire answers as a sparse vector (docs/MODEL.md, "Features").

| part       | size  | content                                                                     |
| subjects   | 18    | 1 if ticked                                                                 |
| work types | 6     | 1 if ticked                                                                 |
| hobbies    | 15    | 1 if ticked                                                                 |
| workplace  | 6     | 1 if ticked                                                                 |
| answered   | 5     | 1 if that question was answered                                             |
| text       | 2^14  | TF-IDF of character 3-5-grams (hashed) of the free text, folded and teen code spelled out |

An answer is a dict with any of: subjects, work_types, hobbies, workplace (lists of keys) and free text under text,
dream or other (the generated sets keep the dream and the "other hobby" apart; the app joins them into text).
"""

from __future__ import annotations

import re
import zlib

import numpy as np
from scipy import sparse

from uniadvisor.student import suggest as sg
from uniadvisor.student.form.options import SUBJECTS
from unidata.text import fold

SUBJ = list(SUBJECTS)
WORK = list(sg.WORK_TYPES)
HOBBY = list(sg.HOBBIES)
PLACE = list(sg.WORKPLACES)
QUESTIONS = ["subjects", "work_types", "hobbies", "workplace", "text"]
TEXT_DIM = 2 ** 14
NGRAMS = (3, 4, 5)
TEEN = {"ko": "khong", "k": "khong", "kh": "khong", "hok": "khong", "dc": "duoc", "j": "gi", "bit": "biet",
        "vs": "voi", "e": "em", "mk": "minh", "mik": "minh", "hc": "hoc", "ng": "nguoi", "mun": "muon", "thik": "thich",
        "lm": "lam", "cx": "cung", "ns": "noi", "nma": "nhung ma", "nhg": "nhung", "trc": "truoc", "r": "roi"}
_TEEN_RE = re.compile(r"\b(" + "|".join(sorted(TEEN, key=len, reverse=True)) + r")\b")

OFFSETS = {}
_o = 0
for _name, _n in (("subjects", len(SUBJ)), ("work_types", len(WORK)), ("hobbies", len(HOBBY)),
                  ("workplace", len(PLACE)), ("answered", len(QUESTIONS))):
    OFFSETS[_name] = _o
    _o += _n
TEXT_OFFSET = _o
DIM = TEXT_OFFSET + TEXT_DIM
KEYS = {"subjects": SUBJ, "work_types": WORK, "hobbies": HOBBY, "workplace": PLACE}


def text_of(a: dict) -> str:
    return " ".join(str(a.get(k) or "") for k in ("text", "dream", "other")).strip()


def normalise(text: str) -> str:
    t = re.sub(r"[^a-z0-9 ]+", " ", fold(text))
    return re.sub(r"\s+", " ", _TEEN_RE.sub(lambda m: TEEN[m.group(1)], t)).strip()


def ngrams(text: str) -> list[int]:
    """Hashed character n-grams of the normalised text, within word boundaries padded with spaces."""
    t = f" {normalise(text)} "
    if len(t) <= 2:
        return []
    return [zlib.crc32(t[i:i + n].encode()) % TEXT_DIM for n in NGRAMS for i in range(len(t) - n + 1)]


def answered(a: dict) -> list[bool]:
    return [bool(a.get("subjects")), bool(a.get("work_types")), bool(a.get("hobbies") or a.get("other")),
            bool(a.get("workplace")), bool(text_of(a))]


class Featurizer:
    """Fits the text IDF on the training answers; then turns answers into rows of a sparse matrix."""

    def __init__(self, idf: np.ndarray | None = None):
        self.idf = idf

    def fit(self, answers: list[dict]) -> "Featurizer":
        df = np.zeros(TEXT_DIM)
        for a in answers:
            for j in set(ngrams(text_of(a))):
                df[j] += 1
        self.idf = np.log((1 + len(answers)) / (1 + df)) + 1
        return self

    def transform(self, answers: list[dict]) -> sparse.csr_matrix:
        rows, cols, vals = [], [], []
        for i, a in enumerate(answers):
            for key, names in KEYS.items():
                for k in a.get(key) or []:
                    if k in names:
                        rows.append(i)
                        cols.append(OFFSETS[key] + names.index(k))
                        vals.append(1.0)
            for q, on in enumerate(answered(a)):
                if on:
                    rows.append(i)
                    cols.append(OFFSETS["answered"] + q)
                    vals.append(1.0)
            grams = ngrams(text_of(a))
            if grams:
                tf: dict[int, float] = {}
                for j in grams:
                    tf[j] = tf.get(j, 0.0) + 1.0
                v = np.array([tf[j] * self.idf[j] for j in tf])
                v /= np.linalg.norm(v)
                rows += [i] * len(tf)
                cols += [TEXT_OFFSET + j for j in tf]
                vals += list(v)
        return sparse.csr_matrix((vals, (rows, cols)), shape=(len(answers), DIM))


def hobby_types(a: dict) -> list[str]:
    return [sg.HOBBIES[h][1] for h in a.get("hobbies") or [] if h in sg.HOBBIES]


def describe(j: int) -> str | None:
    """The Vietnamese reason for one non-text feature ("em thích Tin học"), None for the others."""
    if OFFSETS["subjects"] <= j < OFFSETS["work_types"]:
        return f"em thích hoặc học tốt {SUBJECTS[SUBJ[j - OFFSETS['subjects']]]}"
    if OFFSETS["work_types"] <= j < OFFSETS["hobbies"]:
        return "em thích " + sg.WORK_TYPES[WORK[j - OFFSETS["work_types"]]].lower()
    if OFFSETS["hobbies"] <= j < OFFSETS["workplace"]:
        return "lúc rảnh em hay " + sg.HOBBIES[HOBBY[j - OFFSETS["hobbies"]]][0].lower()
    if OFFSETS["workplace"] <= j < OFFSETS["answered"]:
        return "em muốn làm việc ở " + sg.WORKPLACES[PLACE[j - OFFSETS["workplace"]]].lower()
    return None
