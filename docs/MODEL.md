# Major-group suggester ("Em chưa biết")

A small model that suggests nhóm ngành to a student who does not know what to study. It reads a short questionnaire
and returns a ranked list of MOET nhóm ngành with a reason for each. It stands on its own: it needs only the database
(module 1) and an O\*NET table, and nothing else from module 2. Whatever uses it (today, the guided chat of module 2)
only calls `suggest(answers) -> suggestions`.

Status: design agreed, not built.

## Interface

### Input: the questionnaire answers

Every question is optional. A skipped question is absent from the input, not an empty answer.

| Key | Question shown to the student | Values |
|---|---|---|
| `subjects` | "Em thích hoặc học tốt môn nào?" | up to 3 subject keys: `TO`, `VA`, `LI`, `HO`, `SI`, `SU`, `DI`, `TI`, `GDKTPL`, `N1`-`N7`, `CNCN`, `CNNN` |
| `work_types` | "Em thích làm việc với điều gì hơn?" | up to 2 RIASEC types (table below) |
| `hobbies` | "Lúc rảnh em hay làm gì?" | any of the hobby keys (table below) |
| `workplace` | "Sau này em muốn làm việc ở đâu?" | any of `van_phong`, `ngoai_troi`, `benh_vien`, `nha_may_phong_thi_nghiem`, `truong_hoc`, `tu_do` |
| `text` | "Sau này em mơ ước làm công việc gì?" plus the "Khác" box of the hobbies question | free Vietnamese text, joined into one string |

| RIASEC type | Checkbox text |
|---|---|
| `R` Realistic | Làm với máy móc, dụng cụ, xây dựng, sửa chữa |
| `I` Investigative | Tìm hiểu, nghiên cứu, giải bài toán khó |
| `A` Artistic | Sáng tạo: vẽ, viết, thiết kế, âm nhạc |
| `S` Social | Giúp đỡ, chăm sóc, dạy người khác |
| `E` Enterprising | Thuyết phục, kinh doanh, dẫn dắt nhóm |
| `C` Conventional | Sắp xếp, tính toán, làm với số liệu, giấy tờ |

| Hobby key | Checkbox text | RIASEC type |
|---|---|---|
| `code` | Viết code, mày mò máy tính | I |
| `ve_thiet_ke` | Vẽ, thiết kế | A |
| `am_nhac` | Chơi nhạc, hát | A |
| `viet_doc` | Viết lách, đọc sách | A |
| `quay_dung` | Chụp ảnh, quay và dựng video | A |
| `the_thao` | Chơi thể thao | R |
| `sua_chua` | Sửa chữa, lắp ráp đồ | R |
| `cay_con_vat` | Trồng cây, nuôi con vật | R |
| `thi_nghiem` | Làm thí nghiệm, tìm hiểu khoa học | I |
| `cham_soc` | Chăm sóc người khác, tình nguyện | S |
| `day_ban` | Giảng bài cho bạn bè | S |
| `tranh_bien` | Tranh biện, thuyết trình | E |
| `kinh_doanh` | Buôn bán, kinh doanh online | E |
| `sap_xep` | Lập kế hoạch, sắp xếp, ghi chép | C |
| `du_lich` | Du lịch, tìm hiểu văn hóa, ngoại ngữ | S |

### Output: ranked suggestions

```json
[{"code": "74801", "score": 0.31, "reasons": ["em thích Tin học", "em viết \"muốn làm game\""]},
 {"code": "72104", "score": 0.18, "reasons": ["em thích vẽ, thiết kế"]}]
```

- `code`: a 5-digit MOET nhóm ngành among the groups with at least one program in the database (70 today).
- `score`: the model's probability for that group; the list is sorted by it, ties by number of programs, then code.
- `reasons`: the 1-2 inputs that added most to that group's score, in Vietnamese.
- Length: the top 5 groups whose score is at least 0.6 of the best, and at least 3. Empty when no question was answered.

The caller shows the suggestions ticked; the student unticks or adds. The model never writes anything itself.

## The model

### Data set D

```
D = {(x_i, y_i)}, i = 1..N        N ≈ 5,000 for training; the test set is generated separately (see Data)

x_i  one student's questionnaire answers (any key may be absent)
y_i  ∈ {0,1}^K, K = number of groups (70), with 1-3 ones: the groups that fit the student
```

### Features φ(x) ∈ R^d

| Part | Size | Content |
|---|---|---|
| subjects | 18 | 1 if ticked |
| work types | 6 | 1 if ticked |
| hobbies | 15 | 1 if ticked |
| workplace | 6 | 1 if ticked |
| text | 2^14 | TF-IDF of character 3-5-grams, hashed; the text is lower-cased, diacritics removed and teen code expanded (`ko`, `k` -> `khong`, `dc` -> `duoc`, ...) so typos and spelling variants still share n-grams |
| answered | 5 | 1 if that question was answered, so a skipped question differs from "chose nothing" |

Two prior scores per group come from data, not from the model:

- **`a(x) ∈ R^K`, subject fit from admission combinations (module 1).**
  For a program p with accepted combinations C_p: `share_p(s) = |{c ∈ C_p : s ∈ c}| / |C_p|`.
  `base(s)` = the mean of `share_p(s)` over all programs; `share_k(s)` = the mean over the n_k programs of group k,
  shrunk towards the base for small groups: `(n_k·share_k(s) + 10·base(s)) / (n_k + 10)`.
  `lift(s, k) = share_k(s) / base(s)`: how much more often group k's combinations include s than usual
  (Máy tính: Tin 2.3; Luật: Sử 2.7, Sinh 0.1). Then `a_k(x)` = the mean over the ticked subjects of `min(lift(s, k), 3) / 3`.
- **`c(x) ∈ R^K`, work-type fit from O\*NET.**
  Each group is mapped to a few O\*NET-SOC occupations (`backend/config/suggest/onet_groups.csv`, one row per group,
  occupation codes cited). The group profile `r_k` = the mean of their six RIASEC interest scores, centred on its own
  mean. The student vector `u` = 1 per ticked type plus 0.5 per ticked hobby on its type (the only hand-set number).
  `c_k(x) = (1 + cos(u, r_k)) / 2`.

Both are 0 when their question was not answered.

### Hypothesis family H

Multinomial logistic regression over the groups, plus one learned weight for each prior:

```
H = { f_θ(x) = softmax( W·φ(x) + b + α·a(x) + β·c(x) )  |  θ = (W ∈ R^{K×d}, b ∈ R^K, α ∈ R, β ∈ R) }
```

`α` and `β` learn how far to trust the admission data and O\*NET; `W` learns the rest, including which words point to
which group. A softmax because the task is to rank groups against each other. Reasons come from the largest terms of
`W_k·φ(x)`, `α·a_k(x)` and `β·c_k(x)` for each suggested group.

### Loss L

Cross-entropy against the student's groups, each fitting group counting equally, plus L2:

```
L(θ) = − (1/N) Σ_i Σ_k ỹ_ik · log f_θ(x_i)_k  +  λ‖W‖²        ỹ_i = y_i / Σ_k y_ik
```

Trained with plain gradient descent in numpy (no new dependency, so it runs on the deployed app). `λ` is chosen on a
validation split of the training set. Same data and seed, same model.

## Data

There are no answers from real students, so the training data is generated:

1. **Simulator (answers and labels).** Pick 1-3 groups (the label `y`); draw work types from the groups' O\*NET profiles,
   subjects from their admission-combination lift, hobbies from the work types, a workplace; drop each question with
   some probability so skipped answers are common; add noise (an unrelated tick, a contradictory one).
2. **LLM (text only).** An LLM writes the free text for each simulated student, the way a grade-12 student writes
   (short, teen code, typos, vague or off-topic sometimes). Each call gets a different combination of attributes
   (groups, region, writing style, how clear the student is), following Yu et al. (2023), so the texts vary. The LLM
   writes the text; it does not decide the label. Hosted (Gemini) or an open model run locally (Qwen2.5, SeaLLM) both work.
3. **Test set (separate).** About 500 students written end to end by Gemini, answers and fitting groups, with prompts
   different from the training ones, so the model is not graded only against our simulator. The team skims about 100
   of them for wrong labels.

Nothing a real student enters is used or stored.

## Evaluation

On the test set only:

- **Hit@5**: share of students with at least one fitting group in the top 5 (the main number).
- **Recall@5**: share of all fitting groups in the top 5.
- **Baseline**: the priors alone (`W = 0`, `α = β = 1`). The learned model is kept only if it beats it.

Behaviour checks: every group can reach the top 5 for some answers; no group is in the top 5 for more than about 25%
of random answer sets; no answers gives no suggestions; same input gives the same output.

Limits: the model learns our simulator and the LLM's judgement, not real students' choices, and real text will be
messier than generated text. Accuracy on real students is not measured.

## Planned layout

| Path | What |
|---|---|
| `backend/uniadvisor/student/suggest/` | features, priors, model, training, `suggest()` |
| `backend/config/suggest/` | `onet_groups.csv` (group -> O\*NET occupations), `hobbies.yaml` (hobby -> type), the teen-code table |
| `backend/suggest_data/` | generated train / test sets |
| `artifacts/models/suggester/` | trained weights and metrics |

## References

- Yu et al. (2023). *Large Language Model as Attributed Training Data Generator: A Tale of Diversity and Bias.* NeurIPS
  2023 Datasets and Benchmarks. Attribute-conditioned prompts for varied generated data.
- Ye et al. (2022). *ZeroGen: Efficient Zero-shot Learning via Dataset Generation.* EMNLP 2022. A large model writes the
  data, a small task model is trained on it.
- Schick & Schütze (2021). *Generating Datasets with Pretrained Language Models.* EMNLP 2021.
- Long et al. (2024). *On LLMs-Driven Synthetic Data Generation, Curation, and Evaluation: A Survey.* Findings of ACL 2024.
- Ratner et al. (2017). *Snorkel: Rapid Training Data Creation with Weak Supervision.* VLDB 2017. Labels from rules and
  knowledge sources instead of hand labels.
- O\*NET (U.S. Department of Labor), interest profiles of occupations, CC BY 4.0.

## Open questions

1. Which LLM writes the training text: hosted (Gemini) or local open model.
2. The group -> O\*NET occupation table (70 rows) needs a check by the team.
