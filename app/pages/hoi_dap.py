"""Module 2's guided chat (trial page): nine short steps with widgets fill the student JSON for module 3
(docs/STUDENT_SCHEMA.md). The logic lives in uniadvisor.student.form; this file only draws it.

Nothing is written to disk; answers live in this browser session. Add ?debug=1 to the URL for test mode: the JSON,
the suggester's scoring table, and a .txt log of every suggestion run (answers, scores, what was kept) that the tester
downloads from the sidebar; it is built in memory and only leaves the browser session as that download.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from uniadvisor.student import suggest as sg
from uniadvisor.student.form import (
    ANYWHERE, MODES, NEAR_HOME, SECTIONS, Answers, ScoreEntry, build, picker, problems, search, summary,
)
from uniadvisor.student.form.options import (
    AGREES, AREAS, CATEGORIES, ELECTIVES, GENDERS, LANGUAGES, LEVELS, MAX_INTERESTS, MAX_PRIORITIES, NEAREST_CITY,
    PRIORITIES, PROVINCES, RISKS, STRENGTHS, SUBJECTS, target_year,
)
from uniadvisor.student.form.scores import step as score_step
from unidata.db import get_db

st.set_page_config(page_title="UniAdvisor – Hỏi đáp", page_icon=":material/forum:", layout="centered")

STEPS = [*SECTIONS, "summary"]
QUESTIONS = {
    "scores": "Em cho mình xin điểm các môn thi nhé: Toán, Văn và 2 môn tự chọn. Không nhớ chính xác thì em ước chừng "
              "khoảng điểm hoặc tự đánh giá mức học cũng được.",
    "about": "Giờ mình hỏi vài điều về em nhé.",
    "interests": f"Em muốn học ngành nào? Em có thể chọn tối đa {MAX_INTERESTS} nhóm ngành hoặc ngành.",
    "dislikes": "Có ngành nào em chắc chắn không muốn học không?",
    "family": "Gia đình có mong em học ngành nào không?",
    "budget": "Mỗi năm gia đình em có thể lo học phí khoảng bao nhiêu?",
    "location": "Em muốn học ở đâu?",
    "plan": "Khi đặt nguyện vọng, em nghiêng về hướng nào hơn, và điều gì quan trọng nhất với em khi chọn trường?",
    "summary": "Mình hiểu là:",
}

ss = st.session_state
ss.setdefault("f_step", 0)
ss.setdefault("f_ans", Answers())
ss.setdefault("f_done", [])
ss.setdefault("f_editing", False)
ss.setdefault("f_quiz", False)
ss.setdefault("f_quiz_ans", {})
ss.setdefault("f_suggestions", None)
ss.setdefault("f_finished", False)
ss.setdefault("f_sg_debug", None)
ss.setdefault("t_log", [])          # test mode: one entry per suggestion run; survives "Bắt đầu lại", never written to disk
A: Answers = ss.f_ans
P = picker(get_db())
YEAR = target_year()
DEBUG = st.query_params.get("debug") == "1"


def reset() -> None:
    for k in [k for k in ss if str(k).startswith("f_")]:
        del ss[k]


def advance() -> None:
    key = STEPS[ss.f_step]
    if key not in ss.f_done:
        ss.f_done.append(key)
    ss.f_step = len(STEPS) - 1 if ss.f_editing else ss.f_step + 1
    ss.f_editing = False
    st.rerun()


def nav(skippable: bool = True) -> tuple[bool, bool]:
    """(Tiếp tục pressed, Bỏ qua pressed)."""
    c1, c2, _ = st.columns([1, 1, 3])
    go = c1.button("Tiếp tục", type="primary", key=f"f_next_{STEPS[ss.f_step]}", icon=":material/arrow_forward:")
    skip = c2.button("Bỏ qua", key=f"f_skip_{STEPS[ss.f_step]}") if skippable else False
    return go, skip


def doc_now() -> dict | None:
    try:
        return build(A, P, year=YEAR)[0]
    except ValueError:
        return None


def reply(key: str) -> str:
    """The student's side of a finished step, as one line."""
    if key == "scores":
        return " · ".join(f"{SUBJECTS[e.subject]} {e.score():g}".replace(".", ",") for e in A.scores)
    doc = doc_now()
    return summary(doc, P)[key] if doc else ""


