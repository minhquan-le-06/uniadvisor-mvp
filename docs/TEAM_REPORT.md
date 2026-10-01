# UniAdvisor: báo cáo tiến độ

## 1. Hệ thống làm gì

UniAdvisor giúp học sinh lớp 12 lập danh sách nguyện vọng đại học theo phương thức xét điểm thi THPT. Học sinh nhập
điểm, tỉnh, khu vực ưu tiên và vài câu tự mô tả. Hệ thống trả về danh sách nguyện vọng đã sắp xếp, kèm dự báo điểm
chuẩn, xác suất đỗ và lời giải thích. Phạm vi hiện tại là các trường ở Hà Nội và TP.HCM, khoảng 1.700 ngành.

## 2. Hệ thống gồm 4 phần

| Phần | Làm gì | Cách làm | Tình trạng |
|---|---|---|---|
| 1. Dữ liệu | Thu thập điểm chuẩn, chỉ tiêu, học phí, phổ điểm từ báo và các nguồn công khai, rồi làm sạch | Chương trình tự thu thập dữ liệu từ web, làm sạch bằng quy tắc, đối chiếu nhiều nguồn; phổ điểm dựng bằng thống kê. Không dùng AI. | Đã làm lại, đủ dùng |
| 2. Hiểu học sinh | Đọc thông tin và câu chữ của học sinh để biết em muốn gì | Kết hợp bộ đọc từ khóa (quy tắc) và một mô hình ngôn ngữ nhỏ (SLM) tự huấn luyện, mỗi câu hỏi giao cho bên làm tốt hơn. Gemini chỉ dùng để gán nhãn bộ kiểm tra, không chạy trong ứng dụng. | Sẽ làm (đã có bản thử) |
| 3. Gợi ý | Dự báo điểm chuẩn, tính xác suất đỗ, chọn và xếp danh sách | Luật theo quy chế tuyển sinh 2026, mô hình thống kê để dự báo và tính xác suất, thuật toán tối ưu để chọn danh sách. Không dùng AI. | **Đang làm** |
| 4. Giải thích | Viết lời giải thích cho từng gợi ý | Câu mẫu điền bằng các con số của phần 3, nên không bịa thông tin. Không dùng AI. | Tạm giữ nguyên |

## 3. Đã làm xong: phần 1 (dữ liệu)

- **Một cơ sở dữ liệu duy nhất, tự kiểm tra khi nạp** (không trùng, không thiếu liên kết, điểm trong 0–30).
- **Mỗi con số ghi rõ nguồn gốc:** quan sát được, suy ra, ước tính (ứng dụng hiện chữ "ước tính") hoặc mô phỏng.
- **Dữ liệu mô phỏng để kiểm thử, tách hẳn khỏi dữ liệu thật.**
- **Gắn mã ngành của Bộ GD&ĐT** (Thông tư 09/2022) cho 1.424/1.666 ngành. Lĩnh vực của ngành giờ theo mã Bộ, nhờ đó
  184 ngành trước đây bị xếp sai đã được sửa.
- **Còn thiếu:** điểm chuẩn theo từng tổ hợp, 242 ngành chưa có mã, chỉ tiêu mới có năm 2026, khoảng 44% ngành chưa
  rõ học phí.

## 4. Đang làm: phần 3 (gợi ý)

**Làm trước phần 2 vì** phần 3 chủ yếu dùng thông tin trong form (điểm, khu vực, tổ hợp). Các tiêu chí từ phần 2 có
thể thay bằng câu trả lời cố định khi kiểm thử.

### Thuật toán hiện tại

1. **Lọc:** luật quy chế 2026 loại các ngành học sinh không đủ điều kiện (tổ hợp, điểm sàn, giới tính) và cộng điểm
   ưu tiên khu vực, đối tượng.
2. **Dự báo điểm chuẩn:** lấy trung bình có trọng số các năm trước. Năm gần nhất nặng nhất: mỗi năm lùi lại chỉ còn
   0,2 lần trọng số của năm sau nó, nên kết quả gần như là điểm năm ngoái. Độ bất định (khoảng ±2,2 điểm cho 80%
   trường hợp) đo từ sai số dự báo các năm trước.
