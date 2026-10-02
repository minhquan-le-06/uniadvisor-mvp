# Student JSON: what module 2 hands to module 3

Module 2 talks with the student, in Vietnamese, as a guided conversation: each question comes with input widgets
(text boxes, checkboxes, dropdowns), and the student may skip or say they don't know. From that conversation it
fills one JSON document per student and gives it to module 3. The student never sees the JSON; they see ordinary
questions and a "Mình hiểu là..." summary they can correct.

Only facts module 3 needs go into the JSON. How a value was obtained (typed, estimated, read from text, suggested),
the evidence and the confidence stay inside module 2. A value the student did not give and that has no safe default
is `null` (or an empty list); module 3 must work without it. Nothing a student enters is stored (Decree 13/2023).

Status: schema version 1, agreed.

## The whole document

```json
{
  "meta": {"schema_version": 1, "target_year": 2027, "ruleset": "2026"},
  "profile": {
    "scores": {"TO": 8.4, "VA": 7.5, "LI": 8.5, "N1": 8.25},
    "score_kind": "mock",
    "province": "Nghệ An",
    "area": "KV3",
    "category": "none",
    "gender": "nam",
    "graduation_year": 2027
  },
  "interests": [{"code": "74801", "strength": "love"}, {"code": "7460108", "strength": "like"}],
  "dislikes": [{"code": "73403"}],
  "family": {"codes": ["71402"], "student_agrees": false},
  "budget": {"max_million_per_year": 25, "strict": true},
  "location": {"cities": ["Hà Nội"], "main_campus_only": true},
  "risk": "can_bang",
  "priorities": ["nganh_yeu_thich", "hoc_phi_thap"],
  "assumed": [{"field": "profile.area", "value": "KV3", "reason": "not_given"}]
}
```

Every key is always present. `meta` and `profile` are always filled; every other section may be empty or `null`.

## `meta`

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer | 1; bumped whenever a field is added or its meaning changes |
| `target_year` | integer | the admission year the advice is for |
| `ruleset` | string | the rules file module 3 applies (`backend/config/rules/<ruleset>.yaml`) |

## `profile`

| Field | Type | Required | Allowed values | Used by module 3 for |
|---|---|---|---|---|
| `scores` | object: subject key -> number | yes | exactly 4 keys: `TO`, `VA` and 2 different electives; values 0.0-10.0, `TO` a multiple of 0.05, the others of 0.25 | combination totals, eligibility, ability |
| `score_kind` | enum | yes | `actual`: every subject is an exact official score; `mock`: anything else (mock exam, estimate, self-rated level) | uncertainty added to P(admit) |
| `province` | enum or null | no | the 34 provinces after the July 2025 merger (`REGION_OF` in `backend/uniadvisor/student/slm/synth.py`) | region and nearest city |
| `area` | enum | yes (defaulted) | `KV1`, `KV2-NT`, `KV2`, `KV3` | area priority points (0.75 / 0.5 / 0.25 / 0, tapered from 22.5) |
| `category` | enum | yes (defaulted) | `none`, `UT1` (đối tượng 01-04), `UT2` (đối tượng 05-07) | category priority points (0 / 2.0 / 1.0) |
| `gender` | enum | yes | `nam`, `nu` | programs that admit one gender only |
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
| a self-rated level | `xuat_sac` "Xuất sắc" 9.5 (9-10), `gioi` "Giỏi" 8.5 (8-9), `trung_binh_kha` "Trung bình khá" 7.5 (7-8), `trung_binh_yeu` "Trung bình yếu" 6.5 (6-7), `yeu` "Yếu" 5.0 (< 6) |

Exact scores are recommended. A range is offered when the student only has an estimate, and the level choice when
they cannot estimate at all. Any range or level makes `score_kind` = `mock`.

### The questions