# ------------------------------------------------------------------ steps
def step_scores() -> None:
    old = {i: e for i, e in enumerate(A.scores)}
    c1, c2 = st.columns(2)
    e1_old = old[2].subject if 2 in old else None
    e1 = c1.selectbox("Môn tự chọn 1", ELECTIVES, format_func=SUBJECTS.get, key="f_e1",
                      index=ELECTIVES.index(e1_old) if e1_old else None, placeholder="Chọn môn")
    second = [s for s in ELECTIVES if s != e1 and not (e1 in LANGUAGES and s in LANGUAGES)]
    e2_old = old[3].subject if 3 in old else None
    e2 = c2.selectbox("Môn tự chọn 2", second, format_func=SUBJECTS.get, key="f_e2",
                      index=second.index(e2_old) if e2_old in second else None, placeholder="Chọn môn")

    entries = []
    for i, subject in enumerate(["TO", "VA", e1, e2]):
        if subject is None:
            continue
        prev = old.get(i) if old.get(i) and old[i].subject == subject else ScoreEntry(subject)
        a, b = st.columns([2, 3])
        mode = a.radio(SUBJECTS[subject], list(MODES), format_func=MODES.get, key=f"f_m{i}",
                       index=list(MODES).index(prev.mode))
        s = score_step(subject)
        with b:
            if mode == "exact":
                v = st.number_input("Điểm", 0.0, 10.0, prev.value, s, format="%.2f", key=f"f_v{i}", placeholder="vd 8,25")
                entries.append(ScoreEntry(subject, "exact", value=v))
            elif mode == "range":
                lo_c, hi_c = st.columns(2)
                lo = lo_c.number_input("Từ", 0.0, 10.0, prev.low, 0.25, format="%.2f", key=f"f_lo{i}")
                hi = hi_c.number_input("Đến", 0.0, 10.0, prev.high, 0.25, format="%.2f", key=f"f_hi{i}")
                entries.append(ScoreEntry(subject, "range", low=lo, high=hi))
            else:
                lv = st.selectbox("Mức học", list(LEVELS), format_func=lambda k: LEVELS[k][0], key=f"f_l{i}",
                                  index=list(LEVELS).index(prev.level) if prev.level else None, placeholder="Chọn mức")
                entries.append(ScoreEntry(subject, "level", level=lv))
    official = False
    if entries and all(e.mode == "exact" for e in entries):
        official = st.checkbox("Đây là điểm thi tốt nghiệp THPT chính thức của em", value=A.scores_official, key="f_official")
    go, _ = nav(skippable=False)
    if go:
        A.scores, A.scores_official = entries, official
        if errors := A.score_problems():
            for e in errors:
                st.error(e)
        else:
            advance()


def step_about() -> None:
    gender = st.radio("Giới tính của em? Một số ít ngành chỉ tuyển nam hoặc nữ, nên mình cần biết để không gợi ý nhầm.",
                      list(GENDERS), format_func=GENDERS.get, horizontal=True, key="f_gender",
                      index=list(GENDERS).index(A.gender) if A.gender else None)
    province = st.selectbox("Em đang sống ở tỉnh/thành nào?", PROVINCES, key="f_province", placeholder="Chọn tỉnh/thành",
                            index=PROVINCES.index(A.province) if A.province else None)
    areas = [*AREAS, "unknown"]
    area = st.radio("Trường THPT của em thuộc khu vực ưu tiên nào?", areas, horizontal=True, key="f_area",
                    format_func=lambda k: AREAS.get(k, "Em không biết"),
                    index=areas.index(A.area) if A.area else None,
                    help="Theo nơi em học THPT, ghi trong hồ sơ đăng ký dự thi.")
    category = st.radio("Em có thuộc diện ưu tiên nào không, ví dụ con thương binh, liệt sĩ, hoặc người dân tộc thiểu số "
                        "ở vùng khó khăn?", list(CATEGORIES), format_func=CATEGORIES.get, key="f_category",
                        index=list(CATEGORIES).index(A.category) if A.category else None)
    grad_opts = ["this_year", "other"]
    grad = st.radio("Em đang học lớp 12 năm nay đúng không?", grad_opts, horizontal=True, key="f_grad",
                    format_func={"this_year": "Đúng", "other": "Không, em đã tốt nghiệp"}.get,
                    index=None if A.graduation_year is None else (0 if A.graduation_year == YEAR else 1))
    year = None
    if grad == "other":
        year = st.number_input("Em tốt nghiệp THPT năm nào?", 2020, YEAR - 1, A.graduation_year if A.graduation_year
                               and A.graduation_year < YEAR else YEAR - 1, key="f_grad_year")
    go, _ = nav(skippable=False)
    if go:
        if gender is None:
            st.error("Em cho mình biết giới tính nhé, để mình không gợi ý ngành chỉ tuyển nam hoặc chỉ tuyển nữ.")
            return
        A.gender, A.province = gender, province
        A.area = None if area in (None, "unknown") else area
        A.category = category
        A.graduation_year = YEAR if grad == "this_year" else year
        advance()


