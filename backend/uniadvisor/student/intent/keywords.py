"""The keyword reader: a student's text -> StudentIntent, every fact with the sentence it came from.

Interests, dislikes and the family's wish are read as MOET codes with backend/config/interests.yaml plus MOET's own major
names. Budget, location, risk, priority and self-assessed subjects use the keyword rules the judge has always used
(slm/infer.py imports them from here), so measuring this reader measures what the app reads today.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import yaml

from uniadvisor.student.intent import Fact, Interest, StudentIntent
from unidata.text import fold

# ------------------------------------------------------------------ rules shared with the judge (slm/infer.py)
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
HN = (" ha noi", " hn ", "thu do")
HCM = ("sai gon", "hcm", "ho chi minh")
NEAR = ("gan nha", "xa nha", "di xa", "di hoc xa")
ANYWHERE = ("dau cung duoc", "bac hay nam")
BRANCH = ("phan hieu", "co so tinh", "co so chinh")       # "không học ở phân hiệu", "chỉ học cơ sở chính"
SPEECH = ("noi lap", "noi ngong")
_MONEY = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:trieu|tr)\b")
_FEE_WORDS = ("hoc phi", "tien hoc", "chi duoc", "lo duoc", "dong")

# "Bố mẹ bắt em học X", "Mẹ em muốn em học X", "Gia đình định hướng X": a field the family wants
FAMILY = re.compile(r" (?:bo me|bo|me|ba|gia dinh|vo chong toi|nha) (?:\w+ ){0,3}(?:bat|muon|dinh huong|khuyen|mong) ")
SELF_NEG = ("khong thich", "khong muon", "ko thich", "ko muon", "khong hop", "chang thich")


def sentences(text: str) -> list[str]:
    """Folded sentences with punctuation turned into spaces and padded, so keywords match whole words."""
    return [f" {re.sub(r'[^a-z0-9]+', ' ', fold(s)).strip()} " for s in re.split(r"[.!?\n;]+", text or "") if s.strip()]


_SENTENCE_END = re.compile(r"(?:(?<!\d)\.|\.(?!\d)|[!?;\n])+")  # a full stop, but not the one in "2.5 triệu"


def _raw_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text or "") if s.strip()]


def _evidence(text: str, found) -> str:  # noqa: ANN001
    """The first sentence of `text` where found(padded folded sentence) holds (keywords are matched the same way)."""
    for s in _raw_sentences(text):
        if found(f" {fold(s)} "):
            return s
    return ""


# subject names as written (diacritics folded); English also as "tiếng Anh" / "ngoại ngữ"
_SUBJ = {"TO": r"toan", "VA": r"(?:ngu )?van", "LI": r"(?:vat )?(?:ly|li)", "HO": r"hoa(?: hoc)?", "SI": r"sinh(?: hoc)?",
         "SU": r"(?:lich )?su", "DI": r"dia(?: ly| li)?", "N1": r"(?:tieng anh|anh van|ngoai ngu|mon anh)",
         "TI": r"tin(?: hoc)?", "GDKTPL": r"(?:gd)?ktpl"}
_STRONG = (r"\b(?:hoc )?(?:tot|gioi|manh) (?:mon )?{s}\b", r"\b(?:mon )?{s} (?:la mon manh nhat|la mon tot nhat|"
           r"(?:\w+ ){{0,2}}(?:rat |kha )?(?:tot|gioi|on))\b", r"\btu tin (?:\w+ )?{s}\b", r"\b{s} (?:\w+ ){{0,4}}tu tin\b")
_WEAK = (r"\b(?:yeu|kem|so|mat goc|duoi) (?:nhat la )?(?:mon )?{s}\b", r"\b(?:mon )?{s} (?:\w+ ){{0,2}}(?:hoc )?(?:rat )?(?:kem|yeu|te)\b",
         r"\bso nhat la (?:mon )?{s}\b", r"\b{s} (?:\w+ ){{0,3}}(?:chua|khong|ko|k) (?:\w+ )?(?:tot|gioi|on)\b")


def _subject_sentences(text: str) -> list[tuple[str, str]]:
    """(original sentence, folded sentence) with punctuation removed, as the subject patterns expect."""
    out = []
    for x in _SENTENCE_END.split(text):
        out.append((x.strip(), re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", fold(x))).strip()))
    return out


@lru_cache(maxsize=256)
def self_assessed_evidence(text: str) -> tuple[dict[str, str], dict[str, str]]:
    """Subjects the student says they are good / weak at, each with its sentence ("Toán là môn mạnh nhất",
    "Em yếu môn Lý", "Tiếng Anh em rất kém", "Em có IELTS 6.5")."""
    strong, weak = {}, {}
    for raw, t in _subject_sentences(text):  # sentence by sentence: "...môn Hóa. Môn Văn em học kém" must not make Hóa weak
        for code, name in _SUBJ.items():
            if any(re.search(p.format(s=name), t) for p in _WEAK):
                weak.setdefault(code, raw)
            elif any(re.search(p.format(s=name), t) for p in _STRONG):
                strong.setdefault(code, raw)
    strong = {k: v for k, v in strong.items() if k not in weak}
    if "ielts" in fold(text) and "N1" not in weak:
        strong.setdefault("N1", _evidence(text, lambda s: "ielts" in s))
    return strong, weak


def self_assessed(text: str) -> tuple[frozenset[str], frozenset[str]]:
    strong, weak = self_assessed_evidence(text)
    return frozenset(strong), frozenset(weak)


@lru_cache(maxsize=256)
def budget(text: str) -> tuple[str | None, float | None]:
    t = fold(text)
    m = _MONEY.search(t)
    if m and any(k in t for k in _FEE_WORDS):
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
def location(text: str) -> str | None:
    t = f" {fold(text)} "
    hn = any(k in t for k in HN)
    hcm = any(k in t for k in HCM)
    if any(k in t for k in ANYWHERE) or "khong quan trong" in t and "dia diem" in t:
        return "anywhere"
    if "thanh pho lon" in t:
        return "no_big_city"
    if hn and not hcm:
        return "city:Hà Nội"
    if hcm and not hn:
        return "city:TP. Hồ Chí Minh"
    if any(k in t for k in NEAR):
        return "near_home"
    return None


def risk(text: str) -> str | None:
    """The risk attitude with the most keyword hits; None when nothing or a tie."""
    t = f" {fold(text)} "
    hits = {k: sum(w in t for w in ws) for k, ws in RISK_KW.items()}
    best = max(hits, key=hits.get)
    if hits[best] == 0 or sorted(hits.values())[-2] == hits[best]:
        return None
    return best


def priority(text: str) -> str | None:
    t = f" {fold(text)} "
    hits = {k: sum(w in t for w in ws) for k, ws in PRIORITY_KW.items()}
    best = max(hits, key=hits.get)
    return best if hits[best] else None


# ------------------------------------------------------------------ interests as MOET codes
_OLD_TONE = {"oà": "òa", "oá": "óa", "oả": "ỏa", "oã": "õa", "oạ": "ọa", "oè": "òe", "oé": "óe", "oẻ": "ỏe", "oẽ": "õe",
             "oẹ": "ọe", "uỳ": "ùy", "uý": "úy", "uỷ": "ủy", "uỹ": "ũy", "uỵ": "ụy"}
_CLAUSE_BREAK = {",", ":", "nhung", "con", "ma", "du"}
_STATED = ("muon", "uoc mo", "nguyen vong", "dinh", "dam me")       # a stated wish, not a hobby
_NEG_WORDS = ("khong thich", "khong muon", "khong hop", "khong co nang khieu", "chang thich", "ko thich", "ko muon",
              "k thich", "k muon", "ghet", "chan", "buon ngu", "ngai", "so")


def _norm(s: str) -> str:
    """Lowercase NFC with one tone placement ("hoá" = "hóa"); diacritics kept."""
    s = unicodedata.normalize("NFC", s).lower()
    for a, b in _OLD_TONE.items():
        s = s.replace(a, b)
    return s


def _tokens(s: str) -> list[str]:
    """Words and clause punctuation of a normalised string ("điện - điện tử" -> điện, điện, tử)."""
    return re.findall(r"\w+|[,:]", s)


def _has_marks(s: str) -> bool:
    return any(c in "đĐ" or unicodedata.decomposition(c) for c in s if c.isalpha())


@dataclass(frozen=True)
class Term:
    words: tuple[str, ...]        # folded
    marked: tuple[str, ...]       # with diacritics
    codes: tuple[str, ...]
    cue_only: bool
    needs_marks: bool


@lru_cache(maxsize=1)
def lexicon() -> tuple[tuple[Term, ...], frozenset[str]]:
    """(terms longest first, cue words), from backend/config/interests.yaml and MOET's names."""
    from unidata.build.fields import code_prefixes
    from unidata.build.majors import catalog
    from unidata.paths import BACKEND_CONFIG

    cfg = yaml.safe_load((BACKEND_CONFIG / "interests.yaml").read_text(encoding="utf-8"))
    own_nganh = {p for p, _ in code_prefixes() if len(p) == 7}  # ngành that data/config/fields.yaml places on their own
    cue_only = {_norm(t) for t in cfg["cue_only"]}
    needs_marks = {_norm(t) for t in cfg["needs_diacritics"]}
    skip = {_norm(t) for t in cfg["skip_moet_names"]}
    by_term: dict[str, tuple[str, ...]] = {}
    for r in catalog().itertuples():
        name = _norm(re.sub(r"\(.*?\)", " ", r.name))
        if name in skip or name == "khác":
            continue
        code = r.code if r.level != "nganh" or r.code in own_nganh else r.parent
        by_term.setdefault(" ".join(_tokens(name.replace(",", " "))), (code,))
    for entry in cfg["terms"]:
        for t in entry["terms"]:
            by_term[" ".join(_tokens(_norm(str(t))))] = tuple(str(c) for c in entry["codes"])
    terms = [Term(tuple(fold(w) for w in t.split()), tuple(t.split()), codes, t in cue_only, bool(set(t.split()) & needs_marks))
             for t, codes in by_term.items() if t]
    terms.sort(key=lambda x: (-len(x.words), x.words))
    return tuple(terms), frozenset(fold(w) for w in cfg["cue_words"])


