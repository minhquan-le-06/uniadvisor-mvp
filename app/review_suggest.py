"""Review tool for the group suggester.   uniadvisor suggest-review   (or: streamlit run app/review_suggest.py)

Shows one case of backend/suggest_data/review_cases.jsonl at a time with the current model's top 5. The reviewer
unticks the groups that do not fit, adds the ones that should be there, and saves; every save goes to
backend/suggest_data/expectations.jsonl at once (uniadvisor.student.suggest.review), so the tool can be closed and
reopened at any point. The cases are generated answer sets, not real students.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

import streamlit as st

from uniadvisor.student import suggest as sg
from uniadvisor.student.form import picker
from uniadvisor.student.suggest import review as R
from unidata.db import get_db

st.set_page_config(page_title="UniAdvisor – Duyệt gợi ý", page_icon=":material/fact_check:", layout="wide")
ss = st.session_state
P = picker(get_db())
KIND_VI = {"clear": "rõ một hướng", "mixed": "pha hai hướng", "sparse": "trả lời ít", "text": "có câu chữ", "user": "ca của người thử"}

if not sg.available():
    st.error("Chưa có mô hình (artifacts/models/suggester/). Chạy `uniadvisor suggest-train` trước.")
    st.stop()
cases = R.read(R.CASES)
if not cases:
    st.error("Chưa có ca nào. Chạy `uniadvisor suggest-cases` trước.")
    st.stop()
verdicts = {v["id"]: v for v in R.read(R.EXPECTATIONS)}
ids = [c["id"] for c in cases]
if "cur" not in ss:
    ss.cur = next((i for i, c in enumerate(cases) if c["id"] not in verdicts), 0)


def examples(code: str, n: int = 3) -> str:
    majors = P.group(code).majors
    return ", ".join(m.name for m in majors[:n]) + (f" và {len(majors) - n} ngành khác" if len(majors) > n else "")


def go(i: int) -> None:
    ss.cur = max(0, min(len(cases) - 1, i))


def next_open() -> None:
    later = [i for i in range(ss.cur + 1, len(cases)) if cases[i]["id"] not in verdicts]
    go(later[0] if later else ss.cur + 1)


def verdicts_csv() -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["id", "loai", "tra_loi", "mo_hinh_top5", "giu", "bo", "them", "can_trong_top", "ghi_chu"])
    for v in sorted(verdicts.values(), key=lambda v: v["id"]):
        w.writerow([v["id"], v.get("kind", ""), " | ".join(f"{q}: {a}" for q, a in R.describe(v["answers"])),
                    "; ".join(f"{c} {P.name(c)}" for c in v.get("model_top5", [])),
                    "; ".join(P.name(c) for c in v.get("kept", [])), "; ".join(P.name(c) for c in v.get("dropped", [])),
                    "; ".join(P.name(c) for c in v.get("added", [])), v.get("k", 5), v.get("note", "")])
    return "﻿" + out.getvalue()


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    done = sum(i in verdicts for i in ids)
    st.progress(done / len(ids), text=f"Đã duyệt {done}/{len(ids)} ca")
    pick = st.selectbox("Đến ca", ids, index=ss.cur,
                        format_func=lambda i: f"{i} {'✓' if i in verdicts else '·'} ({KIND_VI.get(next(c['kind'] for c in cases if c['id'] == i), '')})")
    if pick != ids[ss.cur]:
        go(ids.index(pick))
        st.rerun()
    if verdicts:
        st.download_button("Tải kết quả duyệt (.csv)", verdicts_csv(), file_name="duyet_goi_y.csv", mime="text/csv",
                           icon=":material/download:")
    st.caption("Mỗi lần lưu được ghi ngay vào backend/suggest_data/expectations.jsonl.")

# ------------------------------------------------------------------ case
case = cases[ss.cur]
cid, a = case["id"], case["answers"]
old = verdicts.get(cid, {})
st.title(f"Ca {cid}")
st.caption(f"Loại: {KIND_VI.get(case['kind'], case['kind'])}" + (" · đã duyệt" if old else ""))

left, right = st.columns([2, 3], gap="large")
with left:
    st.subheader("Học sinh trả lời")
    for q, ans in R.describe(a):
        st.markdown(f"**{q}:** {ans}")

bd = sg.explain(a, top=5)
reasons = {s["code"]: s["reasons"] for s in sg.suggest(a)}
top5 = [r["code"] for r in bd["rows"]]
with right:
    st.subheader("Mô hình gợi ý (top 5)")
    st.caption("Bỏ chọn nhóm KHÔNG hợp với học sinh này. Học sinh thấy cả 5 nhóm.")
    kept, dropped = [], []
    for r in bd["rows"]:
        code = r["code"]
        default = code not in old.get("dropped", [])
        why = ", ".join(reasons.get(code, [])) or "-"
        label = f"**{r['rank']}. {P.name(code)}** · {r['p']:.0%}"
        if st.checkbox(label, value=default, key=f"{cid}_{code}", help=f"vì: {why}"):
            kept.append(code)
        else:
            dropped.append(code)
        st.caption(f"Ví dụ: {examples(code)} · vì: {why}")
    others = [g.code for g in P.groups if g.code not in top5]
    added = st.multiselect("Nhóm lẽ ra phải có (nếu thiếu)", others, default=[c for c in old.get("added", []) if c in others],
                           format_func=lambda c: f"{P.name(c)} · {P.group(c).field_name}", key=f"{cid}_added",
                           placeholder="Gõ để tìm nhóm ngành")
    k = 5
    if added:
        k = st.radio("Nhóm thêm vào cần nằm trong", [3, 5], index=[3, 5].index(old.get("k", 5)), horizontal=True,
                     format_func=lambda x: f"top {x}", key=f"{cid}_k")
    note = st.text_input("Ghi chú (không bắt buộc)", value=old.get("note", ""), key=f"{cid}_note")

c1, c2, c3, _ = st.columns([1.2, 1, 1, 3])
if c1.button("Lưu & ca tiếp", type="primary", icon=":material/check:"):
    v = {"id": cid, "kind": case["kind"], "answers": a, "kept": kept, "dropped": dropped, "added": added, "k": k,
         "note": note.strip(), "model_top5": top5, "reviewed_at": datetime.now().isoformat(timespec="seconds")}
    R.save_verdict(v)
    verdicts[cid] = v
    next_open()
    st.rerun()
if c2.button("Ca trước", icon=":material/arrow_back:"):
    go(ss.cur - 1)
    st.rerun()
if c3.button("Bỏ qua", icon=":material/skip_next:"):
    go(ss.cur + 1)
    st.rerun()

with st.expander("Chấm điểm chi tiết", icon=":material/analytics:"):
    st.caption(f"z = ô đã chọn + chữ + b + α·a + β·c (α = {bd['alpha']:.2f}, β = {bd['beta']:.2f}); xác suất = softmax(z).")
    st.dataframe([{"#": r["rank"], "Nhóm": P.name(r["code"]), "Xác suất": round(r["p"], 3), "z": round(r["z"], 2),
                   "Ô đã chọn": round(r["answers"], 2), "Chữ": round(r["text"], 2), "b": round(r["bias"], 2),
                   "α·môn": round(r["alpha_a"], 2), "β·RIASEC": round(r["beta_c"], 2)} for r in bd["rows"]],
                 hide_index=True)
    st.caption("RIASEC: " + ", ".join(f"{t} {v:g}" for t, v in bd["riasec"].items())
               + f" · Chữ mô hình đọc: \"{bd['text'] or '(trống)'}\"")
