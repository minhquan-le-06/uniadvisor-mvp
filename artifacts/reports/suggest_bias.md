# Suggester: possible habits of the training-set writer

Training set (Qwen): 9920 students; test set (Gemini): 199. Rates are over the students who answered that question.

## 1. Each option: training vs test

| Question | Option | Train | Test | Ratio |
|---|---|---|---|---|
| workplace | Làm tự do, ở nhà | 0% | 28% | 0.05 |
| subjects | Địa lý | 7% | 23% | 0.34 |
| subjects | Toán | 16% | 48% | 0.34 |
| subjects | Lịch sử | 5% | 16% | 0.36 |
| hobbies | Sửa chữa, lắp ráp đồ | 7% | 19% | 0.39 |
| hobbies | Tranh biện, thuyết trình | 4% | 12% | 0.40 |
| hobbies | Trồng cây, nuôi con vật | 7% | 20% | 0.40 |
| subjects | Tiếng Anh | 6% | 17% | 0.41 |
| hobbies | Buôn bán, kinh doanh online | 4% | 11% | 0.43 |
| subjects | Sinh học | 12% | 29% | 0.44 |
| subjects | Vật lý | 52% | 25% | 2.05 |
| subjects | Tin học | 36% | 19% | 1.89 |
| hobbies | Chơi nhạc, hát | 9% | 4% | 1.89 |
| work_types | Làm với máy móc, dụng cụ, xây dựng, sửa chữa | 23% | 43% | 0.56 |
| subjects | Giáo dục kinh tế và pháp luật | 14% | 25% | 0.57 |
| hobbies | Du lịch, tìm hiểu văn hóa, ngoại ngữ | 15% | 27% | 0.59 |
| workplace | Nhà máy, phòng thí nghiệm | 20% | 34% | 0.59 |
| workplace | Ngoài trời, công trường | 25% | 41% | 0.62 |
| hobbies | Chụp ảnh, quay và dựng video | 9% | 5% | 1.60 |
| hobbies | Giảng bài cho bạn bè | 7% | 4% | 1.57 |

Ratio < 1: Qwen ticks it less than Gemini; > 1: more. The 20 largest gaps are shown.

## 2. Subjects per group: training students vs admission combinations

A subject in at least 60% of a group's combinations that fewer than 30% of its training students tick.

