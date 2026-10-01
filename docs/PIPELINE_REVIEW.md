# Pipeline review

State as of 2026-10-01. UniAdvisor turns a student's exam scores and free-text wishes into an ordered list of up to
15 nguyện vọng, each with an admission probability. This review rates its four modules and lists what to fix first.

The findings come from four places: the code, the generated reports in `artifacts/reports/`, a variance breakdown of
the 2,208 backtest residuals, and one run of the app's own "IT, limited budget" example student through the
deployed path (keyword judge).

| Module | What it decides | Code |
|---|---|---|
| 1. Data collecting | cutoffs, score distributions, tuition and programs; the clean tables the app reads | `collect/`, `fetch.py`, `build/`, `config/scope.yaml`, `data/` |
| 2. Student info and intention | scores and form fields; 7 typed judgments read from free text (risk, priority, interest, ability, budget, location, conditions) | intake in `app/streamlit_app.py`, `slm/state.py`, `slm/questions.py`, `slm/infer.py` |
| 3. Recommendation engine | eligibility and priority points, cutoff forecast, P(admit), criteria and utility, which programs to list and in what order | `kb/rules.py`, `config/rules/`, `engine/`, `compare.py`, `optimizer.py`, `advisor.py` |
| 4. Explaining the suggestions | per-program explanation, confidence label, list summary, strengths and weaknesses | `explain.py`, `compare.wins_losses`, results UI |

Status: module 1 is discussed and its data layer redesigned (see "Decisions" under module 1). Modules 2 and 3
record the findings so far. Module 4 is kept as-is for now.

## Module 1: Data collecting

Module 1 is reproducible and well sourced. Three gaps still limit the engine: one cutoff per program where some
programs have several, missing quota and applicant history, and coarse field labels.

**What works**

- 4 cutoff sources (VnExpress, VietNamNet, tuyensinh247, ADS_Final) are reconciled by majority vote within 0.05 points.
- The fetcher obeys robots.txt, waits 1.5 s per host and caches every response, so rebuilds never hit the sites.
- Exact score distributions for 2023 to 2026 are built from per-candidate files (1.0 to 1.2 M candidates a year).
- Coverage is 48 schools (28 Hà Nội, 20 TP.HCM) and 1,666 programs, with cutoffs from 2018 to 2026. Builds use
  stable sorts, so the same inputs give the same tables.

**Problems, most serious first**

1. **One cutoff kept per program.** When a program sets a different cutoff per subject combination, the build keeps
   the lowest. A student using a combination with a higher cutoff gets an inflated P(admit). This affects 937 of
   7,098 cutoff rows (13%); they are flagged `lowest_of_several`, but the engine ignores the flag.
2. **Missing signals for the forecast.** Only 2026 quotas exist; applicant counts and per-combination cutoffs are
   absent. This is why the forecast cannot beat "same as last year" (module 3).
3. **Field labels are home-made instead of MOET's.** MOET's 7-digit major code is itself the taxonomy:
   digit 1 = level (7 = đại học), digits 1-3 = lĩnh vực (748 Máy tính và công nghệ thông tin), digits 1-5 = nhóm
   ngành (74802), all 7 = ngành (7480201). The build instead files programs into 16 hand-made fields by name keywords
   and uses the code only as a fallback, so it disagrees with MOET (746 Toán và thống kê lands in "cntt";
   "Khoa học thông tin địa không gian" lands in IT because its name contains "thông tin").
   - Coverage: 1,077 of 1,666 programs (65%) carry a MOET code, spanning 22 lĩnh vực, 69 nhóm ngành and 256 ngành.
     The other 589 only have the school's own code (BKA 69, GHA 53, KHA 47, TLA 46, NHH 45, ...); the UniPilot
     export fills just 23 of them. The rest need each school's đề án (it maps school codes to MOET codes) or a
     name match against MOET's catalog of ngành names.
   - Fix: take field and group from the code (catalog of names as a sourced manual input, Thông tư 09/2022/TT-BGDĐT
     danh mục thống kê ngành đào tạo), keep the keywords only for programs without a code, and store the code's
     levels in the database. Interest fit (module 2) can then reason at ngành / nhóm ngành level.
