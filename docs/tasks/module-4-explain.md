# Module 4: Giải thích

## Mục tiêu

Giải thích cho học sinh vì sao mỗi ngành được gợi ý và vì sao danh sách được sắp như vậy, bằng tiếng Việt dễ hiểu. Chỉ
dùng con số do module 3 tính ra, không bịa thông tin.

## Tính độc lập

- **Đầu vào là dữ liệu thuần** (các từ điển Python của từng ngành trong `Advice`), nên có thể làm việc mà không cần
  module 1, 2, 3 hoàn chỉnh:
  - tự tạo vài ví dụ bằng tay;
  - hoặc chạy `advise` trên thế giới mô phỏng (`tiny_db`) với bộ trả lời từ khóa (`HeuristicJudge`) hay bộ trả lời
    "biết trước" (`uniadvisor.student.simulated.OracleJudge`).
- **Ranh giới:** các hàm trong `backend/uniadvisor/explain/__init__.py`. Module 3 sở hữu cấu trúc `Advice`. Khi module 3 thêm hoặc
  đổi trường, module 4 cập nhật cách dùng.

## Đầu vào

Với từng ngành trong danh sách:

- tên ngành, trường, tổ hợp, tổng điểm xét của em;
- điểm chuẩn dự báo, khoảng dao động, lịch sử điểm chuẩn;
- xác suất đậu và mức;
- điểm từng tiêu chí, điểm mạnh và yếu so với các ngành khác trong danh sách;
- cảnh báo (cơ sở phụ, hai nguồn công bố khác nhau, điều kiện riêng), các câu trả lời chưa chắc của module 2.

Với cả danh sách: xác suất đậu ít nhất một nguyện vọng, số nguyện vọng an toàn, điểm thật hay thi thử.

## Đầu ra

- Một đoạn giải thích cho từng ngành (`program_explanation`).
- Một nhãn độ tin cậy kèm lý do (`confidence_label`).
- Một đoạn tóm tắt cả danh sách (`list_summary`).
- Lời lưu ý chung (`DISCLAIMER`).

Ứng dụng (`app/streamlit_app.py`) hiển thị các phần này và cho tải danh sách về dạng CSV.

**Cam kết:** mỗi câu đều dựng từ con số có trong đầu vào. Không đưa ra thông tin hay lời hứa nào mà module 3 không tính.

## Hiện trạng

Đang tạm giữ nguyên. Đúng nguyên tắc không bịa, nhưng:

1. **Không giải thích vì sao danh sách sắp như vậy.** Có lúc tóm tắt nói sai lý do: nói nguyện vọng 1 "hợp em nhất"
   trong khi nó ngang 9 ngành khác về sở thích, và đứng đầu thực ra nhờ độ cạnh tranh và học phí.
2. **Điểm mạnh, điểm yếu thường trống hoặc hiển nhiên.**
3. **Nhận định của module 2 không kèm bằng chứng** (câu nào của học sinh dẫn tới nhận định đó).
4. **Không có "vì sao không chọn ngành X?",** dù đã tính sẵn giải thích cho các ngành thay thế.
5. **Có câu trộn hai tổ hợp,** ví dụ "tổ hợp A01: 22,50 … top 14% của A00".
6. **Nhãn độ tin cậy không gắn với sai số đo được:** thưởng cho số năm có lịch sử, trong khi sai số dự báo gần như
   không đổi theo số năm.
7. **Chưa có kiểm thử,** chưa thử với học sinh thật.

Khi module 3 đổi cách chọn danh sách (sắp theo độ khó, mức đậu thay cho %, lót an toàn), phần giải thích cần theo.

## Quy trình làm việc (gợi ý)

1. **Chọn việc** trong danh sách bên dưới.
2. **Tạo bộ ví dụ cố định:**
   - vài học sinh mô phỏng chạy trên `tiny_db`, lưu đầu vào và đầu ra hiện tại;
   - đọc lại như một học sinh để thấy câu nào sai, thừa hoặc khó hiểu.
3. **Sửa** trong `backend/uniadvisor/explain/__init__.py`. Phần hiển thị nằm ở `app/streamlit_app.py`.
4. **Kiểm thử:**
   - mỗi con số trong câu giải thích phải có trong đầu vào;
   - không trộn tổ hợp;
   - tóm tắt nêu đúng lý do sắp xếp.
5. **Xem trên app** (`uniadvisor app`, hoặc `UNIADVISOR_DB=data/sim/tiny uniadvisor app` để chạy trên dữ liệu mô phỏng).
6. **Khi có thể, hỏi ý kiến học sinh thật** về độ dễ hiểu. Đây là bước đánh giá chính của MVP.

## Việc có thể nhận (theo mức ưu tiên)

1. **Kiểm thử cho `explain.py`.**
2. **Giải thích thứ tự danh sách** theo cách mới của module 3: vì sao ngành này đứng trên ngành kia, nguyện vọng nào là
   lót an toàn.
3. **Hiện bằng chứng:** câu của học sinh dẫn tới từng nhận định (dùng dữ kiện kèm câu gốc của module 2).
4. **"Vì sao không chọn ngành X?"** cho các ngành thay thế.
5. **Sửa câu trộn tổ hợp;** gắn nhãn độ tin cậy với sai số đo được.