def chosen_list(section: str, codes: list[str], strengths: dict[str, str] | None = None) -> None:
    """The items picked so far, each with a remove button."""
    for code in list(codes):
        a, b = st.columns([6, 1])
        extra = f" · {STRENGTHS[strengths[code]]}" if strengths else ""
        a.markdown(f"- **{P.name(code)}**{extra}")
        if b.button("Bỏ", key=f"f_rm_{section}_{code}", icon=":material/close:"):
            if section == "interests":
                A.interests = [x for x in A.interests if x[0] != code]
            elif section == "dislikes":
                A.dislikes = [c for c in A.dislikes if c != code]
            else:
                A.family_codes = [c for c in A.family_codes if c != code]
            st.rerun()


def pick(section: str, exclude: set[str], with_strength: bool) -> tuple[str, str] | None:
    """The shared picker: a search box with quick picks, then nhóm ngành and ngành dropdowns. Returns (code,
    strength) when "Thêm" is pressed."""
    gkey, mkey, chips = f"f_pg_{section}", f"f_pm_{section}", f"f_chips_{section}"

    def take_chip() -> None:
        code = ss.get(chips)
        if code:
            ss[gkey], ss[mkey] = code[:5], (code if len(code) == 7 else "")
        ss[chips] = None

    query = st.text_input("Gõ tên ngành em nghĩ tới", key=f"f_q_{section}", placeholder="vd: IT, bác sĩ, marketing")
    if query:
        found = [c for c in search(query, P) if c not in exclude]
        if found:
            st.pills("Có phải em muốn tìm:", found, format_func=P.name, key=chips, on_change=take_chip)
        else:
            st.caption("Mình chưa tìm thấy, em chọn trong danh sách bên dưới nhé.")
    groups = [g.code for g in P.groups]
    ss.setdefault(gkey, None)
    g = st.selectbox("Nhóm ngành", groups, key=gkey, placeholder="Chọn hoặc gõ để tìm nhóm ngành",
                     format_func=lambda c: P.group(c).label)
    if g is None:
        return None
    majors = ["", *(m.code for m in P.group(g).majors)]       # "" = the whole group
    if ss.get(mkey) not in majors:
        ss[mkey] = ""
    m = st.selectbox("Ngành (không bắt buộc)", majors, key=mkey,
                     format_func=lambda c: P.name(c) if c else "Tất cả ngành trong nhóm này")
    strength = "like"
    if with_strength:
        strength = st.radio("Mức độ", list(STRENGTHS), format_func=STRENGTHS.get, horizontal=True, key=f"f_st_{section}")
    code = m or g
    if st.button("Thêm", key=f"f_add_{section}", icon=":material/add:"):
        if code in exclude:
            st.warning(f"{P.name(code)} đã có trong danh sách rồi.")
            return None
        return code, strength
    return None