4. **Tuition is thin.** 756 programs (45%) have a sourced fee, 182 (11%) use their school's median, and 728 (44%) are
   unknown. *Fixed:* the old `tuition_imputed` flag was also set on the 728 programs with no fee, so students saw
   "học phí là ước tính" where nothing was estimated; the database now records observed, estimated or missing.
5. **Problems are logged, not acted on.** 1,248 year-on-year jumps over 3 points and 422 source disagreements sit in
   `check_problems.csv`, but those rows still feed the forecast.
6. **Coverage holes and untested scrapers.** 12 candidate schools were dropped (including TMU, KMA and IUH) for lack
   of usable 30-point cutoffs. The scrapers have no tests against saved pages, so a site change fails silently at the
   next yearly refresh.

**Decisions (2026-10-01)**

- Simulate to train and test; estimate a missing real value only when its error is measured and students see it
  labelled "ước tính"; never make up cutoffs, quotas, applicant counts or programs that feed P(admit), and never
  score the backtest or gold set on simulated data.
- Every fact carries one of four provenance classes (observed, derived, estimated, simulated). The data now lives in
  one database with a checked schema: `data/db/` (real), `data/sim/<name>/` (simulated, `SIM-` ids, seed in the
  manifest). The loader refuses simulated rows in the real database, and steps that need real data refuse a
  simulated one. Details: [DATA.md](DATA.md).
- Two simulated databases exist: `sim tiny` (3 schools, 12 programs, for fast tests of modules 2-4) and
  `sim season` (the real data plus one 2027 season with school-correlated shocks sized from the backtest; reform-year
  drop optional, off by default), the test bed for module 3's correlated-error problem.
- Deferred to the module 2 discussion: moving the SLM's synthetic training data (`data/slm/*.jsonl`) under
  `data/sim/`. It never reaches the app, and moving it changes the Kaggle training workflow.

## Module 2: Student info and intention processing

Module 2 scores 0.823 (keyword rules, as deployed) and 0.864 (hybrid with the SLM) on Gemini's 294 gold labels. Its
main flaw is structural: what the student wants is never pulled out as explicit facts the student can confirm.
Discussion to come.

**What works**

- The intake is a form (scores, province, priority area and group, gender, real or mock scores) plus one free-text
  message; later messages are appended.
- 7 typed questions with written rubrics. An unsure answer to a profile question becomes a clarifying question; an
  unsure program answer becomes a "cần xác nhận" flag.
- The hybrid judge routes location, risk, budget and conditions to the SLM and the rest to keyword rules.

**Problems, most serious first**

1. **Intent is never extracted as facts.** Each program question re-reads the raw text. "Mình hiểu là" shows only
   risk tolerance and top priority, so the student never sees or corrects "IT, Hà Nội, at most 25 triệu/năm".
2. **Interest fit did not separate programs.** In the example run, all 10 picks scored interest_fit 5, so the
   criterion with 35% of the weight changed nothing. interest_fit is also the weakest question (0.55 on the gold set).
3. **Clarifying questions cover only risk and priority.** Budget, location and interest are facts about the student
   but are judged per program, so the app cannot simply ask about them once.
4. **Keyword confidences are fixed** (0.7, 0.55 or 0.5) and uncalibrated (ECE 0.23 on ability_fit). Some branches are
   flagged unsure by construction.
5. **No real data yet.** 0 of 294 gold rows have human labels, and all training text is synthetic.
6. **Small parsing bugs.** "Tự tin" anywhere counts as good English for conditions_ok; a monthly family income can be
   read as the yearly budget.

## Module 3: Recommendation engine

