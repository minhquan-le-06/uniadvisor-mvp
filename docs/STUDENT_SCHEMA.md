# Student JSON: what module 2 hands to module 3

Module 2 talks with the student, in Vietnamese, as a guided conversation: each question comes with input widgets
(text boxes, checkboxes, dropdowns), and the student may skip or say they don't know. From that conversation it
fills one JSON document per student and gives it to module 3. The student never sees the JSON; they see ordinary
questions and a "Mình hiểu là..." summary they can correct.

Only facts module 3 needs go into the JSON. How a value was obtained (typed, estimated, read from text), the
evidence and the confidence stay inside module 2. A value the student did not give and that has no safe default is
`null`; module 3 must work without it.

Status: `meta`, `profile`, `interests`, `dislikes`, `family`, `budget`, `location`, `risk` and `priorities` are decided.
English certificates and achievements are being discussed. Which LLM turns free answers into JSON is an open question for the
"form to JSON" step.

## Top level

```json
{
  "meta": {"schema_version": 1, "target_year": 2027, "ruleset": "2026"},
  "profile": { },
  "assumed": [ ]
}
```

| Field | Type | Meaning |
|---|---|---|
| `meta.schema_version` | integer | Bumped whenever a field is added or its meaning changes |
| `meta.target_year` | integer | The admission year the advice is for |
| `meta.ruleset` | string | The rules file module 3 applies (`backend/config/rules/<ruleset>.yaml`) |
| `assumed` | list | Defaults module 2 filled in; the student was told about each (see below) |

## `profile`

```json
"profile": {
  "scores": {"TO": 8.4, "VA": 7.5, "LI": 8.5, "N1": 8.25},
  "score_kind": "mock",
  "province": "Nghệ An",
  "area": "KV3",
  "category": "none",
  "gender": null,
  "graduation_year": 2027
}
```

| Field | Type | Required | Allowed values | Used by module 3 for |
|---|---|---|---|---|
| `scores` | object: subject key -> number | yes | exactly 4 keys: `TO`, `VA` and 2 electives; values 0.0-10.0 | combination totals, eligibility, ability |
| `score_kind` | enum | yes | `actual`: every subject is an exact official score; `mock`: anything else (mock exam, estimate, self-rated level) | uncertainty added to P(admit) |
| `province` | enum or null | no | the 34 provinces after the July 2025 merger (`REGION_OF` in `student/slm/synth.py`) | region and nearest hub for "near home" |
| `area` | enum | yes (defaulted) | `KV1`, `KV2-NT`, `KV2`, `KV3` | area priority points (0.75 / 0.5 / 0.25 / 0, tapered from 22.5) |
| `category` | enum | yes (defaulted) | `none`, `UT1` (đối tượng 01-04), `UT2` (đối tượng 05-07) | category priority points (0 / 2.0 / 1.0) |
| `gender` | enum or null | no | `nam`, `nu`, `null` | programs that admit one gender only (how module 3 asks for it is still open) |
| `graduation_year` | integer | yes (defaulted) | 2020 to `target_year` | area points count only in the graduation year and the next |

Subject keys (the 2025+ exam: Toán and Ngữ văn plus 2 electives):

| Key | Shown as | Key | Shown as |
|---|---|---|---|
| `TO` | Toán | `N1` | Tiếng Anh |
| `VA` | Ngữ văn | `N2` | Tiếng Nga |
| `LI` | Vật lý | `N3` | Tiếng Pháp |
| `HO` | Hóa học | `N4` | Tiếng Trung |
| `SI` | Sinh học | `N5` | Tiếng Đức |
| `SU` | Lịch sử | `N6` | Tiếng Nhật |
| `DI` | Địa lý | `N7` | Tiếng Hàn |
| `TI` | Tin học | `CNCN` | Công nghệ công nghiệp |
| `GDKTPL` | Giáo dục kinh tế và pháp luật | `CNNN` | Công nghệ nông nghiệp |

### How module 2 turns answers into scores (internal)