@lru_cache(maxsize=1)
def _by_first_word() -> dict[str, tuple[Term, ...]]:
    out: dict[str, list[Term]] = {}
    for t in lexicon()[0]:
        out.setdefault(t.words[0], []).append(t)
    return {k: tuple(v) for k, v in out.items()}


def _match(marked: list[str], cues: frozenset[str]) -> list[tuple[int, Term]]:
    """(start token, term) for each term found, longest first, never overlapping."""
    folded = [fold(w) for w in marked]
    has_marks = _has_marks(" ".join(marked))
    index = _by_first_word()
    candidates = []
    for i, w in enumerate(folded):
        for term in index.get(w, ()):
            if term.needs_marks and not has_marks:
                continue
            seq, want = (marked, term.marked) if term.needs_marks else (folded, term.words)
            if tuple(seq[i:i + len(want)]) != want:
                continue
            if term.cue_only and (i == 0 or folded[i - 1] not in cues):
                continue
            candidates.append((i, term))
    used = [False] * len(marked)
    found = []
    for i, term in sorted(candidates, key=lambda x: (-len(x[1].words), x[0])):
        n = len(term.words)
        if not any(used[i:i + n]):
            used[i:i + n] = [True] * n
            found.append((i, term))
    return sorted(found, key=lambda x: x[0])


