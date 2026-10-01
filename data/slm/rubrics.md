# SLM question rubrics

Every question also allows **insufficient** (not enough information).


## risk_tolerance (choice, profile)

**Question:** Mức độ chấp nhận rủi ro của học sinh khi đặt nguyện vọng là gì?

**Labels:** `an_toan` = Thận trọng, ưu tiên chắc chắn đỗ, `can_bang` = Cân bằng, `mao_hiem` = Sẵn sàng mạo hiểm vì trường/ngành mơ ước, `insufficient`


an_toan: nói rõ muốn chắc chắn đỗ, sợ trượt, không thể thi lại / ôn thêm một năm, gia đình yêu cầu phải đỗ.
can_bang: muốn thử vài lựa chọn cao nhưng vẫn cần phương án an toàn; hoặc nói 'vừa sức'.
mao_hiem: chấp nhận trượt để thử trường/ngành mơ ước, sẵn sàng thi lại năm sau, 'được ăn cả ngã về không'.
insufficient: không có câu nào cho biết thái độ với rủi ro. Mâu thuẫn mạnh (vừa 'phải đỗ bằng mọi giá' vừa 'không đỗ thì thi lại') mà không nói cái nào quan trọng hơn cũng là insufficient.


## top_priority (choice, profile)

**Question:** Điều học sinh coi trọng nhất khi chọn trường/ngành là gì?

**Labels:** `nganh_yeu_thich` = Đúng ngành mình thích, `truong_danh_tieng` = Trường danh tiếng, `hoc_phi_thap` = Học phí thấp, `gan_nha` = Gần nhà / đúng nơi mong muốn, `viec_lam_thu_nhap` = Dễ xin việc, thu nhập cao, `insufficient`


Chọn điều học sinh nói là QUAN TRỌNG NHẤT (hoặc nhấn mạnh nhiều nhất). Nhắc tới nhiều thứ ngang nhau mà không xếp thứ tự -> chọn thứ được nhấn mạnh rõ nhất; nếu không có -> insufficient.
nganh_yeu_thich: đam mê, sở thích, 'học đúng cái mình thích'. truong_danh_tieng: trường top, tên tuổi, 'trường có tiếng'. hoc_phi_thap: kinh tế khó khăn là mối lo chính, 'học phí rẻ'. gan_nha: muốn ở gần gia đình, chỉ học ở một thành phố. viec_lam_thu_nhap: ra trường dễ có việc, lương cao, ổn định.
insufficient: không nói điều gì được ưu tiên.


## interest_fit (score, program)

**Question:** Ngành này hợp với sở thích và định hướng nghề nghiệp của học sinh đến mức nào (1-5)?

**Labels:** `1` = Rất không hợp, `2` = Ít hợp, `3` = Trung bình, `4` = Khá hợp, `5` = Rất hợp, `insufficient`


Xét theo 'Lĩnh vực' của ngành (cùng lĩnh vực là đủ, không cần đúng tên ngành).
5: ngành thuộc lĩnh vực học sinh NÓI RÕ muốn học, hoặc lĩnh vực của nghề học sinh nói muốn làm.
4: lĩnh vực học sinh chỉ GỢI Ý qua sở thích, hoạt động (vd 'hay tự viết code', 'hay chăm sóc ông bà khi ốm') mà không nói thẳng; hoặc lĩnh vực gần, liên quan rõ tới lĩnh vực học sinh muốn (vd CNTT và kỹ thuật điện tử).
3: học sinh KHÔNG nêu lĩnh vực hay nghề mong muốn nào (chỉ nói điều không thích, hoặc chỉ có mong muốn của gia đình) và ngành không trái với điều đã nói; hoặc là ngành gia đình muốn mà học sinh chấp nhận.
2: học sinh ĐÃ nêu lĩnh vực/nghề muốn theo (nói rõ hoặc gợi ý) và ngành này thuộc lĩnh vực khác, không liên quan (kể cả khi không trái với gì); hoặc là ngành gia đình ép mà học sinh không muốn.
1: học sinh nói rõ không thích / sợ lĩnh vực này.
insufficient: không nói gì về sở thích, môn thích, nghề muốn làm, điều không thích hay mong muốn của gia đình.


## ability_fit (score, program)

**Question:** Điểm mạnh học tập của học sinh (điểm các môn, tự nhận xét) phù hợp với yêu cầu của ngành này đến mức nào (1-5)?

**Labels:** `1` = Rất không phù hợp, `2` = Ít phù hợp, `3` = Trung bình, `4` = Khá phù hợp, `5` = Rất phù hợp, `insufficient`


