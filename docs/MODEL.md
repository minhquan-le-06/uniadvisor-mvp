# Major-group suggester ("Em chưa biết")

A small model that suggests nhóm ngành to a student who does not know what to study. It reads a short questionnaire
and returns a ranked list of MOET nhóm ngành with a reason for each. It stands on its own: it needs only the database
(module 1) and an O\*NET table, and nothing else from module 2. Whatever uses it (today, the guided chat of module 2)
only calls `suggest(answers) -> suggestions`.

Status: built and trained (outside the repo, in `../MLAI_suggester/`) on the first 1,922 generated students, results
under Evaluation; not yet wired into the app.

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

$$
D = \{(x_i, y_i)\}_{i=1}^{N}
$$

- $x_i$: one student's questionnaire answers (any question may be skipped).
- $y_i$: the 1-3 groups that fit that student, out of the $K$ groups ($K = 70$ today).
- $N \approx 5{,}000$ for training; the test set is generated separately (see Data).

### Features

Each student's answers become one vector $\varphi(x)$:

| Part | Size | Content |
|---|---|---|
| subjects | 18 | 1 if ticked |
| work types | 6 | 1 if ticked |
| hobbies | 15 | 1 if ticked |
| workplace | 6 | 1 if ticked |
| text | $2^{14}$ | TF-IDF of character 3-5-grams, hashed; the text is lower-cased, diacritics removed and teen code expanded (`ko`, `k` -> `khong`, `dc` -> `duoc`, ...) so typos and spelling variants still share n-grams |
| answered | 5 | 1 if that question was answered, so a skipped question differs from "chose nothing" |

Two more scores per group come from data, not from training. Both are between 0 and 1, and 0 when their question
was skipped.