Module 3's rules and optimizer are correct and tested, and P(admit) is calibrated (Brier 0.118, ECE 0.056). Its two
weak points are the optimizer's assumption that forecast errors are independent, and a forecast that equals last
year's cutoff. Discussion to come.

**What works**

- The 2026 rules (priority points with the 2025 taper, ministry floors, gender-only programs, risk buckets) are
  verified against the regulation and unit-tested.
- P(admit) leans conservative: predicted safe 92% vs actual 95%; match 63% vs 73%; reach 26% vs 34%.
- The optimizer solves the choice exactly and matches brute force; ordering by utility is proven optimal for
  independent cutoffs.

**Problems, most serious first**

1. **Correlated errors are treated as independent.** 45% of forecast error variance (1.54 of 3.42 points²) is shared
   by programs of one school in one year, and two such programs' errors correlate at about 0.47. The optimizer allows
   4 programs per school; the example run picked 4 from XDA. "≈100% chance of at least one admission" is therefore
   overstated.
2. **The forecast is last year's cutoff.** Error is 1.37 points, the same as the naive baseline; the 80% interval is
   ±2.2 points. Recency 0.2 is chosen on purpose over the marginally better 0.0 (1.3729 vs 1.3686 MAE): the backtest
   keeps some history when it costs under 1%, to damp one-year spikes. There is no trend term: the top pick rose 20.4, 22.5, 23.5, 24.38 from 2023 to 2026, yet its 2027 forecast is 24.15.
3. **Hand-set criterion weights.** Selectivity (how high the cutoff is) carries 20% of the weight and also stands in
   for job prospects, so it rewards programs that are hard to get into. In the example, NV1 (geospatial science, 22%
   chance) ranks first because fit was tied and selectivity and tuition broke the tie.
4. **Untested and assumed parts.** `compare.py` has no tests; the mock-score uncertainty (1.2 points) is assumed,
   not measured; the cap of 4 programs per school is hard-coded rather than in the ruleset.

## Module 4: Explaining the suggestions

Module 4 never makes anything up, but it does not explain why the list is ordered the way it is, and its summary can
be wrong about that. Kept as-is for now.

**What works**

- Every sentence is built from engine numbers: forecast, 80% interval, cutoff history, the student's total,
  P(admit), bucket, flags and a confidence label.
- The list summary names the main trade-off; a disclaimer and a CSV export come with every list.

**Problems, most serious first**

1. **The ranking is never explained.** In the example, the summary says NV1 "hợp em nhất" (fits you best), yet it
   ties on fit with 9 other picks. The real reasons, selectivity and tuition, are not mentioned.
2. **Strengths and weaknesses are often empty or trivial.** Each pick is compared with the median of the other picks
   using a 0.15 margin; NV1's only strength was "Học phí".
3. **Judgments come without evidence.** The app shows a label and a percentage, not the phrase in the student's text
   that led to it.
4. **No "why not X?"** Explanations for the alternatives are computed but never shown.
5. **Two combinations in one sentence:** "tổ hợp A01: 22.50 … top 14% of A00".
6. **The confidence label is not tied to measured error.** It rewards years of history, but forecast error barely
   changes with history length (σ 1.43, 1.46 and 1.36 points for 1, 2 and 3+ years).
7. **Untested.** No unit tests for `explain.py`, and no review with real students yet, which is the MVP's own
   evaluation step.

## Priorities

Across modules, the biggest fixes are correlated errors in the optimizer (module 3) and explicit intent facts
(module 2). For module 1:

1. ~~Separate "estimated" from "missing" tuition.~~ Done with the database redesign.
2. ~~Simulated data and a checked database.~~ Done: [DATA.md](DATA.md).
3. Use per-combination cutoffs where `lowest_of_several` is set (13% of cutoff rows) instead of the lowest one; the
   `cutoffs` table already has a `combo` column for them.
4. Derive fields from MOET's major code (lĩnh vực / nhóm ngành / ngành) and fill the 589 missing codes; see
   problem 3. Planned as the first step of module 2, since interest fit depends on it.
