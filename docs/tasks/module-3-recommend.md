# Module 3: Gợi ý

## Mục tiêu

Từ thông tin của học sinh và dữ liệu các ngành, lập danh sách nguyện vọng (tối đa 15) đã sắp xếp. Danh sách phải gồm
ngành em mong muốn, đặt đúng thứ tự để không có nguyện vọng vô dụng, và có lót an toàn để không rớt hết.

## Tính độc lập

- **Không cần module 1 hoàn chỉnh:** dùng thế giới mô phỏng (`tiny_db`, `uniadvisor sim tiny`), CSDL thật trong git,
  hoặc một mùa tuyển sinh giả lập (`uniadvisor sim season`). Mùa giả lập có biến động chung của cả năm, của từng trường
  và của từng ngành, nên biết trước "đáp án" để chấm.
- **Không cần module 2 hoàn hảo:** dùng học sinh mô phỏng (`uniadvisor sim students`) và bộ trả lời "biết trước"
  (`uniadvisor.sim.students.OracleJudge`). Bộ này trả lời đúng theo dữ kiện thật của học sinh, nên mọi sai sót đo được
  là của module 3.
- **Ranh giới:**
  - vào: hàm `advise(hồ_sơ, judge=..., db=..., params=...)` trong `src/uniadvisor/advisor.py`;
  - ra: đối tượng `Advice`, mà module 4 đọc.

  Thêm trường vào `Advice` thì thoải mái. Bỏ hoặc đổi nghĩa một trường thì báo module 4.

## Đầu vào

- **Hồ sơ từ form:** điểm từng môn, khu vực và đối tượng ưu tiên, giới tính, điểm thật hay điểm thi thử
  (`StudentProfile`).
- **Câu trả lời của module 2:** mức chịu rủi ro, ưu tiên, mức hợp sở thích, năng lực, ngân sách, nơi học, điều kiện
  riêng của từng ngành.
- **CSDL của module 1:** ngành, điểm chuẩn các năm, phổ điểm, chỉ tiêu, học phí.
- **Quy chế tuyển sinh theo năm:** `config/rules/<năm>.yaml` (điểm ưu tiên, điểm sàn, số nguyện vọng tối đa, mức an
  toàn).
- **Tham số dự báo** đã chọn từ dữ liệu quá khứ: `artifacts/models/forecast_params.json`.

## Đầu ra

`Advice` gồm:

- danh sách nguyện vọng theo thứ tự. Mỗi ngành có:
  - tổ hợp và tổng điểm xét của em;
  - điểm chuẩn dự báo và khoảng dao động;
  - xác suất đậu và mức (an toàn / vừa sức / thử thách / khó đỗ);
  - điểm từng tiêu chí và độ phù hợp;
  - các cảnh báo;
- các ngành thay thế;
- xác suất đậu ít nhất một nguyện vọng;
- câu hỏi cần hỏi lại học sinh;
- ghi chú.

**Cam kết:** cùng đầu vào thì cùng danh sách. Không có ngành em không đủ điều kiện. Mọi con số giải thích được từ CSDL
và quy chế.

## Hiện trạng

Thuật toán hiện tại:

1. Lọc theo quy chế 2026 và cộng điểm ưu tiên.
2. Dự báo điểm chuẩn bằng trung bình có trọng số các năm trước, gần như là điểm năm ngoái.
3. Tính xác suất đậu từng ngành.
4. Tính độ phù hợp bằng 5 tiêu chí có trọng số đặt tay.
5. Chọn danh sách tối đa "xác suất trúng × độ phù hợp", rồi sắp theo độ phù hợp.

Phần luật và tối ưu đã kiểm thử. Xác suất đậu khá sát thực tế: dự đoán "an toàn" 92% thì thực tế đỗ 95%.

**Vấn đề:**

- **Xác suất đậu chi phối việc chọn ngành.** Ngành mơ ước khó đậu bị đánh giá thấp. Ngành dưới 10% bị loại hẳn.
- **Thứ tự theo độ phù hợp, không theo điểm chuẩn,** nên có thể sinh nguyện vọng vô dụng: ngành điểm cao đặt dưới ngành
  điểm thấp.
- **Coi các ngành độc lập,** trong khi ngành cùng trường lên xuống cùng nhau (tương quan khoảng 0,47). Lót an toàn có
  thể dồn vào một trường.
- **Dự báo được chấm theo sai số điểm** (khoảng 1,37, không hơn "lấy điểm năm ngoái"), chưa ai đo độ đúng về thứ tự.
- **Trọng số đặt tay.** "Độ cạnh tranh" thưởng cho ngành khó vào.

Hướng sửa đã thống nhất: [docs/TEAM_REPORT.md](../TEAM_REPORT.md), mục 4.

## Quy trình làm việc (gợi ý)

1. **Chọn việc** trong danh sách bên dưới.
2. **Đo trước khi sửa:**
   - `uniadvisor backtest` (dự báo 2025 và 2026 từ các năm trước);
   - chạy `advise` cho học sinh mô phỏng trên các mùa giả lập, đo: số nguyện vọng vô dụng, tỉ lệ rớt hết, em vào được
     ngành thứ mấy trong mong muốn.
3. **Sửa:**
   - quy chế ở `config/rules/`, luật ở `src/uniadvisor/kb/rules.py`;
   - dự báo ở `src/uniadvisor/engine/`;
   - tiêu chí ở `src/uniadvisor/compare.py`;
   - chọn danh sách ở `src/uniadvisor/optimizer.py` và `advisor.py`.
4. **Đo lại** bằng cùng cách. Thay đổi về dự báo chỉ giữ khi tốt hơn trên dữ liệu quá khứ (backtest), không chỉ trên
   mô phỏng.
5. **Thêm kiểm thử** cho luật mới, chạy trên thế giới mô phỏng (`tiny_db`).
6. **Cập nhật số liệu** ở đây và `docs/HANDOFF.md`. Đổi `Advice` thì báo module 4.

## Việc có thể nhận (theo mức ưu tiên)

1. **Thước đo mới:** chấm dự báo theo tỉ lệ cặp ngành sắp đúng thứ tự; chấm danh sách trên học sinh × mùa giả lập.
   Cần làm trước, vì các việc sau dựa vào nó.
2. **Chọn và sắp danh sách theo cách mới:**
   - đề xuất ngành theo độ phù hợp, không loại ngành mơ ước;
   - sắp theo độ khó với chính em (điểm chuẩn dự báo trừ tổng điểm của em);
   - chỉ ra mâu thuẫn giữa sở thích và thứ tự.
3. **Lót an toàn:** 2–3 nguyện vọng chắc đậu ở các trường khác nhau, kiểm tra tỉ lệ rớt hết trên mùa giả lập.
4. **Mức đậu:** vẫn tính %, chỉ hiện 3–4 mức, ngưỡng đặt trong `config/rules/` và kiểm chứng trên dữ liệu quá khứ.
5. **Dự báo điểm chuẩn:** thử xu hướng qua các năm, thay đổi chỉ tiêu, và một mô hình học máy dạng bảng làm đối chứng.
   Chỉ giữ cái nào làm thứ tự đúng hơn.
6. **Kiểm thử cho `compare.py`,** hiện chưa có.