def step_interests() -> None:
    if ss.f_quiz:
        return quiz()
    chosen = [c for c, _ in A.interests]
    chosen_list("interests", chosen, dict(A.interests))
    if len(chosen) < MAX_INTERESTS:
        got = pick("interests", set(chosen) | set(A.dislikes), with_strength=True)
        if got:
            A.interests.append(got)
            st.rerun()
    else:
        st.caption(f"Em đã chọn đủ {MAX_INTERESTS} ngành.")
    if st.button("Em chưa biết mình muốn học gì", key="f_unsure", icon=":material/help:"):
        ss.f_quiz = True
        st.rerun()
    go, skip = nav()
    if skip:
        A.interests = []
    if go or skip:
        advance()


def quiz() -> None:
    """"Em chưa biết": a few optional questions, then suggestions to tick (docs/MODEL.md)."""
    if ss.f_suggestions is not None:
        return confirm_suggestions()
    st.markdown("Không sao, mình hỏi em vài câu nhé. Câu nào không muốn trả lời thì em cứ để trống.")
    qa = ss.f_quiz_ans
    best = sorted(A.scores, key=lambda e: -e.score())[:2]
    subjects = st.multiselect(sg.QUESTIONS["subjects"], list(SUBJECTS), format_func=SUBJECTS.get, key="f_qz_subjects",
                              default=qa.get("subjects", [e.subject for e in best]), max_selections=sg.MAX_SUBJECTS,
                              placeholder="Chọn môn")
    work = st.multiselect(sg.QUESTIONS["work_types"], list(sg.WORK_TYPES), format_func=sg.WORK_TYPES.get,
                          key="f_qz_work", default=qa.get("work_types", []), max_selections=sg.MAX_WORK_TYPES,
                          placeholder="Chọn điều em thích")
    hobbies = st.pills(sg.QUESTIONS["hobbies"], list(sg.HOBBIES), format_func=lambda k: sg.HOBBIES[k][0],
                       selection_mode="multi", key="f_qz_hobbies", default=qa.get("hobbies", []))
    other = st.text_input("Sở thích khác", key="f_qz_other", value=qa.get("other", ""))
    place = st.pills(sg.QUESTIONS["workplace"], list(sg.WORKPLACES), format_func=sg.WORKPLACES.get,
                     selection_mode="multi", key="f_qz_place", default=qa.get("workplace", []))
    dream = st.text_input(sg.QUESTIONS["text"], key="f_qz_dream", value=qa.get("dream", ""))
    c1, c2, _ = st.columns([1.3, 1.3, 2])
    if c1.button("Gợi ý cho em", type="primary", key="f_qz_go", icon=":material/lightbulb:"):
        ss.f_quiz_ans = {"subjects": subjects, "work_types": work, "hobbies": hobbies, "workplace": place,
                         "other": other, "dream": dream}
        answers = {"subjects": subjects, "work_types": work, "hobbies": hobbies, "workplace": place,
                   "text": " ".join(t for t in (dream, other) if t.strip())}
        if not sg.available():
            st.info("Phần gợi ý ngành đang được hoàn thiện. Em chọn trong danh sách giúp mình nhé.")
        elif not (got := sg.suggest(answers, get_db())):
            st.info("Mình chưa đủ thông tin để gợi ý. Em trả lời thêm vài câu, hoặc chọn trong danh sách nhé.")
            if DEBUG:
                ss.t_log.append(log_entry([], {}))
        else:
            ss.f_suggestions = got
            if DEBUG:
                ss.f_sg_debug = sg.explain(answers)
                ss.t_log.append(log_entry(got, ss.f_sg_debug))
            st.rerun()
    if c2.button("Quay lại danh sách", key="f_qz_back", icon=":material/arrow_back:"):
        ss.f_quiz = False
        st.rerun()