def _clauses(tokens: list[str]) -> list[tuple[int, int]]:
    """(start, end) token ranges split at commas and "nhưng / còn / mà / dù"."""
    out, start = [], 0
    for i, w in enumerate(tokens):
        if fold(w) in _CLAUSE_BREAK:
            out.append((start, i))
            start = i + 1
    out.append((start, len(tokens)))
    return [(a, b) for a, b in out if b > a]


def _negated(folded_clause: str) -> bool:
    t = f" {folded_clause} "
    t = t.replace(" con so ", " ").replace(" so sach ", " sach ")  # "các con số", "sổ sách" are not "sợ"
    return any(f" {w} " in t for w in _NEG_WORDS)


@lru_cache(maxsize=256)
def areas(text: str) -> tuple[tuple[Interest, ...], tuple[Interest, ...], Interest | None, bool | None]:
    """(interests, dislikes, family wish, does the student accept it) as MOET codes."""
    cues = lexicon()[1]
    likes: dict[tuple[str, ...], Interest] = {}
    dislikes: dict[tuple[str, ...], Interest] = {}
    family, agrees = None, None
    for raw in _raw_sentences(text):
        tokens = _tokens(_norm(raw))
        folded = " ".join(fold(w) for w in tokens)
        found = _match(tokens, cues)
        if not found:
            continue
        codes = tuple(sorted({c for _, t in found for c in t.codes}))
        if FAMILY.search(f" {re.sub(r'[^a-z0-9]+', ' ', folded)} "):
            # the family's wish is neither a like nor a dislike of the student
            t = f" {re.sub(r'[^a-z0-9]+', ' ', folded)} "
            if family is None:
                family = Interest(codes, raw)
                agrees = not (any(n in t for n in SELF_NEG) and "khong phan doi" not in t)
            continue
        for a, b in _clauses(tokens):
            in_clause = [(i, t) for i, t in found if a <= i < b]
            if not in_clause:
                continue
            clause = " ".join(fold(w) for w in tokens[a:b])
            c = tuple(sorted({x for _, t in in_clause for x in t.codes}))
            if _negated(clause):
                dislikes.setdefault(c, Interest(c, raw))
            else:
                stated = any(f" {w} " in f" {folded} " for w in _STATED) or any(
                    i > 0 and fold(tokens[i - 1]) in ("hoc", "nganh", "theo", "lam") for i, _ in in_clause)
                likes.setdefault(c, Interest(c, raw, implied=not stated))
    disliked = {x for d in dislikes.values() for x in d.codes}
    kept = tuple(i for i in likes.values() if not set(i.codes) <= disliked)
    return kept, tuple(dislikes.values()), family, agrees


