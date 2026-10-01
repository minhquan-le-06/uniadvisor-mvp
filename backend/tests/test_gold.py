"""Gold-label helpers: resume, atomic save, and that the saved file feeds slm-eval --gold."""

import json

import pytest

from uniadvisor.student.slm import gold


@pytest.fixture
def files(tmp_path):
    template = tmp_path / "gold_to_label.csv"
    rows = [
        {"id": "a1", "question": "risk_tolerance", "options": "x", "text_a": "Hồ sơ: A", "text_b": "B", "human_label": "", "labeller": "", "note": ""},
        {"id": "b2", "question": "location_ok", "options": "x", "text_a": "Hồ sơ: C", "text_b": "D", "human_label": "", "labeller": "", "note": ""},
    ]
    import pandas as pd

    pd.DataFrame(rows).to_csv(template, index=False, encoding="utf-8-sig")
    return template, tmp_path / "gold_labeled.csv"


def test_save_and_resume(files):
    template, labeled = files
    df = gold.load(template, labeled)
    assert (df.human_label == "").all()
    df.loc[df.id == "b2", ["human_label", "labeller", "note"]] = ["yes", "quan", "rõ ràng"]
    gold.save(df, labeled)
    assert not labeled.with_suffix(".tmp").exists()
    again = gold.load(template, labeled)
    assert again.set_index("id").loc["b2", "human_label"] == "yes" and again.set_index("id").loc["b2", "note"] == "rõ ràng"
    assert again.set_index("id").loc["a1", "human_label"] == ""
    assert gold.progress(again).loc["location_ok", "done"] == 1 and gold.progress(again).done.sum() == 1


def test_unmatched_ids(files, tmp_path):
    template, labeled = files
    df = gold.load(template, labeled)
    assert gold.unmatched_ids(df, tmp_path / "missing.jsonl") is None
    test = tmp_path / "test.jsonl"
    test.write_text(json.dumps({"id": "a1"}) + "\n", encoding="utf-8")
    assert gold.unmatched_ids(df, test) == 1


def test_labeled_file_feeds_evaluate(tmp_path):
    from unidata.paths import SLM_DATA

    if not (SLM_DATA / "test.jsonl").exists() or not gold.TEMPLATE.exists():
        pytest.skip("run `uniadvisor slm-data` first")
    from uniadvisor.student.slm.evaluate import evaluate
    from uniadvisor.student.slm.infer import HeuristicJudge

    df = gold.load(gold.TEMPLATE, tmp_path / "none.csv")
    assert gold.unmatched_ids(df) == 0, "gold template is out of sync with backend/slm_data/test.jsonl"
    pick = df.groupby("question").head(1).index
    df.loc[pick, "human_label"] = [_first_label(q) for q in df.loc[pick, "question"]]
    out = tmp_path / "gold_labeled.csv"
    gold.save(df, out)
    r = evaluate(HeuristicJudge(), gold=out)
    assert r["split"] == "gold" and r["n"] == len(pick)


def _first_label(qid: str) -> str:
    from uniadvisor.student.slm.questions import BY_ID

    return BY_ID[qid].labels[0]


def test_frozen_gold_set_evaluates_without_the_test_split(tmp_path):
    """Gold labels stay usable after the synthetic data is regenerated: evaluation reads gold_frozen.jsonl."""
    import shutil
    from pathlib import Path

    from uniadvisor.student.slm.evaluate import evaluate
    from uniadvisor.student.slm.infer import HeuristicJudge

    src = Path("backend/slm_data")
    if not (src / "gold_frozen.jsonl").exists() or not (src / "gold_llm.csv").exists():
        pytest.skip("no frozen gold set")
    shutil.copy(src / "gold_frozen.jsonl", tmp_path)  # no test.jsonl, latents or snapshot next to it
    r = evaluate(HeuristicJudge(), gold=src / "gold_llm.csv", data=tmp_path)
    assert r["n"] == 294 and r["split"] == "gold"
