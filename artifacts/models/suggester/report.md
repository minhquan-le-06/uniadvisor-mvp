# Suggester run

```json
{
 "n_train": 11648,
 "n_val": 1294,
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
 "alpha": 5.545,
 "beta": 2.508,
 "model": {
  "hit@5": 0.899,
  "recall@5": 0.8484
 },
 "baseline": {
  "hit@5": 0.4899,
  "recall@5": 0.4016
 },
 "val_model": {
  "hit@5": 0.6955,
  "recall@5": 0.5209
 },
 "behaviour": {
  "unreachable_groups": [],
  "top5_share_highest": {
   "73103": 0.333,
   "72202": 0.253,
   "73801": 0.233,
   "73104": 0.223,
   "72102": 0.184
  },
  "groups_over_25pct": [
   "73103",
   "72202"
  ],
  "empty_input_gives_nothing": true,
  "deterministic": true
 },
 "review": {
  "n": 34,
  "cases_passed": 0.4412,
  "kept_in_top5": "32/33",
  "added_in_top": "2/18",
  "dropped_out_of_top3": "15/22",
  "failing": [
   {
    "id": "C002",
    "top5": [
     "75103",
     "75203",
     "75104",
     "75201",
     "75202"
    ],
    "added_in_top": false
   },
   {
    "id": "C004",
    "top5": [
     "75206",
     "75104",
     "75401",
     "76201",
     "78103"
    ],
    "added_in_top": false
   },
   {
    "id": "C005",
    "top5": [
     "73203",
     "73801",
     "73106",
     "73202",
     "73105"
    ],
    "added_in_top": false
   },
   {
    "id": "C007",
    "top5": [
     "77205",
     "76201",
     "76401",
     "77201",
     "77206"
    ],
    "added_in_top": false
   },
   {
    "id": "C008",
    "top5": [
     "78103",
     "75206",
     "78502",
     "75802",
     "78102"
    ],
    "added_in_top": false
   },
   {
    "id": "C011",
    "top5": [
     "75802",
     "75402",
     "75102",
     "76203",
     "75201"
    ],
    "dropped_out_of_top3": false
   },
   {
    "id": "C013",
    "top5": [
     "78102",
     "73801",
     "73106",
     "78101",
     "72290"
    ],
    "added_in_top": false
   },
   {
    "id": "C014",
    "top5": [
     "77205",
     "75401",
     "75206",
     "76201",
     "77203"
    ],
    "added_in_top": false
   },
   {
    "id": "C017",
    "top5": [
     "73401",
     "73801",
     "73404",
     "73403",
     "73105"
    ],
    "dropped_out_of_top3": false
   },
   {
    "id": "C018",
    "top5": [
     "74202",
     "74201",
     "75490",
     "74403",
     "76201"
    ],
    "added_in_top": false
   },
   {
    "id": "C021",
    "top5": [
     "73290",
     "72102",
     "72103",
     "73201",
     "72104"
    ],
    "added_in_top": false
   },
   {
    "id": "C022",
    "top5": [
     "76202",
     "78103",
     "72202",
     "73103",
     "75206"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C023",
    "top5": [
     "72104",
     "72103",
     "72102",
     "73290",
     "75801"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C025",
    "top5": [
     "76202",
     "78103",
     "75402",
     "74402",
     "76201"
    ],
    "dropped_out_of_top3": false,
    "kept_in_top5": false
   },
   {
    "id": "C028",
    "top5": [
     "75102",
     "75101",
     "75190",
     "78103",
     "75402"
    ],
    "added_in_top": false
   },
   {
    "id": "C029",
    "top5": [
     "75102",
     "75101",
     "75190",
     "75103",
     "75402"
    ],
    "added_in_top": false
   },
   {
    "id": "C031",
    "top5": [
     "72103",
     "73403",
     "78102",
     "73203",
     "72102"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C032",
    "top5": [
     "78102",
     "78190",
     "78103",
     "75401",
     "75803"
    ],
    "added_in_top": false
   },
   {
    "id": "C033",
    "top5": [
     "77201",
     "77203",
     "77205",
     "77206",
     "77207"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   }
  ]
 },
 "beats_baseline": true
}
```