def confirm_suggestions() -> None:
    st.markdown("Dựa trên câu trả lời của em, mình nghĩ em có thể hợp với các nhóm ngành sau. Em bỏ chọn ngành không thích nhé.")
    taken = {c for c, _ in A.interests} | set(A.dislikes)
    keep = []
    for s in ss.f_suggestions:
        if s["code"] in taken:
            continue
        reason = ", ".join(s.get("reasons") or [])
        if st.checkbox(f"**{P.name(s['code'])}**" + (f" (vì {reason})" if reason else ""), value=True,
                       key=f"f_sg_{s['code']}", help=f"Gồm các ngành như: {examples(s['code'])}"):
            keep.append(s["code"])
        st.caption(P.group(s["code"]).caption())
    if DEBUG and ss.f_sg_debug:
        scoring_panel(ss.f_sg_debug)
    if st.button("Xác nhận", type="primary", key="f_sg_ok", icon=":material/check:"):
        room = MAX_INTERESTS - len(A.interests)
        A.interests += [(c, "like") for c in keep[:room]]
        if DEBUG and ss.t_log:
            shown = [s["code"] for s in ss.f_suggestions if s["code"] not in taken]
            ss.t_log[-1]["kept"] = keep[:room]
            ss.t_log[-1]["dropped"] = [c for c in shown if c not in keep[:room]]
        ss.f_quiz, ss.f_suggestions, ss.f_sg_debug = False, None, None
        st.rerun()


def examples(code: str, n: int = 3) -> str:
    return P.group(code).examples(n)


# ------------------------------------------------------------------ test mode (?debug=1): scoring and a trial log
SCORING_COLS = {"rank": "#", "code": "Mã", "name": "Nhóm ngành", "p": "Xác suất", "z": "Điểm z", "answers": "Ô đã chọn",
                "text": "Chữ", "bias": "Hệ số b", "alpha_a": "α·môn", "beta_c": "β·RIASEC", "popularity": "Phổ biến",
                "a": "a (môn)", "c": "c (RIASEC)", "shown": "Hiện"}


def scoring_panel(bd: dict) -> None:
    with st.expander("Chấm điểm (bản thử)", expanded=True, icon=":material/analytics:"):
        st.caption(f"z = ô đã chọn + chữ + b + α·a + β·c + phổ biến, xác suất = softmax(z); chỉ chênh lệch giữa các "
                   f"nhóm là có nghĩa. α = {bd['alpha']:.2f}, β = {bd['beta']:.2f}, phổ biến = "
                   f"{bd['popularity']:.1f} × log(chỉ tiêu của nhóm), trừ thêm {bd['unpopular'][1]:g} nếu nhóm có dưới "
                   f"{bd['unpopular'][0]:.1%} tổng chỉ tiêu. Hiện ra: {bd['rule']}.")
        rows = [{**r, "name": P.name(r["code"])} for r in bd["rows"]]
        st.dataframe([{SCORING_COLS[k]: (round(r[k], 3) if isinstance(r[k], float) else r[k]) for k in SCORING_COLS}
                      for r in rows], hide_index=True)
        st.caption("Hồ sơ RIASEC của em: " + ", ".join(f"{t} {v:g}" for t, v in bd["riasec"].items())
                   + f" · Chữ mô hình đọc: \"{bd['text'] or '(trống)'}\"")


def log_entry(suggestions: list[dict], breakdown: dict) -> dict:
    return {"time": datetime.now().strftime("%H:%M:%S"), "scores": [(e.subject, e.score()) for e in A.scores],
            "answers": dict(ss.f_quiz_ans), "suggestions": suggestions, "breakdown": breakdown}


