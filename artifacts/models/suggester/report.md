# Suggester run

```json
{
 "n_train": 8928,
 "n_val": 992,
 "n_test": 198,
 "test_review": {
  "marked_y": 59,
  "marked_n": 1,
  "unchecked": 139
 },
 "confident_learning": {
  "skipped": true
 },
 "lambda": 1e-05,
 "alpha": 2.387,
 "beta": 1.869,
 "model": {
  "hit@5": 0.899,
  "recall@5": 0.8115
 },
 "baseline": {
  "hit@5": 0.4899,
  "recall@5": 0.4016
 },
 "val_model": {
  "hit@5": 0.7087,
  "recall@5": 0.5689
 },
 "behaviour": {
  "unreachable_groups": [],
  "top5_share_highest": {
   "73106": 0.203,
   "73103": 0.189,
   "76201": 0.177,
   "73104": 0.157,
   "75402": 0.152
  },
  "groups_over_25pct": [],
  "empty_input_gives_nothing": true,
  "deterministic": true
 },
 "beats_baseline": true
}
```

First test students:
- groups ['71401']: 74802 (0.23: lúc rảnh em hay viết code, mày mò máy tính, em viết "Em mong muốn sau này xây dựng được những phần mềm học tập th..."); 71401 (0.17: em muốn làm việc ở trường học, lúc rảnh em hay giảng bài cho bạn bè); 74801 (0.16: lúc rảnh em hay viết code, mày mò máy tính, em viết "Em mong muốn sau này xây dựng được những phần mềm học tập th...")
- groups ['71401']: 74802 (0.37: lúc rảnh em hay viết code, mày mò máy tính, em viết "uoc mo sau nay dc lam sep quan ly may du an nang cap truong ..."); 74801 (0.19: lúc rảnh em hay viết code, mày mò máy tính, em viết "uoc mo sau nay dc lam sep quan ly may du an nang cap truong ..."); 71401 (0.14: em muốn làm việc ở trường học, em viết "uoc mo sau nay dc lam sep quan ly may du an nang cap truong ...")
- groups ['71401', '71402']: 71402 (0.57: em viết "Chắc làm gì đó ở trường học hoặc chăm mấy đứa nhỏ, cũng chưa...", em muốn làm việc ở trường học); 71401 (0.14: em muốn làm việc ở trường học, lúc rảnh em hay giảng bài cho bạn bè); 77601 (0.05: lúc rảnh em hay chăm sóc người khác, tình nguyện, em thích giúp đỡ, chăm sóc, dạy người khác)
- groups ['71402']: 71402 (0.49: em viết "e cug thich tro thanh co giao dung tren buc giang chi bao ca...", em muốn làm việc ở trường học); 76202 (0.13: lúc rảnh em hay trồng cây, nuôi con vật, em thích hoặc học tốt Sinh học); 76201 (0.08: lúc rảnh em hay trồng cây, nuôi con vật, em viết "e cug thich tro thanh co giao dung tren buc giang chi bao ca...")
- groups ['71402']: 77601 (0.16: lúc rảnh em hay chăm sóc người khác, tình nguyện, em viết "hay sua do choi hong cho may dua nho gan nha"); 75803 (0.15: em viết "hay sua do choi hong cho may dua nho gan nha", em muốn làm việc ở ngoài trời, công trường); 75802 (0.14: em thích làm với máy móc, dụng cụ, xây dựng, sửa chữa, em muốn làm việc ở ngoài trời, công trường); 76401 (0.10: em thích giúp đỡ, chăm sóc, dạy người khác, lúc rảnh em hay chăm sóc người khác, tình nguyện)
