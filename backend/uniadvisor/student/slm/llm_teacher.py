"""Optional LLM teacher: relabel SLM examples from the written rubric alone (it never sees the
synthetic latents), several samples per item -> soft labels. Uses Gemini through `google-genai`,
the same setup as the UniPilotData pipeline (GEMINI_API_KEYS comma-separated, GEMINI_MODEL,
GEMINI_REQUESTS_PER_MINUTE).

  uniadvisor slm-relabel --split train --limit 3000 --samples 3

Writes backend/slm_data/<split>.llm.jsonl (same format, soft_label from the LLM, `teacher` field set) and
reports agreement with the rubric teacher. Answers are cached in backend/slm_data/llm_cache/.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from pathlib import Path

from unidata.paths import SLM_DATA
from uniadvisor.student.slm.questions import BY_ID

PROMPT = """Bạn là người gán nhãn dữ liệu tư vấn tuyển sinh. Với mỗi mục, đọc CÂU HỎI, HỒ SƠ học sinh và NGÀNH,
rồi chọn đúng MỘT nhãn trong danh sách được phép, theo rubric. Chỉ dựa vào thông tin có trong văn bản;
nếu văn bản không đủ để trả lời thì chọn "insufficient".

RUBRIC:
{rubrics}

Trả về JSON: {{"answers": [{{"i": <số thứ tự>, "label": "<nhãn>"}}, ...]}}

CÁC MỤC:
{items}
"""


class GeminiTeacher:
    def __init__(self, model: str | None = None, rpm: float | None = None):
        from google import genai  # pip install google-genai

        from uniadvisor.student.slm.llm_label import env_keys

        keys = env_keys()
        if not keys:
            raise RuntimeError("Set GEMINI_API_KEYS (comma-separated) to use the LLM teacher.")
        self.clients = [genai.Client(api_key=k) for k in keys]
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.gap = 60.0 / float(rpm or os.environ.get("GEMINI_REQUESTS_PER_MINUTE", 8))
        self.last = [0.0] * len(keys)
        self.turn = 0
        self.name = f"gemini:{self.model}"

    def complete(self, prompt: str, temperature: float) -> str:
        from google.genai import types

        for _ in range(len(self.clients) * 3):
            i = self.turn % len(self.clients)
            self.turn += 1
            wait = self.gap - (time.monotonic() - self.last[i])
            if wait > 0:
                time.sleep(wait)
            self.last[i] = time.monotonic()
            try:
                r = self.clients[i].models.generate_content(
                    model=self.model, contents=prompt,
                    config=types.GenerateContentConfig(temperature=temperature, response_mime_type="application/json"))
                return r.text or ""
            except Exception as e:  # noqa: BLE001 - rate limit on this key: try the next one
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    continue
                raise
        raise RuntimeError("all keys are rate-limited")


def _rubrics(qids: set[str]) -> str:
    out = []
    for q in qids:
        spec = BY_ID[q]
        out.append(f"[{q}] {spec.text_vi}\nNhãn: {', '.join(spec.all_labels)}\n{spec.rubric}")
    return "\n\n".join(out)


def relabel(split: str = "train", limit: int | None = None, samples: int = 3, batch: int = 8, temperature: float = 0.7,
            data: Path = SLM_DATA, teacher: GeminiTeacher | None = None) -> dict:
    teacher = teacher or GeminiTeacher()
    rows = [json.loads(line) for line in open(data / f"{split}.jsonl", encoding="utf-8")][: limit or None]
    cache_dir = data / "llm_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    votes: dict[str, list[str]] = {r["id"]: [] for r in rows}
    for s in range(0, len(rows), batch):
        chunk = rows[s:s + batch]
        items = "\n\n".join(f"#{i} [{r['question']}] Nhãn được phép: {', '.join(BY_ID[r['question']].all_labels)}\n{r['text_a']}\nNGÀNH: {r['text_b']}"
                            for i, r in enumerate(chunk))
        prompt = PROMPT.format(rubrics=_rubrics({r["question"] for r in chunk}), items=items)
        for k in range(samples):
            key = hashlib.sha1(f"{teacher.name}|{temperature}|{k}|{prompt}".encode()).hexdigest()
            path = cache_dir / f"{key}.json"
            if path.exists():
                text = path.read_text(encoding="utf-8")
            else:
                text = teacher.complete(prompt, temperature)
                path.write_text(text, encoding="utf-8")
            try:
                answers = json.loads(text).get("answers", [])
            except json.JSONDecodeError:
                continue
            for a in answers:
                i, lab = a.get("i"), str(a.get("label", "")).strip()
                if isinstance(i, int) and 0 <= i < len(chunk) and lab in BY_ID[chunk[i]["question"]].all_labels:
                    votes[chunk[i]["id"]].append(lab)
    out, agree, n = [], 0, 0
    for r in rows:
        v = votes[r["id"]]
        if not v:
            continue
        labels = BY_ID[r["question"]].all_labels
        c = Counter(v)
        soft = {lab: c[lab] / len(v) for lab in labels}
        hard = max(soft, key=soft.get)
        agree += hard == r["label"]
        n += 1
        out.append({**r, "soft_label": soft, "label": hard, "teacher": teacher.name, "rubric_teacher_label": r["label"]})
    with open(data / f"{split}.llm.jsonl", "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return {"split": split, "labelled": n, "agreement_with_rubric_teacher": round(agree / max(1, n), 4)}