def log_text() -> str:
    lines = [f"UniAdvisor, nhật ký thử gợi ý nhóm ngành ({len(ss.t_log)} lần)", ""]
    for i, e in enumerate(ss.t_log, 1):
        a = e["answers"]
        lines += [f"=== Lần {i} · {e['time']} ===",
                  "Điểm: " + (", ".join(f"{SUBJECTS[s]} {v:g}" for s, v in e["scores"]) or "(chưa có)"),
                  "Môn thích/học tốt: " + (", ".join(SUBJECTS.get(s, s) for s in a.get("subjects") or []) or "-"),
                  "Thích làm việc với: " + ("; ".join(sg.WORK_TYPES[t] for t in a.get("work_types") or []) or "-"),
                  "Lúc rảnh: " + ("; ".join(sg.HOBBIES[h][0] for h in a.get("hobbies") or []) or "-"),
                  "Sở thích khác: " + (a.get("other") or "-"),
                  "Muốn làm việc ở: " + ("; ".join(sg.WORKPLACES[w] for w in a.get("workplace") or []) or "-"),
                  "Mơ ước: " + (a.get("dream") or "-")]
        bd = e["breakdown"]
        if not e["suggestions"]:
            lines += ["Kết quả: không đủ thông tin để gợi ý.", ""]
            continue
        lines += [f"Chữ mô hình đọc: \"{bd['text']}\"",
                  "Hồ sơ RIASEC: " + ", ".join(f"{t} {v:g}" for t, v in bd["riasec"].items()),
                  f"Chấm điểm (z = ô đã chọn + chữ + b + α·a + β·c; α = {bd['alpha']:.2f}, β = {bd['beta']:.2f}):"]
        for r in bd["rows"]:
            lines.append(f"  {r['rank']:>2}. {r['code']} {P.name(r['code'])}: p = {r['p']:.3f}, z = {r['z']:.2f} "
                         f"(ô {r['answers']:+.2f}, chữ {r['text']:+.2f}, b {r['bias']:+.2f}, α·a {r['alpha_a']:+.2f}, "
                         f"β·c {r['beta_c']:+.2f}){'  <- hiện' if r['shown'] else ''}")
        lines.append("Gợi ý hiện ra:")
        lines += [f"  - {s['code']} {P.name(s['code'])} ({s['score']:.3f}): {', '.join(s['reasons'])}"
                  for s in e["suggestions"]]
        if "kept" in e:
            lines.append("Em giữ: " + (", ".join(f"{c} {P.name(c)}" for c in e["kept"]) or "(không giữ nhóm nào)"))
            lines.append("Em bỏ: " + (", ".join(f"{c} {P.name(c)}" for c in e["dropped"]) or "(không bỏ nhóm nào)"))
        else:
            lines.append("(chưa bấm Xác nhận)")
        lines.append("")
    return "\n".join(lines)


def step_dislikes() -> None:
    chosen_list("dislikes", A.dislikes)
    got = pick("dislikes", set(A.dislikes) | {c for c, _ in A.interests}, with_strength=False)
    if got:
        A.dislikes.append(got[0])
        st.rerun()
    go, skip = nav()
    if skip:
        A.dislikes = []
    if go or skip:
        advance()


def step_family() -> None:
    chosen_list("family", A.family_codes)
    got = pick("family", set(A.family_codes), with_strength=False)
    if got:
        A.family_codes.append(got[0])
        st.rerun()
    agree = None
    if A.family_codes:
        opts = list(AGREES)
        agree = st.radio("Em có đồng ý với mong muốn này không?", opts, format_func=AGREES.get, horizontal=True,
                         key="f_agree", index=opts.index(A.family_agrees))
    go, skip = nav()
    if skip:
        A.family_codes, A.family_agrees = [], None
    elif go:
        A.family_agrees = agree
    if go or skip:
        advance()


def step_budget() -> None:
    opts = ["amount", "no_limit", "unknown"]
    labels = {"amount": "Khoảng một mức", "no_limit": "Gia đình không lo về học phí", "unknown": "Em chưa rõ"}
    kind = st.radio("Gia đình em có thể lo:", opts, format_func=labels.get, key="f_bkind",
                    index=opts.index(A.budget_kind) if A.budget_kind else None)
    amount, strict = None, False
    if kind == "amount":
        amount = st.number_input("Triệu đồng mỗi năm", 1.0, 1000.0, A.budget_million or 30.0, 5.0, format="%.0f",
                                 key="f_bamount")
        strict = st.checkbox("Đây là mức tối đa, không thể vượt", value=A.budget_strict, key="f_bstrict")
    go, skip = nav()
    if skip or (go and kind in (None, "unknown")):
        A.budget_kind, A.budget_million, A.budget_strict = None, None, False
    elif go:
        A.budget_kind, A.budget_million, A.budget_strict = kind, amount, strict
    if go or skip:
        advance()