First test students:
- groups ['71401']: 71401 (0.18: em viết "Em mong muốn sau này xây dựng được những phần mềm học tập th...", em muốn làm việc ở trường học); 74802 (0.12: lúc rảnh em hay viết code, mày mò máy tính, em viết "Em mong muốn sau này xây dựng được những phần mềm học tập th..."); 74801 (0.07: em viết "Em mong muốn sau này xây dựng được những phần mềm học tập th...", lúc rảnh em hay viết code, mày mò máy tính); 73401 (0.05: em viết "Em mong muốn sau này xây dựng được những phần mềm học tập th...", em muốn làm việc ở văn phòng); 73202 (0.04: em viết "Em mong muốn sau này xây dựng được những phần mềm học tập th...", em thích tìm hiểu, nghiên cứu, giải bài toán khó)
- groups ['71401']: 74802 (0.19: lúc rảnh em hay viết code, mày mò máy tính, em viết "uoc mo sau nay dc lam sep quan ly may du an nang cap truong ..."); 75106 (0.08: em viết "uoc mo sau nay dc lam sep quan ly may du an nang cap truong ...", em thích tìm hiểu, nghiên cứu, giải bài toán khó); 75803 (0.08: em viết "uoc mo sau nay dc lam sep quan ly may du an nang cap truong ...", em thích tìm hiểu, nghiên cứu, giải bài toán khó); 71401 (0.07: em viết "uoc mo sau nay dc lam sep quan ly may du an nang cap truong ...", em muốn làm việc ở trường học); 74801 (0.04: lúc rảnh em hay viết code, mày mò máy tính, em thích tìm hiểu, nghiên cứu, giải bài toán khó)
- groups ['71401', '71402']: 71402 (0.47: em thích giúp đỡ, chăm sóc, dạy người khác, em viết "Chắc làm gì đó ở trường học hoặc chăm mấy đứa nhỏ, cũng chưa..."); 71401 (0.08: em viết "Chắc làm gì đó ở trường học hoặc chăm mấy đứa nhỏ, cũng chưa...", em thích giúp đỡ, chăm sóc, dạy người khác); 77601 (0.07: em thích giúp đỡ, chăm sóc, dạy người khác, em viết "Chắc làm gì đó ở trường học hoặc chăm mấy đứa nhỏ, cũng chưa..."); 77205 (0.02: lúc rảnh em hay chăm sóc người khác, tình nguyện, em thích giúp đỡ, chăm sóc, dạy người khác); 78590 (0.02: em viết "Chắc làm gì đó ở trường học hoặc chăm mấy đứa nhỏ, cũng chưa...", em thích giúp đỡ, chăm sóc, dạy người khác)
- groups ['71402']: 71402 (0.51: em viết "e cug thich tro thanh co giao dung tren buc giang chi bao ca...", em thích sáng tạo: vẽ, viết, thiết kế, âm nhạc); 74202 (0.06: em thích hoặc học tốt Sinh học, em viết "e cug thich tro thanh co giao dung tren buc giang chi bao ca..."); 76201 (0.04: lúc rảnh em hay trồng cây, nuôi con vật, em viết "e cug thich tro thanh co giao dung tren buc giang chi bao ca..."); 71401 (0.04: em viết "e cug thich tro thanh co giao dung tren buc giang chi bao ca...", em muốn làm việc ở trường học); 78590 (0.03: em thích sáng tạo: vẽ, viết, thiết kế, âm nhạc, em viết "e cug thich tro thanh co giao dung tren buc giang chi bao ca...")
- groups ['71402']: 75802 (0.20: em viết "hay sua do choi hong cho may dua nho gan nha", em muốn làm việc ở ngoài trời, công trường); 75201 (0.08: em viết "hay sua do choi hong cho may dua nho gan nha", em thích làm với máy móc, dụng cụ, xây dựng, sửa chữa); 71402 (0.07: em muốn làm việc ở trường học, em thích giúp đỡ, chăm sóc, dạy người khác); 76203 (0.06: em muốn làm việc ở ngoài trời, công trường, em viết "hay sua do choi hong cho may dua nho gan nha"); 77205 (0.06: em viết "hay sua do choi hong cho may dua nho gan nha", em thích giúp đỡ, chăm sóc, dạy người khác)
