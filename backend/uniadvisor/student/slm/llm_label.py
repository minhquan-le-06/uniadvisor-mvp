"""Label the gold set with Gemini (a second, independent labeller; never trained on).

    uniadvisor gold-llm                      # keys from .env / environment (GEMINI_API_KEYS=k1,k2,... or GEMINI_API_KEY_1..N)

Two rows per request (same question), so the model can't mix cases up. Each request carries the question's
rubric and a plain "look only at / ignore" guide (~1-2k tokens in total). Output goes to backend/slm_data/gold_llm.csv,
in the same format as the human file, so `uniadvisor slm-eval --gold backend/slm_data/gold_llm.csv` works on it. The
model that answered is stored in `labeller`, its one-line reason in `note`. Saved after every request: re-run
to resume (e.g. the next day, when the free quota resets).

Quota handling: models are tried in order (Flash, then Flash-Lite), each with every key. A key whose daily quota
is used up for a model is skipped for that model; a per-minute limit waits and retries the same key.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Callable

import httpx
import pandas as pd

from unidata.paths import SLM_DATA
from uniadvisor.student.slm import gold
from uniadvisor.student.slm.questions import BY_ID, INSUFFICIENT

log = logging.getLogger(__name__)

OUT = SLM_DATA / "gold_llm.csv"
KEYS_FILE = SLM_DATA / "gemini_keys.txt"  # one key per line; git-ignored
MODELS = ("gemini-3.5-flash", "gemini-3.5-flash-lite")
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ROWS_PER_REQUEST = 2
CASE_IDS = "AB"

# what each question may look at; the app combines the 7 answers itself
FOCUS = {
    "ability_fit": ("the student's scores and self-assessment in the program field's CORE subjects",
                    "money, location, interests, and the chance of admission (another part of the app handles that)"),
    "interest_fit": ("the student's stated interests, favourite subjects, dream job and dislikes", "scores, money, location"),
    "budget_ok": ("the program's tuition vs what the family says it can pay", "everything else"),
    "location_ok": ("where the program is taught vs where the student wants to study or live", "everything else"),
    "conditions_ok": ("the program's special conditions (English-taught, gender, health/speech, branch campus) vs the student",
                      "everything else"),
    "risk_tolerance": ("the student's (or parent's) own words about risk: must pass vs willing to gamble", "any program"),
    "top_priority": ("what the student (or parent) says matters MOST when choosing", "any program"),
}

GENERAL = """You label test data for a Vietnamese university-admission advice app. Each case is a student profile (partly
synthetic: scores, home province, and free text written by the student or a parent, sometimes in teen-speak, without
diacritics, or with typos) and, for most questions, one real university program.

Answer ONE question per case, following the rubric exactly.
- Look only at: {focus}. Ignore: {ignore}.
- Label what the text says, not what is probably true. If the text does not give the information the rubric needs,
  answer "insufficient".
- Programs were paired with students partly at random on purpose. Never judge whether the pairing makes sense;
  just answer the question for it.
- Cases are independent: never let one case influence the other.
- "reason": at most 20 words, in English, naming the evidence you used.

Question (Vietnamese): {question}
Allowed labels:
{labels}

