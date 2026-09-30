import json

import pandas as pd

from uniadvisor.slm import gold, llm_label


def _template(tmp_path, n=5):
    rows = [dict(id=f"id{i}", question="budget_ok" if i < 3 else "location_ok", options="yes | no | insufficient",
                 text_a=f"Câu hỏi: ... Hồ sơ: Điểm thi: Toán 8. Học sinh chia sẻ: case {i}", text_b=f"Ngành: P{i}",
                 human_label="", labeller="", note="") for i in range(n)]
    path = tmp_path / "gold_to_label.csv"
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _reply(body, label="yes"):
    cases = body["generationConfig"]["responseSchema"]["properties"]["answers"]["items"]["properties"]["case"]["enum"]
    text = json.dumps({"answers": [{"case": c, "reason": "r", "label": label} for c in cases]})
    return {"candidates": [{"content": {"parts": [{"text": "thinking...", "thought": True}, {"text": text}]}}]}


def test_two_rows_per_request_quota_fallback_and_resume(tmp_path, monkeypatch):
    monkeypatch.setattr(gold, "TEMPLATE", _template(tmp_path))
    monkeypatch.setattr(gold.load, "__defaults__", (gold.TEMPLATE, gold.LABELED))
    out = tmp_path / "gold_llm.csv"
    calls = []

    def post(model, key, body):
        calls.append((model, key))
        assert body["contents"][0]["parts"][0]["text"].count("Case ") == len(
            body["generationConfig"]["responseSchema"]["properties"]["answers"]["items"]["properties"]["case"]["enum"]) <= 2
        assert "Look only at" in body["systemInstruction"]["parts"][0]["text"]
        if (model, key) == ("flash", "k1") and len(calls) > 1:  # k1 runs out after one request
            return 429, {"error": {"details": [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}}
        return 200, _reply(body)

    s = llm_label.run(["k1", "k2"], models=("flash", "lite"), out=out, delay=0, limit=2, post=post, sleep=lambda _: None)
    assert s["labelled"] == 3 and calls == [("flash", "k1"), ("flash", "k1"), ("flash", "k2")]
    s = llm_label.run(["k1", "k2"], models=("flash", "lite"), out=out, delay=0, post=post, sleep=lambda _: None)
    assert s["labelled"] == 2  # resumed: only the 2 location rows were left
    df = pd.read_csv(out, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    assert (df.human_label == "yes").all() and set(df.labeller) == {"flash"}


def test_invalid_reply_and_all_quota_gone(tmp_path, monkeypatch):
    monkeypatch.setattr(gold.load, "__defaults__", (_template(tmp_path, 2), gold.LABELED))
    out = tmp_path / "gold_llm.csv"
    replies = iter([(200, {"candidates": [{"content": {"parts": [{"text": '{"answers": [{"case": "A", "label": "maybe"}]}'}]}}]}),
                    (429, {"error": {"message": "quota", "details": [{"retryDelay": "3600s"}]}})])
    s = llm_label.run(["k1"], models=("flash",), out=out, delay=0, post=lambda m, k, b: next(replies), sleep=lambda _: None)
    assert s["invalid_replies"] == 1 and s["labelled"] == 0 and s["left"] == 1


def test_instructions_cover_every_question():
    from uniadvisor.slm.questions import QUESTIONS

    for q in QUESTIONS:
        text = llm_label.instructions(q.id)
        assert q.rubric in text and "insufficient" in text and len(text) < 6000


def test_keys_come_from_dotenv_and_shell_wins(tmp_path, monkeypatch):
    from uniadvisor.env import load_dotenv

    for k in ("GEMINI_API_KEYS", "GEMINI_API_KEY", "GEMINI_API_KEY_1", "GEMINI_API_KEY_2", "GEMINI_API_KEY_10", "OTHER"):
        monkeypatch.delenv(k, raising=False)
    env = tmp_path / ".env"
    env.write_text('# my keys\nGEMINI_API_KEYS="a, b"\nexport GEMINI_API_KEY_2=d  # comment\nGEMINI_API_KEY_10=\'e\'\n'
                   "GEMINI_API_KEY_1=c\n\nOTHER=from-file\n", encoding="utf-8")
    monkeypatch.setenv("OTHER", "from-shell")
    assert sorted(load_dotenv(env)) == ["GEMINI_API_KEYS", "GEMINI_API_KEY_1", "GEMINI_API_KEY_10", "GEMINI_API_KEY_2"]
    import os

    assert os.environ["OTHER"] == "from-shell"
    assert llm_label.load_keys(tmp_path / "missing.txt") == ["a", "b", "c", "d", "e"]  # numbered keys in numeric order


def test_dotenv_windows_variants_and_diagnostics(tmp_path, monkeypatch):
    import os

    from uniadvisor import env as envmod

    for k in [k for k in os.environ if k.upper().startswith(("GEMINI", "GOOGLE_API"))]:
        monkeypatch.delenv(k, raising=False)
    # PowerShell 5 `echo ... > .env` writes UTF-16 with a BOM; `$env:` prefix and a numbered name without '_'
    (tmp_path / ".env.txt").write_bytes("﻿$env:GEMINI_API_KEY1 = 'x1'\r\nset GEMINI_API_KEY2=x2;x3\r\n".encode("utf-16-le"))
    monkeypatch.setattr(envmod, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    assert sorted(envmod.load_dotenv()) == ["GEMINI_API_KEY1", "GEMINI_API_KEY2"]
    assert llm_label.load_keys(tmp_path / "missing.txt") == ["x1", "x2", "x3"]
    assert "GEMINI_API_KEY1, GEMINI_API_KEY2" in envmod.describe() and "x1" not in envmod.describe()