Môn cốt lõi theo 'Lĩnh vực' của ngành (môn đầu tiên tính hệ số 2):
- Công nghệ thông tin - Máy tính - Dữ liệu - AI: Toán, Lý, Tin
- Kỹ thuật - Công nghệ (cơ khí, điện, điện tử, ô tô, tự động hóa, vật liệu): Toán, Lý
- Khoa học tự nhiên - Toán - Vật lý - Thống kê: Toán, Lý
- Tài chính - Ngân hàng - Kế toán - Kiểm toán - Bảo hiểm: Toán, Anh
- Kinh tế - Kinh doanh - Quản trị - Marketing - Thương mại: Toán, Anh, Văn
- Y - Dược - Điều dưỡng - Sức khỏe: Sinh, Hóa, Toán
- Sinh học - Hóa học - Công nghệ sinh học - Thực phẩm: Hóa, Sinh, Toán
- Kiến trúc - Xây dựng - Giao thông - Quy hoạch: Toán, Lý
- Nông - Lâm - Thủy sản - Môi trường - Tài nguyên: Sinh, Hóa, Địa
- Ngôn ngữ - Văn hóa - Quốc tế học: Anh, Văn
- Du lịch - Khách sạn - Logistics - Hàng không - Dịch vụ: Anh, Văn, Địa
- Báo chí - Truyền thông - Quan hệ công chúng: Văn, Sử
- Khoa học xã hội - Tâm lý - Nhân văn - Chính trị - Hành chính: Văn, Sử, Địa
- Luật: Văn, Sử, KTPL
- Sư phạm - Giáo dục: Văn, Toán
- Thiết kế - Nghệ thuật - Sáng tạo số: Văn, Toán
- Lĩnh vực khác / không rõ: Toán, Văn
Cách chấm: lấy trung bình có trọng số của các môn cốt lõi mà học sinh CÓ điểm (bỏ qua môn không có điểm), rồi 5: >= 8.5, 4: 7.5-8.5, 3: 6.5-7.5, 2: 5-6.5, 1: < 5. Học sinh tự nhận giỏi một môn cốt lõi -> cộng 1 mức; tự nhận yếu/kém một môn cốt lõi -> trừ 1 mức (trong khoảng 1-5). Không có điểm môn cốt lõi nào nhưng có tự nhận xét: tự nhận giỏi -> 4, tự nhận yếu -> 2.
insufficient: không có điểm và không có tự nhận xét nào về các môn cốt lõi.


## budget_ok (bool, program)

**Question:** Học phí của chương trình này có nằm trong khả năng tài chính học sinh đã nêu không?

**Labels:** `yes` = Trong khả năng, `no` = Vượt khả năng, `insufficient`


So học phí/năm của chương trình với mức gia đình lo được. yes: học phí cao nhất <= ngân sách, hoặc gia đình nói kinh tế thoải mái / không lo học phí. no: học phí thấp nhất > ngân sách (cho phép lệch ~10%), hoặc gia đình khó khăn và học phí > 25 triệu/năm, hoặc nói 'không học được chương trình liên kết/đắt'.
Mức theo tháng x10 = theo năm. insufficient: không nói gì về tài chính, hoặc chương trình không có học phí.


## location_ok (bool, program)

**Question:** Nơi học của chương trình này có phù hợp với mong muốn về địa điểm của học sinh không?

**Labels:** `yes` = Phù hợp, `no` = Không phù hợp, `insufficient`


yes: đúng thành phố học sinh muốn, hoặc học sinh nói đi đâu cũng được, hoặc 'gần nhà' mà trường ở vùng của nhà (miền Bắc -> Hà Nội, miền Nam -> TP.HCM). no: học sinh chỉ muốn nơi khác, không muốn xa nhà mà trường ở miền khác, không muốn sống ở thành phố lớn, hoặc chương trình học ở phân hiệu/tỉnh khác mà học sinh không muốn.
insufficient: không nói gì về nơi học hay nơi ở; nhà ở miền Trung + chỉ nói 'gần nhà' (cả hai thành phố đều xa).


## conditions_ok (bool, program)

**Question:** Học sinh có đáp ứng/chấp nhận được các điều kiện riêng của chương trình này không?

**Labels:** `yes` = Đáp ứng, `no` = Không đáp ứng, `insufficient`


Điều kiện riêng: học bằng tiếng Anh, chỉ tuyển nam/nữ, yêu cầu sức khỏe/phát âm (sư phạm), học ở phân hiệu.
yes: chương trình không có điều kiện riêng; hoặc có và học sinh đáp ứng (tiếng Anh tốt: điểm Anh >= 7 hoặc tự nhận khá/giỏi, có IELTS); sư phạm mà học sinh không nhắc tới vấn đề phát âm/sức khỏe -> yes. no: học sinh nói điều trái với điều kiện (tiếng Anh kém / điểm Anh < 5 với chương trình tiếng Anh; nói lắp với sư phạm; sai giới tính; không muốn học phân hiệu).
insufficient: có điều kiện riêng nhưng không có thông tin nào về điều đó (vd chương trình tiếng Anh, không có điểm Anh, không nói gì về tiếng Anh; chỉ tuyển nam/nữ mà không biết giới tính). Điểm Anh 5-7 mà không tự nhận xét: không chắc chắn.
