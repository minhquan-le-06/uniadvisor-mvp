# Module 1: Dữ liệu

## Mục tiêu

Cung cấp một cơ sở dữ liệu (CSDL) đúng, có nguồn gốc rõ ràng, về các ngành đại học: điểm chuẩn, chỉ tiêu, học phí,
phổ điểm, mã ngành. Đây là nguồn duy nhất mà các module khác đọc.

## Tính độc lập

Ranh giới giữa module 1 và các module khác là **cấu trúc CSDL** (`src/uniadvisor/db/schema.py`) cùng hàm đọc
`get_db()`.

- **Các module khác không cần chờ module 1.** Họ phát triển và kiểm thử trên CSDL mô phỏng có cùng cấu trúc ("thế giới
  nhỏ" 3 trường, 12 ngành: `uniadvisor sim tiny`), hoặc trên bản CSDL thật đang có trong git.
- **Module 1 được tự do thay đổi cách thu thập và làm sạch**, miễn là CSDL vẫn qua được bước kiểm tra
  (`uniadvisor check-db`).
- **Khi đổi cấu trúc** (thêm bảng, thêm cột): sửa `schema.py` trước, cập nhật thế giới mô phỏng
  (`src/uniadvisor/sim/tiny.py`), cập nhật [docs/DATA.md](../DATA.md), rồi báo các module khác. Các cột cũ không được
  xóa hay đổi nghĩa mà không báo trước.

## Đầu vào

| Nguồn | Lấy gì |
|---|---|
| VietNamNet, VnExpress (API và trang tra cứu) | Điểm chuẩn 2023–2026, học phí |
| ADS_Final (dữ liệu tổng hợp trên GitHub) | Điểm chuẩn 2018–2024 theo tổ hợp |
| UniPilotData (`data/unipilot/`) | Danh sách trường, ngành 2026, chỉ tiêu, tổ hợp xét tuyển |
| File điểm thi từng thí sinh (công khai, tải về `data/inbox/`, không lưu trong git) | Phổ điểm chính xác theo tổ hợp |
| Thông tư 09/2022 của Bộ GD&ĐT | Danh mục mã ngành |
| Nhập tay (`data/manual/`) | Số liệu Bộ công bố trên báo, các sửa lỗi thủ công |

## Đầu ra

Thư mục `data/db/` gồm các bảng CSV, một file phổ điểm (`distributions.parquet`) và một file mô tả
(`manifest.json`):

| Bảng | Mỗi dòng là |
|---|---|
| `schools` | một trường |
| `programs` | một ngành xét điểm thi THPT, kèm mã ngành Bộ, lĩnh vực, tổ hợp |
| `cutoffs` | điểm chuẩn của một ngành trong một năm |
| `quotas` | chỉ tiêu |
| `tuition` | học phí |
| `majors` | danh mục mã ngành của Bộ |
| `combos` | tổ hợp môn |
| `distributions` | phổ điểm theo tổ hợp và năm |

Ngoài ra có một bảng tổng hợp `catalog` (`get_db().catalog`): mỗi ngành một dòng, gồm trường, thành phố, điểm chuẩn
gần nhất, số năm có điểm, chỉ tiêu, học phí, tên ngành theo Bộ. Chi tiết từng cột: [docs/DATA.md](../DATA.md).

**Cam kết với các module khác:**

- Mỗi con số ghi nguồn gốc: quan sát được, suy ra, ước tính hoặc mô phỏng. Không có dữ liệu thì không có dòng, không
  bao giờ để ô trống thay cho "chưa biết".
- Mỗi ngành có điểm chuẩn và phổ điểm cho tổ hợp tham chiếu của nó.
- Không trùng, không thiếu liên kết, điểm nằm trong 0–30, học phí hợp lệ.
- CSDL thật không chứa dữ liệu mô phỏng.
- Cùng đầu vào thì cùng đầu ra.

## Hiện trạng

- **Quy mô:** 48 trường ở Hà Nội và TP.HCM, 1.666 ngành.
- **Điểm chuẩn:** 7.098 dòng. Năm 2023–2026 đầy đủ, từ 847 đến 1.666 ngành mỗi năm. Năm 2018–2022 chỉ khoảng 400–580
  ngành mỗi năm, một nguồn duy nhất.
- **Mã ngành Bộ:** có cho 1.424/1.666 ngành (85%), trong đó 347 ngành gắn bằng cách so tên, đúng khoảng 99%.
- **Phổ điểm:** chính xác cho 2023–2026; 47 tổ hợp năm 2026 là ước tính.
- **Còn thiếu:**
  - Học phí: chưa rõ cho 728 ngành (44%); 182 ngành dùng mức ước tính của trường.
  - Chỉ tiêu: chỉ có năm 2026.
  - Điểm chuẩn theo từng tổ hợp: khi một ngành có nhiều mức, đang chỉ giữ mức thấp nhất (13% số dòng).
  - Mã ngành: 242 ngành chưa có.
  - Chất lượng trường (kiểm định, xếp hạng, việc làm): chưa thu thập.

## Quy trình làm việc (gợi ý)

1. **Chọn việc** trong danh sách bên dưới. Trước khi bắt đầu, ghi rõ việc đó thêm hay sửa bảng nào, cột nào.
2. **Thu thập:** mỗi nguồn một chương trình riêng (`src/uniadvisor/collect/`). Kết quả thô lưu ở `data/collected/`.
3. **Làm sạch và dựng CSDL:** `uniadvisor build`. Phần trung gian và danh sách lỗi nằm ở `artifacts/build/`.
4. **Kiểm tra:**
   - chạy `uniadvisor check-db` và bộ kiểm thử (`python -m pytest -q`);
   - chạy `uniadvisor report` để so số liệu với lần trước (`artifacts/reports/data_report.md`). Số dòng giảm hoặc
     nhảy bất thường thì phải giải thích được.
5. **Nếu đổi cấu trúc:** cập nhật `schema.py`, thế giới mô phỏng và `docs/DATA.md`, rồi báo các module khác.
6. **Commit** CSDL và báo cáo dữ liệu cùng nhau.

**Làm mới hằng năm** (khi có điểm chuẩn mới, khoảng tháng 8), theo thứ tự lệnh: `collect` → `fetch-scores` → `build`
→ `check-db` → `backtest` → `report`.

## Việc có thể nhận (theo mức ưu tiên)

1. **Học phí** cho 728 ngành còn thiếu, lấy từ đề án tuyển sinh của các trường.
2. **Chất lượng trường:** tìm và thu thập các tín hiệu như công lập hay tư thục, kiểm định, xếp hạng, tỉ lệ có việc làm.
   Module 3 cần cái này.
3. **Chỉ tiêu các năm trước** (2023–2025). Dự báo điểm chuẩn cần để thấy chỉ tiêu tăng hay giảm.
4. **Điểm chuẩn theo từng tổ hợp** thay vì chỉ lấy mức thấp nhất.
5. **Mã ngành** cho 242 ngành còn thiếu, từ đề án tuyển sinh.
