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
D = \{(x_i, y_i)\}_{i=1}^{N}, \qquad y_i \in \{0,1\}^K, \qquad 1 \le \textstyle\sum_k y_{ik} \le 3
$$

- $x_i$: one student's questionnaire answers (any key may be absent).
- $y_i$: the groups that fit the student, as a 0/1 vector over the $K$ groups ($K = 70$ today).
- $N \approx 5{,}000$ for training; the test set is generated separately (see Data).

### Features $\varphi(x) \in \mathbb{R}^d$

| Part | Size | Content |
|---|---|---|
| subjects | 18 | 1 if ticked |
| work types | 6 | 1 if ticked |
| hobbies | 15 | 1 if ticked |
| workplace | 6 | 1 if ticked |
| text | $2^{14}$ | TF-IDF of character 3-5-grams, hashed; the text is lower-cased, diacritics removed and teen code expanded (`ko`, `k` -> `khong`, `dc` -> `duoc`, ...) so typos and spelling variants still share n-grams |
| answered | 5 | 1 if that question was answered, so a skipped question differs from "chose nothing" |

Two prior scores per group come from data, not from the model:

**$a(x) \in [0,1]^K$, subject fit from admission combinations (module 1).** For a program $p$ with accepted
combinations $C_p$ (each a set of subjects), the share of its combinations that include subject $s$ is

$$
\mathrm{share}_p(s) = \frac{|\{c \in C_p : s \in c\}|}{|C_p|}.
$$

Let $P$ be all programs and $P_k$ the $n_k$ programs of group $k$. The usual share, and group $k$'s share shrunk
towards it so that small groups do not get extreme values, are

$$
\mathrm{base}(s) = \frac{1}{|P|} \sum_{p \in P} \mathrm{share}_p(s), \qquad
\mathrm{share}_k(s) = \frac{\sum_{p \in P_k} \mathrm{share}_p(s) + 10 \cdot \mathrm{base}(s)}{n_k + 10}.
$$

The lift says how much more often group $k$'s combinations include $s$ than usual (Máy tính: Tin 2.3; Luật: Sử 2.7,
Sinh 0.1). With $S(x)$ the ticked subjects,

$$
\mathrm{lift}(s, k) = \frac{\mathrm{share}_k(s)}{\mathrm{base}(s)}, \qquad
a_k(x) = \frac{1}{|S(x)|} \sum_{s \in S(x)} \frac{\min(\mathrm{lift}(s, k),\, 3)}{3}.
$$

**$c(x) \in [0,1]^K$, work-type fit from O\*NET.** Each group is mapped to a few O\*NET-SOC occupations
(`backend/config/suggest/onet_groups.csv`, one row per group, occupation codes cited). The group profile
$r_k \in \mathbb{R}^6$ is the mean of their six RIASEC interest scores, minus its own mean (so it shows which types stand
out). The student vector $u(x) \in \mathbb{R}^6$ counts 1 per ticked work type and 0.5 per ticked hobby on that hobby's
type (0.5 is the only hand-set number). Then

$$
c_k(x) = \frac{1}{2}\left(1 + \frac{u(x) \cdot r_k}{\lVert u(x) \rVert\, \lVert r_k \rVert}\right).
$$

$a(x) = 0$ when the subjects question was not answered; $c(x) = 0$ when neither work types nor hobbies were.

### Hypothesis family H

Multinomial logistic regression over the groups, plus one learned weight for each prior:

$$
\mathcal{H} = \left\{\, f_\theta(x) = \mathrm{softmax}\big(W \varphi(x) + b + \alpha\, a(x) + \beta\, c(x)\big) \;\middle|\;
\theta = (W, b, \alpha, \beta),\; W \in \mathbb{R}^{K \times d},\; b \in \mathbb{R}^K,\; \alpha, \beta \in \mathbb{R} \,\right\}
$$

$$
f_\theta(x)_k = \frac{\exp z_k(x)}{\sum_{j=1}^{K} \exp z_j(x)}, \qquad
z_k(x) = w_k^\top \varphi(x) + b_k + \alpha\, a_k(x) + \beta\, c_k(x)
$$

$\alpha$ and $\beta$ learn how far to trust the admission data and O\*NET; $W$ learns the rest, including which words
point to which group. A softmax because the task is to rank groups against each other. Reasons come from the largest
terms of $z_k(x)$ (single features of $w_k^\top \varphi(x)$, $\alpha\, a_k(x)$, $\beta\, c_k(x)$) for each suggested group.

### Loss L

Cross-entropy against the student's groups, each fitting group counting equally, plus L2:

$$
L(\theta) = -\frac{1}{N} \sum_{i=1}^{N} \sum_{k=1}^{K} \tilde{y}_{ik} \log f_\theta(x_i)_k \;+\; \lambda \lVert W \rVert_F^2,
\qquad \tilde{y}_{ik} = \frac{y_{ik}}{\sum_{j} y_{ij}}
$$

$$
\hat{\theta} = \arg\min_{\theta} L(\theta)
$$

Trained with plain gradient descent in numpy (no new dependency, so it runs on the deployed app). $\lambda$ is chosen on
a validation split of the training set. Same data and seed, same model.

## Data

There are no answers from real students, so the training data is generated:

1. **Simulator (answers and labels).** Pick 1-3 groups (the label $y$); draw work types from the groups' O\*NET profiles,
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

On the test set $T$ only. With $\mathrm{top}_5(x)$ the 5 groups with the highest $f_{\hat\theta}(x)_k$ and
$G_i = \{k : y_{ik} = 1\}$ the fitting groups of student $i$:

$$
\mathrm{Hit@5} = \frac{1}{|T|} \sum_{i \in T} \mathbb{1}\big[\, G_i \cap \mathrm{top}_5(x_i) \neq \emptyset \,\big],
\qquad
\mathrm{Recall@5} = \frac{\sum_{i \in T} |G_i \cap \mathrm{top}_5(x_i)|}{\sum_{i \in T} |G_i|}
$$

Hit@5 is the main number. The baseline is the priors alone ($W = 0$, $b = 0$, $\alpha = \beta = 1$); the learned model
is kept only if it beats it.

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