- **Subject fit $a_k(x)$, from admission combinations (module 1).** For each subject, the lift says how much more
  often group $k$'s admission combinations include it than combinations overall:

  $$
  \mathrm{lift}(s, k) = \frac{\text{share of group } k\text{'s combinations that include } s}{\text{share of all combinations that include } s}
  $$

  Máy tính: Tin 2.3; Luật: Sử 2.7, Sinh 0.1. Each lift is capped at 3 and divided by 3, then averaged over the ticked
  subjects. Groups with few programs are pulled towards the overall share so they do not get extreme values.
- **Work-type fit $c_k(x)$, from O\*NET.** Each group is mapped to a few O\*NET occupations
  (`backend/config/suggest/onet_groups.csv`, occupation codes cited), which gives the group a RIASEC profile. The
  student's profile counts 1 for each ticked work type and 0.5 for each ticked hobby's type (0.5 is the only hand-set
  number). $c_k(x)$ is the correlation between the two six-number profiles, rescaled from $[-1, 1]$ to $[0, 1]$: the
  way the O\*NET Interest Profiler matches a person to occupations (it compares the shape of the profiles, not their
  level).

### Hypothesis family H

Multinomial logistic regression: one score per group, turned into probabilities that sum to 1.

$$
z_k(x) = w_k \cdot \varphi(x) + b_k + \alpha\, a_k(x) + \beta\, c_k(x), \qquad
f(x)_k = \frac{e^{z_k(x)}}{\sum_{j} e^{z_j(x)}}
$$

The parameters are $W = (w_1, \dots, w_K)$, $b$, $\alpha$ and $\beta$. $\alpha$ and $\beta$ learn how far to trust the
admission data and O\*NET; $W$ learns the rest, including which words point to which group. The reasons shown for a
group are the inputs that added most to its $z_k$.

### Loss L

The right groups should get high probability, and weights are kept small so the model does not memorise:

$$
L = -\frac{1}{N} \sum_{i=1}^{N} \frac{1}{|y_i|} \sum_{k \in y_i} \log f(x_i)_k \;+\; \lambda \lVert W \rVert^2
$$

Each fitting group of a student counts equally ($1/|y_i|$).

Trained with plain gradient descent in numpy (no new dependency, so it runs on the deployed app). $\lambda$ is chosen on
a validation split of the training set. Same data and seed, same model.

## Data

There are no answers from real students, so both sets are written by LLMs. Each student is written whole (the ticked
answers and the free text) for a given label, so no hand-made rule decides what a student with a given group ticks,
and the data owes nothing to the two data scores the model uses ($a$ and $c$).

**Training set** (6,000 seeds; written on a Kaggle GPU, not on a laptop):

1. **Seeds.** Each seed is a label (1-3 groups, every group covered) plus attributes: region, writing style (careful,
   short, teen code, rambling), how clear the student is (clear, unsure, slightly contradictory), which questions they
   skip, and a short persona (family background, what they did in school).
2. **Writing.** Qwen3.5-9B writes the students: it is told the groups and the attributes, writes the questionnaire
   answers, and must not name a major. Vistral-7B-Chat (Vietnamese, Mistral family) can take every other seed once
   Hugging Face grants access. Tried and dropped: Gemma 3 and 4 (their attention needs more GPU shared memory than
   Kaggle's T4s have) and Llama-3.1-8B (a third of its outputs unreadable, garbled Vietnamese).
3. **Cleaning** (`collect.py`): unknown option codes, extra subjects or work types and skipped questions are removed;
   empty students are dropped.
4. **Label filter: confident learning, tried and not used.** The training set is split into 5 parts; a model trained
   on the other 4 scores each student of the held-out part. A student is dropped when none of its groups gets a
   confident probability but another group does (the per-group threshold is that group's average probability over the
   students labelled with it). It replaced the first plan, a blind check by a second open model (Llama passed only 19%
   of Qwen's students and put one group first for a fifth of them; Gemini's free quota is too small to check
   thousands of students in time). On the 1,922 students it dropped 52% and lowered test Hit@5 from 0.81 to 0.77: the
   method needs good out-of-sample probabilities, and with about 27 students per group the held-out model found the
   right group in its top 5 for only 57% of them, so most flags were its own mistakes. The training set is used
   unfiltered; the filter stays in the code (`--cl`) to retry on a bigger set.

**Test set** (3 seeds per group): written and blind-checked by Gemini, a different model family from the training set,
without personas and with its own prompt wording; a student is kept only if the blind check recovers its groups.
Gemini's free tier was overloaded, so the set mixes gemini-3.5/3.6/3.7/3.8-flash and 3.5-flash-lite (counts per
model in its `stats.json`). 199 students passed (73290 has none; 7 groups have 1-2). A random 60 were checked by
hand: 59 right, 1 wrong (removed), so about 2% of the labels are wrong (95% upper bound about 9%). The test set is
frozen before training.

Nothing a real student enters is used or stored.

### What each step rests on

| Step | Source | What it shows |
|---|---|---|
| A large LLM writes labelled data; a small model is trained on it | Schick & Schütze (2021); Ye et al. (2022) | a whole labelled set generated from scratch; a tiny task model trained on it |
| Label plus attributes in each prompt (region, style, clarity, skipped questions) | Yu et al. (2023) | attributed prompts beat plain "write an example of class X" prompts on many-class tasks and reduce bias such as regional bias |
| A short persona per seed | Chan et al. (2024) | a persona in the prompt steers the LLM to a different perspective, giving varied data |
| A second writer from another family (Vistral), when available | Schaffelder & Gatt (2026) | synthetic data from several sources keeps outputs varied (less "distribution collapse"); shown for fine-tuning LLMs, not small classifiers |
| Training labels filtered by confident learning (tried, not used: see step 4) | Northcutt et al. (2021) | out-of-sample predicted probabilities and per-class thresholds find wrong labels without a second labeller |
| Test set: keep a student only if a blind model recovers its label | Alberti et al. (2019) | "roundtrip consistency" filtering of generated data |
| Test set written by a model, checked by people | Perez et al. (2023) | model-written evaluation sets; human raters agreed with 90-100% of the labels |
| Work-type fit by profile correlation | Rounds et al., O\*NET Interest Profiler Manual | the Interest Profiler's own person-occupation matching |
| Generation, curation and evaluation as a whole | Long et al. (2024) | survey of the field |

The subject lift is a plain statistic of our own admission data and needs no source.

## Evaluation

On the test set only:

- **Hit@5**: share of students with at least one fitting group in the top 5 (the main number).
- **Recall@5**: share of all fitting groups that land in the top 5.
- **Baseline**: the two data scores alone ($W = 0$, $\alpha = \beta = 1$). The trained model is kept only if it beats it.

Behaviour checks: every group can reach the top 5 for some answers; no group is in the top 5 for more than about 25%
of random answer sets; no answers gives no suggestions; same input gives the same output.

### Results (1,922 training students, 198 test students)

| | Hit@5 | Recall@5 |
|---|---|---|
| Trained model ($\lambda = 10^{-5}$, $\alpha = 1.76$, $\beta = 1.71$) | 0.81 | 0.71 |
| Baseline (data scores alone) | 0.49 | 0.40 |

With 198 test students, differences under about 0.03 are noise. Hit@5 against training size (same test set): 480
students 0.63, 961 0.67, 1,441 0.80, 1,922 0.84 (another split; still rising, so more data should help).

Behaviour: every group reaches the top 5; no answers gives no suggestions; same input, same output. One group is
slightly over the 25% mark: 78102 (Khách sạn, nhà hàng) is in the top 5 for 26% of random answer sets. Before the
O\*NET table was checked, 78190 was at 37%: its occupations mixed chefs and dietitians, which gave a flat profile, and
a correlation with a flat profile swings on tiny differences.

Limits: the model learns the LLMs' judgement, not real students' choices, and real answers will be messier and less
typical than generated ones. The test set is easier than the training set: its students passed a blind check, while
the training students include unsure, contradictory and question-skipping ones on purpose. The held-out Hit@5 on
training students is 0.57 against 0.81 on the test set, so expect lower numbers on real, vaguer answers. If only Qwen writes the training set, its students share one model's habits (the variety
argument above then does not apply). Li et al. (2023) found that models trained on synthetic data lose more the more
subjective the task, and choosing a major is fairly subjective, so expect a gap on real students. Accuracy on real
students is not measured.

## Planned layout

| Path | What |
|---|---|
| `backend/uniadvisor/student/suggest/` | features, priors, model, training, `suggest()` |
| `backend/config/suggest/` | `onet_groups.csv` (group -> O\*NET occupations), `hobbies.yaml` (hobby -> type), the teen-code table |
| `backend/suggest_data/` | generated train / test sets |
| `artifacts/models/suggester/` | trained weights and metrics |

Generation and training scripts, model downloads and scratch runs live outside the repo, in `../MLAI_suggester/`;
only the frozen sets, the final weights and the stable code are copied in.

## References

- Alberti, C., Andor, D., Pitler, E., Devlin, J., Collins, M. (2019). Synthetic QA Corpora Generation with Roundtrip
  Consistency. ACL 2019. https://aclanthology.org/P19-1620/
- Chan, X., Wang, X., Yu, D., Mi, H., Yu, D. (2024). Scaling Synthetic Data Creation with 1,000,000,000 Personas.
  arXiv:2406.20094 (technical report). https://arxiv.org/abs/2406.20094
- Li, Z., Zhu, H., Lu, Z., Yin, M. (2023). Synthetic Data Generation with Large Language Models for Text Classification:
  Potential and Limitations. EMNLP 2023. https://aclanthology.org/2023.emnlp-main.647/
- Long, L., Wang, R., Xiao, R., Zhao, J., Ding, X., Chen, G., Wang, H. (2024). On LLMs-Driven Synthetic Data Generation,
  Curation, and Evaluation: A Survey. Findings of ACL 2024. https://aclanthology.org/2024.findings-acl.658/
- Northcutt, C. G., Jiang, L., Chuang, I. L. (2021). Confident Learning: Estimating Uncertainty in Dataset Labels.
  Journal of Artificial Intelligence Research 70, 1373-1411. https://arxiv.org/abs/1911.00068
- Perez, E., et al. (2023). Discovering Language Model Behaviors with Model-Written Evaluations. Findings of ACL 2023.
  https://aclanthology.org/2023.findings-acl.847/
- Rounds, J., Hoff, K., Lewis, P. (eds.). O\*NET Interest Profiler Manual. National Center for O\*NET Development.
  https://www.onetcenter.org/dl_files/IP_Manual.pdf
- Schaffelder, M., Gatt, A. (2026). Synthetic Eggs in Many Baskets: The Impact of Synthetic Data Diversity on LLM
  Fine-Tuning. Findings of ACL 2026. https://aclanthology.org/2026.findings-acl.360.pdf
- Schick, T., Schütze, H. (2021). Generating Datasets with Pretrained Language Models. EMNLP 2021.
  https://aclanthology.org/2021.emnlp-main.555/
- Ye, J., Gao, J., Li, Q., Xu, H., Feng, J., Wu, Z., Yu, T., Kong, L. (2022). ZeroGen: Efficient Zero-shot Learning via
  Dataset Generation. EMNLP 2022. https://aclanthology.org/2022.emnlp-main.801/
- Yu, Y., Zhuang, Y., Zhang, J., Meng, Y., Ratner, A., Krishna, R., Shen, J., Zhang, C. (2023). Large Language Model as
  Attributed Training Data Generator: A Tale of Diversity and Bias. NeurIPS 2023 Datasets and Benchmarks.
  https://arxiv.org/abs/2306.15895
- O\*NET (U.S. Department of Labor), occupation interest profiles, CC BY 4.0.

## Open questions

1. The group -> O\*NET occupation table (70 rows) was checked by hand (2026-10-03). Occupation choices were fixed where
   the check found a better match (73401, 73404, 75402, 75490, 76203, 77601, 78190, 78590); the RIASEC values are
   O\*NET's own and are not edited. Still weak: 78590 (two unrelated programs, eco-tourism and landscape, give a flat
   profile) and 72201 (English literature teachers stand in for Vietnamese literature).
2. Group 73290 (Khác, Công nghệ đa phương tiện: one ngành) never passed the test set's blind check: it overlaps with
   Mỹ thuật ứng dụng and Báo chí - truyền thông. Whether the picker should list it is for module 1 and the team.
