# MVP: University Application Advisor for Vietnamese Grade-12 Students

## Goal

A decision-support app that helps a grade-12 student in Vietnam build and order their university application list (nguyện vọng). It must:

- Clarify the student's goals and priorities
- Gather relevant admissions information
- Compare options on multiple criteria
- Explain trade-offs
- Output a usable, ordered application list with admission probabilities

Architecture is hybrid: **knowledge base (rules) + statistical engine + a self-built small language model (SLM)** for soft judgments.

## Scope

**In scope**
- Admission method: national high-school exam scores (thi THPT) only
- Narrow coverage: ~30–50 universities, limited to 1–2 regions or field groups
- Student inputs: 3 subject scores, subject combination (tổ hợp, e.g. A00), province, priority category, free-text interests/constraints

**Out of scope (later)**
- Other methods: transcript (học bạ), aptitude tests (ĐGNL, ĐGTD), certificates
- Talent-based programs, nationwide coverage
- ML forecasting of cutoff scores

## Core principle

- Anything with a **verifiable correct answer** (score conversion, eligibility rules, admission probability, list ordering) → deterministic rules/statistics.
- Anything that is a **soft judgment** (interests, fit, reading free-text conditions) → SLM.
- The SLM **never** computes admission probability or regulation facts.

## Components

### 1. Data pipeline
- Unified schema: `university – program – combination – method – year – cutoff_score – quota`
- Sources: university admission plans, 2–3 years of cutoff scores, national score distributions per combination, current admission regulations, tuition/location
- Clean and normalize names/codes; cross-check cutoffs against ≥2 sources
- Convert cutoffs to **percentiles** using the score distribution of that year and combination (makes years comparable despite exam changes)

### 2. Knowledge base (rules)
- Eligibility filters (combination, program-specific conditions)
- Priority-point rules (region/category)
- Application constraints from current regulations
- Risk buckets from probability: Safe / Match / Reach
- Rules must be versioned per admission year

### 3. Statistical engine (admission probability)
- Baseline forecast of this year's cutoff percentile: recency-weighted average of past years, adjusted for quota change
- Uncertainty from historical backtest error
- `P(admit) = P(student percentile > forecast cutoff percentile)`
- Must support backtesting on past years

### 4. SLM module (System-1 style, self-built)
- Input: `state` JSON (student profile + program description) + typed question
- Output: typed answer with calibrated probability/confidence
- Question types:
  - **Bool**: e.g. meets program-specific conditions? tuition within budget?
  - **Choice**: e.g. risk tolerance, top priority
  - **Score** (5-level ordinal): e.g. interest fit, ability fit
- Keep < 10 questions for MVP
- Model: small Vietnamese-capable encoder or small decoder, typed heads (sigmoid / softmax / ordinal), LoRA fine-tuning, commercial-use license
- Calibration: temperature scaling or isotonic per head; report ECE
- Low confidence → ask student a clarifying question or flag for human review

### 5. SLM training data
- Written rubric per question (including "insufficient info")
- Synthetic student profiles (score distributions close to real ones, diverse free-text, ambiguous and contradictory cases) paired with **real** program data
- Teacher LLM labels each sample several times → soft labels
- Human-labeled gold test set (a few hundred samples), never used for training
- Split by program/university to test generalization; deduplicate

### 6. Optimizer
- Maximize expected value of the ordered list:
  `E = Σᵢ pᵢ · Π_{j before i}(1 − pⱼ) · uᵢ`
  where `pᵢ` = admission probability (engine), `uᵢ` = utility (SLM fit + student weights)
- Constraints from KB (max number of choices, at least N Safe options)

### 7. Multi-criteria comparison
- Criteria: admission probability, fit, tuition, location, (optional) employment
- Weights from the student's goal profile

### 8. Conversational intake + explanation
- Chat flow collects goals and builds a structured profile (via SLM questions)
- Explanations generated from engine numbers only (probability, uncertainty, which criteria win/lose)
- Every recommendation shows a confidence label

## Evaluation

| Component | Metrics |
|---|---|
| Statistical engine | Backtest percentile error; calibration of probability buckets |
| SLM | Accuracy/F1 per question on gold set; ECE; escalation rate; per-group quality (province, combination, score band) |
| Whole system | Human review of list reasonableness and explanation clarity |

## Non-functional requirements

- **Privacy**: comply with Vietnam Decree 13/2023 on personal data; SLM runs in-house; explicit consent before storing any real student data
- **Reproducibility**: same input → same output for rule/statistical parts
- **Disclaimer**: results are advisory; students must verify with official regulations
- **Yearly update**: data and rules must be easy to refresh each admission season
- **UI language**: Vietnamese

## Suggested milestones

1. Schema + narrow-scope dataset
2. KB + baseline probability engine + backtest
3. SLM question set, rubrics, labeled data, fine-tune, calibrate
4. Optimizer + comparison + explanations, end-to-end demo
5. Pilot with real students, collect feedback

## Left to the agent

Tech stack, storage, crawling approach, base SLM choice, exact thresholds, UI design, API shape, project structure, dataset sizes.
