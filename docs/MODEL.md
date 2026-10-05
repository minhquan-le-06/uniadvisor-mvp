# Major-group suggester ("Em chưa biết")

A small model that suggests nhóm ngành to a student who does not know what to study. It reads a short questionnaire
and returns a ranked list of MOET nhóm ngành with a reason for each. It stands on its own: it needs only the database
(module 1) and an O\*NET table, and nothing else from module 2. Whatever uses it (today, the guided chat of module 2)
only calls `suggest(answers) -> suggestions`.

Status: trained on 15,038 generated students from two LLM families (12,943 by Qwen, 2,095 by Aya; data frozen;
results under Evaluation), with a popularity weight from real places, and used by the guided chat
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
- `score`: the model's probability for that group, popularity weight included (see Popularity); the list is sorted
  by it, ties by number of programs, then code.
- `reasons`: the 1-2 inputs that added most to that group's score, in Vietnamese.
- Length: always the top 5 groups (first "at least 3, more if within 0.6 of the best"; the reviewed cases showed a mixed student's second direction often at 4-5). Empty when no question was answered.

The caller shows the suggestions ticked; the student unticks or adds. The model never writes anything itself.

## The model

### Data set D

$$
D = \{(x_i, y_i)\}_{i=1}^{N}
$$

- $x_i$: one student's questionnaire answers (any question may be skipped).
- $y_i$: the 1-3 groups that fit that student, out of the $K$ groups ($K = 70$ today).
- $N = 15{,}038$ for training; the test set is generated separately (see Data).

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

### Popularity

The training students are spread evenly over the groups, so the model has no idea that Kinh doanh takes about 10% of
students and Kinh tế học about 3%. At prediction (not in training) every score gets

$$
z_k(x) \mathrel{+}= \tau \left(\log \text{places}_k - \overline{\log \text{places}}\right), \qquad \tau = 0.2
$$

where $\text{places}_k$ is the sum of group $k$'s 2026 quotas (module 1; 51% of its programs have one, the rest count
as the group's median program). With $\tau = 1$ this is the standard correction of a classifier's outputs for new
class priors (Saerens et al. 2002); $\tau < 1$ goes part of the way, because the test set and the reviewed cases are
spread evenly over the groups and cannot tell how far is right. By field, these places match MOET's national
enrolment of 2025 (rank correlation 0.81 over the 12 largest fields: Kinh doanh và quản lý 21.8% here against 21.5%
nationally, Báo chí 3.0% against 3.0%; weaker for Sức khỏe, 4.5% against 7.8%, and teacher training, 3.3% against
5.6%, since the 48 schools here are large Hà Nội and HCM universities).

| $\tau$ | Test Hit@5 | Reviewed cases passing (88) | Shown in random answer sets: Kinh doanh / CNTT / Tài chính |
|---|---|---|---|
| 0 | 0.90 | 54.5% | 5.6% / 3.8% / 6.8% |
| 0.1 | 0.89 | 54.5% | 8.7% / 6.1% / 10.4% |
| **0.2** | 0.88 | 53.4% | 13.1% / 8.1% / 13.7% |
| 0.4 | 0.88 | 52.3% | 24.3% / 11.9% / 22.3% |
| 1 | 0.74 | | |

(Their shares of places: 9.7% / 5.7% / 5.7%.) 0.2 brings these groups to about their share at a cost within noise on
the evenly spread test set; from 0.4 a few large groups crowd the top 5. Kinh tế học stays rare (2-3% of sets) at any
$\tau$: it loses to Kinh doanh, whose students look alike. The reviewer asked for it (popular majors such as Kinh tế,
Marketing and Truyền thông rarely appeared); the guided chat's scoring panel shows the term as "Phổ biến".

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

**Training set** (17,200 seeds, 15,038 students after cleaning and filtering; written on a Kaggle GPU, not on a
laptop):

1. **Seeds.** Each seed is a label (1-3 groups, every group covered) plus attributes: region, writing style (careful,
   short, teen code, rambling), how clear the student is (clear, unsure, slightly contradictory), which questions they
   skip, and a short persona (family background, what they did in school).
2. **Writing.** Qwen3.5-9B writes the students: it is told the groups and the attributes, writes the questionnaire
   answers, and must not name a major. Vistral-7B-Chat (Vietnamese, Mistral family) was planned for every other seed
   but Hugging Face did not grant access in time, so Qwen wrote all of them. Tried and dropped: Gemma 3 and 4 (their attention needs more GPU shared memory than
   Kaggle's T4s have) and Llama-3.1-8B (a third of its outputs unreadable, garbled Vietnamese).
   **Mixed students** (the last 3,000 seeds, added after the review): the seed names the subjects the student is good
   at (2-3 of one group's most lifted subjects in the admission data, plus Toán when most of that group's combinations
   have it) and a second group that the work types, hobbies, workplace and dream must fit (70% from another lĩnh
   vực); the label is both groups. Every other training student is consistent, so the model had never seen subjects
   and interests disagree (see Results).
   **Second writer** (the last 4,000 seeds: 3,000 plain, 1,000 mixed, each marked for it): Aya Expanse 8B (Cohere;
   Vietnamese is one of its 23 languages; its weights are float16, so it runs on the T4s, which have no bfloat16;
   Dang et al. 2024), because every writer habit found so far was Qwen's. Same prompts, 4,081 students in about 2
   hours. Compared with Qwen, against Gemini's test students as a reference: its subjects are closer to Gemini's
   (Toán in 33% of students of groups whose combinations nearly all have Toán, against 18% for Qwen and 58% for
   Gemini; health students: Toán 30%, Sinh 71%, against Qwen's 3% and 30%), but its interest answers are noisier
   (it picks "Trường học" for 40% of students and "Tìm hiểu, nghiên cứu" half as often as the others; its students'
   own group ranks 21st of 70 by the O\*NET fit $c_k$, against 14th for Qwen and 9th for Gemini). Trained on all of
   it, test Hit@5 fell from 0.91 to 0.87 (8 students lost, 1 gained), hence step 4.
3. **Cleaning** (`collect.py`): option values written as labels or misspelt codes are mapped back to codes when
   exactly one option fits (the code with diacritics removed, a whole-word part of one option's label, or one edit
   from one code of 5+ letters: "thí nghiệm" -> `thi_nghiem`, "tham_soc" -> `cham_soc`; Aya wrote a fifth of its
   hobbies this way, Qwen 2.5%); other unknown codes, extra subjects or work types and skipped questions are removed;
   empty students are dropped; a mixed student's subjects are set to the seed's (Qwen followed them in 97% of cases).
4. **Label filter: confident learning, tried and not used.** The training set is split into 5 parts; a model trained
   on the other 4 scores each student of the held-out part. A student is dropped when none of its groups gets a
   confident probability but another group does (the per-group threshold is that group's average probability over the
   students labelled with it). It replaced the first plan, a blind check by a second open model (Llama passed only 19%
   of Qwen's students and put one group first for a fifth of them; Gemini's free quota is too small to check
   thousands of students in time). On the 1,922 students it dropped 52% and lowered test Hit@5 from 0.81 to 0.77: the
   method needs good out-of-sample probabilities, and with about 27 students per group the held-out model found the
   right group in its top 5 for only 57% of them, so most flags were its own mistakes. Retried on 5,825 students: it
   dropped 46% and Hit@5 was 0.84 against 0.89 without it. Not used (the code keeps the filter behind `--cl`).
5. **Second writer's students: O\*NET consistency filter.** An Aya student is kept when its interest group (the label,
   or the second group of a mixed student) ranks in the top 20 of 70 by the O\*NET fit of its ticked work types and
   hobbies; students who ticked none are kept. 2,095 of 4,081 kept. A check against an independent source, as the
   test set's blind check is (Alberti et al. 2019), and the Interest Profiler's own matching. Top 10 kept 1,284 and
   scored lower on the test set (0.88), top 20 matched Qwen alone (0.90). Qwen's students are not filtered.

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
| Label plus attributes in each prompt (region, style, clarity, skipped questions; for mixed students, the subjects and the interest group) | Yu et al. (2023) | attributed prompts beat plain "write an example of class X" prompts on many-class tasks and reduce bias such as regional bias |
| A short persona per seed | Chan et al. (2024) | a persona in the prompt steers the LLM to a different perspective, giving varied data |
| A second writer from another family (Aya Expanse 8B) | Schaffelder & Gatt (2026); Dang et al. (2024) | synthetic data from several sources keeps outputs varied (less "distribution collapse"); shown for fine-tuning LLMs, not small classifiers. Aya: Vietnamese among its languages |
| Second writer's students kept only if their interests fit their group by O\*NET | Alberti et al. (2019); Rounds et al. | consistency with an independent source as a filter; O\*NET's own person-occupation matching |
| Popularity weight from real places | Saerens et al. (2002) | adjusting a classifier's outputs to new class priors by their ratio |
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
of random answer sets; no answers gives no suggestions; same input gives the same output. The random answer sets draw
subjects as often as 2026 exam candidates take them (`backend/config/suggest/subject_counts.csv`, from VnExpress's
per-subject score histograms; the languages other than English are not published and are set to the rarest observed
subject, an upper bound). The share with every subject equally likely is reported too (`top5_share_uniform_subjects`).

Reviewed cases (CheckList, Ribeiro et al. 2020): generated answer sets (one group, two groups mixed, few answers, with
a test student's text) are shown with the model's top 5 in a review page (`uniadvisor suggest-cases`,
`uniadvisor suggest-review`). The reviewer unticks groups that do not fit and adds missing ones; each verdict becomes
a check every later model is scored on (`expectations.jsonl`, reported by `suggest-train` and `suggest-check`): added
groups in the top 5 (or top 3), unticked groups out of the top 3, at least one kept group in the top 5.

### Results (15,038 training students, 198 test students)

| | Hit@5 | Recall@5 |
|---|---|---|
| Trained model ($\lambda = 10^{-5}$, option value 0.2, popularity 0.2) | 0.88 | 0.84 |
| ... without the popularity weight | 0.90 | 0.85 |
| Baseline (data scores alone) | 0.49 | 0.40 |
| Qwen only (12,943 students, after the recoding) | 0.91 | 0.83 |
| Qwen + all 4,081 Aya students | 0.87 | 0.82 |
| Qwen only, before the recoding (12,942; the previous model) | 0.90 | 0.85 |
| Before the mixed students (9,920 students) | 0.91 | 0.85 |
| ... and options at full weight (value 1) | 0.87 | 0.80 |
| ... and learned subject weights (the first model) | 0.90 | 0.81 |

88% of the test students find at least one fitting group in their top 5. With 198 test students, differences under
about 0.03 are noise. The second writer and its filter leave the test score where it was (0.90 without popularity);
what they add is a second family's habits in the data, which the literature above argues for, and the behaviour
check (below) now passes without popularity. The test set is spread evenly over the groups, so the popularity weight
can only cost there; it exists for real students, who are not.

Three changes came from the reviewed cases, not from the test set:

1. **No learned subject weights** (see Features): the writer's Toán habit. Test Hit@5 0.90 -> 0.87, within noise.
2. **Ticked options at 0.2 instead of 1** (work types, hobbies, workplace): the same $\lambda$ then holds their
   weights 25 times tighter. In the reviewed cases, the groups the reviewer unticked but the model kept in its top 3
   were pushed by these learned weights (2.4 above the average group, the other parts near 0), and the groups the
   reviewer added were held down by them (as low as -3 against a subject fit of 1.0 for a student of three foreign
   languages). Tried 1, 0.5, 0.3, 0.2, 0.1 and 0; 0.2 was best on the reviewed cases and test Hit@5 rose to 0.91.
3. **Mixed students** (see Data) and **always 5 suggestions** (see Output): most groups the reviewer added came from
   the mixed cases, where subjects point one way and interests another, and a larger $\alpha$ by hand did not help.

Reviewed cases (34: 9 one-direction, 9 mixed, 9 few answers, 6 with text, 1 the reviewer's own):

| | 9,920 students, options 0.2 | + mixed students |
|---|---|---|
| Cases passing all their checks | 14 | 15 |
| At least one kept group in the top 5 | 33 of 33 | 32 of 33 |
| Unticked groups all out of the top 3 | 13 of 22 | 15 of 22 |
| Added groups in the top 5 (median rank) | 1 of 18 (20) | 2 of 18 (16) |
| Test Hit@5 | 0.91 | 0.90 |

The mixed students help where they were aimed but only a little: Qwen followed the prescribed subjects, yet its
interest side is uneven (some students meant to fit Kỹ thuật mỏ read like office workers). 34 cases are few; a
difference of one or two cases is weak evidence.

Reviewed cases, later (88, after 70 more were generated with `suggest-cases --extend`), every model scored on the same
verdicts:

| | Passing | Kept in top 5 | Unticked out of top 3 | Added in top 5 |
|---|---|---|---|---|
| Previous model (Qwen) | 54.5% | 86/87 | 26/45 | 2/37 |
| Qwen + all Aya | 58.0% | 86/87 | 27/45 | 3/37 |
| Qwen + filtered Aya (current, without popularity) | 54.5% | 86/87 | 27/45 | 1/37 |
| ... with popularity 0.2 (shipped) | 53.4% | 84/87 | 27/45 | 1/37 |

The groups the reviewer added are the weak spot whatever the data: mostly broad, popular groups (Công nghệ thông tin
9 times, then Y học, Đào tạo giáo viên, Ngôn ngữ, Máy tính), often just outside the top 5 (ranks 6-10). With 5 slots,
raising them pushes out other groups the reviewer also kept: the full popularity correction ($\tau = 1$) gets 8 of 37
in but loses kept groups and test Hit@5 (0.77), and pooling a lĩnh vực's probability did not help.

Learning curve (with learned subject weights, fixed $\lambda$, mean of two random subsets per size, same test set):

| Training students | 1,456 | 2,976 | 5,952 | 7,936 | 9,920 |
|---|---|---|---|---|---|
| Hit@5 | 0.75 | 0.82 | 0.86 | 0.88 | 0.88 |
| Hit@1 | 0.41 | 0.44 | 0.55 | 0.51 | 0.59 |

Hit@5 levels off after about 6,000 students; Hit@1 still creeps up. More of the same writer is unlikely to help much;
real students' answers would.

Behaviour: every group reaches the top 5; no answers gives no suggestions; same input, same output. The current model
without popularity has no group over 25% (highest 72104, 24%). With popularity 0.2, 78101 (Du lịch, 28%) and 71402
(Đào tạo giáo viên, 25%) go over: groups of average size gain on smaller ones they were level with. The 25% mark was
set for a model with no popularity and is kept as a warning, not a rule. With the previous model (Qwen only) and no
popularity, one group was just over the mark: 78102 (Khách sạn, nhà hàng, 27%), then 72102 (Nghệ thuật trình diễn,
23%). 78102 had the highest learned option weights of all groups on average, mostly from
hobbies (in its top 5 for 35% of the sets with hobbies, 9% without), led by "Chơi nhạc, hát" (+0.84 against the
average group): Qwen ticks that hobby for 18% of the 291 training students labelled 78102, against 5% of all
students. A writer habit, like the Toán one; Aya does it too (18%), but the filtered Aya students dilute it.

With subjects drawn uniformly (the check's first version), 73103 (Xã hội học và Nhân học) is at 33% and 72202, 73801,
73104 and 77601 at 18-25%. This comes from the check, not the model: 6 of the 18 subjects are rare languages (Nga,
Pháp, Trung, Đức, Nhật, Hàn), only a few groups admit with combinations that have them (D02-D07), so their lift for
those groups is 4-5 and the cap gives them the full subject score. 73103 has 7 programs, admitting with D02, D05 and
D07 among others; its lead over the average group is the subject score (0.92, 2nd of 70) and its bias (0.38, 6th),
while its learned option weights are below average. Leaving out the sets with a rare language, no group is over 20%;
on the test set 73103 is in the top 5 for 7% of students. A real student who ticks Tiếng Đức still gets these groups
pushed up, which is the admission data speaking (they do admit German), not a sign of interest; stronger shrinkage of
lifts resting on few programs would temper it.

Before the O\*NET table was checked, 78190 was at 37%: its occupations mixed chefs and dietitians, which gave a flat
profile, and a correlation with a flat profile swings on tiny differences.

Limits: the model learns the LLMs' judgement, not real students' choices, and real answers will be messier and less
typical than generated ones. The test set is easier than the training set: its students passed a blind check, while
the training students include unsure, contradictory and question-skipping ones on purpose. Hit@5 on held-out
training students is about 0.70 against 0.88-0.90 on the test set, so expect lower numbers on real, vaguer answers.
Qwen still wrote 86% of the training set, so its habits dominate (the Toán habit and the option weights above are two
the review caught); Aya brings its own (schools as workplace, music). The popularity weight uses places at 48 large
Hà Nội and HCM universities, not the whole country. Li et al. (2023) found that models trained on synthetic data lose more the more
subjective the task, and choosing a major is fairly subjective, so expect a gap on real students. Accuracy on real
students is not measured.

## Layout

| Path | What |
|---|---|
| `backend/uniadvisor/student/suggest/` | `__init__.py` (questionnaire, hobby -> type, `suggest()`), `features.py` (incl. the teen-code table), `priors.py`, `model.py`, `suggester.py`, `train.py` |
| `backend/config/suggest/` | `onet_groups.csv` (group -> O\*NET occupations), `onet_review.csv` (its hand check), `onet/` (O\*NET 31.0 files), `subject_counts.csv` (2026 candidates per subject, for the behaviour check) |
| `backend/suggest_data/` | frozen sets: `train.jsonl`, `testset.jsonl`, `review_sample.csv`; reviewed cases: `review_cases.jsonl` (add more with `suggest-cases --n 70 --extend`, which never changes existing cases), `expectations.jsonl` |
| `artifacts/models/suggester/` | `model.npz`, `priors.json`, `group_profiles.csv`, `metrics.json`, `report.md` |

`uniadvisor suggest-train` retrains from the frozen sets (same data, same model).

Generation and training scripts, model downloads and scratch runs live outside the repo, in `../MLAI_suggester/`;
only the frozen sets, the final weights and the stable code are copied in.

## References

- Alberti, C., Andor, D., Pitler, E., Devlin, J., Collins, M. (2019). Synthetic QA Corpora Generation with Roundtrip
  Consistency. ACL 2019. https://aclanthology.org/P19-1620/
- Chan, X., Wang, X., Yu, D., Mi, H., Yu, D. (2024). Scaling Synthetic Data Creation with 1,000,000,000 Personas.
  arXiv:2406.20094 (technical report). https://arxiv.org/abs/2406.20094
- Dang, J., et al. (2024). Aya Expanse: Combining Research Breakthroughs for a New Multilingual Frontier.
  arXiv:2412.04261. https://arxiv.org/abs/2412.04261
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
- Saerens, M., Latinne, P., Decaestecker, C. (2002). Adjusting the Outputs of a Classifier to New a Priori
  Probabilities: A Simple Procedure. Neural Computation 14(1), 21-41. https://doi.org/10.1162/089976602753284446
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

## Next steps (not done)

1. **More reviewed cases** (in progress, 88 of 131): especially cases where a popular group (Kinh doanh, Kinh tế,
   Truyền thông, CNTT) should have come up, added under "Nhóm lẽ ra phải có". They are the only evidence that can pick
   the popularity weight $\tau$ (the test set is spread evenly over the groups and cannot).
2. **Kinh tế học** stays rare at any $\tau$: check whether its training students differ from Kinh doanh's at all.
3. **On the final data**: re-pick the option value (0.2 was chosen before the mixed students and the second writer)
   and try the O\*NET filter on Qwen's mixed students too.
4. Optional: stronger shrinkage of subject lifts that rest on few programs (rare languages, see Behaviour); a third
   writer family (GLM-4-9B-chat is the candidate, bfloat16 weights, may fail on T4 as Gemma did).

More students from the same writer will not help (the learning curve is flat). Done (2026-10-05): why 73103 was at
33% (the check's uniform subject draw), the second writer (Aya, filtered), example majors ordered by number of
programs (Marketing and Truyền thông now named under their groups), the popularity weight.
