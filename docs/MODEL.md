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

**Training set** (about 5,000 students; run on a Kaggle GPU, not on a laptop):

1. **Seeds.** Each seed is a label (1-3 groups, every group covered) plus attributes: region, writing style (careful,
   short, teen code, rambling), how clear the student is (clear, unsure, slightly contradictory), which questions they
   skip, and a short persona (family background, what they did in school).
2. **Writing.** Three open models from three different families, each writing a third of the seeds: Qwen3.5-9B, Gemma 4
   12B (4-bit) and Vistral-7B-Chat (Vietnamese). The model is told the groups and the attributes, writes the
   questionnaire answers, and must not name a major.
3. **Blind check.** A model other than the writer reads only the answers and names the 3 groups that fit best (Gemma
   checks Qwen's and Vistral's students, Qwen checks Gemma's). A student is kept only if its groups are among them.

**Test set** (210 students: 3 per group): the same steps without personas and with its own prompt wording, written
and checked by Gemini, a different model family from the training set. Every student is then checked by hand. The test set is made and frozen before any
training data exists.

Nothing a real student enters is used or stored.

### What each step rests on

| Step | Source | What it shows |
|---|---|---|
| A large LLM writes labelled data; a small model is trained on it | Schick & Schütze (2021); Ye et al. (2022) | a whole labelled set generated from scratch; a tiny task model trained on it |
| Label plus attributes in each prompt (region, style, clarity, skipped questions) | Yu et al. (2023) | attributed prompts beat plain "write an example of class X" prompts on many-class tasks and reduce bias such as regional bias |
| A short persona per seed | Chan et al. (2024) | a persona in the prompt steers the LLM to a different perspective, giving varied data |
| Training text from three model families | Schaffelder & Gatt (2026) | synthetic data from several sources keeps outputs varied (less "distribution collapse"); shown for fine-tuning LLMs, not small classifiers |
| Keep a student only if a blind model agrees with its label | Alberti et al. (2019) | "roundtrip consistency" filtering of generated data |
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

Limits: the model learns the LLMs' judgement, not real students' choices, and real answers will be messier and less
typical than generated ones. Li et al. (2023) found that models trained on synthetic data lose more the more
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

1. The group -> O\*NET occupation table (70 rows) needs a check by the team.