# ------------------------------------------------------------------ the reader
def extract(text: str) -> StudentIntent:
    """Every fact the keyword rules find in a student's text, with the sentence it came from."""
    text = text or ""
    interests, dislikes, family, agrees = areas(text)
    out = StudentIntent(interests=list(interests), dislikes=list(dislikes), family=family, family_agrees=agrees)

    kind, amount = budget(text)
    if kind == "number":
        out.budget = Fact(amount, _evidence(text, lambda s: bool(_MONEY.search(s))))
    elif kind is not None:
        out.budget = Fact(kind, _evidence(text, lambda s: any(k in s for k in (RICH if kind == "rich" else POOR))))
    loc = location(text)
    if loc is not None:
        words = {"anywhere": ANYWHERE + ("dia diem",), "no_big_city": ("thanh pho lon",), "near_home": NEAR,
                 "city:Hà Nội": HN, "city:TP. Hồ Chí Minh": HCM}[loc]
        out.location = Fact(loc, _evidence(text, lambda s: any(k in s for k in words)))
    if any(k in f" {fold(text)} " for k in BRANCH):
        out.avoid_branch = Fact(True, _evidence(text, lambda s: any(k in s for k in BRANCH)))
    r = risk(text)
    if r is not None:
        out.risk = Fact(r, _evidence(text, lambda s: any(w in s for w in RISK_KW[r])))
    p = priority(text)
    if p is not None:
        out.priority = Fact(p, _evidence(text, lambda s: any(w in s for w in PRIORITY_KW[p])))
    strong, weak = self_assessed_evidence(text)
    if "ielts" in fold(text) and "N1" not in weak:
        out.english = Fact("ielts", strong["N1"])
    elif "N1" in weak:
        out.english = Fact("weak", weak["N1"])
    elif "N1" in strong:
        out.english = Fact("good", strong["N1"])
    out.strong = {s: e for s, e in strong.items() if s != "N1"}
    out.weak = {s: e for s, e in weak.items() if s != "N1"}
    if any(k in f" {fold(text)} " for k in SPEECH):
        out.speech_issue = Fact(True, _evidence(text, lambda s: any(k in s for k in SPEECH)))
    return out
