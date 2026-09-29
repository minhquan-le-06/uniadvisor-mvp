# UniAdvisor — tư vấn đặt nguyện vọng đại học (MVP)

Decision support for Vietnamese grade-12 students building an ordered university application list
(nguyện vọng) for the **THPT exam-score method**, following [MVP.md](MVP.md). Hybrid design:

| Part | What it decides | Where |
|---|---|---|
| Knowledge base (rules, versioned per year) | eligibility, priority points (with the 2025 taper), ministry floors, risk buckets, list constraints | `config/rules/`, `src/uniadvisor/kb/` |
| Statistical engine | next cutoff forecast, uncertainty, `P(admit)`, backtest | `src/uniadvisor/engine/` |
| Small language model (self-built) | soft judgments only: risk tolerance, top priority, interest fit, ability fit, budget / location / special-condition fit read from free text | `src/uniadvisor/slm/` |
| Optimizer | which programs to list and in what order: max `E = Σ pᵢ·Π(1−pⱼ)·uᵢ` s.t. KB constraints | `src/uniadvisor/optimizer.py` |
| Comparison + explanations | criteria, goal-based weights, wins/losses, Vietnamese explanations from engine numbers only | `compare.py`, `explain.py` |
| UI / API | Vietnamese chat (Streamlit), REST (FastAPI) | `app/`, `src/uniadvisor/api.py` |

The SLM never computes probabilities or regulation facts. Low-confidence SLM answers become clarifying
questions (profile level) or "cần xác nhận" flags (program level).

## Quick start

```bash
py -3.14 -m venv .venv --system-site-packages     # reuses torch/streamlit/fastapi if installed globally
.venv/Scripts/python -m pip install -e ".[slm,dev]"
.venv/Scripts/uniadvisor app                        # chat UI on http://localhost:8501
.venv/Scripts/uniadvisor serve                      # API on http://localhost:8000/docs
.venv/Scripts/uniadvisor advise --scores "TO=8.4,VA=7,LI=8,N1=8.2" --province "Nghệ An" --area KV2-NT --text "Em muốn học CNTT, học phí tối đa 30 triệu/năm, muốn học ở Hà Nội"
.venv/Scripts/python -m pytest -q
```

The processed data (`data/processed/`) is included, so the app runs without re-collecting. Without a
trained SLM in `models/slm/`, a transparent keyword judge is used (and says so in the sidebar).

## Data pipeline (yearly refresh)

```bash
uniadvisor collect      # polite + cached: robots.txt, 1.5 s/host, raw responses in data/raw/
uniadvisor build        # distributions -> cutoffs (3-source consensus) -> catalog
uniadvisor backtest     # fits forecast parameters, writes reports/backtest.json
uniadvisor report       # reports/data_report.md: coverage, quality, gaps
uniadvisor slm-data     # synthetic students x real programs -> data/slm/
```

Sources (trust levels as in UniPilotData): VietNamNet cutoff API (3, 2023–2026), VnExpress (3,
2025–2026 + tuition + 2026 score histograms), tuyensinh247 (4, 2026 cross-check), UniPilotData
step-1 export (schools, 2026 programs, quotas, combos), and ministry percentiles/means quoted in news
(`data/manual/distribution_anchors.csv`, each row with its quote). Only public aggregate data is
stored; no per-candidate records are kept.

**Read [reports/data_report.md](reports/data_report.md) before trusting any number.** The short version:

- 48 schools (28 Hà Nội, 20 TP.HCM), ~1,670 programs; 2026 cutoffs cross-checked across up to 3 sources.
- Only 2026 has real score distributions. Past years are approximations, and the backtest showed
  percentile-equating through them is *worse* than not equating, so the engine gates equating on
  distribution quality. Today it therefore forecasts on raw scores (MAE ≈ 1.37 points, same as
  "last year's cutoff"); **dropping per-candidate score files for 2023–2025 into `data/inbox/`**
  (e.g. the Kaggle dataset "Dữ liệu điểm thi THPT quốc gia 2020-2024") and running `uniadvisor build`
  switches real percentile equating on.
- `P(admit)` is calibrated on held-out years (Brier 0.12, ECE 0.056) and errs on the safe side.

## SLM

- Base: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (Apache-2.0, multilingual incl. Vietnamese,
  118M params). Frozen; LoRA (r=16) on attention + FFN projections, written in-house (no peft).
- Heads: bool (sigmoid yes + sigmoid insufficient), choice (softmax incl. insufficient), score
  (CORAL ordinal 1–5 + insufficient). Soft-label losses. Temperature scaling per question on val;
  ECE, accuracy, macro-F1, escalation rate and per-group quality (region, elective track, score band)
  on test. Confidence thresholds are chosen on val for 90% accuracy on non-escalated answers.
- 7 questions with written rubrics: `data/slm/rubrics.md` (generated from `slm/questions.py`).
- Data: synthetic students (scores drawn from the real 2026 subject distributions, diverse Vietnamese
  free text incl. teen-code, no diacritics, parent voice, typos, contradictions) paired with real
  programs; rubric teacher with 5 simulated annotators → soft labels; split by university; deduped.
  Optional LLM teacher (`uniadvisor slm-relabel`, Gemini via `GEMINI_API_KEYS`, as in UniPilotData).
- Human gold set: label `data/slm/gold_to_label.csv` (never used for training), save as
  `gold_labeled.csv`, then `uniadvisor slm-eval --gold data/slm/gold_labeled.csv`.
- Training: see [kaggle/README.md](kaggle/README.md) (`uniadvisor kaggle-bundle` → Kaggle GPU →
  unzip into `models/slm/`). `uniadvisor slm-train --limit 2000 --epochs 1` is a local smoke test.

## Privacy, reproducibility, disclaimer

- Nothing a student enters is stored (UI and API keep it in memory for the session only); the UI asks
  for consent before processing (Decree 13/2023/NĐ-CP). The SLM runs locally.
- Rules and statistics are deterministic: same input → same output (tested).
- Every result carries the disclaimer that it is advisory and must be checked against the official
  regulation and each school's đề án. Rule values not yet checked line by line against the official
  text are marked `verified: false` in `config/rules/2026.yaml`; 2027 is a draft ruleset inheriting 2026.

## Layout

```
config/            scope.yaml (schools/regions), sources.yaml, rules/<year>.yaml
data/manual/       hand-entered anchors with quotes          data/inbox/  drop-in files (not in git)
data/collected/    raw parsed rows per source                data/processed/  clean tables the app reads
data/slm/          SLM dataset, rubrics, gold template       models/  forecast params, SLM adapter
reports/           data_report.md, backtest.json, distributions.json, SLM metrics
src/uniadvisor/    collect/ build/ kb/ engine/ slm/ optimizer.py compare.py explain.py advisor.py api.py cli.py
app/               streamlit_app.py                           kaggle/  training notebook + guide
```
