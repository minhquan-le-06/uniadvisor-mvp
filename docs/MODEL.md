# Major-group suggester ("Em chưa biết")

A small model that suggests nhóm ngành to a student who does not know what to study. It reads a short questionnaire
and returns a ranked list of MOET nhóm ngành with a reason for each. It stands on its own: it needs only the database
(module 1) and an O\*NET table, and nothing else from module 2. Whatever uses it (today, the guided chat of module 2)
only calls `suggest(answers) -> suggestions`.

Status: trained on 9,920 generated students (data frozen; results under Evaluation) and used by the guided chat
(`app/pages/hoi_dap.py`).

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
| subjects | 18 | always 0: ticked subjects enter only through the subject fit $a_k$ below (see the note after the list) |
| work types | 6 | 0.2 if ticked (see Results: 1 let these learned weights override the data scores) |
| hobbies | 15 | 0.2 if ticked |
| workplace | 6 | 0.2 if ticked |
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

Why subjects have no learned weights: the training set's writer (Qwen) almost never ticks Toán (16% of its students,
against 48% of the test set's), and in 52 of the 70 groups a subject that is in most of the group's admission
combinations is ticked by few of its students (Y học: Toán in 99% of combinations, ticked by 3%). Learned weights
copied that habit: ticking Toán pushed a student away from medicine, pharmacy and most sciences. The admission data
says which subjects a group asks for, so the subjects are left to $a_k$ alone (`uniadvisor suggest-audit` lists such
gaps for every option).

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

**Training set** (10,200 seeds, 9,920 students after cleaning; written on a Kaggle GPU, not on a laptop):

1. **Seeds.** Each seed is a label (1-3 groups, every group covered) plus attributes: region, writing style (careful,
   short, teen code, rambling), how clear the student is (clear, unsure, slightly contradictory), which questions they
   skip, and a short persona (family background, what they did in school).
