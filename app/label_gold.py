"""Gold-label tool for the SLM test set.   uniadvisor label   (or: streamlit run app/label_gold.py)

Shows one row of data/slm/gold_to_label.csv at a time with the question's rubric and the answer
options as buttons. Every click is saved to data/slm/gold_labeled.csv at once, so the tool can be
closed and reopened at any point. No model or teacher answer is shown: the labels must be your own.
"""

from __future__ import annotations

import streamlit as st

from uniadvisor.slm import gold
from uniadvisor.slm.questions import BY_ID, INSUFFICIENT

st.set_page_config(page_title="UniAdvisor – Gán nhãn", page_icon=":material/label:", layout="wide")
ss = st.session_state

if "df" not in ss:
    ss.df = gold.load()
    ss.cur = None
df = ss.df


def label_vi(qid: str, label: str) -> str:
    q = BY_ID[qid]
    return "Không đủ thông tin" if label == INSUFFICIENT else dict(zip(q.labels, q.labels_vi)).get(label, label)


def is_done(i: int) -> bool:
    return df.at[i, "human_label"].strip() != ""


def next_open(order: list[int], after: int | None, default: int | None = None) -> int | None:
    """First unlabelled row after `after` in `order`, wrapping around; None when all are done."""
    start = order.index(after) + 1 if after in order else 0
    for i in order[start:] + order[:start]:
        if not is_done(i):
            return i
    return default


def set_label(i: int, label: str, order: list[int]) -> None:
    df.at[i, "human_label"] = label
    df.at[i, "labeller"] = ss.labeller.strip()
    df.at[i, "note"] = ss.get(f"note_{df.at[i, 'id']}", "").strip()
    gold.save(df)
    ss.cur = next_open(order, i, default=i)


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("### :material/label: Gán nhãn gold")
    st.text_input("Tên người gán nhãn", key="labeller", placeholder="vd: quan")
    questions = sorted(df.question.unique())
    pick = st.selectbox("Câu hỏi", ["all", *questions], format_func=lambda q: "Tất cả" if q == "all" else q)
    prog = gold.progress(df)
    done, total = int(prog.done.sum()), int(prog.total.sum())
    st.progress(done / total if total else 0.0, text=f"Đã gán {done}/{total}")
    st.dataframe(prog.rename(columns={"done": "Đã gán", "total": "Tổng"}), use_container_width=True)
    st.caption(f"Lưu tự động vào `{gold.LABELED.relative_to(gold.SLM_DATA.parent.parent)}`")
    st.download_button("Tải file đã gán nhãn", gold.LABELED.read_bytes() if gold.LABELED.exists() else b"",
                       "gold_labeled.csv", "text/csv", disabled=not gold.LABELED.exists(), icon=":material/download:")

    missing = gold.unmatched_ids(df)
    if missing is None:
        st.info("Chưa có data/slm/test.jsonl. Chạy `uniadvisor slm-data` trước khi đánh giá bằng file này.")
    elif missing:
        st.warning(f"{missing} dòng không khớp với data/slm/test.jsonl. Dữ liệu SLM đã cũ: chạy `uniadvisor slm-data`.")

order = [i for i in df.index if pick == "all" or df.at[i, "question"] == pick]
if ss.cur not in order:
    ss.cur = next_open(order, None)
    if ss.cur is None:
        ss.cur = order[0] if order else None

# ------------------------------------------------------------------ main
if ss.cur is None:
    st.info("Không có dòng nào.")
    st.stop()

i = ss.cur
row = df.loc[i]
q = BY_ID[row.question]
pos = order.index(i)

nav = st.columns([1, 1, 1, 3])
if nav[0].button("Trước", icon=":material/arrow_back:", disabled=pos == 0, use_container_width=True):
    ss.cur = order[pos - 1]
    st.rerun()
if nav[1].button("Tiếp", icon=":material/arrow_forward:", disabled=pos == len(order) - 1, use_container_width=True):
    ss.cur = order[pos + 1]
    st.rerun()
if nav[2].button("Câu chưa gán", icon=":material/skip_next:", use_container_width=True):
    ss.cur = next_open(order, i, default=i)
    st.rerun()
nav[3].markdown(f"Dòng **{pos + 1}/{len(order)}** · `{row.question}` · id `{row.id}`")

if all(is_done(j) for j in order):
    st.success("Đã gán nhãn xong phần này. Chạy `uniadvisor slm-eval --judge hybrid --gold data/slm/gold_labeled.csv`.")

st.subheader(q.text_vi)
with st.expander("Hướng dẫn chấm (rubric)", expanded=True, icon=":material/rule:"):
    st.markdown(q.rubric.replace("\n", "  \n"))

profile = row.text_a.split("Hồ sơ:", 1)[-1].strip()
facts, _, shared = profile.partition("Học sinh chia sẻ:")
left, right = st.columns(2)
with left:
    st.markdown("**Hồ sơ học sinh**")
    st.markdown(facts.strip())
    if shared.strip():
        st.markdown("**Học sinh chia sẻ**")
        st.info(shared.strip())
with right:
    st.markdown("**Ngành**" if q.scope == "program" else "**Phạm vi**")
    st.markdown(row.text_b)

st.divider()
if row.human_label:
    st.markdown(f"Nhãn hiện tại: **{label_vi(row.question, row.human_label)}** (`{row.human_label}`)"
                + (f" · {row.labeller}" if row.labeller else ""))
st.text_input("Ghi chú (không bắt buộc)", key=f"note_{row.id}", value=row.note)
if not ss.get("labeller", "").strip():
    st.warning("Nhập tên người gán nhãn ở thanh bên trái trước khi chọn nhãn.")
cols = st.columns(len(q.all_labels))
for col, lab in zip(cols, q.all_labels):
    col.button(label_vi(row.question, lab), key=f"btn_{row.id}_{lab}", use_container_width=True,
               type="primary" if lab == row.human_label else "secondary",
               disabled=not ss.get("labeller", "").strip(), on_click=set_label, args=(i, lab, order))
