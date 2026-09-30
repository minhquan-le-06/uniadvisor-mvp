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
1. Find the program's field ("Lĩnh vực") in the table the tool shows under the rubric; it lists that field's core
   subjects (the first counts double). Fields not in the table use Toán, Văn.
2. Average the core subjects the student HAS scores for (weighted), then 5: >= 8.5 · 4: 7.5–8.5 · 3: 6.5–7.5 ·
   2: 5–6.5 · 1: < 5.
3. Says they are good at a core subject: one level up; weak/bad at one: one level down (stay within 1–5). No core
   score at all but a self-assessment: good → 4, weak → 2.
4. "Không đủ thông tin" only when there is neither a score nor a self-assessment for any core subject.

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
# keys: copy .env.example to .env (git-ignored) and fill in GEMINI_API_KEYS=key1,key2,...
# (or GEMINI_API_KEY_1=..., GEMINI_API_KEY_2=..., one per line); the CLI reads .env itself
uniadvisor gold-llm                         # 2 rows per request -> 147 requests; resumable
uniadvisor slm-eval --judge hybrid --gold data/slm/gold_llm.csv
```

- Each request holds 2 rows of one question, that question's rubric, and a plain "look only at / ignore" guide
  (~3,000 characters). The answer is forced into JSON with the allowed labels only; a reply that skips a case
  or invents a label is retried (3 tries).
- Quota: models are tried in order (`--models gemini-3.5-flash,gemini-3.5-flash-lite`), each with every key.
  A key out of its daily quota is skipped for that model; when all are out, the run stops and saves. Re-run
  the next day to finish. The free quota is per Google Cloud project, not per key: keys in the same project share it.
- Each label records the rubric version it was made under (`labeller` = `model#version`). When a rubric changes,
  re-running relabels only the rows of that question. Rows labelled before versions existed are redone only
  when you ask: `uniadvisor gold-llm --redo ability_fit`.
- The printout shows how often Gemini agrees with the synthetic teacher label (and with you, once
  `gold_labeled.csv` has labels). Low agreement on a question points at an unclear rubric.
