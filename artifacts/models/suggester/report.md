# Suggester run

```json
{
 "n_train": 13535,
 "n_val": 1503,
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
 "alpha": 5.312,
 "beta": 2.585,
 "popularity": 0.2,
 "writers": {
  "qwen": 12943,
  "aya": 2095
 },
 "model": {
  "hit@5": 0.8838,
  "recall@5": 0.8361
 },
 "model_without_popularity": {
  "hit@5": 0.904,
  "recall@5": 0.8484
 },
 "baseline": {
  "hit@5": 0.4899,
  "recall@5": 0.4016
 },
 "val_model": {
  "hit@5": 0.7112,
  "recall@5": 0.5287
 },
 "behaviour": {
  "unreachable_groups": [],
  "top5_share_highest": {
   "78101": 0.279,
   "71402": 0.254,
   "73801": 0.225,
   "72104": 0.196,
   "75802": 0.192
  },
  "groups_over_25pct": [
   "78101",
   "71402"
  ],
  "top5_share_uniform_subjects": {
   "72202": 0.349,
   "73801": 0.326,
   "71402": 0.27,
   "73104": 0.243,
   "73402": 0.191
  },
  "empty_input_gives_nothing": true,
  "deterministic": true
 },
 "review": {
  "n": 88,
  "cases_passed": 0.5341,
  "kept_in_top5": "84/87",
  "added_in_top": "1/37",
  "dropped_out_of_top3": "27/45",
  "failing": [
   {
    "id": "C002",
    "top5": [
     "75103",
     "75104",
     "75201",
     "75203",
     "75202"
    ],
    "added_in_top": false
   },
   {
    "id": "C004",
    "top5": [
     "75206",
     "75104",
     "76201",
     "75201",
     "75401"
    ],
    "added_in_top": false
   },
   {
    "id": "C005",
    "top5": [
     "73203",
     "73106",
     "73402",
     "73801",
     "73105"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C006",
    "top5": [
     "73402",
     "78501",
     "73401",
     "73403",
     "77202"
    ],
    "kept_in_top5": false
   },
   {
    "id": "C007",
    "top5": [
     "77205",
     "76401",
     "76201",
     "77201",
     "75104"
    ],
    "added_in_top": false
   },
   {
    "id": "C008",
    "top5": [
     "78103",
     "78502",
     "75206",
     "75802",
     "75402"
    ],
    "added_in_top": false
   },
   {
    "id": "C010",
    "top5": [
     "74201",
     "74202",
     "73104",
     "72290",
     "74401"
    ],
    "added_in_top": false
   },
   {
    "id": "C011",
    "top5": [
     "75802",
     "75402",
     "75201",
     "75102",
     "75101"
    ],
    "dropped_out_of_top3": false
   },
   {
    "id": "C013",
    "top5": [
     "73801",
     "78102",
     "78101",
     "72290",
     "73106"
    ],
    "added_in_top": false
   },
   {
    "id": "C014",
    "top5": [
     "77205",
     "75104",
     "76401",
     "75201",
     "75401"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C018",
    "top5": [
     "74202",
     "74201",
     "75490",
     "76201",
     "74403"
    ],
    "added_in_top": false
   },
   {
    "id": "C021",
    "top5": [
     "73290",
     "72103",
     "73201",
     "72104",
     "72102"
    ],
    "added_in_top": false
   },
   {
    "id": "C022",
    "top5": [
     "72202",
     "73801",
     "75206",
     "76202",
     "73103"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false,
    "kept_in_top5": false
   },
   {
    "id": "C023",
    "top5": [
     "72104",
     "72103",
     "73290",
     "74802",
     "75801"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C025",
    "top5": [
     "75204",
     "76201",
     "76202",
     "74402",
     "78103"
    ],
    "kept_in_top5": false
   },
   {
    "id": "C028",
    "top5": [
     "75102",
     "75103",
     "75402",
     "75101",
     "75803"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C029",
    "top5": [
     "75102",
     "75103",
     "75101",
     "75402",
     "75190"
    ],
    "added_in_top": false
   },
   {
    "id": "C031",
    "top5": [
     "73403",
     "73402",
     "74802",
     "72103",
     "74801"
    ],
    "added_in_top": false
   },
   {
    "id": "C032",
    "top5": [
     "78102",
     "78190",
     "75401",
     "75803",
     "78103"
    ],
    "added_in_top": false
   },
   {
    "id": "C033",
    "top5": [
     "77201",
     "77205",
     "77206",
     "77203",
     "77202"
    ],
    "added_in_top": false
   },
   {
    "id": "C034",
    "top5": [
     "73401",
     "73801",
     "73402",
     "73101",
     "73404"
    ],
    "added_in_top": false
   },
   {
    "id": "C036",
    "top5": [
     "74601",
     "74802",
     "75204",
     "74401",
     "75802"
    ],
    "added_in_top": false
   },
   {
    "id": "C038",
    "top5": [
     "72103",
     "75401",
     "75206",
     "78101",
     "76201"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C039",
    "top5": [
     "75104",
     "77206",
     "75401",
     "74401",
     "77205"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C040",
    "top5": [
     "76201",
     "75206",
     "75104",
     "75201",
     "75401"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C041",
    "top5": [
     "71402",
     "73801",
     "78101",
     "73106",
     "72290"
    ],
    "added_in_top": false
   },
   {
    "id": "C042",
    "top5": [
     "75802",
     "75201",
     "75206",
     "75102",
     "75104"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C044",
    "top5": [
     "75201",
     "74401",
     "75206",
     "75103",
     "75202"
    ],
    "added_in_top": false
   },
   {
    "id": "C047",
    "top5": [
     "72290",
     "73106",
     "73801",
     "72202",
     "71402"
    ],
    "added_in_top": false
   },
   {
    "id": "C048",
    "top5": [
     "75402",
     "75802",
     "75201",
     "76201",
     "75102"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C049",
    "top5": [
     "77601",
     "73104",
     "72202",
     "73106",
     "73801"
    ],
    "added_in_top": false
   },
   {
    "id": "C050",
    "top5": [
     "77202",
     "77207",
     "75401",
     "77205",
     "77203"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C052",
    "top5": [
     "77203",
     "77201",
     "77205",
     "77206",
     "77207"
    ],
    "dropped_out_of_top3": false
   },
   {
    "id": "C059",
    "top5": [
     "72202",
     "73801",
     "73106",
     "72290",
     "73202"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C070",
    "top5": [
     "75104",
     "77206",
     "74401",
     "75401",
     "77201"
    ],
    "added_in_top": false
   },
   {
    "id": "C071",
    "top5": [
     "75802",
     "75803",
     "78102",
     "75106",
     "72104"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C078",
    "top5": [
     "74403",
     "74201",
     "75490",
     "74801",
     "71402"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C079",
    "top5": [
     "73104",
     "73402",
     "73801",
     "73101",
     "73401"
    ],
    "added_in_top": false
   },
   {
    "id": "C080",
    "top5": [
     "76201",
     "75104",
     "75802",
     "75203",
     "75201"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C082",
    "top5": [
     "73801",
     "78102",
     "73404",
     "73201",
     "72202"
    ],
    "dropped_out_of_top3": false
   },
   {
    "id": "C084",
    "top5": [
     "72103",
     "75401",
     "72102",
     "76201",
     "75206"
    ],
    "added_in_top": false
   }
  ]
 },
 "beats_baseline": true
}
```

