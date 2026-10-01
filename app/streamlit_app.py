"""UniAdvisor - Vietnamese chat UI.   streamlit run app/streamlit_app.py

Flow: consent -> scores & priority form -> free-text sharing -> clarifying questions (only when the
model is unsure) -> ordered list with probabilities, comparison and explanations. Nothing is written
to disk; everything lives in this browser session.
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from uniadvisor.advisor import Advice, advise
from uniadvisor.compare import BASE_WEIGHTS, CRITERIA
from uniadvisor.db import get_db
from uniadvisor.explain import DISCLAIMER
from uniadvisor.kb.rules import BUCKET_VI, load_rules
from uniadvisor.slm.infer import get_judge
from uniadvisor.slm.questions import BY_ID
from uniadvisor.slm.state import SUBJECT_VI, StudentProfile
from uniadvisor.slm.synth import CENTRAL, NORTH, SOUTH

st.set_page_config(page_title="UniAdvisor – Tư vấn nguyện vọng", page_icon=":material/school:", layout="wide")

ELECTIVES = ["LI", "HO", "SI", "SU", "DI", "TI", "GDKTPL", "CNCN", "CNNN"]
LANGS = {"N1": "Tiếng Anh", "N3": "Tiếng Pháp", "N4": "Tiếng Trung", "N6": "Tiếng Nhật", "N7": "Tiếng Hàn", "N5": "Tiếng Đức", "N2": "Tiếng Nga"}
EXAMPLES = {
    ":material/computer: Thích CNTT, ngân sách hạn chế": "Em muốn học Công nghệ thông tin, sau này làm kỹ sư phần mềm. Nhà em chỉ lo được khoảng 25 triệu một năm. Em muốn học ở Hà Nội và cần chắc chắn đỗ.",
    ":material/medical_services: Muốn học Y, sợ xa nhà": "Em muốn học Y để làm bác sĩ. Em không muốn học xa nhà. Gia đình không lo về học phí. Em sẵn sàng thử sức với trường top.",
    ":material/campaign: Thích truyền thông, tiếng Anh tốt": "Em làm kênh TikTok riêng và thích viết bài, muốn làm content creator. Tiếng Anh của em khá tốt. Em muốn vào Sài Gòn học. Quan trọng nhất là học đúng ngành mình thích.",
}


# ------------------------------------------------------------------ cached resources
@st.cache_resource(show_spinner="Đang tải dữ liệu và mô hình…")
def warm_up() -> str:
    db = get_db()
    db.catalog, db.history, db.distributions  # noqa: B018 - build the cached views once
    return get_judge().name


@st.cache_data(max_entries=30, show_spinner=False)
def run_advice(profile_json: str, weights_json: str, k: int) -> Advice:
    profile = StudentProfile(**json.loads(profile_json))
    weights = json.loads(weights_json) or None
    return advise(profile, k_max=k, weights_override=weights)


# ------------------------------------------------------------------ state
ss = st.session_state
ss.setdefault("stage", "consent")          # consent -> scores -> story -> results
ss.setdefault("messages", [])              # chat transcript: {"role", "content"}
ss.setdefault("profile", None)             # dict for StudentProfile
ss.setdefault("weights", {})
ss.setdefault("k", 10)


def say(role: str, content: str) -> None:
    ss.messages.append({"role": role, "content": content})


def reset() -> None:
    for key in ("stage", "messages", "profile", "weights"):
        ss.pop(key, None)


judge_name = warm_up()
rules = load_rules()

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header(":material/school: UniAdvisor")
    st.caption("Tư vấn đặt nguyện vọng đại học bằng điểm thi tốt nghiệp THPT.")
    db = get_db()
    prog = db.catalog
    if db.simulated:
        st.warning(f"Dữ liệu MÔ PHỎNG ({db.name}), không phải dữ liệu thật: chỉ dùng để thử nghiệm.", icon=":material/science:")
    st.markdown(f"**Phạm vi dữ liệu:** {prog.school_code.nunique()} trường, {len(prog)} ngành ở Hà Nội và TP.HCM · "
                f"quy chế `{rules['ruleset']}` ({'dự thảo' if rules.get('status') == 'draft' else 'chính thức'})")
    st.markdown(f"**Mô hình đánh giá mềm:** {'SLM đã tinh chỉnh + luật' if judge_name == 'hybrid' else 'luật từ khóa (chưa có SLM)'}")
    if ss.stage == "results":
        st.divider()
        st.subheader("Tùy chỉnh")
        ss.k = st.slider("Số nguyện vọng", 3, int(rules["application"]["max_choices"]), ss.k)
        with st.expander("Trọng số tiêu chí", icon=":material/tune:"):
            st.caption("Mặc định được suy ra từ điều em coi trọng nhất.")
            custom = {c: st.slider(label, 0.0, 1.0, float(ss.weights.get(c, BASE_WEIGHTS[c])), 0.05, key=f"w_{c}") for c, label in CRITERIA.items()}
            if st.button("Áp dụng trọng số", icon=":material/check:"):
                ss.weights = custom
                st.rerun()
    st.divider()
    st.button("Bắt đầu lại", icon=":material/restart_alt:", on_click=reset)

st.title("Tư vấn nguyện vọng xét tuyển đại học")

for m in ss.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ------------------------------------------------------------------ stage: consent
if ss.stage == "consent":
    with st.chat_message("assistant"):
        st.markdown(
            "Chào em! Mình sẽ giúp em lập **danh sách nguyện vọng** xét bằng **điểm thi tốt nghiệp THPT**: "
            "ước tính khả năng đỗ từng ngành, so sánh các lựa chọn và giải thích lý do.\n\n"
            "- Mình **không lưu** thông tin của em: mọi thứ chỉ nằm trong phiên làm việc này và mất khi em đóng trang.\n"
            "- Thông tin em chia sẻ chỉ dùng để tư vấn (Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân).")
        st.info(DISCLAIMER, icon=":material/info:")
        agree = st.checkbox("Em đồng ý để ứng dụng xử lý thông tin em nhập trong phiên này.")
        if st.button("Bắt đầu", type="primary", disabled=not agree, icon=":material/arrow_forward:"):
            say("assistant", "Cảm ơn em. Trước hết, cho mình biết điểm các môn thi của em nhé.")
            ss.stage = "scores"
            st.rerun()

# ------------------------------------------------------------------ stage: scores form
elif ss.stage == "scores":
    with st.chat_message("assistant"):
        with st.form("scores"):
            kind = st.segmented_control("Loại điểm", ["Điểm thi thật", "Điểm thi thử / dự kiến"], default="Điểm thi thật")
            c1, c2 = st.columns(2)
            to = c1.number_input("Toán", 0.0, 10.0, value=None, step=0.25, placeholder="vd 8.25")
            va = c2.number_input("Ngữ văn", 0.0, 10.0, value=None, step=0.25, placeholder="vd 7.5")
            electives = st.multiselect("Hai môn tự chọn em thi", ELECTIVES + ["N1"], max_selections=2,
                                       format_func=lambda s: "Ngoại ngữ" if s == "N1" else SUBJECT_VI.get(s, s))
            lang = st.selectbox("Ngoại ngữ (nếu có thi)", list(LANGS), format_func=LANGS.get)
            e1, e2 = st.columns(2)
            s1 = e1.number_input("Điểm môn tự chọn 1", 0.0, 10.0, value=None, step=0.25)
            s2 = e2.number_input("Điểm môn tự chọn 2", 0.0, 10.0, value=None, step=0.25)
            st.divider()
            p1, p2 = st.columns(2)
            province = p1.selectbox("Tỉnh/thành nơi em ở", sorted(NORTH + CENTRAL + SOUTH), index=None, placeholder="Chọn tỉnh")
            gender = p2.segmented_control("Giới tính (không bắt buộc)", ["nam", "nu"], format_func={"nam": "Nam", "nu": "Nữ"}.get)
            area = st.segmented_control("Khu vực ưu tiên", ["KV1", "KV2-NT", "KV2", "KV3"], default="KV3",
                                        help="Theo nơi em học THPT. Xem Quy chế tuyển sinh nếu chưa rõ.")
            category = st.selectbox("Đối tượng ưu tiên", ["none", "UT1", "UT2"],
                                    format_func={"none": "Không thuộc đối tượng ưu tiên", "UT1": "Nhóm UT1 (đối tượng 01-04)", "UT2": "Nhóm UT2 (đối tượng 05-07)"}.get)
            ok = st.form_submit_button("Tiếp tục", type="primary", icon=":material/arrow_forward:")
        if ok:
            if to is None or va is None or len(electives) != 2 or s1 is None or s2 is None:
                st.error("Em nhập đủ điểm Toán, Văn và hai môn tự chọn nhé.")
            else:
                scores = {"TO": to, "VA": va}
                for code, val in zip(electives, (s1, s2)):
                    scores[lang if code == "N1" else code] = val
                ss.profile = StudentProfile(scores=scores, province=province, area=area or "KV3", category=category, gender=gender,
                                            score_kind="mock" if kind and "thử" in kind else "actual").to_dict()
                shown = ", ".join(f"{SUBJECT_VI.get(k, k)} {v:g}" for k, v in scores.items())
                say("user", f"Điểm của em: {shown}. {province or ''} · {area}.")
                say("assistant", "Giờ em kể cho mình nghe: em **thích** gì, muốn làm **nghề** gì, gia đình lo được **học phí** "
                                 "khoảng bao nhiêu, muốn học **ở đâu**, và em muốn **chắc chắn đỗ** hay sẵn sàng **thử sức**? "
                                 "Viết tự nhiên như nói chuyện là được.")
                ss.stage = "story"
                st.rerun()

# ------------------------------------------------------------------ stage: free text
elif ss.stage == "story":
    picked = st.pills("Ví dụ", list(EXAMPLES), label_visibility="collapsed")
    text = st.chat_input("Kể về sở thích, mong muốn của em…")
    if picked and not text:
        text = EXAMPLES[picked]
    if text:
        ss.profile["free_text"] = text
        say("user", text)
        ss.stage = "results"
        st.rerun()

# ------------------------------------------------------------------ stage: results (+ follow-up chat)
elif ss.stage == "results":
    profile = ss.profile
    with st.spinner("Đang tính khả năng đỗ và sắp xếp nguyện vọng…"):
        a = run_advice(json.dumps(profile, ensure_ascii=False, sort_keys=True), json.dumps(ss.weights, sort_keys=True), ss.k)

    with st.chat_message("assistant"):
        if a.clarify:
            with st.container(border=True):
                st.markdown(":material/help: **Mình chưa chắc về một vài điều. Em trả lời giúp để danh sách sát hơn nhé:**")
                for q in a.clarify:
                    choice = st.segmented_control(q["ask"], list(q["options"]), format_func=q["options"].get, key=f"clarify_{q['question_id']}")
                    if choice:
                        profile.setdefault("answers", {})[q["question_id"]] = choice
                        say("user", f"{q['ask']} → {q['options'][choice]}")
                        st.rerun()
        if not a.chosen:
            st.warning(a.summary)
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Số nguyện vọng", len(a.chosen))
            m2.metric("Đỗ ít nhất 1 NV", f"{100 * a.p_any:.0f}%")
            buckets = [b for b in ("safe", "match", "reach", "unlikely") if b != "unlikely" or any(c["bucket"] == b for c in a.chosen)]
            m3.metric(" / ".join(BUCKET_VI[b] for b in buckets),
                      " / ".join(str(sum(c["bucket"] == b for c in a.chosen)) for b in buckets))
            m4.metric("Ngành đủ điều kiện xét", a.n_eligible)
            st.markdown(a.summary)
            for n in a.notes:
                st.caption(f":material/info: {n}")
            pj = a.profile_answers
            st.caption("Mình hiểu là: " + "; ".join(
                f"{BY_ID[q].text_vi.split('?')[0].lower()}: **{dict(zip(BY_ID[q].labels, BY_ID[q].labels_vi)).get(x.label, 'chưa rõ')}**"
                + (" (em đã trả lời)" if x.source == "student" else f" (độ tin cậy {x.confidence:.0%})") for q, x in pj.items()))

            tab_list, tab_compare, tab_alt = st.tabs([":material/format_list_numbered: Danh sách", ":material/compare_arrows: So sánh", ":material/alt_route: Lựa chọn khác"])
            with tab_list:
                df = a.table()
                st.dataframe(
                    df[["NV", "Trường", "Ngành", "Tổ hợp", "Điểm xét", "Dự báo điểm chuẩn", "P(đỗ)", "Nhóm", "Độ tin cậy"]],
                    hide_index=True,
                    column_config={"P(đỗ)": st.column_config.ProgressColumn("P(đỗ)", min_value=0, max_value=1, format="percent"),
                                   "Dự báo điểm chuẩn": st.column_config.NumberColumn(format="%.2f")})
                for i, ev in enumerate(a.chosen, 1):
                    p = ev["program"]
                    with st.expander(f"NV{i} · {p['program_name']} – {p['school_code']} · {BUCKET_VI[ev['bucket']]} {100 * ev['p_admit']:.0f}%"):
                        st.markdown(ev["explanation"])
                        st.caption(f"Độ tin cậy: **{ev['confidence']}**" + (" – " + "; ".join(ev["confidence_reasons"]) if ev["confidence_reasons"] else ""))
                        fc = ev["forecast"]
                        hist = pd.DataFrame({"Năm": [str(y) for y in fc.years] + [str(fc.target_year)],
                                             "Điểm chuẩn": fc.past_scores + [fc.score],
                                             "Loại": ["thực tế"] * len(fc.years) + ["dự báo"]})
                        st.bar_chart(hist, x="Năm", y="Điểm chuẩn", color="Loại", height=180)
                        soft = {BY_ID[q].text_vi: f"{dict(zip(BY_ID[q].all_labels, (*BY_ID[q].labels_vi, 'chưa đủ thông tin'))).get(x.label, x.label)} "
                                                  f"({x.confidence:.0%}{', cần xác nhận' if x.escalate else ''})" for q, x in ev["answers"].items()}
                        st.table(pd.Series(soft, name="Nhận định"))
                        if p.get("source_url"):
                            st.caption(f"Nguồn điểm chuẩn: {p['source_url']}")
                st.download_button("Tải danh sách (CSV)", df.to_csv(index=False).encode("utf-8-sig"), "nguyen_vong.csv", "text/csv",
                                   icon=":material/download:")
            with tab_compare:
                st.caption("Điểm từng tiêu chí từ 0 (kém) đến 1 (tốt). Trọng số hiện tại: "
                           + ", ".join(f"{CRITERIA[k]} {v:.0%}" for k, v in a.weights.items()))
                comp = a.table()[["NV", "Ngành", "P(đỗ)", *CRITERIA.values(), "Độ phù hợp (u)"]]
                st.dataframe(comp, hide_index=True, column_config={
                    **{c: st.column_config.ProgressColumn(c, min_value=0, max_value=1, format="%.2f") for c in [*CRITERIA.values(), "Độ phù hợp (u)"]},
                    "P(đỗ)": st.column_config.NumberColumn(format="percent")})
                for i, ev in enumerate(a.chosen, 1):
                    if ev["wins"] or ev["losses"]:
                        st.markdown(f"**NV{i}** – mạnh: {', '.join(ev['wins']) or '–'} · yếu: {', '.join(ev['losses']) or '–'}")
            with tab_alt:
                if a.alternatives:
                    st.dataframe(a.table(a.alternatives)[["Trường", "Ngành", "Dự báo điểm chuẩn", "P(đỗ)", "Nhóm", "Độ phù hợp (u)"]], hide_index=True,
                                 column_config={"P(đỗ)": st.column_config.ProgressColumn("P(đỗ)", min_value=0, max_value=1, format="percent")})
                else:
                    st.caption("Không có lựa chọn khác trong phạm vi dữ liệu.")
        st.info(DISCLAIMER, icon=":material/info:")

    more = st.chat_input("Muốn bổ sung hay đổi ý? (vd: em muốn học ở TP.HCM hơn)")
    if more:
        profile["free_text"] = (profile.get("free_text", "") + " " + more).strip()
        say("user", more)
        st.rerun()
