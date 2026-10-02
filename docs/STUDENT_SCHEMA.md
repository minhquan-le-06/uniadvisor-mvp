# Student JSON: what module 2 hands to module 3

Module 2 talks with the student, in Vietnamese, as a guided conversation: each question comes with input widgets
(text boxes, checkboxes, dropdowns), and the student may skip or say they don't know. From that conversation it
fills one JSON document per student and gives it to module 3. The student never sees the JSON; they see ordinary
questions and a "Mình hiểu là..." summary they can correct.

Only facts module 3 needs go into the JSON. How a value was obtained (typed, estimated, read from text), the
evidence and the confidence stay inside module 2. A value the student did not give and that has no safe default is
`null`; module 3 must work without it.

Status: `meta` and `profile` are decided. `interests` is being designed; budget, location, risk, priorities, family,
English and achievements are still to be defined.

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