First test students:
- groups ['71401']: 71401 (0.20: em viết "Em mong muốn sau này xây dựng được những phần mềm học tập th...", em muốn làm việc ở trường học); 74801 (0.10: lúc rảnh em hay viết code, mày mò máy tính, em viết "Em mong muốn sau này xây dựng được những phần mềm học tập th..."); 74802 (0.09: lúc rảnh em hay viết code, mày mò máy tính, em viết "Em mong muốn sau này xây dựng được những phần mềm học tập th..."); 73104 (0.07: em viết "Em mong muốn sau này xây dựng được những phần mềm học tập th...", em thích tìm hiểu, nghiên cứu, giải bài toán khó); 71402 (0.06: em muốn làm việc ở trường học, lúc rảnh em hay giảng bài cho bạn bè)
- groups ['71401']: 75803 (0.15: em viết "uoc mo sau nay dc lam sep quan ly may du an nang cap truong ...", em thích tìm hiểu, nghiên cứu, giải bài toán khó); 74802 (0.14: lúc rảnh em hay viết code, mày mò máy tính, em viết "uoc mo sau nay dc lam sep quan ly may du an nang cap truong ..."); 71401 (0.10: em viết "uoc mo sau nay dc lam sep quan ly may du an nang cap truong ...", em muốn làm việc ở trường học); 73401 (0.07: em viết "uoc mo sau nay dc lam sep quan ly may du an nang cap truong ...", em thích tìm hiểu, nghiên cứu, giải bài toán khó); 74801 (0.05: lúc rảnh em hay viết code, mày mò máy tính, em thích tìm hiểu, nghiên cứu, giải bài toán khó)
- groups ['71401', '71402']: 71402 (0.72: em viết "Chắc làm gì đó ở trường học hoặc chăm mấy đứa nhỏ, cũng chưa...", em thích giúp đỡ, chăm sóc, dạy người khác); 71401 (0.03: em thích giúp đỡ, chăm sóc, dạy người khác, em muốn làm việc ở trường học); 77601 (0.02: em thích giúp đỡ, chăm sóc, dạy người khác, lúc rảnh em hay chăm sóc người khác, tình nguyện); 77205 (0.02: lúc rảnh em hay chăm sóc người khác, tình nguyện, em viết "Chắc làm gì đó ở trường học hoặc chăm mấy đứa nhỏ, cũng chưa..."); 72202 (0.01: em thích giúp đỡ, chăm sóc, dạy người khác, em viết "Chắc làm gì đó ở trường học hoặc chăm mấy đứa nhỏ, cũng chưa...")
- groups ['71402']: 71402 (0.78: em viết "e cug thich tro thanh co giao dung tren buc giang chi bao ca...", em thích sáng tạo: vẽ, viết, thiết kế, âm nhạc); 71401 (0.03: em viết "e cug thich tro thanh co giao dung tren buc giang chi bao ca...", em muốn làm việc ở trường học); 76401 (0.02: em thích hoặc học tốt Sinh học, em thích giúp đỡ, chăm sóc, dạy người khác); 77205 (0.02: em thích hoặc học tốt Sinh học, lúc rảnh em hay chăm sóc người khác, tình nguyện); 77203 (0.01: em thích hoặc học tốt Sinh học, lúc rảnh em hay chăm sóc người khác, tình nguyện)
- groups ['71402']: 75802 (0.23: em viết "hay sua do choi hong cho may dua nho gan nha", em muốn làm việc ở ngoài trời, công trường); 71402 (0.09: em thích giúp đỡ, chăm sóc, dạy người khác, em muốn làm việc ở trường học); 75201 (0.07: em viết "hay sua do choi hong cho may dua nho gan nha", em thích làm với máy móc, dụng cụ, xây dựng, sửa chữa); 75102 (0.06: em viết "hay sua do choi hong cho may dua nho gan nha", em thích làm với máy móc, dụng cụ, xây dựng, sửa chữa); 75402 (0.06: em thích làm với máy móc, dụng cụ, xây dựng, sửa chữa, lúc rảnh em hay sửa chữa, lắp ráp đồ)