| The student gives | Score written |
|---|---|
| an exact score | as given; Toán in steps of 0.05, other subjects in steps of 0.25 (anything else is rejected) |
| a range, e.g. "7 đến 8" | the midpoint rounded **down** to the subject's step (7.5; 7.5-8.25 -> 7.75) |
| a self-rated level | `xuat_sac` "Xuất sắc" 9.5 (9-10), `gioi` "Giỏi" 8.5 (8-9), `trung_binh_kha` "Trung bình khá" 7.5 (7-8), `trung_binh_yeu` "Trung bình yếu" 6.5 (6-7), `yeu` "Yếu" 5.0 (< 6; the value is provisional) |

Exact scores are recommended. A range is offered when the student only has an estimate, and the level choice when
they cannot estimate at all. Any range or level makes `score_kind` = `mock`.

### The questions (shown in Vietnamese, each with its widgets)

| Field | Question | Widget | If unknown or skipped |
|---|---|---|---|
| `scores` | "Em cho mình xin điểm các môn thi nhé: Toán, Văn và 2 môn tự chọn. Không nhớ chính xác thì em ước chừng hoặc tự đánh giá mức học cũng được." | per subject: elective dropdown; mode (điểm chính xác / khoảng điểm / mức học); number box, two number boxes or level dropdown | required: without them no list can be made; the app explains this and offers the level choice |
| `province` | "Em đang sống ở tỉnh/thành nào?" | dropdown | `null` |
| `area` | "Trường THPT của em thuộc khu vực ưu tiên nào?" (hint: theo nơi học THPT, ghi trong hồ sơ đăng ký dự thi) | radio KV1 / KV2 nông thôn / KV2 / KV3 / Em không biết | `KV3`, with a notice |
| `category` | "Em có thuộc diện ưu tiên nào không, ví dụ con thương binh, liệt sĩ, hoặc người dân tộc thiểu số ở vùng khó khăn?" | radio Không / nhóm 1 / nhóm 2 | `none` |
| `graduation_year` | "Em đang học lớp 12 năm nay đúng không?" | radio Đúng / Không, em tốt nghiệp năm [number] | `target_year` |
| `gender` | "Giới tính của em? Một số ít ngành chỉ tuyển nam hoặc nữ." | radio Nam / Nữ / Không muốn trả lời | `null` |

## `interests`, `dislikes`, `family`

```json
"interests": [{"code": "74801", "strength": "love"}, {"code": "7460108", "strength": "like"}],
"dislikes":  [{"code": "73403"}],
"family":    {"codes": ["71402"], "student_agrees": false}
```

| Field | Type | Allowed values | Meaning |
|---|---|---|---|
| `interests` | list, 0-5 items | `code`: a MOET nhóm ngành (5 digits) or ngành (7 digits) from the picker; `strength`: `love` "Rất thích", `like` "Thích" | what the student wants to study; empty = no preference given |
| `dislikes` | list | `code` as above | what the student will not study |
| `family` | object or null | `codes`: list as above; `student_agrees`: `true` "Em đồng ý", `false` "Em không muốn", `null` "Em chưa chắc" | what the family wants the student to study, and whether the student goes along with it; null = not given |

Module 3 matches a program to a code with `uniadvisor.student.intent.covers(code, program_major_code)`: the code is a
prefix of the program's MOET code and `data/config/fields.yaml` does not move that program to another field. A code
may not appear in both `interests` and `dislikes` (the form prevents it).

### The picker (interests, dislikes and family use the same one)

1. **Nhóm ngành** dropdown: only the groups with at least one program in the database (70 of MOET's 95 today,
   recomputed from `get_db()` every build), listed under their lĩnh vực, searchable, each with its number of programs
   ("Công nghệ thông tin (68 ngành)"). Groups without programs are hidden.
2. **Ngành** dropdown, optional: the ngành in that group that our schools offer (283 today), plus "Tất cả ngành trong
   nhóm này" (the default, which writes the nhóm ngành code).
3. For interests only, **Rất thích / Thích**.

| Section | Question | If skipped |
|---|---|---|
| `interests` | "Em muốn học ngành nào? Em có thể chọn tối đa 5 nhóm ngành hoặc ngành." plus a button "Em chưa biết" | `[]`, or the questionnaire below |
| `dislikes` | "Có ngành nào em chắc chắn không muốn học không?" | `[]` |
| `family` | "Gia đình có mong em học ngành nào không?" then "Em có đồng ý với mong muốn này không?" (Em đồng ý / Em không muốn / Em chưa chắc) | `null` |

### "Em chưa biết": a short questionnaire

