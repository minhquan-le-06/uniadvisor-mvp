# Module 2: Hiểu học sinh

## Mục tiêu

Đọc thông tin và câu chữ của học sinh để biết em muốn gì: ngành thích, ngân sách, nơi học, mức chịu rủi ro, ưu tiên.
Kết quả phải đủ rõ để module 3 dùng và để học sinh tự kiểm tra lại ("Mình hiểu là...").

## Tính độc lập

- **Module 2 chỉ cần CSDL để đọc thông tin ngành** (học phí, thành phố, lĩnh vực, mã ngành Bộ) cho các câu hỏi theo
  từng ngành. Khi phát triển, dùng thế giới mô phỏng (`tiny_db` trong bộ kiểm thử) hoặc CSDL thật trong git, không
  cần chờ module 1.
- **Module 2 không cần module 3.** Chất lượng được đo riêng: trên bộ câu hỏi đã gán nhãn (gold set) và trên học sinh
  mô phỏng biết sẵn "sự thật".
- **Module 3 không cần module 2 hoàn hảo.** Module 3 kiểm thử bằng một bộ trả lời "biết trước"
  (`uniadvisor.sim.students.OracleJudge`), trả lời đúng theo dữ kiện thật của học sinh mô phỏng.
- **Ranh giới** là giao diện của bộ trả lời: `judge.answer([(câu_hỏi, hồ_sơ, ngành)])`. Đổi cách đọc bên trong thoải
  mái, miễn giữ giao diện này.

## Đầu vào

- **Form:** điểm từng môn, tỉnh, khu vực ưu tiên, đối tượng ưu tiên, giới tính, điểm thật hay điểm thi thử
  (`StudentProfile` trong `src/uniadvisor/slm/state.py`).
- **Câu chữ tự do** của học sinh, cộng các tin nhắn sau.
- **Câu trả lời cho câu hỏi làm rõ** (nếu app đã hỏi lại).
- **Thông tin ngành** từ CSDL, cho các câu hỏi theo từng ngành.

## Đầu ra

**Hiện tại:** trả lời 7 câu hỏi. Mỗi câu trả lời có nhãn, xác suất từng nhãn, độ tin cậy, và cờ "chưa chắc, cần hỏi
lại" (`Answer` trong `src/uniadvisor/slm/infer.py`).

| Câu hỏi | Phạm vi | Nhãn |
|---|---|---|
| `risk_tolerance` | hồ sơ | an toàn / cân bằng / mạo hiểm |
| `top_priority` | hồ sơ | ngành yêu thích / trường danh tiếng / học phí thấp / gần nhà / việc làm, thu nhập |
| `interest_fit` | từng ngành | 1–5 |
| `ability_fit` | từng ngành | 1–5 |
| `budget_ok` | từng ngành | có / không |
| `location_ok` | từng ngành | có / không |
| `conditions_ok` | từng ngành | có / không |

Câu nào cũng có thêm nhãn "không đủ thông tin".

**Mục tiêu (đang làm dở):** một bản tóm tắt dữ kiện về học sinh (`StudentIntent` trong `src/uniadvisor/intent/`),
đọc một lần, mỗi dữ kiện kèm câu gốc làm bằng chứng:

- ngành thích, ngành không thích, mong muốn của gia đình, theo mã nhóm ngành của Bộ;
- ngân sách, nơi học, chỉ học cơ sở chính;
- mức chịu rủi ro, ưu tiên hàng đầu;
- trình độ tiếng Anh, môn mạnh, môn yếu.

Khi xong, các câu hỏi theo từng ngành sẽ được trả lời bằng cách so dữ kiện với CSDL, ví dụ học phí với ngân sách,
thành phố với nơi học, mã ngành với nhóm ngành em thích.

## Hiện trạng