| Group | Subject | In combinations | Ticked in training |
|---|---|---|---|
| 74201 Sinh học | Toán | 100% | 1% |
| 74402 Khoa học trái đất | Toán | 100% | 2% |
| 77202 Dược học | Toán | 99% | 2% |
| 73203 Văn thư - Lưu trữ - Bảo tàng | Tiếng Anh | 100% | 3% |
| 77201 Y học | Toán | 99% | 3% |
| 77205 Răng - Hàm - Mặt (Nha khoa) | Toán | 100% | 4% |
| 74202 Sinh học ứng dụng | Toán | 99% | 3% |
| 76201 Nông nghiệp | Toán | 100% | 5% |
| 76202 Lâm nghiệp | Toán | 100% | 6% |
| 77203 Điều dưỡng - hộ sinh | Toán | 97% | 3% |
| 77206 Kỹ thuật Y học | Toán | 98% | 4% |
| 74403 Khoa học môi trường | Toán | 100% | 6% |
| 76401 Thú y | Toán | 99% | 6% |
| 76203 Thủy sản | Toán | 100% | 7% |
| 75401 Chế biến lương thực, thực phẩm và đồ uống | Toán | 99% | 6% |
| 75402 Sản xuất, chế biến sợi, vải, giày, da | Toán | 100% | 8% |
| 75203 Kỹ thuật hóa học, vật liệu, luyện kim và môi trường | Toán | 99% | 8% |
| 74401 Khoa học vật chất | Toán | 100% | 9% |
| 77204 Dinh dưỡng | Toán | 98% | 8% |
| 78590 Khác thuộc lĩnh vực Môi trường và bảo vệ môi trường | Toán | 100% | 11% |
| 75204 Vật lý kỹ thuật | Toán | 100% | 11% |
| 78190 Khác thuộc lĩnh vực Du lịch, khách sạn, thể thao và dịch vụ cá nhân | Toán | 100% | 11% |
| 77207 Y tế công cộng | Toán | 98% | 10% |
| 75490 Khác thuộc lĩnh vực Sản xuất và chế biến | Toán | 100% | 12% |
| 78501 Quản lý tài nguyên và môi trường | Toán | 100% | 12% |
| 73290 Khác thuộc lĩnh vực Báo chí và thông tin | Toán | 100% | 14% |
| 75104 Công nghệ hóa học, vật liệu, luyện kim và môi trường | Toán | 100% | 15% |
| 75205 Kỹ thuật địa chất, địa vật lý và trắc địa | Toán | 99% | 13% |
| 75206 Kỹ thuật mỏ | Toán | 100% | 19% |
| 72104 Mỹ thuật ứng dụng | Toán | 86% | 7% |
| 78502 Dịch vụ an toàn lao động và vệ sinh công nghiệp | Toán | 100% | 22% |
| 75108 Công nghệ kỹ thuật in | Toán | 100% | 23% |
| 75190 Khác thuộc lĩnh vực Công nghệ kỹ thuật | Toán | 100% | 24% |
| 75801 Kiến trúc và quy hoạch | Toán | 96% | 19% |
| 75202 Kỹ thuật điện, điện tử và viễn thông | Toán | 100% | 24% |
| 75201 Kỹ thuật cơ khí và cơ kỹ thuật | Toán | 100% | 26% |
| 73101 Kinh tế học | Toán | 97% | 24% |
| 78401 Khai thác vận tải | Toán | 100% | 27% |
| 75101 Công nghệ kỹ thuật kiến trúc và công trình xây dựng | Toán | 100% | 27% |
| 71401 Khoa học giáo dục | Toán | 86% | 15% |
| 73201 Báo chí và truyền thông | Toán | 78% | 8% |
| 78101 Du lịch | Toán | 78% | 9% |
| 73401 Kinh doanh | Toán | 95% | 26% |
| 72103 Nghệ thuật nghe nhìn | Toán | 73% | 5% |
| 72202 Ngôn ngữ, văn học và văn hóa nước ngoài | Toán | 71% | 3% |
| 78102 Khách sạn, nhà hàng | Toán | 81% | 13% |
| 73404 Quản trị - Quản lý | Toán | 92% | 28% |
| 73202 Thông tin - Thư viện | Tiếng Anh | 69% | 5% |
| 71402 Đào tạo giáo viên | Toán | 77% | 15% |
| 73102 Khoa học chính trị | Toán | 73% | 12% |
| 73801 Luật | Toán | 76% | 15% |
| 75108 Công nghệ kỹ thuật in | Tiếng Anh | 60% | 4% |
| 73290 Khác thuộc lĩnh vực Báo chí và thông tin | Tiếng Anh | 60% | 4% |
| 73201 Báo chí và truyền thông | Tiếng Anh | 64% | 10% |
| 77601 Công tác xã hội | Toán | 67% | 13% |
| 73104 Tâm lý học | Toán | 62% | 9% |
| 78101 Du lịch | Tiếng Anh | 62% | 10% |
| 78103 Thể dục, thể thao | Toán | 71% | 20% |
| 73403 Kế toán - Kiểm toán | Tiếng Anh | 61% | 12% |
| 73101 Kinh tế học | Tiếng Anh | 62% | 18% |
| 77205 Răng - Hàm - Mặt (Nha khoa) | Sinh học | 71% | 29% |

61 group-subject pairs flagged; by subject: Toán 52, Tiếng Anh 8, Sinh học 1.