2. **Writing.** Qwen3.5-9B writes the students: it is told the groups and the attributes, writes the questionnaire
   answers, and must not name a major. Vistral-7B-Chat (Vietnamese, Mistral family) was planned for every other seed
   but Hugging Face did not grant access in time, so Qwen wrote all of them. Tried and dropped: Gemma 3 and 4 (their attention needs more GPU shared memory than
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
   right group in its top 5 for only 57% of them, so most flags were its own mistakes. Retried on 5,825 students: it
   dropped 46% and Hit@5 was 0.84 against 0.89 without it. The training set is used unfiltered (the code keeps the
   filter behind `--cl`).

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
| A second writer from another family (Vistral; planned, not available in time) | Schaffelder & Gatt (2026) | synthetic data from several sources keeps outputs varied (less "distribution collapse"); shown for fine-tuning LLMs, not small classifiers |
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

Reviewed cases (CheckList, Ribeiro et al. 2020): generated answer sets (one group, two groups mixed, few answers, with
a test student's text) are shown with the model's top 5 in a review page (`uniadvisor suggest-cases`,
`uniadvisor suggest-review`). The reviewer unticks groups that do not fit and adds missing ones; each verdict becomes
a check every later model is scored on (`expectations.jsonl`, reported by `suggest-train` and `suggest-check`): added
groups in the top 5 (or top 3), unticked groups out of the top 3, at least one kept group in the top 5.

### Results (9,920 training students, 198 test students)

| | Hit@5 | Recall@5 |
|---|---|---|
| Trained model ($\lambda = 10^{-5}$, option value 0.2, $\alpha = 5.25$, $\beta = 2.93$) | 0.91 | 0.85 |
| Baseline (data scores alone) | 0.49 | 0.40 |
| Options at full weight (value 1) | 0.87 | 0.80 |
| Options at full weight and learned subject weights (the first model) | 0.90 | 0.81 |

91% of the test students find at least one fitting group in their top 5 (Hit@1 0.64). With 198 test students,
differences under about 0.03 are noise.

Two changes came from the reviewed cases, not from the test set:

1. **No learned subject weights** (see Features): the writer's Toán habit. Test Hit@5 0.90 -> 0.87, within noise.
2. **Ticked options at 0.2 instead of 1** (work types, hobbies, workplace): the same $\lambda$ then holds their
   weights 25 times tighter. In the reviewed cases, the groups the reviewer unticked but the model kept in its top 3
   were pushed by these learned weights (2.4 above the average group, the other parts near 0), and the groups the
   reviewer added were held down by them (as low as -3 against a subject fit of 1.0 for a student of three foreign
   languages). Tried 1, 0.5, 0.3, 0.2, 0.1 and 0; 0.2 was best on the reviewed cases and test Hit@5 rose to 0.91.

Reviewed cases (34: 9 one-direction, 9 mixed, 9 few answers, 6 with text, 1 the reviewer's own): at least one kept
group stays in the top 5 in 33 of 33; 13 of 22 cases with unticked groups have none of them left in the top 3 (6
before the option change); the groups the reviewer added reach the top 5 in only 1 of 18 cases. The added groups are
mostly from the mixed cases (subjects pointing one way, interests another): the training students' subjects and
interests always agree, so the model never learned how much subjects should weigh in a conflict, and a larger
$\alpha$ by hand did not help (x2: 4 of 18). 14 of the 34 cases pass all their checks.

Learning curve (with learned subject weights, fixed $\lambda$, mean of two random subsets per size, same test set):

| Training students | 1,456 | 2,976 | 5,952 | 7,936 | 9,920 |
|---|---|---|---|---|---|
| Hit@5 | 0.75 | 0.82 | 0.86 | 0.88 | 0.88 |
| Hit@1 | 0.41 | 0.44 | 0.55 | 0.51 | 0.59 |

Hit@5 levels off after about 6,000 students; Hit@1 still creeps up. More of the same writer is unlikely to help much;
real students' answers would.

Behaviour: every group reaches the top 5; no answers gives no suggestions; same input, same output. Two groups are over
the 25% mark: 72202 (Ngôn ngữ nước ngoài, 29%) and 73801 (Luật, 27%). Part of it is the check itself: its random answer
sets pick subjects uniformly, and 7 of the 18 subjects are foreign languages, which real students seldom tick; with
the subject fit weighing more, those random sets lean to 72202. Before the O\*NET table was checked, 78190 was
at 37%: its occupations mixed chefs and dietitians, which gave a flat profile, and a correlation with a flat profile
swings on tiny differences.

Limits: the model learns the LLMs' judgement, not real students' choices, and real answers will be messier and less
typical than generated ones. The test set is easier than the training set: its students passed a blind check, while
the training students include unsure, contradictory and question-skipping ones on purpose. Hit@5 on held-out
training students is 0.68 against 0.91 on the test set, so expect lower numbers on real, vaguer answers. Qwen wrote
the whole training set, so its students share one model's habits (the variety argument of Schaffelder & Gatt does not
apply). Li et al. (2023) found that models trained on synthetic data lose more the more
subjective the task, and choosing a major is fairly subjective, so expect a gap on real students. Accuracy on real
students is not measured.

## Layout

| Path | What |
|---|---|
| `backend/uniadvisor/student/suggest/` | `__init__.py` (questionnaire, hobby -> type, `suggest()`), `features.py` (incl. the teen-code table), `priors.py`, `model.py`, `suggester.py`, `train.py` |
| `backend/config/suggest/` | `onet_groups.csv` (group -> O\*NET occupations), `onet_review.csv` (its hand check), `onet/` (O\*NET 31.0 files) |
| `backend/suggest_data/` | frozen sets: `train.jsonl`, `testset.jsonl`, `review_sample.csv` |
| `artifacts/models/suggester/` | `model.npz`, `priors.json`, `group_profiles.csv`, `metrics.json`, `report.md` |

`uniadvisor suggest-train` retrains from the frozen sets (same data, same model).

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
- Ribeiro, M. T., Wu, T., Guestrin, C., Singh, S. (2020). Beyond Accuracy: Behavioral Testing of NLP Models with
  CheckList. ACL 2020. https://aclanthology.org/2020.acl-main.442/
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
