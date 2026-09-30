# Labelling the SLM gold set

`uniadvisor slm-data` (once, so gold ids match your test split), then `uniadvisor label`
(http://localhost:8502). Every click is saved to `data/slm/gold_labeled.csv`; commit that file when done.
Then compare judges on your labels:

```bash
uniadvisor slm-eval --judge hybrid --gold data/slm/gold_labeled.csv
uniadvisor slm-eval --judge heuristic --gold data/slm/gold_labeled.csv
```

## What you are looking at

- **Ngành (right)**: a real program from the catalog (real name, school, field, tuition, conditions), always
  from the 7 universities held out of training.
- **Student (left)**: synthetic. Scores drawn from real 2026 distributions; free text generated (teen-code,
  no diacritics, parent voice, typos, contradictions).
- **The pairing is partly random on purpose.** Each student gets ~4 programs: one per top-2 interest field,
  one from a disliked field, one from the parents' field, sometimes one with special conditions, the rest
  random. Mismatches are intended. Do not judge whether the pairing is sensible; answer the question for it.
- No model or teacher answer is ever shown, so your labels are an independent test.

## One question at a time, in isolation

The app combines the 7 answers itself. Each question looks only at its own evidence:

| Question | Look only at | Ignore |
|---|---|---|
| ability_fit | scores and self-assessment in the field's **core subjects** | money, location, interest, admission chance |
| interest_fit | stated interests, dream job, dislikes | scores, money, location |
| budget_ok | tuition vs what the family can pay | everything else |
| location_ok | where the program is vs where the student wants to study | everything else |
| conditions_ok | special conditions (English-taught, gender, health, campus) vs the student | everything else |
| risk_tolerance / top_priority | the student's own words about risk / what matters most | the program |

Admission chance is never part of ability_fit: the statistical engine handles it.

### ability_fit
1. Field ("Lĩnh vực") → core subjects: IT/engineering/science/finance → Toán (+Lý); health/biology →
   Sinh, Hóa; languages/international → Ngoại ngữ, Văn; journalism/social/law → Văn, Sử/Địa, writing and
   speaking; economics → Toán, Ngoại ngữ.
2. 5: core ≥ 8.5 or "very strong" · 4: 7.5–8.5 · 3: 6.5–7.5 or mixed · 2: 5–6.5 or "weak" · 1: < 5 or "very bad".
3. Self-assessment counts ("em học Toán rất kém" works without a score).
4. "Không đủ thông tin" only when there is neither a score nor a self-assessment for the core subjects.

## Rules of thumb

- Label what the text says, not what is probably true (no word about money → budget_ok is insufficient).
- Follow the rubric shown in the tool. If you think the rubric is wrong for a case (e.g. psychology counted as
  health), still follow it and say so in the note, so the rubric can be fixed without muddying the test.
- Filter to one question in the sidebar; consistency matters more than speed. ~1 hour for 294 rows.

## Second labeller: Gemini (`uniadvisor gold-llm`)

Gemini labels the same 294 rows into `data/slm/gold_llm.csv` (same format; `labeller` = the model that
answered, `note` = its one-line reason). It is a second independent labeller, not a replacement for yours:
compare the two before trusting either.

```bash
# keys: comma list in an env var, or one per line in data/slm/gemini_keys.txt (git-ignored)
set GEMINI_API_KEYS=key1,key2,key3          # PowerShell: $env:GEMINI_API_KEYS="key1,key2,key3"
uniadvisor gold-llm                         # 2 rows per request -> 147 requests; resumable
uniadvisor slm-eval --judge hybrid --gold data/slm/gold_llm.csv
```

- Each request holds 2 rows of one question, that question's rubric, and a plain "look only at / ignore" guide
  (~3,000 characters). The answer is forced into JSON with the allowed labels only; a reply that skips a case
  or invents a label is retried (3 tries).
- Quota: models are tried in order (`--models gemini-3.5-flash,gemini-3.5-flash-lite`), each with every key.
  A key out of its daily quota is skipped for that model; when all are out, the run stops and saves. Re-run
  the next day to finish. 6 keys x 20 requests/day covers 120 Flash + 120 Flash-Lite requests.
- The printout shows how often Gemini agrees with the synthetic teacher label (and with you, once
  `gold_labeled.csv` has labels). Low agreement on a question points at an unclear rubric.