def step_location() -> None:
    near = NEAREST_CITY.get(A.province or "")
    opts = list(P.cities) + ([NEAR_HOME] if near in P.cities else []) + [ANYWHERE]
    labels = {NEAR_HOME: f"Gần nhà em nhất ({near})", ANYWHERE: "Ở đâu cũng được"}
    where = st.radio("Thành phố", opts, format_func=lambda k: labels.get(k, k), key="f_loc",
                     index=opts.index(A.location) if A.location in opts else None)
    main = st.checkbox("Em chỉ muốn học ở cơ sở chính, không học phân hiệu", value=A.main_campus_only, key="f_main")
    go, skip = nav()
    if skip:
        A.location, A.main_campus_only = None, False
    elif go:
        A.location, A.main_campus_only = where, main
    if go or skip:
        advance()


def step_plan() -> None:
    risk = st.radio("Khi đặt nguyện vọng, em nghiêng về hướng nào hơn?", list(RISKS), format_func=RISKS.get,
                    key="f_risk", index=list(RISKS).index(A.risk) if A.risk else None)
    st.markdown("Điều gì quan trọng nhất với em khi chọn trường? (chọn tối đa 3, theo thứ tự)")
    st.caption("Mình chưa có số liệu việc làm và thu nhập của từng ngành, nên ưu tiên này chỉ dùng để sắp xếp.")
    picked: list[str] = []
    for i, title in enumerate(["Quan trọng nhất", "Thứ hai", "Thứ ba"][:MAX_PRIORITIES]):
        left = [k for k in PRIORITIES if k not in picked]
        prev = A.priorities[i] if i < len(A.priorities) and A.priorities[i] in left else None
        x = st.selectbox(title, left, format_func=PRIORITIES.get, key=f"f_pri{i}", placeholder="Không chọn",
                         index=left.index(prev) if prev else None)
        if x is None:
            break
        picked.append(x)
    go, skip = nav()
    if skip:
        A.risk, A.priorities = None, []
    elif go:
        A.risk, A.priorities = risk, picked
    if go or skip:
        advance()


def step_summary() -> None:
    doc, notices = build(A, P, year=YEAR)
    for key, line in summary(doc, P).items():
        a, b = st.columns([6, 1])
        a.markdown(f"**{SECTIONS[key]}:** {line}")
        if b.button("Sửa", key=f"f_edit_{key}", icon=":material/edit:"):
            ss.f_step, ss.f_editing = STEPS.index(key), True
            st.rerun()
    for n in notices:
        st.info(n, icon=":material/info:")
    if st.button("Đúng rồi", type="primary", key="f_finish", icon=":material/check:"):
        ss.f_finished = True
    if ss.f_finished:
        st.success("Cảm ơn em! Phần lập danh sách nguyện vọng đang được nối với phần này.")
    if st.query_params.get("debug") == "1":
        with st.expander("JSON gửi module 3 (chỉ để kiểm tra)"):
            st.json(doc)
            st.write(problems(doc, P) or "Hợp lệ.")


RENDER = {"scores": step_scores, "about": step_about, "interests": step_interests, "dislikes": step_dislikes,
          "family": step_family, "budget": step_budget, "location": step_location, "plan": step_plan,
          "summary": step_summary}


# ------------------------------------------------------------------ page
with st.sidebar:
    st.button("Bắt đầu lại", icon=":material/restart_alt:", on_click=reset, key="f_reset")
    if DEBUG:
        st.caption(f"Bản thử: {len(ss.t_log)} lần gợi ý trong nhật ký (giữ qua \"Bắt đầu lại\").")
        if ss.t_log:
            st.download_button("Tải nhật ký (.txt)", log_text(), file_name="goi_y_nhom_nganh_log.txt",
                               mime="text/plain", icon=":material/download:", key="t_log_dl")
    if get_db().simulated:
        st.warning("Đang dùng dữ liệu MÔ PHỎNG.")
st.title("Hỏi đáp cùng UniAdvisor")
st.caption("Mình hỏi em vài câu để hiểu em muốn gì. Câu nào không biết, em cứ bỏ qua. Mình không lưu lại gì em nhập.")

current = STEPS[ss.f_step]
if not ss.f_editing:
    for key in STEPS[:ss.f_step]:
        if key in ss.f_done:
            st.chat_message("assistant").markdown(QUESTIONS[key])
            st.chat_message("user").markdown(reply(key) or "(bỏ qua)")
with st.chat_message("assistant"):
    st.markdown(QUESTIONS[current])
    RENDER[current]()