| Field | Question | Widget | If unknown or skipped |
|---|---|---|---|
| `scores` | "Em cho mình xin điểm các môn thi nhé: Toán, Văn và 2 môn tự chọn. Không nhớ chính xác thì em ước chừng hoặc tự đánh giá mức học cũng được." | per subject: elective dropdown; mode (điểm chính xác / khoảng điểm / mức học); a number box, two number boxes, or a level dropdown | required: without them no list can be made; the app explains this and offers the level choice |
| `province` | "Em đang sống ở tỉnh/thành nào?" | dropdown | `null` |
| `area` | "Trường THPT của em thuộc khu vực ưu tiên nào?" (hint: theo nơi học THPT, ghi trong hồ sơ đăng ký dự thi) | radio KV1 / KV2 nông thôn / KV2 / KV3 / Em không biết | `KV3`, listed in `assumed`, with a notice |
| `category` | "Em có thuộc diện ưu tiên nào không, ví dụ con thương binh, liệt sĩ, hoặc người dân tộc thiểu số ở vùng khó khăn?" | radio Không / Có, nhóm 1 (đối tượng 01-04) / Có, nhóm 2 (đối tượng 05-07) | `none`, listed in `assumed` |
| `graduation_year` | "Em đang học lớp 12 năm nay đúng không?" | radio Đúng / Không, em tốt nghiệp năm [number] | `target_year`, listed in `assumed` |
| `gender` | "Giới tính của em? Một số ít ngành chỉ tuyển nam hoặc nữ, nên mình cần biết để không gợi ý nhầm." | radio Nam / Nữ | required: the app explains why it asks |

## `interests`, `dislikes`, `family`

| Field | Type | Allowed values | Meaning |
|---|---|---|---|
| `interests` | list, 0-5 items, no repeated code | `code`: a MOET nhóm ngành (5 digits) or ngành (7 digits) from the picker; `strength`: `love` "Rất thích", `like` "Thích" | what the student wants to study; `[]` = no preference |
| `dislikes` | list, no repeated code | `code` as above | what the student will not study; `[]` = none |
| `family` | object or null | `codes`: a non-empty list of codes as above; `student_agrees`: `true` "Em đồng ý", `false` "Em không muốn", `null` "Em chưa chắc" | what the family wants the student to study and whether the student goes along with it; `null` = not given |

A code never appears in both `interests` and `dislikes` (the form prevents it). Module 3 matches a program to a code
with `uniadvisor.student.intent.covers(code, program_major_code)`: the code is a prefix of the program's MOET code and
`data/config/fields.yaml` does not move that program to another field.

### The picker (interests, dislikes and family use the same one)

1. **Nhóm ngành** dropdown: only the groups with at least one program in the database (70 of MOET's 95 today,
   recomputed from `get_db()`), listed under their lĩnh vực, searchable, each with its number of programs
   ("Công nghệ thông tin (68 ngành)"). Groups without programs are hidden.
2. **Ngành** dropdown, optional: the ngành in that group our schools offer (283 today), plus "Tất cả ngành trong
   nhóm này" (the default, which writes the nhóm ngành code).
3. For interests only, **Rất thích / Thích**.

| Section | Question | If skipped |
|---|---|---|
| `interests` | "Em muốn học ngành nào? Em có thể chọn tối đa 5 nhóm ngành hoặc ngành." plus a button "Em chưa biết" | `[]`, or the questionnaire below |
| `dislikes` | "Có ngành nào em chắc chắn không muốn học không?" | `[]` |
| `family` | "Gia đình có mong em học ngành nào không?" then "Em có đồng ý với mong muốn này không?" (Em đồng ý / Em không muốn / Em chưa chắc) | `null` |

### "Em chưa biết": a short questionnaire

When the student does not know what to study, module 2 asks a few questions instead (subjects, work types, hobbies,
workplace, dream job; every one optional), then suggests 3-5 groups from the picker's list with a short reason each
("Vì em thích Tin học và viết 'muốn làm game'"). Suggestions start ticked; the student unticks or adds, and only the
confirmed ones are written to `interests`, as `like`. If the student answers nothing, they pick from the list.

