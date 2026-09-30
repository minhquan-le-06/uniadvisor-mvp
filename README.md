# UniAdvisor — tư vấn đặt nguyện vọng đại học (MVP)

Decision support for Vietnamese grade-12 students building an ordered university application list
(nguyện vọng) for the **THPT exam-score method**, following [MVP.md](MVP.md). Hybrid design:

| Part | What it decides | Where |
|---|---|---|
| Knowledge base (rules, versioned per year) | eligibility, priority points (with the 2025 taper), ministry floors, risk buckets, list constraints | `config/rules/`, `src/uniadvisor/kb/` |
| Statistical engine | next cutoff forecast, uncertainty, `P(admit)`, backtest | `src/uniadvisor/engine/` |
| Small language model (self-built) + keyword rules | soft judgments only: risk tolerance, top priority, interest fit, ability fit, budget / location / special-condition fit read from free text; each question is routed to whichever judge answers it better | `src/uniadvisor/slm/` |
| Optimizer | which programs to list and in what order: max `E = Σ pᵢ·Π(1−pⱼ)·uᵢ` s.t. KB constraints | `src/uniadvisor/optimizer.py` |
| Comparison + explanations | criteria, goal-based weights, wins/losses, Vietnamese explanations from engine numbers only | `compare.py`, `explain.py` |
| UI / API | Vietnamese chat (Streamlit), REST (FastAPI) | `app/`, `src/uniadvisor/api.py` |

The SLM never computes probabilities or regulation facts. Low-confidence SLM answers become clarifying
questions (profile level) or "cần xác nhận" flags (program level).

## Quick start

Python 3.11+. Commands below are for Windows; on Linux/macOS use `.venv/bin/` instead of `.venv/Scripts/`.
Run everything from the project root (the folder with `pyproject.toml`).

```bash
py -3.14 -m venv .venv --system-site-packages     # reuses torch/streamlit/fastapi if installed globally
.venv/Scripts/python -m pip install -e ".[slm,dev]"
.venv/Scripts/uniadvisor slm-data                   # regenerates data/slm/*.jsonl (not in git, ~40 s)
.venv/Scripts/uniadvisor app                        # chat UI on http://localhost:8501
.venv/Scripts/uniadvisor serve                      # API on http://localhost:8000/docs
.venv/Scripts/uniadvisor advise --scores "TO=8.4,VA=7,LI=8,N1=8.2" --province "Nghệ An" --area KV2-NT --text "Em muốn học CNTT, học phí tối đa 30 triệu/năm, muốn học ở Hà Nội"
.venv/Scripts/python -m pytest -q
```

The processed data (`data/processed/`) is included, so the app runs without re-collecting. Without a
trained SLM in `models/slm/`, a transparent keyword judge is used; with one, the hybrid judge is used.
The sidebar says which.

## Data pipeline (yearly refresh)

```bash
uniadvisor collect      # polite + cached: robots.txt, 1.5 s/host, raw responses in data/raw/
uniadvisor fetch-scores # per-candidate exam scores 2023-2026 -> data/inbox/ (~350 MB, not in git)
uniadvisor build        # distributions -> cutoffs (3-source consensus) -> catalog
uniadvisor backtest     # fits forecast parameters, writes reports/backtest.json
uniadvisor report       # reports/data_report.md: coverage, quality, gaps
uniadvisor slm-data     # synthetic students x real programs -> data/slm/
```

Sources (trust levels as in UniPilotData): VietNamNet cutoff API (3, 2023–2026), VnExpress (3,
2025–2026 + tuition + 2026 score histograms), tuyensinh247 (4, 2026 cross-check), the ADS_Final
student project's scraped cutoffs ([HTNam1710/ADS_Final](https://github.com/HTNam1710/ADS_Final), 4, 2018–2024:
the only source for 2018–2022 and a second opinion on 2023–2024), UniPilotData
step-1 export (schools, 2026 programs, quotas, combos), and ministry percentiles/means quoted in news
(`data/manual/distribution_anchors.csv`, each row with its quote), and per-candidate exam scores
compiled from the Ministry's public results ([sdgedfegw/du-lieu-diem-thi](https://github.com/sdgedfegw/du-lieu-diem-thi),
subject scores only, no names). Those files stay in `data/inbox/` (git-ignored); only the aggregate
distributions built from them are committed. Without them, `build` falls back to approximations.

**Read [reports/data_report.md](reports/data_report.md) before trusting any number.** The short version:

- 48 schools (28 Hà Nội, 20 TP.HCM), ~1,670 programs; cutoffs 2018–2026, cross-checked across up to 3 sources per year
  (2023–2024 now confirmed by 2 sources for 55–65% of rows, up from none).
