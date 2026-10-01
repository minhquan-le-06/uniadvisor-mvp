# Hand-off (state as of 2026-10-01)

Work happens on branch `claude/ecstatic-pasteur-9qby7f`; PRs #1-#3 are merged into `main`, the rest goes in PR #4.
Read this file, then README.md and reports/data_report.md.

## Setup (Python 3.11+, run everything from the project root; `.venv/Scripts/` on Windows)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"            # add ".[slm]" to run the SLM (pulls torch)
uniadvisor slm-data                # regenerates data/slm/*.jsonl (not in git, ~40 s)
python -m pytest -q                # 66 pass (1 skips without torch)
uniadvisor fetch-scores            # optional: per-candidate scores 2023-2026 into data/inbox/ (~350 MB,
                                   # git-ignored); needed only to rebuild the distributions exactly
uniadvisor gold-llm                # Gemini labels for the gold set; keys in .env (see .env.example), resumable
```

Committed: `data/processed`, `data/collected`, `data/unipilot`, `models/forecast_params.json`. Not committed:
`data/inbox/` (per-candidate files), `data/slm/*.jsonl` except `gold_frozen.jsonl`, `models/slm/` (the trained SLM
lives only on the owner's Windows machine), `.env` (Gemini keys).

## Current state

| Component | State |
|---|---|
| Data | 48 schools (HN 28, HCM 20), 1,666 programs, cutoffs 2018-2026 from 4 sources (2018-2022 ADS_Final only); exact score distributions 2023-2026 (1.0-1.2 M candidates/year) |
| Rules | 2026 verified by the owner (`verified: true`); 2027 is a draft inheriting 2026 |
| Forecast | MAE 1.373 ≈ naive "last year's cutoff" (1.369). Percentile equating with exact data is worse (1.55), so the backtest picks `equate=never`. P(admit) calibrated: Brier 0.119, ECE 0.056 |
| Optimizer | tested vs brute force; never recommends "unlikely" (< 15%) programs |
| SLM | Third Kaggle run (fixed teacher, 5 epochs, DDP on 2×T4, ~24 min, VRAM ~14/15 GB per GPU) is the current model (owner's `models/slm/`). On Gemini's gold labels: keywords 0.823 (after rubric fixes), SLM 0.765, hybrid 0.864 (measured) with `SLM_QUESTIONS` = location_ok, risk_tolerance, budget_ok, conditions_ok. Weakest: interest_fit (0.55). The teacher changed since (English self-assessment counts for ability_fit; 48 program fields fixed), so the next retrain trains on slightly better labels |
| App / API | Streamlit chat + FastAPI both tested (headless Chromium, TestClient). Deploy-ready for Streamlit Community Cloud with the keyword judge (`requirements.txt`, `.streamlit/config.toml`, [DEPLOY.md](DEPLOY.md)); tested from a clean clone: ~250 MB RAM, results in ~2 s. The owner still has to create the app on share.streamlit.io |
| Labelling | Gemini labelled all 294 gold rows (`data/slm/gold_llm.csv`, committed). 6 rows (4 ability_fit, 2 interest_fit) still carry labels from before the rubric fixes; `uniadvisor gold-llm --redo interest_fit,ability_fit` relabels just those. The gold set is frozen in `data/slm/gold_frozen.jsonl` (evaluation reads it; its students are excluded from training). 0/294 human labels |

## Next, in order of value

SLM work is wrapped up for the MVP (owner decision, 2026-10-01): hybrid 0.864 on Gemini's gold labels.

1. **Owner: deploy** on Streamlit Community Cloud following [DEPLOY.md](DEPLOY.md) (keyword judge), then test with
   5-10 real students. The SLM version is a later step (DEPLOY.md, last section).
2. **Forecast signals beyond last year's cutoff.** Better distributions and 2018-2022 history did not help; next try quota
   history 2023-2025 (turns on `kappa_quota`), applicant counts per program, per-combination cutoffs.
3. Optional SLM follow-ups: a human spot-check of ~5-10 gold rows per question (`uniadvisor label`) to confirm
   Gemini's labels; interest_fit (0.55) is the weakest question; one more retrain would pick up the teacher fixes
   made after the third run.
4. Out of MVP scope (owner decision, 2026-09-30): real tuition from each school's đề án. 910 programs keep a
   school-level estimate; budget_ok judges against it or says insufficient when tuition is unknown.

## SLM history (for reference)

| Run | Change | Gold (Gemini) hybrid |
|---|---|---|
| 1 | first model, 3 epochs | 0.728 (location learned a teacher bug) |
| 2 | NaN-free texts, 3 epochs, built before the teacher fix | not scored on gold |
| 3 | teacher fix (NaN campus), clearer interest/ability rubrics, 5 epochs, DDP on 2×T4 | 0.799 |
| 3 + rules | keyword ability/interest rules follow the rubric, whole-word field matching | **0.864** |

## SLM: improvement methods for future versions

Ordered by expected value. Measure every change on the frozen gold set (`slm-eval --judge hybrid|slm|heuristic
--gold data/slm/gold_llm.csv`) and re-pick `SLM_QUESTIONS` after each retrain.

**Labels (biggest lever)**
- Train on LLM labels, not only the rubric teacher: relabel a train subset with Gemini (`slm-relabel` exists;
  `gold-llm` shows the batching/quota pattern) and mix soft labels. The teacher is a hand-written rule, so the SLM
  can at best copy it; every teacher bug so far (NaN campus, English self-assessment) went straight into the model.
- Grow the gold set: 42 rows per question means one row = 2.4 points. Aim for 100+ per question, stratified by label
  (budget_ok is 81% "insufficient", so it tests almost nothing). Add a human spot-check (`uniadvisor label`) of
  rows where Gemini and the teacher disagree.
- Decouple the teacher's RNG from the dataset sampler (seed per example): today any teacher change reshuffles which
  programs students are paired with (that is why the gold set had to be frozen).

**Per question**
- interest_fit (0.55, weakest): relatedness is judged at the level of 16 broad fields, while Gemini reads the program
  name (food technology vs biotechnology; "Kinh tế xây dựng" filed under finance). Use a finer taxonomy (ministry
  major code, 4-6 digits) with a related-majors table, and generate more hinted interests (hobbies, dream jobs).
- ability_fit: keep the arithmetic in the rules. If the SLM is used, have it only extract facts (strong/weak subjects
  from free text) and let the rules score; the current SLM almost always defers on it.
- budget_ok: needs real tuition (out of MVP scope); until then most rows are correctly "insufficient".
- Confidence: the keyword judge uses a fixed 0.7, so it is under-confident where it is right (ability_fit ECE 0.23).
  Calibrate its confidences on the gold set, per question and rule branch.

**Model and training**
- Thresholds: `--target-acc 0.9` is too strict for the 1-5 score questions (their threshold ends at 0.95, so the SLM
  defers on 80-95% of rows). Use a per-question target, or pick thresholds on the gold set.
- Base model: try a larger multilingual or Vietnamese encoder (XLM-R base, PhoBERT, a Vietnamese bi-encoder) with
  the same typed heads; the current MiniLM (L12, H384) is small. Batch 128/GPU is the T4 ceiling (~14/15 GB); a
  larger model needs a smaller batch or gradient accumulation.
- Validation accuracy flattened at epoch 5 (0.772 -> 0.777): add early stopping instead of more epochs.
- Domain shift: synthetic free text is template-based. Collect real (anonymised, consented) student messages and
  add them to the gold set before trusting the scores on real users.

**Evaluation**
- Score the whole advisor, not only the 7 questions: for gold students, compare the recommended list (and the
  clarifying questions asked) with what a human counsellor would choose.

## Cloud-environment notes (for the next Claude session)

- The container's default `python3` is 3.11 and fine now; `python3.12` also exists.
- Blocked: huggingface.co, download.pytorch.org, kaggle.com, the news sites. torch installs from PyPI. SLM
  code paths can be smoke-tested with a tiny local random BERT (`--base <dir>`), not the real base model.
- Reachable: GitHub (anonymous clone of public repos) and media.githubusercontent.com (serves LFS files;
  `fetch-scores` uses it).
- Chromium + global Playwright are installed: drive Streamlit with Node Playwright
  (`createRequire(npm root -g)`); in the chat app the sidebar also has a "Bắt đầu lại" button, so select the
  primary button by `data-testid=stBaseButton-primary`.
- Avoid shell heredoc edits containing backslash escapes (caused corrupted regexes before); use the Edit tool.

## Decisions and findings worth remembering

- Build is reproducible across platforms: stable sorts with explicit tie-breaks (program dedupe prefers
  longest history, then best-confirmed row, then program_id).
- Percentile equating fails at the tails: selective programs stay sticky in points; low ones sit on the
  ministry floors. The backtest grid chooses equate on/off from measured MAE.
- ADS_Final (2018-2024 cutoffs) has correct scores but wrong program names in some years (BKA IT1 2019 named
  "Kỹ thuật xây dựng"). So code reuse is detected by name mismatch AND a > 2.5-point jump, never name alone
  (`catalog._drop_reused_codes`). Its 'Thang 40' label marks 40-point rows even when the number is <= 30.
- The 2025 `ct2006` score file (old-curriculum exam) is skipped by the importer on purpose.
- The SLM is poor at score arithmetic (ability_fit 0.47): keep that question on the rules.
- Gold ids hash the row text. The gold rows are frozen in `data/slm/gold_frozen.jsonl` (text, latent, program), so
  regenerating the synthetic data no longer invalidates labels; teacher labels for them are recomputed on the fly.
- The teacher and the dataset sampler share one RNG stream: any teacher change reshuffles later pairings.
- pandas 3: `df.where(df.notna(), None)` keeps NaN in string columns; use `df.astype(object).where(...)`.
- Keyword matching (program fields, free text) is on whole words: substring matching put "Thiết kế thời trang"
  ("rang") and "Tâm lý học" ("y học") under health.
