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
 "alpha": 5.25,
 "beta": 2.934,
 "model": {
  "hit@5": 0.9141,
  "recall@5": 0.8525
 },
 "baseline": {
  "hit@5": 0.4899,
  "recall@5": 0.4016
 },
 "val_model": {
  "hit@5": 0.6794,
  "recall@5": 0.5413
 },
 "behaviour": {
  "unreachable_groups": [],
  "top5_share_highest": {
   "72202": 0.294,
   "73801": 0.269,
   "73106": 0.243,
   "73104": 0.214,
   "73103": 0.209
  },
  "groups_over_25pct": [
   "72202",
   "73801"
  ],
  "empty_input_gives_nothing": true,
  "deterministic": true
 },
 "review": {
  "n": 34,
  "cases_passed": 0.4118,
  "kept_in_top5": "33/33",
  "added_in_top": "1/18",
  "dropped_out_of_top3": "13/22",
  "failing": [
   {
    "id": "C002",
    "top5": [
     "75104",
     "75108",
     "75103",
     "75190",
     "76201"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C004",
    "top5": [
     "75206",
     "75104",
     "76201",
     "75402",
     "77205"
    ],
    "added_in_top": false
   },
   {
    "id": "C005",
    "top5": [
     "73203",
     "73106",
     "73801",
     "73402",
     "75190"
    ],
    "added_in_top": false
   },
   {
    "id": "C007",
    "top5": [
     "77205",
     "77206",
     "74202",
     "76201",
     "75190"
    ],
    "added_in_top": false
   },
   {
    "id": "C008",
    "top5": [
     "78103",
     "75802",
     "76202",
     "75402",
     "75101"
    ],
    "added_in_top": false
   },
   {
    "id": "C010",
    "top5": [
     "73106",
     "74201",
     "74202",
     "75801",
     "73104"
    ],
    "added_in_top": false
   },
   {
    "id": "C011",
    "top5": [
     "75402",
     "75802",
     "75102",
     "76201",
     "75101"
    ],
    "dropped_out_of_top3": false
   },
   {
    "id": "C013",
    "top5": [
     "73106",
     "78102",
     "73801",
     "78101",
     "75206"
    ],
    "added_in_top": false
   },
   {
    "id": "C014",
    "top5": [
     "77205",
     "75190",
     "75401",
     "75104",
     "75206"
    ],
    "added_in_top": false
   },
   {
    "id": "C016",
    "top5": [
     "71402",
     "74202",
     "73105",
     "74201",
     "73104"
    ],
    "dropped_out_of_top3": false
   },
   {
    "id": "C017",
    "top5": [
     "73801",
     "73101",
     "73403",
     "73404",
     "73401"
    ],
    "dropped_out_of_top3": false
   },
   {
    "id": "C018",
    "top5": [
     "74202",
     "74201",
     "76201",
     "75490",
     "74403"
    ],
    "added_in_top": false
   },
   {
    "id": "C021",
    "top5": [
     "73290",
     "72104",
     "73201",
     "72103",
     "72102"
    ],
    "added_in_top": false
   },
   {
    "id": "C022",
    "top5": [
     "76202",
     "78103",
     "73801",
     "75206",
     "72202"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C023",
    "top5": [
     "72103",
     "72104",
     "73290",
     "75801",
     "72102"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C028",
    "top5": [
     "75190",
     "75102",
     "75402",
     "78103",
     "75101"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
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
     "78102",
     "72103",
     "73403",
     "75108",
     "73402"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C032",
    "top5": [
     "78102",
     "75402",
     "78103",
     "75490",
     "78190"
    ],
    "added_in_top": false,
    "dropped_out_of_top3": false
   },
   {
    "id": "C033",
    "top5": [
     "77205",
     "77201",
     "77206",
     "77207",
     "77203"
    ],
    "added_in_top": false
   }
  ]
 },
 "beats_baseline": true
}
```

First test students:
- groups ['71401']: 71401 (0.15: em viết "Em mong muốn sau này xây dựng được những phần mềm học tập th...", em muốn làm việc ở trường học); 74802 (0.15: lúc rảnh em hay viết code, mày mò máy tính, em viết "Em mong muốn sau này xây dựng được những phần mềm học tập th..."); 74801 (0.13: em viết "Em mong muốn sau này xây dựng được những phần mềm học tập th...", lúc rảnh em hay viết code, mày mò máy tính)
- groups ['71401']: 74802 (0.40: em viết "uoc mo sau nay dc lam sep quan ly may du an nang cap truong ...", lúc rảnh em hay viết code, mày mò máy tính); 71401 (0.12: em viết "uoc mo sau nay dc lam sep quan ly may du an nang cap truong ...", em muốn làm việc ở trường học); 74801 (0.07: lúc rảnh em hay viết code, mày mò máy tính, em viết "uoc mo sau nay dc lam sep quan ly may du an nang cap truong ...")
- groups ['71401', '71402']: 71402 (0.45: em viết "Chắc làm gì đó ở trường học hoặc chăm mấy đứa nhỏ, cũng chưa...", em thích giúp đỡ, chăm sóc, dạy người khác); 71401 (0.23: em viết "Chắc làm gì đó ở trường học hoặc chăm mấy đứa nhỏ, cũng chưa...", em thích giúp đỡ, chăm sóc, dạy người khác); 77204 (0.05: em viết "Chắc làm gì đó ở trường học hoặc chăm mấy đứa nhỏ, cũng chưa...", em thích giúp đỡ, chăm sóc, dạy người khác)
- groups ['71402']: 71402 (0.70: em viết "e cug thich tro thanh co giao dung tren buc giang chi bao ca...", em thích sáng tạo: vẽ, viết, thiết kế, âm nhạc); 71401 (0.05: em viết "e cug thich tro thanh co giao dung tren buc giang chi bao ca...", em muốn làm việc ở trường học); 74202 (0.02: em thích hoặc học tốt Sinh học, lúc rảnh em hay chăm sóc người khác, tình nguyện)
- groups ['71402']: 75102 (0.13: em viết "hay sua do choi hong cho may dua nho gan nha", em thích làm với máy móc, dụng cụ, xây dựng, sửa chữa); 77205 (0.11: em viết "hay sua do choi hong cho may dua nho gan nha", em thích giúp đỡ, chăm sóc, dạy người khác); 75803 (0.08: em viết "hay sua do choi hong cho may dua nho gan nha", em muốn làm việc ở ngoài trời, công trường)