Rubric (Vietnamese; the authority when in doubt):
{rubric}"""


def instructions(qid: str) -> str:
    q = BY_ID[qid]
    labels = "\n".join(f"- {lab}: {vi}" for lab, vi in zip(q.labels, q.labels_vi))
    labels += f"\n- {INSUFFICIENT}: the text does not say enough to answer"
    focus, ignore = FOCUS[qid]
    return GENERAL.format(focus=focus, ignore=ignore, question=q.text_vi, labels=labels, rubric=q.rubric)


def case_text(text_a: str, text_b: str) -> str:
    profile = text_a.split("Hồ sơ:", 1)[-1].strip()  # the question is already in the instructions
    return f"Student: {profile}\nProgram: {text_b}"


def request_body(qid: str, cases: list[tuple[str, str]]) -> dict:
    """cases: [(text_a, text_b)] -> Gemini generateContent body with a JSON schema for the answers."""
    ids = list(CASE_IDS[: len(cases)])
    user = "\n\n".join(f"Case {i}:\n{case_text(a, b)}" for i, (a, b) in zip(ids, cases))
    user += f"\n\nAnswer every case ({', '.join(ids)}) exactly once."
    schema = {"type": "OBJECT", "required": ["answers"], "properties": {"answers": {"type": "ARRAY", "items": {
        "type": "OBJECT", "required": ["case", "label", "reason"], "propertyOrdering": ["case", "reason", "label"],
        "properties": {"case": {"type": "STRING", "enum": ids}, "reason": {"type": "STRING"},
                       "label": {"type": "STRING", "enum": list(BY_ID[qid].all_labels)}}}}}}
    return {"systemInstruction": {"parts": [{"text": instructions(qid)}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "responseSchema": schema}}


def parse_answers(resp: dict, qid: str, n: int) -> list[tuple[str, str]] | None:
    """[(label, reason)] in case order, or None when the reply is incomplete or off the label set."""
    try:
        parts = resp["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        answers = json.loads(text)["answers"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None
    by_case = {a.get("case"): a for a in answers if isinstance(a, dict)}
    out = []
    for i in CASE_IDS[:n]:
        a = by_case.get(i)
        if a is None or a.get("label") not in BY_ID[qid].all_labels:
            return None
        out.append((a["label"], re.sub(r"\s+", " ", str(a.get("reason", ""))).strip()[:200]))
    return out


KEY_NAME = re.compile(r"(GEMINI|GOOGLE)_API_KEYS?_?(\d*)", re.IGNORECASE)


def env_keys() -> list[str]:
    """Keys from GEMINI_API_KEYS / GEMINI_API_KEY / GEMINI_API_KEY_1.._N (also KEY1, and GOOGLE_API_KEY...).
    A value may hold several keys separated by commas, semicolons or spaces. Unnumbered names come first,
    numbered ones in numeric order."""
    found = []
    for name, value in os.environ.items():
        m = KEY_NAME.fullmatch(name)
        if m:
            vendor = 0 if m.group(1).upper() == "GEMINI" else 1
            found.append((vendor, int(m.group(2) or 0), name, value))
    keys = [k for *_, value in sorted(found) for k in re.split(r"[,;\s]+", value.strip().strip("'\""))]
    return list(dict.fromkeys(k for k in keys if k))


def load_keys(keys_file: Path = KEYS_FILE) -> list[str]:
    """Keys from the environment (the CLI loads .env into it first), then backend/slm_data/gemini_keys.txt."""
    keys = env_keys()
    if keys_file.exists():
        keys += [line.strip() for line in keys_file.read_text(encoding="utf-8").splitlines()]
    return list(dict.fromkeys(k for k in keys if k and not k.startswith("#")))


Post = Callable[[str, str, dict], tuple[int, dict]]


def _post(model: str, key: str, body: dict) -> tuple[int, dict]:
    r = httpx.post(URL.format(model=model), json=body, headers={"x-goog-api-key": key}, timeout=120)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"error": {"message": r.text[:300]}}


def _retry_after(err: dict) -> float | None:
    for d in err.get("error", {}).get("details", []) or []:
        m = re.fullmatch(r"(\d+(?:\.\d+)?)s", str(d.get("retryDelay", "")))
        if m:
            return float(m.group(1))
    return None


def _daily(err: dict) -> bool:
    return "perday" in json.dumps(err).lower().replace("_", "").replace(" ", "")


def rubric_version(qid: str) -> str:
    """Short hash of the instructions a question is labelled with; stored as 'model#version' in `labeller`."""
    return hashlib.sha1(instructions(qid).encode()).hexdigest()[:6]


def needs_label(row: pd.Series, redo: tuple[str, ...] = ()) -> bool:
    """Unlabelled; or labelled under older instructions (tag differs); or untagged (labelled before tags existed)
    for a question listed in `redo`."""
    if not row.human_label.strip():
        return True
    _, _, tag = row.labeller.partition("#")
    return tag != rubric_version(row.question) if tag else row.question in redo


def run(keys: list[str], models: tuple[str, ...] = MODELS, out: Path = OUT, delay: float = 4.0,
        limit: int | None = None, post: Post = _post, sleep: Callable[[float], None] = time.sleep,
        redo: tuple[str, ...] = ()) -> dict:
    """Label every unlabelled gold row; returns counts. Stops early when every key/model is out of quota."""
    if not keys:
        from unidata.env import describe

        raise ValueError("no Gemini API key found. Put a line GEMINI_API_KEYS=key1,key2,... in a file named exactly "
                         f".env in the project root (see .env.example). Checked:\n{describe()}")
    df = gold.load(labeled=out)
    open_rows = df[df.apply(needs_label, axis=1, redo=redo)]
    batches = [list(g.index[i:i + ROWS_PER_REQUEST]) for _, g in open_rows.groupby("question", sort=True)
               for i in range(0, len(g), ROWS_PER_REQUEST)]
    if limit is not None:
        batches = batches[:limit]
    done = int((df.human_label.str.strip() != "").sum())
    log.info("%s: %s, %d/%d labelled; this run: %d requests (%d rows)", out.name,
             "found" if out.exists() else "NOT FOUND, starting from scratch", done, len(df), len(batches), len(open_rows))
    dead: set[tuple[str, str]] = set()   # (model, key) out of daily quota
    bad_models: set[str] = set()
    stats = {"requests": 0, "labelled": 0, "invalid_replies": 0, "left": 0, "by_model": {}}
    for bi, idx in enumerate(batches):
        qid = df.at[idx[0], "question"]
        body = request_body(qid, [(df.at[i, "text_a"], df.at[i, "text_b"]) for i in idx])
        answers, tries = None, 0
        while answers is None:
            combo = next(((m, k) for m in models if m not in bad_models for k in keys if (m, k) not in dead), None)
            if combo is None:
                stats["left"] = len(batches) - bi
                log.warning("no usable key/model left (daily quota used up or key rejected); re-run later for the remaining %d requests", stats["left"])
                gold.save(df, out)
                return stats
            model, key = combo
            status, resp = post(model, key, body)
            stats["requests"] += 1
            if status == 200:
                answers = parse_answers(resp, qid, len(idx))
                if answers is None:
                    stats["invalid_replies"] += 1
                    tries += 1
                    if tries >= 3:
                        log.warning("giving up on %s after 3 invalid replies", [df.at[i, "id"] for i in idx])
                        break
            elif status == 429:
                wait = _retry_after(resp)
                if _daily(resp) or wait is None or wait > 120:
                    dead.add(combo)
                    log.info("%s: key #%d out of daily quota", model, keys.index(key) + 1)
                else:
                    sleep(wait + 1)
            elif status == 404:
                bad_models.add(model)
                log.warning("model %s not found; skipping it", model)
            elif status in (400, 401, 403):
                for m in models:
                    dead.add((m, key))
                log.warning("key #%d rejected (%s): %s", keys.index(key) + 1, status, resp.get("error", {}).get("message", "")[:120])
            else:
                tries += 1
                if tries >= 3:
                    log.warning("giving up on this request after HTTP %s", status)
                    break
                sleep(2 ** tries)
            sleep(delay)
        if answers is None:
            continue
        for i, (label, reason) in zip(idx, answers):
            df.at[i, "human_label"], df.at[i, "labeller"], df.at[i, "note"] = label, f"{model}#{rubric_version(qid)}", reason
        stats["labelled"] += len(idx)
        stats["by_model"][model] = stats["by_model"].get(model, 0) + len(idx)
        gold.save(df, out)
        log.info("%d/%d %s -> %s", bi + 1, len(batches), qid, [a for a, _ in answers])
    return stats


def current_teacher_labels(data: Path = SLM_DATA) -> dict[str, str]:
    """Teacher label per gold id, recomputed with the current teacher from the frozen rows (falls back to test.jsonl)."""
    import random
    from dataclasses import fields

    from uniadvisor.student.slm import teacher
    from uniadvisor.student.slm.synth import Latent

    frozen = data / "gold_frozen.jsonl"
    if not frozen.exists():
        test = data / "test.jsonl"
        return {r["id"]: r["label"] for r in map(json.loads, open(test, encoding="utf-8"))} if test.exists() else {}
    names = {f.name for f in fields(Latent)}
    out = {}
    for r in map(json.loads, open(frozen, encoding="utf-8")):
        z = {k: v for k, v in r["latent"].items() if k in names}
        z["interests"] = [tuple(x) for x in z.get("interests") or []]
        soft = teacher.label(r["question"], Latent(**z), r["program"], random.Random(r["id"]))
        out[r["id"]] = max(soft, key=soft.get)
    return out


def agreement(out: Path = OUT, human: Path = gold.LABELED, test: Path = SLM_DATA / "test.jsonl") -> pd.DataFrame:
    """Per question: how often Gemini agrees with the synthetic teacher label (and with you, once you have labelled)."""
    g = pd.read_csv(out, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    g = g[g.human_label != ""]
    teacher = current_teacher_labels(test.parent)
    if teacher:
        g["teacher"] = g.id.map(teacher)
    if human.exists():
        h = pd.read_csv(human, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        g["you"] = g.id.map(dict(zip(h.id, h.human_label))).replace("", None)
    rows = []
    for q, s in g.groupby("question"):
        r = {"question": q, "labelled": len(s)}
        for col in ("teacher", "you"):
            if col in s and s[col].notna().any():
                m = s[col].notna()
                r[f"agree_{col}"] = round(float((s.human_label[m] == s[col][m]).mean()), 3)
        rows.append(r)
    return pd.DataFrame(rows)
