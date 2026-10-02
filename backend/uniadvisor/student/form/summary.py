"""The "Mình hiểu là..." summary: the JSON document read back to the student in plain Vietnamese, one line per section,
so they can see what the app understood and correct it."""

from __future__ import annotations

from uniadvisor.student.form.options import AGREES, AREAS, CATEGORIES, GENDERS, PRIORITIES, RISKS, STRENGTHS, SUBJECTS
from uniadvisor.student.form.picker import Picker
from uniadvisor.student.form.scores import vn_number

# section -> its title on screen; the guided chat uses the same keys for its steps
SECTIONS = {
    "scores": "Điểm thi",
    "about": "Về em",
    "interests": "Ngành em thích",
    "dislikes": "Ngành em không muốn học",
    "family": "Mong muốn của gia đình",
    "budget": "Học phí",
    "location": "Nơi học",
    "plan": "Cách đặt nguyện vọng",
}


def summary(doc: dict, p: Picker) -> dict[str, str]:
    """Section key -> one line of Vietnamese."""
    pr = doc["profile"]
    assumed = {x["field"] for x in doc["assumed"]}
    out = {}

    scores = " · ".join(f"{SUBJECTS[k]} {vn_number(v)}" for k, v in pr["scores"].items())
    kind = "điểm thi chính thức" if pr["score_kind"] == "actual" else "điểm thi thử hoặc ước lượng"
    out["scores"] = f"{scores} ({kind})"

    about = [GENDERS[pr["gender"]]]
    about.append(f"sống ở {pr['province']}" if pr["province"] else "chưa cho biết tỉnh/thành")
    about.append(f"khu vực {AREAS[pr['area']]}" + (" (tạm tính)" if "profile.area" in assumed else ""))
    about.append("không thuộc diện ưu tiên" if pr["category"] == "none" else f"diện ưu tiên {CATEGORIES[pr['category']]}")
    about.append(f"tốt nghiệp THPT năm {pr['graduation_year']}")
    out["about"] = ", ".join(about) + "."

    out["interests"] = (", ".join(f"{p.name(x['code'])} ({STRENGTHS[x['strength']].lower()})" for x in doc["interests"])
                        or "Em chưa chọn ngành nào.")
    out["dislikes"] = ", ".join(p.name(x["code"]) for x in doc["dislikes"]) or "Không có."
    fam = doc["family"]
    out["family"] = (f"{', '.join(p.name(c) for c in fam['codes'])} ({AGREES[fam['student_agrees']].lower()})"
                     if fam else "Em chưa cho biết.")

    b = doc["budget"]
    if b is None:
        out["budget"] = "Em chưa rõ."
    elif b["max_million_per_year"] is None:
        out["budget"] = "Gia đình không lo về học phí."
    else:
        amount = vn_number(b["max_million_per_year"])
        out["budget"] = (f"Tối đa {amount} triệu/năm, không thể vượt." if b["strict"]
                         else f"Khoảng {amount} triệu/năm.")

    loc = doc["location"]
    if loc is None:
        out["location"] = "Em chưa cho biết."
    else:
        where = "Ở đâu cũng được" if set(loc["cities"]) == set(p.cities) else ", ".join(loc["cities"])
        out["location"] = where + (", chỉ học ở cơ sở chính." if loc["main_campus_only"] else ".")

    plan = [RISKS[doc["risk"]] if doc["risk"] else "Em chưa chọn hướng đặt nguyện vọng"]
    if doc["priorities"]:
        plan.append("ưu tiên: " + ", ".join(f"{i}. {PRIORITIES[x].lower()}" for i, x in enumerate(doc["priorities"], 1)))
    out["plan"] = "; ".join(plan) + "."
    return out