3. **Xác suất đỗ từng ngành:** khả năng điểm của học sinh cao hơn điểm chuẩn năm tới, theo dự báo và độ bất định ở
   bước 2. Nếu là điểm thi thử thì cộng thêm độ không chắc của điểm học sinh.
4. **Độ phù hợp từng ngành:** tổng có trọng số của 5 tiêu chí, trọng số đặt tay:
   - sở thích 35%;
   - độ cạnh tranh 20%;
   - năng lực 15%;
   - học phí 15%;
   - địa điểm 15%.

   Ưu tiên hàng đầu của học sinh thì được nhân trọng số lên 2,5 lần.
5. **Chọn danh sách:** học sinh trúng nguyện vọng cao nhất mà mình đủ điểm. Ta chọn danh sách sao cho tổng "xác suất
   trúng × độ phù hợp" là lớn nhất. Ràng buộc gồm số nguyện vọng tối đa, ít nhất N nguyện vọng an toàn và tối đa 4
   ngành mỗi trường. Thứ tự: ngành phù hợp hơn đứng trước. Việc chọn tập ngành được giải chính xác bằng quy hoạch động.

### Hỏng ở đâu

- **Xác suất đậu chi phối việc chọn ngành.** Bước 5 tối đa "xác suất trúng × độ phù hợp", nên một ngành em mơ ước
  nhưng khó đậu bị đánh giá thấp và dễ bị bỏ. Ngành dưới 10% khả năng đậu thì bị loại hẳn, ngành "khó đậu" không bao
  giờ được tự động đề xuất. Điều này ngược với thực tế: cứ đặt ngành mơ ước lên trên, rớt cũng không sao.
- **Thứ tự theo độ phù hợp, không theo điểm chuẩn.** Một ngành điểm chuẩn cao nhưng kém phù hợp hơn sẽ bị đặt dưới một
  ngành điểm thấp, thành nguyện vọng vô dụng. App không phát hiện và không báo cho học sinh.
- **Lót an toàn giả sử các ngành độc lập.** Gần một nửa sai số dự báo là phần chung của cả trường trong năm đó. Hai
  ngành cùng trường có sai số tương quan khoảng 0,47. Các nguyện vọng "an toàn" có thể dồn vào một trường, và con số
  "gần như chắc chắn đỗ ít nhất một nguyện vọng" bị nói quá.
- **Dự báo được chấm theo sai số điểm, không theo thứ tự.** Sai số khoảng 1,37 điểm, không hơn "lấy điểm năm ngoái".
  Chưa ai đo xem nó sắp đúng thứ tự giữa các ngành đến đâu, mà đó mới là việc chính. Dự báo cũng không thấy xu hướng:
  một ngành tăng đều 20,4 → 24,38 qua 2023–2026 vẫn được dự báo 24,15 cho 2027.
- **Trọng số đặt bằng tay.** "Độ cạnh tranh" vừa chiếm 20% vừa đứng thay cho "việc làm", nên thưởng cho ngành khó vào.

### Thuật toán dự định

**Nguyên tắc (rút từ kinh nghiệm thực tế đặt nguyện vọng):**
- Học sinh trúng nguyện vọng cao nhất mà mình đủ điểm. Vì vậy ngành có điểm chuẩn cao hơn phải đặt trên. Đặt nó dưới
  một ngành điểm thấp hơn là vô dụng: đủ điểm ngành trên thì đã trúng ngành dưới trước rồi.
- Đặt nhiều nguyện vọng và có lót an toàn thì gần như không thể rớt hết. Rớt vài nguyện vọng đầu là bình thường, và
  học sinh nên cứ đặt ngành mình mơ ước lên trên.
- Do đó việc chính là **chọn đúng ngành, đúng trường**. Dự đoán điểm chuẩn chủ yếu để **so sánh tương đối** giữa các
  ngành, ví dụ CNTT trường A cao hơn hay thấp hơn trường B. Dự đoán tuyệt đối ("em có đủ điểm không") chỉ thật sự
  cần cho phần lót an toàn.