- **Hai bộ trả lời:**
  - bộ đọc từ khóa (quy tắc), đang chạy trên bản web;
  - mô hình ngôn ngữ nhỏ (SLM) tự huấn luyện, chạy được khi có file mô hình.

  Bản kết hợp giao mỗi câu cho bên làm tốt hơn.
- **Độ đúng trên 294 câu gán nhãn:** từ khóa 0,823, kết hợp 0,864. Nhãn do Gemini gán, chưa có nhãn của người.
- **Dữ liệu huấn luyện:** toàn bộ là học sinh mô phỏng (`uniadvisor slm-data`).
- **Bộ đọc dữ kiện (bản thử):** đo trên 2.000 học sinh mô phỏng (`uniadvisor intent-eval`), đọc đúng 91–95% các dữ kiện
  ngân sách, nơi học, ưu tiên, tiếng Anh; mức chịu rủi ro 81%; ngành thích khoảng 84%. Chưa nối vào ứng dụng.
- **Vấn đề chính:**
  - App không tóm lại "em muốn gì" nên học sinh không thấy được máy hiểu mình thế nào để sửa.
  - Tiêu chí sở thích không phân biệt được ngành (trong một ví dụ, cả 10 gợi ý đều được 5/5).
  - Chỉ hỏi lại được về rủi ro và ưu tiên.
  - Độ tin cậy của bộ từ khóa là số đặt sẵn, chưa hiệu chỉnh.

## Quy trình làm việc (gợi ý)

1. **Chọn việc** trong danh sách bên dưới.
2. **Đo trước khi sửa:** chạy `uniadvisor intent-eval` (từng dữ kiện) và
   `uniadvisor slm-eval --judge heuristic --gold data/slm/gold_llm.csv` (7 câu hỏi), ghi lại số liệu.
3. **Sửa:** từ khóa ở `config/interests.yaml` và `src/uniadvisor/intent/keywords.py`; câu hỏi và cách chấm ở
   `src/uniadvisor/slm/`.
4. **Đo lại** bằng cùng hai lệnh. Chỉ giữ thay đổi làm số liệu tốt lên, và không làm câu hỏi nào tệ đi rõ rệt.
5. **Nếu đổi cách SLM học:** tạo lại dữ liệu (`uniadvisor slm-data`), huấn luyện lại (hướng dẫn ở `docs/kaggle/`), rồi
   chọn lại câu nào giao cho SLM (`SLM_QUESTIONS` trong `slm/infer.py`).
6. **Cập nhật số liệu** trong mục Hiện trạng ở trên và `docs/HANDOFF.md`.

Lưu ý: chữ do máy sinh ra chỉ cho biết bộ đọc phủ được các cách diễn đạt đó. Nhãn của người và câu chữ của học sinh
thật mới cho biết chất lượng thật. Không lưu bất cứ thứ gì học sinh nhập (Nghị định 13/2023).

## Việc có thể nhận (theo mức ưu tiên)

1. **Nối bộ đọc dữ kiện vào ứng dụng:**
   - các câu hỏi theo từng ngành dùng dữ kiện thay vì đọc lại câu chữ;
   - hiện "Mình hiểu là..." cho học sinh sửa;
   - hỏi lại một lần cho dữ kiện chưa rõ.
2. **Chấm sở thích theo mã ngành Bộ** để các ngành được phân biệt, thay cho cách chấm theo lĩnh vực.
3. **Sửa các lỗi đọc đã thấy:**
   - câu nói cả an toàn lẫn mạo hiểm bị bỏ sót;
   - ưu tiên bị đoán khi học sinh không nói;
   - thu nhập tháng của gia đình bị đọc thành ngân sách năm;
   - "tự tin" ở bất cứ đâu bị hiểu là giỏi tiếng Anh.
4. **Nhãn của người** cho bộ gold set (công cụ: `uniadvisor label`), và câu chữ của học sinh thật nếu có thể.
5. **Hiệu chỉnh độ tin cậy** của từng dữ kiện theo độ đúng đo được.