When the student does not know what to study, module 2 asks a few questions instead, then suggests 3-5 groups with a
short reason each ("Vì em thích máy móc và học tốt Toán, Lý, mình nghĩ em có thể hợp với..."). Suggestions start
ticked; the student unticks or adds, and only the confirmed ones are written to `interests`, as `like`. The suggestion
step turns free answers into codes from the picker's list only (an LLM is planned; which one is open); if it is
unavailable, the student picks from the list.

| Question | Widget |
|---|---|
| "Em thích hoặc học tốt môn nào nhất?" | subject checkboxes |
| "Em thích làm việc với điều gì hơn?" | checkboxes: con người, máy móc và kỹ thuật, số liệu, ý tưởng và sáng tạo, thiên nhiên, chữ nghĩa (Holland / RIASEC types) |
| "Lúc rảnh em hay làm gì?" | checkboxes (viết code, vẽ, tranh biện, chăm sóc người khác, làm thí nghiệm, kinh doanh online, ...) and a free box |
| "Sau này em mơ ước làm công việc gì?" | free box, optional |

## `budget`, `location`, `risk`, `priorities`

```json
"budget":     {"max_million_per_year": 25, "strict": true},
"location":   {"cities": ["Hà Nội"], "main_campus_only": true},
"risk":       "can_bang",
"priorities": ["nganh_yeu_thich", "hoc_phi_thap"]
```

| Field | Type | Allowed values | If skipped |
|---|---|---|---|
| `budget.max_million_per_year` | number or null | tuition the family can pay per academic year, in million VND; `null` = no limit ("Gia đình không lo về học phí") | `budget` = `null` ("Em chưa rõ" or skipped) |
| `budget.strict` | boolean | `true`: a hard ceiling ("Đây là mức tối đa, không thể vượt"); `false`: a guide | |
| `location.cities` | list | `Hà Nội`, `TP. Hồ Chí Minh` (the cities in scope); both = "Ở đâu cũng được"; "Gần nhà em nhất" writes the city nearer the student's province | `location` = `null` |
| `location.main_campus_only` | boolean | `true`: no branch campuses ("Em chỉ muốn học ở cơ sở chính, không học phân hiệu") | `false` |
| `risk` | enum or null | `an_toan` "Em muốn chắc chắn có trường", `can_bang` "Vừa thử sức vừa có lót", `mao_hiem` "Em sẵn sàng liều vì trường mơ ước" | `null` |
| `priorities` | list, 0-3, ranked | `nganh_yeu_thich` "Học đúng ngành yêu thích", `truong_danh_tieng` "Trường danh tiếng", `hoc_phi_thap` "Học phí thấp", `gan_nha` "Học gần nhà", `viec_lam_thu_nhap` "Việc làm, thu nhập sau này" (no employment data yet; the app says so) | `[]` |

| Field | Question | Widget |
|---|---|---|
| `budget` | "Mỗi năm gia đình em có thể lo học phí khoảng bao nhiêu?" | number box (triệu/năm), checkbox "Đây là mức tối đa, không thể vượt", buttons "Gia đình không lo về học phí" / "Em chưa rõ" |
| `location` | "Em muốn học ở đâu?" | checkboxes Hà Nội / TP.HCM, options "Gần nhà em nhất" / "Ở đâu cũng được", checkbox "Em chỉ muốn học ở cơ sở chính" |
| `risk` | "Khi đặt nguyện vọng, em nghiêng về hướng nào hơn?" | three radio options |
| `priorities` | "Điều gì quan trọng nhất với em khi chọn trường?" | pick and rank up to 3 |

Not collected: speech difficulties or other health information (sensitive, rarely relevant); module 3 shows a program's
special conditions as a warning instead.

## `assumed`

Every default module 2 fills in is listed, and the student is told about it in plain words:

```json
"assumed": [
  {"field": "profile.area", "value": "KV3", "reason": "not_given"}
]
```

Notice shown for `profile.area`: "Em chưa chọn khu vực ưu tiên nên mình tạm tính KV3, tức là chưa cộng điểm khu
vực. Nếu biết khu vực của mình, em báo mình nhé."

## Closed lists

Every field with fixed values is an enum: the JSON holds the key, the screen shows its Vietnamese name. Keys are
the ones the code, the gold sets and the SLM already use (Vietnamese slugs), so they are not renamed.