The questions and the model that makes the suggestions are defined in [MODEL.md](MODEL.md).

## `budget`, `location`, `risk`, `priorities`

| Field | Type | Allowed values | If skipped |
|---|---|---|---|
| `budget` | object or null | | `null` ("Em chưa rõ" or skipped) |
| `budget.max_million_per_year` | number > 0, or null | tuition the family can pay per academic year, in million VND; `null` = no limit ("Gia đình không lo về học phí") | |
| `budget.strict` | boolean | `true`: a hard ceiling ("Đây là mức tối đa, không thể vượt"); `false`: a guide (always `false` when there is no limit) | |
| `location` | object or null | | `null` |
| `location.cities` | non-empty list | `Hà Nội`, `TP. Hồ Chí Minh` (the cities in scope); both = "Ở đâu cũng được"; "Gần nhà em nhất" writes the city nearer the student's province (offered only when `province` is known) | |
| `location.main_campus_only` | boolean | `true`: no branch campuses ("Em chỉ muốn học ở cơ sở chính, không học phân hiệu") | `false` |
| `risk` | enum or null | `an_toan` "Em muốn chắc chắn có trường", `can_bang` "Vừa thử sức vừa có lót", `mao_hiem` "Em sẵn sàng liều vì trường mơ ước" | `null` |
| `priorities` | list, 0-3, ranked, no repeats | `nganh_yeu_thich` "Học đúng ngành yêu thích", `truong_danh_tieng` "Trường danh tiếng", `hoc_phi_thap` "Học phí thấp", `gan_nha` "Học gần nhà", `viec_lam_thu_nhap` "Việc làm, thu nhập sau này" (no employment data yet; the app says so) | `[]` |

| Field | Question | Widget |
|---|---|---|
| `budget` | "Mỗi năm gia đình em có thể lo học phí khoảng bao nhiêu?" | number box (triệu/năm), checkbox "Đây là mức tối đa, không thể vượt", buttons "Gia đình không lo về học phí" / "Em chưa rõ" |
| `location` | "Em muốn học ở đâu?" | checkboxes Hà Nội / TP.HCM, options "Gần nhà em nhất" / "Ở đâu cũng được", checkbox "Em chỉ muốn học ở cơ sở chính" |
| `risk` | "Khi đặt nguyện vọng, em nghiêng về hướng nào hơn?" | three radio options |
| `priorities` | "Điều gì quan trọng nhất với em khi chọn trường?" | pick and rank up to 3 |

## `assumed`

Every default module 2 fills in is listed, and the student is told about it in plain words:

| `field` | `value` | Notice to the student |
|---|---|---|
| `profile.area` | `KV3` | "Em chưa chọn khu vực ưu tiên nên mình tạm tính KV3, tức là chưa cộng điểm khu vực. Nếu biết khu vực của mình, em báo mình nhé." |
| `profile.category` | `none` | "Mình tạm tính em không thuộc diện ưu tiên nào. Nếu có, em báo mình nhé." |
| `profile.graduation_year` | the target year | "Mình tạm hiểu em là học sinh lớp 12 năm nay." |

`reason` is always `not_given` in version 1.

## Closed lists

Every field with fixed values is an enum: the JSON holds the key, the screen shows its Vietnamese name. Keys are the
ones the code, the gold sets and the SLM already use (Vietnamese slugs), so they are not renamed.

## Not in version 1

- **Other admission methods.** Only the THPT exam-score method is in scope, so tuyển thẳng and ưu tiên xét tuyển
  are out.
- **Bonus points and certificate conversion** (a future feature). The 2025 regulation lets each school add bonus
  points for language certificates and special achievements (HSG, KHKT; at most 3 points on 30) and convert a language
  certificate into the language subject's score. Both are set per school in its đề án. Planned: module 1 collects
  each school's rules, module 3 computes the points, and the schema gains certificate and award fields.
- **Health information** (for example speech difficulties): sensitive and rarely relevant; module 3 shows a
  program's special conditions as a warning instead.