- Score distributions are exact for 2023–2026 (1.0–1.2 M candidates per year; the 2026 file matches
  VnExpress's per-subject counts exactly). Even so, same-percentile equating of past cutoffs was
  *worse* than comparing raw cutoffs (MAE 1.55 vs 1.37, even onto the target year's own distribution):
  selective programs stay sticky in points and low ones sit on the ministry floors. The backtest
  therefore chooses no equating, and the forecast is about as good as "last year's cutoff"
  (MAE ≈ 1.37). The distributions still drive the "top X% of candidates" figures in explanations.
  Adding 2018–2022 history did not change that either (like-for-like MAE 1.362 → 1.359).
  Beating the naive forecast needs other signals (quota history, applicants per program).
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
- Gemini as a second gold labeller: `uniadvisor gold-llm` (2 rows per request, Flash then Flash-Lite across all
  keys, resumable) writes `data/slm/gold_llm.csv`; compare it with your labels before trusting either.
- Human gold set: `uniadvisor label` opens a labelling tool (http://localhost:8502) over
  `data/slm/gold_to_label.csv` (294 test rows, 42 per question, never used for training). It shows the
  rubric, never a model answer (guide: [data/slm/LABELLING.md](data/slm/LABELLING.md)), and saves every click to `data/slm/gold_labeled.csv` (commit it). Then
  `uniadvisor slm-eval --judge hybrid --gold data/slm/gold_labeled.csv`. Run `uniadvisor slm-data` first:
  gold ids must match your local test split (the tool warns when they do not).
- Training: see [kaggle/README.md](kaggle/README.md) (`uniadvisor kaggle-bundle` → Kaggle GPU →
  unzip into `models/slm/`). `uniadvisor slm-train --limit 300 --eval-limit 200 --epochs 1 --bs 16
  --out models/slm_smoke` is a local smoke test.
- Hybrid judge (`HybridJudge` in `slm/infer.py`): the SLM answers `SLM_QUESTIONS`, the keyword rules
  answer the rest, and the SLM runs only on its questions. Change the split with a `"route"` list in
  `models/slm/config.json`. Evaluate with `uniadvisor slm-eval --judge hybrid|slm|heuristic [--limit N]`
  (`auto` = what the app uses). On CPU the full test split takes 5–20 min; `--limit 3000` is enough to
  compare judges (use the same limit for each).

First Kaggle run (3 epochs), test split, first 3,000 rows. Labels are the synthetic rubric labels, not
human labels:

| Question | Keywords | SLM | Routed to |
|---|---|---|---|
| location_ok | 0.602 | **0.984** | SLM |
| budget_ok | 0.952 | **0.962** | SLM |
| risk_tolerance (n=137) | 0.832 | **0.905** | SLM |
| ability_fit | **0.851** | 0.477 | keywords (score arithmetic; the SLM is never confident) |
| conditions_ok | **0.996** | 0.991 | keywords (tie, and far cheaper) |
| interest_fit | **0.650** | 0.463 | keywords (weakest question for both) |
| top_priority (n=137) | **0.891** | 0.803 | keywords |
| **Overall** | 0.815 | 0.782 | **hybrid 0.889** |

The SLM's confidences are better calibrated on 5 of 7 questions (ECE ≤ 0.10 everywhere; the keyword
judge reaches 0.34 on budget_ok), so its escalations to clarifying questions are more meaningful.
Re-pick the routing after every retrain.

## Privacy, reproducibility, disclaimer

- Nothing a student enters is stored (UI and API keep it in memory for the session only); the UI asks
  for consent before processing (Decree 13/2023/NĐ-CP). The SLM runs locally.
- Rules and statistics are deterministic: same input → same output (tested).
- Every result carries the disclaimer that it is advisory and must be checked against the official
  regulation and each school's đề án. The 2026 rules in `config/rules/2026.yaml` were checked against the
  official text (`verified: true`); 2027 is a draft ruleset inheriting 2026.

## Layout

```
config/            scope.yaml (schools/regions), sources.yaml, rules/<year>.yaml
data/manual/       hand-entered anchors with quotes          data/inbox/  drop-in files (not in git)
data/collected/    raw parsed rows per source                data/processed/  clean tables the app reads
data/slm/          SLM dataset, rubrics, gold template       models/  forecast params, SLM adapter (models/slm/)
reports/           data_report.md, backtest.json, distributions.json, SLM metrics
src/uniadvisor/    collect/ build/ kb/ engine/ slm/ optimizer.py compare.py explain.py advisor.py api.py cli.py
app/               streamlit_app.py                           kaggle/  training notebook + guide
```
