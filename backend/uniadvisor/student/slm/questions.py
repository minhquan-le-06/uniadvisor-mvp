"""The typed questions the SLM answers, with their written rubrics.

Every question has an extra 'insufficient' outcome: the text does not say enough to answer.
kinds:  bool   -> yes / no            (+ insufficient)   head: 2 sigmoids (yes, insufficient)
        choice -> one of K options    (+ insufficient)   head: softmax over K+1
        score  -> ordinal level 1..5  (+ insufficient)   head: CORAL cumulative sigmoids + insufficient sigmoid
scope:  profile -> asked once per student;  program -> asked per (student, program)
"""

from __future__ import annotations

from dataclasses import dataclass

from unidata.build.fields import FIELDS

INSUFFICIENT = "insufficient"

# core subjects per field (first one weighs double). The rubric text below is generated from this table,
# and the rubric teacher (slm/teacher.py) uses the same table, so the two can never disagree.
CORE_SUBJECTS = {
    "cntt": ["TO", "LI", "TI"], "ky_thuat": ["TO", "LI"], "khoa_hoc_tn": ["TO", "LI"], "tai_chinh": ["TO", "N1"],
    "kinh_te": ["TO", "N1", "VA"], "y_duoc": ["SI", "HO", "TO"], "sinh_hoa": ["HO", "SI", "TO"], "xay_dung": ["TO", "LI"],
    "nong_lam_mt": ["SI", "HO", "DI"], "ngon_ngu": ["N1", "VA"], "du_lich": ["N1", "VA", "DI"], "bao_chi": ["VA", "SU"],
    "xa_hoi": ["VA", "SU", "DI"], "luat": ["VA", "SU", "GDKTPL"], "su_pham": ["VA", "TO"], "thiet_ke": ["VA", "TO"],
}
DEFAULT_CORE = ["TO", "VA"]  # a field not in the table
_SUBJECT_VI = {"TO": "Toán", "VA": "Văn", "LI": "Lý", "HO": "Hóa", "SI": "Sinh", "SU": "Sử", "DI": "Địa", "N1": "Anh",
               "TI": "Tin", "GDKTPL": "KTPL"}


def _core_table() -> str:
    rows = [f"- {FIELDS[f]}: {', '.join(_SUBJECT_VI[s] for s in subs)}" for f, subs in CORE_SUBJECTS.items() if f in FIELDS]
    return "\n".join(rows + [f"- Lĩnh vực khác / không rõ: {', '.join(_SUBJECT_VI[s] for s in DEFAULT_CORE)}"])


ABILITY_RUBRIC = (
    "Môn cốt lõi theo 'Lĩnh vực' của ngành (môn đầu tiên tính hệ số 2):\n" + _core_table() + "\n"
    "Cách chấm: lấy trung bình có trọng số của các môn cốt lõi mà học sinh CÓ điểm (bỏ qua môn không có điểm), rồi "
    "5: >= 8.5, 4: 7.5-8.5, 3: 6.5-7.5, 2: 5-6.5, 1: < 5. Học sinh tự nhận giỏi một môn cốt lõi -> cộng 1 mức; tự nhận "
    "yếu/kém một môn cốt lõi -> trừ 1 mức (trong khoảng 1-5). Không có điểm môn cốt lõi nào nhưng có tự nhận xét: tự nhận "
    "giỏi -> 4, tự nhận yếu -> 2.\n"
    "insufficient: không có điểm và không có tự nhận xét nào về các môn cốt lõi."
)


@dataclass(frozen=True)
class Question:
    id: str
    kind: str                 # bool | choice | score
    scope: str                # profile | program
    text_vi: str              # the question as given to the model
    labels: tuple[str, ...]   # without 'insufficient'
    labels_vi: tuple[str, ...]
    rubric: str
    clarify_vi: str = ""      # what to ask the student when the answer is uncertain

    @property
    def all_labels(self) -> tuple[str, ...]:
        return (*self.labels, INSUFFICIENT)