**Các bước:**
1. **Đề xuất ngành phù hợp (trọng tâm).** App xếp các ngành em đủ điều kiện theo mức hợp với em: sở thích (từ phần
   2), chất lượng trường, học phí, nơi học. Em xem, bỏ bớt hoặc thêm. Khả năng đậu không được dùng để loại ngành mơ
   ước.
2. **Sắp thứ tự theo điểm chuẩn tương đối.** Dự đoán ngành nào điểm chuẩn cao hơn ngành nào, rồi sắp từ cao xuống
   thấp. Khi hai ngành sát nhau, không chắc bên nào cao hơn, thì ngành em thích hơn đứng trên.
3. **Chỉ ra mâu thuẫn.** Nếu em thích ngành A hơn ngành B nhưng A có điểm chuẩn thấp hơn rõ, app hỏi em và giải thích:
   đặt B dưới A là vô nghĩa. Nếu em thực sự thích A hơn thì nên bỏ hẳn B.
4. **Lót an toàn.** Cuối danh sách luôn có 2–3 nguyện vọng mà điểm em cao hơn hẳn điểm chuẩn dự báo (dư khoảng 2–3
   điểm). Các nguyện vọng lót nên ở các trường khác nhau, vì các ngành cùng trường thường lên xuống cùng nhau, và ưu
   tiên ngành em vẫn chấp nhận học. Đây là chỗ duy nhất cần dự đoán tuyệt đối, cần cẩn thận nhất với học sinh điểm
   thấp, gần điểm sàn.
5. **Hiện khả năng đậu theo mức.** App vẫn tính xác suất đậu (%) bên trong nhưng chỉ hiện 3–4 mức: mơ ước, thử sức,
   vừa sức, an toàn.
6. **Kiểm chứng bằng mô phỏng.** Tạo hàng trăm mùa tuyển sinh giả lập, có biến động chung của năm, của trường và của
   ngành, kể cả kịch bản năm cải cách như 2025. Đo ba thứ:
   - thứ tự tương đối có đúng không: tỉ lệ cặp ngành sắp đúng, số nguyện vọng bị đặt sai thành vô dụng;
   - tỉ lệ rớt hết nguyện vọng, nhất là ở nhóm điểm thấp;
   - em vào được ngành thứ mấy trong danh sách mong muốn của mình.
7. **Đánh giá dự báo theo thước đo mới.** Trên dữ liệu thật 2023–2026, chấm dự báo theo tỉ lệ sắp đúng thứ tự cặp ngành
   thay vì sai số điểm. So tương đối dễ hơn so tuyệt đối: biến động chung của cả năm, và với hai ngành cùng trường cả
   biến động chung của trường, đều triệt tiêu khi so. Sau đó thử thêm xu hướng qua các năm, và chỉ giữ cái nào làm thứ
   tự đúng hơn.

## 5. Sẽ làm: phần 2 (hiểu học sinh)

- **Vấn đề:** ứng dụng không tóm lại "em muốn gì" mà đọc lại câu chữ cho từng ngành. Học sinh không thấy được máy hiểu
  mình thế nào để sửa. Tiêu chí sở thích (35% trọng số) cũng không phân biệt được ngành.
- **Hướng sửa:** đọc một lần, rút ra các dữ kiện, mỗi dữ kiện kèm câu gốc làm bằng chứng. Các dữ kiện gồm ngành thích,
  ngân sách, nơi học, mức chịu rủi ro, ưu tiên, tiếng Anh. Sở thích ghi theo nhóm ngành của Bộ. Học sinh xem và sửa
  một dòng như: "Mình hiểu là: em thích CNTT, học ở Hà Nội, tối đa 25 triệu/năm".
- **Bản thử:** đo trên 2.000 học sinh mô phỏng, đọc đúng 91–95% các dữ kiện ngân sách, nơi học, ưu tiên và tiếng Anh.
  Mức chịu rủi ro đúng 81%, ngành thích khoảng 84%. Đây là chữ do máy sinh, chưa phải học sinh thật.

## 6. Cần lưu ý

- Chưa có đánh giá với học sinh thật. Bộ kiểm tra phần 2 (294 câu) do Gemini gán nhãn, chưa có nhãn của người.
- Bản trên web chưa có file mô hình nên phần 2 chỉ chạy bộ đọc từ khóa.