QUESTIONS: list[Question] = [
    Question(
        id="risk_tolerance", kind="choice", scope="profile",
        text_vi="Mức độ chấp nhận rủi ro của học sinh khi đặt nguyện vọng là gì?",
        labels=("an_toan", "can_bang", "mao_hiem"),
        labels_vi=("Thận trọng, ưu tiên chắc chắn đỗ", "Cân bằng", "Sẵn sàng mạo hiểm vì trường/ngành mơ ước"),
        rubric=(
            "an_toan: nói rõ muốn chắc chắn đỗ, sợ trượt, không thể thi lại / ôn thêm một năm, gia đình yêu cầu phải đỗ.\n"
            "can_bang: muốn thử vài lựa chọn cao nhưng vẫn cần phương án an toàn; hoặc nói 'vừa sức'.\n"
            "mao_hiem: chấp nhận trượt để thử trường/ngành mơ ước, sẵn sàng thi lại năm sau, 'được ăn cả ngã về không'.\n"
            "insufficient: không có câu nào cho biết thái độ với rủi ro. Mâu thuẫn mạnh (vừa 'phải đỗ bằng mọi giá' vừa "
            "'không đỗ thì thi lại') mà không nói cái nào quan trọng hơn cũng là insufficient."
        ),
        clarify_vi="Nếu phải chọn, em ưu tiên CHẮC CHẮN có trường để học, hay chấp nhận rủi ro để thử trường/ngành mơ ước?",
    ),
    Question(
        id="top_priority", kind="choice", scope="profile",
        text_vi="Điều học sinh coi trọng nhất khi chọn trường/ngành là gì?",
        labels=("nganh_yeu_thich", "truong_danh_tieng", "hoc_phi_thap", "gan_nha", "viec_lam_thu_nhap"),
        labels_vi=("Đúng ngành mình thích", "Trường danh tiếng", "Học phí thấp", "Gần nhà / đúng nơi mong muốn", "Dễ xin việc, thu nhập cao"),
        rubric=(
            "Chọn điều học sinh nói là QUAN TRỌNG NHẤT (hoặc nhấn mạnh nhiều nhất). Nhắc tới nhiều thứ ngang nhau mà "
            "không xếp thứ tự -> chọn thứ được nhấn mạnh rõ nhất; nếu không có -> insufficient.\n"
            "nganh_yeu_thich: đam mê, sở thích, 'học đúng cái mình thích'. truong_danh_tieng: trường top, tên tuổi, "
            "'trường có tiếng'. hoc_phi_thap: kinh tế khó khăn là mối lo chính, 'học phí rẻ'. gan_nha: muốn ở gần gia đình, "
            "chỉ học ở một thành phố. viec_lam_thu_nhap: ra trường dễ có việc, lương cao, ổn định.\n"
            "insufficient: không nói điều gì được ưu tiên."
        ),
        clarify_vi="Trong các yếu tố: đúng ngành thích, trường danh tiếng, học phí, gần nhà, việc làm sau này — điều nào quan trọng nhất với em?",
    ),
    Question(
        id="interest_fit", kind="score", scope="program",
        text_vi="Ngành này hợp với sở thích và định hướng nghề nghiệp của học sinh đến mức nào (1-5)?",
        labels=("1", "2", "3", "4", "5"),
        labels_vi=("Rất không hợp", "Ít hợp", "Trung bình", "Khá hợp", "Rất hợp"),
        rubric=(
            "Xét theo 'Lĩnh vực' của ngành (cùng lĩnh vực là đủ, không cần đúng tên ngành).\n"
            "5: ngành thuộc lĩnh vực học sinh NÓI RÕ muốn học, hoặc lĩnh vực của nghề học sinh nói muốn làm.\n"
            "4: lĩnh vực học sinh chỉ GỢI Ý qua sở thích, hoạt động (vd 'hay tự viết code', 'hay chăm sóc ông bà khi ốm') "
            "mà không nói thẳng; hoặc lĩnh vực gần, liên quan rõ tới lĩnh vực học sinh muốn (vd CNTT và kỹ thuật điện tử).\n"
            "3: học sinh KHÔNG nêu lĩnh vực hay nghề mong muốn nào (chỉ nói điều không thích, hoặc chỉ có mong muốn của gia "
            "đình) và ngành không trái với điều đã nói; hoặc là ngành gia đình muốn mà học sinh chấp nhận.\n"
            "2: học sinh ĐÃ nêu lĩnh vực/nghề muốn theo (nói rõ hoặc gợi ý) và ngành này thuộc lĩnh vực khác, không liên "
            "quan (kể cả khi không trái với gì); hoặc là ngành gia đình ép mà học sinh không muốn.\n"
            "1: học sinh nói rõ không thích / sợ lĩnh vực này.\n"
            "insufficient: không nói gì về sở thích, môn thích, nghề muốn làm, điều không thích hay mong muốn của gia đình."
        ),
        clarify_vi="Em thích làm công việc gì sau này, hoặc có môn học/hoạt động nào em thật sự hứng thú không?",
    ),
    Question(
        id="ability_fit", kind="score", scope="program",
        text_vi="Điểm mạnh học tập của học sinh (điểm các môn, tự nhận xét) phù hợp với yêu cầu của ngành này đến mức nào (1-5)?",
        labels=("1", "2", "3", "4", "5"),
        labels_vi=("Rất không phù hợp", "Ít phù hợp", "Trung bình", "Khá phù hợp", "Rất phù hợp"),
        rubric=ABILITY_RUBRIC,
        clarify_vi="Em thấy mình mạnh và yếu ở môn nào nhất?",
    ),
    Question(
        id="budget_ok", kind="bool", scope="program",
        text_vi="Học phí của chương trình này có nằm trong khả năng tài chính học sinh đã nêu không?",
        labels=("yes", "no"),
        labels_vi=("Trong khả năng", "Vượt khả năng"),
        rubric=(
            "So học phí/năm của chương trình với mức gia đình lo được. yes: học phí cao nhất <= ngân sách, hoặc gia đình nói "
            "kinh tế thoải mái / không lo học phí. no: học phí thấp nhất > ngân sách (cho phép lệch ~10%), hoặc gia đình khó "
            "khăn và học phí > 25 triệu/năm, hoặc nói 'không học được chương trình liên kết/đắt'.\n"
            "Mức theo tháng x10 = theo năm. insufficient: không nói gì về tài chính, hoặc chương trình không có học phí."
        ),
        clarify_vi="Gia đình em có thể chi khoảng bao nhiêu tiền học phí mỗi năm?",
    ),
    Question(
        id="location_ok", kind="bool", scope="program",
        text_vi="Nơi học của chương trình này có phù hợp với mong muốn về địa điểm của học sinh không?",
        labels=("yes", "no"),
        labels_vi=("Phù hợp", "Không phù hợp"),
        rubric=(
            "yes: đúng thành phố học sinh muốn, hoặc học sinh nói đi đâu cũng được, hoặc 'gần nhà' mà trường ở vùng của nhà "
            "(miền Bắc -> Hà Nội, miền Nam -> TP.HCM). no: học sinh chỉ muốn nơi khác, không muốn xa nhà mà trường ở miền "
            "khác, không muốn sống ở thành phố lớn, hoặc chương trình học ở phân hiệu/tỉnh khác mà học sinh không muốn.\n"
            "insufficient: không nói gì về nơi học hay nơi ở; nhà ở miền Trung + chỉ nói 'gần nhà' (cả hai thành phố đều xa)."
        ),
        clarify_vi="Em muốn học ở Hà Nội, TP.HCM, hay ở đâu cũng được?",
    ),
    Question(
        id="conditions_ok", kind="bool", scope="program",
        text_vi="Học sinh có đáp ứng/chấp nhận được các điều kiện riêng của chương trình này không?",
        labels=("yes", "no"),
        labels_vi=("Đáp ứng", "Không đáp ứng"),
        rubric=(
            "Điều kiện riêng: học bằng tiếng Anh, chỉ tuyển nam/nữ, yêu cầu sức khỏe/phát âm (sư phạm), học ở phân hiệu.\n"
            "yes: chương trình không có điều kiện riêng; hoặc có và học sinh đáp ứng (tiếng Anh tốt: điểm Anh >= 7 hoặc tự "
            "nhận khá/giỏi, có IELTS); sư phạm mà học sinh không nhắc tới vấn đề phát âm/sức khỏe -> yes. no: học sinh nói điều trái với điều kiện (tiếng Anh kém / điểm Anh < 5 với chương trình "
            "tiếng Anh; nói lắp với sư phạm; sai giới tính; không muốn học phân hiệu).\n"
            "insufficient: có điều kiện riêng nhưng không có thông tin nào về điều đó (vd chương trình tiếng Anh, không có điểm "
            "Anh, không nói gì về tiếng Anh; chỉ tuyển nam/nữ mà không biết giới tính). Điểm Anh 5-7 mà không tự nhận xét: không chắc chắn."
        ),
        clarify_vi="Chương trình này học bằng tiếng Anh / có điều kiện riêng. Em có đáp ứng được không (ví dụ trình độ tiếng Anh)?",
    ),
]

BY_ID = {q.id: q for q in QUESTIONS}
PROFILE_QUESTIONS = [q for q in QUESTIONS if q.scope == "profile"]
PROGRAM_QUESTIONS = [q for q in QUESTIONS if q.scope == "program"]
